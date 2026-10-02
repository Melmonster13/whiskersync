import random

import httpx
import pytest

from harness.faults.faults import PROFILES, FaultRule, FaultTransport, profile_from_env, wrap_transport



class Upstream:
    """Inner transport that records every request it actually receives."""

    def __init__(self):
        self.seen = []
        self.transport = httpx.MockTransport(self.handle)

    def handle(self, request):
        self.seen.append((request.method, request.url.path))
        return httpx.Response(200, json={"ok": True})


class FakeSleep:
    def __init__(self):
        self.calls = []

    async def __call__(self, seconds):
        self.calls.append(seconds)


@pytest.fixture
def upstream():
    return Upstream()


@pytest.fixture
def sleep():
    return FakeSleep()


def client(upstream, rules, sleep=None, seed=0):
    transport = FaultTransport(upstream.transport, rules, rng=random.Random(seed), sleep=sleep or FakeSleep())
    return httpx.AsyncClient(transport=transport, base_url="http://airline"), transport


@pytest.mark.asyncio
async def test_no_rules_passes_through(upstream):
    c, t = client(upstream, [])
    resp = await c.get("/flights/WS100")
    assert resp.json() == {"ok": True}
    assert upstream.seen == [("GET", "/flights/WS100")]
    assert t.log == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rule_method, rule_path, method, path, fires",
    [
        (None, ".*", "GET", "/flights", True),
        ("GET", ".*", "GET", "/flights", True),
        ("GET", ".*", "PATCH", "/bookings/ABC123", False),
        ("patch", r"/bookings/.+", "PATCH", "/bookings/ABC123", True),   # method case-insensitive
        (None, r"/bookings/.+", "GET", "/flights/WS100", False),
        (None, r"/flights", "GET", "/flights/WS100", False),           # whole-path match, not prefix
    ],
)
async def test_matching(upstream, rule_method, rule_path, method, path, fires):
    c, t = client(upstream, [FaultRule("status", method=rule_method, path=rule_path)])
    resp = await c.request(method, path)
    assert (resp.status_code == 503) is fires
    assert (len(upstream.seen) == 0) is fires


@pytest.mark.asyncio
async def test_status_fault_has_non_json_body(upstream):
    c, _ = client(upstream, [FaultRule("status", status_code=429)])
    resp = await c.get("/flights")
    assert resp.status_code == 429
    with pytest.raises(ValueError):
        resp.json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind, error",
    [("connect_error", httpx.ConnectError), ("timeout", httpx.ReadTimeout)],
)
async def test_raising_faults_never_reach_upstream(upstream, kind, error):
    c, _ = client(upstream, [FaultRule(kind)])
    with pytest.raises(error):
        await c.get("/flights")
    assert upstream.seen == []


@pytest.mark.asyncio
async def test_bad_json(upstream):
    c, _ = client(upstream, [FaultRule("bad_json")])
    resp = await c.get("/flights")
    assert resp.status_code == 200
    with pytest.raises(ValueError):
        resp.json()
    assert upstream.seen == []


@pytest.mark.asyncio
async def test_timeout_after_send_reaches_upstream(upstream):
    c, _ = client(upstream, [FaultRule("timeout_after_send", method="PATCH")])
    with pytest.raises(httpx.ReadTimeout):
        await c.patch("/bookings/ABC123", json={"flight_id": "WS104"})
    assert upstream.seen == [("PATCH", "/bookings/ABC123")]


@pytest.mark.asyncio
async def test_fixed_latency_then_passthrough(upstream, sleep):
    c, _ = client(upstream, [FaultRule("latency", delay_s=1.5)], sleep=sleep)
    resp = await c.get("/flights")
    assert resp.status_code == 200
    assert sleep.calls == [1.5]


@pytest.mark.asyncio
async def test_ranged_latency_stays_in_range(upstream, sleep):
    c, _ = client(upstream, [FaultRule("latency", delay_s=(0.5, 2.0))], sleep=sleep)
    for _ in range(50):
        await c.get("/flights")
    assert len(sleep.calls) == 50
    assert all(0.5 <= s <= 2.0 for s in sleep.calls)


@pytest.mark.asyncio
async def test_latency_rules_add_up_before_a_fault(upstream, sleep):
    rules = [FaultRule("latency", delay_s=1.0), FaultRule("latency", delay_s=2.0), FaultRule("status")]
    c, t = client(upstream, rules, sleep=sleep)
    resp = await c.get("/flights")
    assert resp.status_code == 503
    assert sleep.calls == [1.0, 2.0]
    assert [k for k, _, _ in t.log] == ["latency", "latency", "status"]


@pytest.mark.asyncio
async def test_first_matching_fault_wins(upstream):
    c, _ = client(upstream, [FaultRule("status", status_code=500), FaultRule("connect_error")])
    assert (await c.get("/flights")).status_code == 500


@pytest.mark.asyncio
async def test_times_limits_firing_then_recovers(upstream):
    c, t = client(upstream, [FaultRule("status", times=2)])
    codes = [(await c.get("/flights")).status_code for _ in range(4)]
    assert codes == [503, 503, 200, 200]
    assert len(t.log) == 2


@pytest.mark.asyncio
async def test_times_zero_never_fires(upstream):
    c, _ = client(upstream, [FaultRule("status", times=0)])
    assert (await c.get("/flights")).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("p, low, high", [(0.0, 0, 0), (1.0, 1000, 1000), (0.3, 250, 350)])
async def test_probability(upstream, p, low, high):
    c, t = client(upstream, [FaultRule("status", probability=p)])
    for _ in range(1000):
        await c.get("/flights")
    assert low <= len(t.log) <= high


@pytest.mark.asyncio
async def test_same_seed_same_faults(upstream):
    async def run(seed):
        c, _ = client(Upstream(), [FaultRule("status", probability=0.5)], seed=seed)
        return [(await c.get("/flights")).status_code for _ in range(30)]

    assert await run(42) == await run(42)
    assert await run(42) != await run(43)


@pytest.mark.asyncio
async def test_log_records_every_fired_fault(upstream):
    c, t = client(upstream, [FaultRule("status", method="GET", times=1)])
    await c.get("/flights")
    await c.get("/flights")
    await c.patch("/bookings/ABC123", json={})
    assert t.log == [("status", "GET", "/flights")]


@pytest.mark.parametrize(
    "kwargs",
    [{"kind": "explode"}, {"kind": "status", "probability": 1.5}, {"kind": "status", "probability": -0.1},
     {"kind": "status", "times": -1}],
)
def test_invalid_rule_raises(kwargs):
    with pytest.raises(ValueError):
        FaultRule(**kwargs)


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_every_profile_builds(upstream, profile):
    transport = wrap_transport(upstream.transport, profile, rng=random.Random(0))
    if profile == "none":
        assert transport is upstream.transport
    else:
        transport.sleep = FakeSleep()
        assert isinstance(transport, FaultTransport)


def test_unknown_profile_raises(upstream):
    with pytest.raises(ValueError):
        wrap_transport(upstream.transport, "chaos")


@pytest.mark.parametrize("value, expected", [(None, "none"), ("", "none"), (" slow ", "slow"), ("down", "down")])
def test_profile_from_env(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("FAULT_PROFILE", raising=False)
    else:
        monkeypatch.setenv("FAULT_PROFILE", value)
    assert profile_from_env() == expected
