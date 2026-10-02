"""Fault injection at the HTTP transport layer.

Wrap any httpx async transport to add latency, error statuses, connection failures,
timeouts, broken bodies, or a "lost write" (request applied, reply lost). The code under
test doesn't change. Randomness and sleeping are injected, so tests are repeatable and
never actually wait.
"""

import asyncio
import os
import random
import re
from dataclasses import dataclass

import httpx

FAULT_KINDS = {"latency", "status", "connect_error", "timeout", "bad_json", "timeout_after_send"}


@dataclass(frozen=True)
class FaultRule:
    kind: str
    method: str | None = None           # None matches any method
    path: str = ".*"                    # regex, must match the whole path
    probability: float = 1.0
    times: int | None = None            # fire at most this many times
    delay_s: float | tuple[float, float] = 0.0   # latency: fixed or (min, max)
    status_code: int = 503

    def __post_init__(self):
        if self.kind not in FAULT_KINDS:
            raise ValueError(f"unknown fault kind: {self.kind}")
        if not 0 <= self.probability <= 1:
            raise ValueError("probability must be between 0 and 1")
        if self.times is not None and self.times < 0:
            raise ValueError("times must be >= 0")

    def matches(self, request: httpx.Request) -> bool:
        if self.method is not None and request.method != self.method.upper():
            return False
        return re.fullmatch(self.path, request.url.path) is not None


class FaultTransport(httpx.AsyncBaseTransport):
    """Applies rules in order. Latency rules add up and continue; the first other rule
    that fires decides the outcome. Unmatched requests pass through to `inner`."""

    def __init__(self, inner: httpx.AsyncBaseTransport, rules: list[FaultRule], rng=None, sleep=asyncio.sleep):
        self.inner = inner
        self.rules = list(rules)
        self.rng = rng or random.Random(0)
        self.sleep = sleep
        self._fired = [0] * len(self.rules)
        self.log: list[tuple[str, str, str]] = []   # (kind, method, path) of every fault that fired

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        for i, rule in enumerate(self.rules):
            if not rule.matches(request):
                continue
            if rule.times is not None and self._fired[i] >= rule.times:
                continue
            if rule.probability < 1 and self.rng.random() >= rule.probability:
                continue
            self._fired[i] += 1
            self.log.append((rule.kind, request.method, request.url.path))
            if rule.kind == "latency":
                await self.sleep(self._delay(rule))
                continue
            return await self._fail(rule, request)
        return await self.inner.handle_async_request(request)

    def _delay(self, rule: FaultRule) -> float:
        if isinstance(rule.delay_s, tuple):
            return self.rng.uniform(*rule.delay_s)
        return rule.delay_s

    async def _fail(self, rule: FaultRule, request: httpx.Request) -> httpx.Response:
        if rule.kind == "status":
            # Plain-text body, like a proxy error page: callers mustn't assume JSON.
            return httpx.Response(rule.status_code, text="<html>injected fault</html>", request=request)
        if rule.kind == "connect_error":
            raise httpx.ConnectError("injected connect error", request=request)
        if rule.kind == "timeout":
            raise httpx.ReadTimeout("injected timeout", request=request)
        if rule.kind == "bad_json":
            return httpx.Response(
                200, content=b'{"truncated":', headers={"content-type": "application/json"}, request=request
            )
        # timeout_after_send: the request reaches the server and takes effect; the reply is lost.
        response = await self.inner.handle_async_request(request)
        await response.aread()
        await response.aclose()
        raise httpx.ReadTimeout("injected timeout after send", request=request)

    async def aclose(self) -> None:
        await self.inner.aclose()


PROFILES: dict[str, list[FaultRule]] = {
    "none": [],
    "slow": [FaultRule("latency", delay_s=(1.0, 3.0))],
    "flaky": [
        FaultRule("latency", probability=0.3, delay_s=(0.5, 2.0)),
        FaultRule("status", probability=0.3, status_code=503),
    ],
    "down": [FaultRule("connect_error")],
    "lost_write": [FaultRule("timeout_after_send", method="PATCH", path=r"/bookings/.+", times=1)],
}


def wrap_transport(inner: httpx.AsyncBaseTransport, profile: str, rng=None) -> httpx.AsyncBaseTransport:
    if profile not in PROFILES:
        raise ValueError(f"unknown fault profile {profile!r}; choose from {sorted(PROFILES)}")
    if profile == "none":
        return inner
    return FaultTransport(inner, PROFILES[profile], rng=rng)


def profile_from_env() -> str:
    return os.environ.get("FAULT_PROFILE", "none").strip() or "none"
