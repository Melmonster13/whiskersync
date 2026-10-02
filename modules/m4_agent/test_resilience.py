"""m4 tools and dispatcher under injected airline faults.

The two xfail tests are known gaps found by this harness. They're strict, so fixing a
gap makes its test fail until the marker is removed.
"""

import random

import httpx
import pytest

from harness.faults.faults import FaultRule, FaultTransport
from modules.m4_agent.agent import handle_tool_call
from modules.m4_agent.audit import AuditLog
from modules.m4_agent.tools import AirlineTools
from sandbox.mock_airline.app import create_app

pytestmark = pytest.mark.asyncio

CONV = "conv-faults"
LOOKUP = {"confirmation_code": "ABC123", "last_name": "Sample"}
QUOTE = {**LOOKUP, "new_flight_id": "WS104"}


class FakeSleep:
    def __init__(self):
        self.calls = []

    async def __call__(self, seconds):
        self.calls.append(seconds)


@pytest.fixture
def audit(tmp_path):
    return AuditLog(tmp_path / "audit.jsonl")


@pytest.fixture
def make_tools(conn):
    clients = []

    def make(rules, dry_run=True, sleep=None):
        transport = FaultTransport(
            httpx.ASGITransport(app=create_app(conn)), rules, rng=random.Random(0), sleep=sleep or FakeSleep()
        )
        client = httpx.AsyncClient(transport=transport, base_url="http://airline")
        clients.append(client)
        return AirlineTools(client, dry_run=dry_run, new_id=lambda: "q1"), transport

    yield make


def booked_flight(conn):
    return conn.execute("SELECT flight_id FROM bookings WHERE confirmation_code = 'ABC123'").fetchone()[0]


async def test_latency_does_not_change_results(make_tools, audit):
    sleep = FakeSleep()
    tools, _ = make_tools([FaultRule("latency", delay_s=2.5)], sleep=sleep)
    resp = await handle_tool_call(tools, audit, "lookup_booking", LOOKUP, CONV)
    assert resp["ok"] is True
    assert sleep.calls == [2.5, 2.5]          # booking + flight requests


@pytest.mark.parametrize(
    "rule",
    [
        FaultRule("status", status_code=500),
        FaultRule("status", status_code=503),
        FaultRule("status", status_code=429),
        FaultRule("connect_error"),
        FaultRule("timeout"),
    ],
    ids=["500", "503", "429", "connect_error", "timeout"],
)
async def test_airline_failures_become_airline_unavailable(make_tools, audit, rule):
    tools, _ = make_tools([rule])
    resp = await handle_tool_call(tools, audit, "lookup_booking", LOOKUP, CONV)
    assert resp["error"] == "airline_unavailable"
    assert resp["message"]
    [entry] = audit.entries()
    assert (entry["outcome"], entry["error"]) == ("error", "airline_unavailable")


async def test_flaky_airline_recovers(make_tools, audit):
    tools, _ = make_tools([FaultRule("status", times=1)])
    first = await handle_tool_call(tools, audit, "lookup_booking", LOOKUP, CONV)
    second = await handle_tool_call(tools, audit, "lookup_booking", LOOKUP, CONV)
    assert first["error"] == "airline_unavailable"
    assert second["ok"] is True


async def test_confirm_failure_before_send_leaves_booking_and_needs_requote(make_tools, audit, conn):
    tools, _ = make_tools([FaultRule("status", method="PATCH")], dry_run=False)
    quote = await handle_tool_call(tools, audit, "quote_rebook", QUOTE, CONV)
    confirm = await handle_tool_call(tools, audit, "confirm_rebook", {"confirmation_id": "q1"}, CONV)
    retry = await handle_tool_call(tools, audit, "confirm_rebook", {"confirmation_id": "q1"}, CONV)
    assert quote["ok"] is True
    assert confirm["error"] == "airline_unavailable"
    assert retry["error"] == "unknown_confirmation"    # the quote was used up; the agent must quote again
    assert booked_flight(conn) == "WS100"


async def test_dry_run_confirm_never_reaches_airline(make_tools, audit, conn):
    tools, transport = make_tools([FaultRule("timeout_after_send", method="PATCH")], dry_run=True)
    await handle_tool_call(tools, audit, "quote_rebook", QUOTE, CONV)
    confirm = await handle_tool_call(tools, audit, "confirm_rebook", {"confirmation_id": "q1"}, CONV)
    assert confirm["result"]["status"] == "dry_run"
    assert not any(method == "PATCH" for _, method, _ in transport.log)
    assert booked_flight(conn) == "WS100"


async def test_lost_write_does_change_the_booking(make_tools, audit, conn):
    """Proves the fault is real: the airline applied the change even though the reply was lost."""
    tools, _ = make_tools([FaultRule("timeout_after_send", method="PATCH")], dry_run=False)
    await handle_tool_call(tools, audit, "quote_rebook", QUOTE, CONV)
    await handle_tool_call(tools, audit, "confirm_rebook", {"confirmation_id": "q1"}, CONV)
    assert booked_flight(conn) == "WS104"


@pytest.mark.xfail(strict=True, reason="known gap 1: non-JSON airline replies crash the dispatcher")
@pytest.mark.parametrize(
    "rule",
    [FaultRule("bad_json", path=r"/bookings/.+"), FaultRule("status", status_code=404, path=r"/bookings/.+")],
    ids=["bad_json_200", "non_json_404"],
)
async def test_gap_non_json_reply_is_airline_unavailable(make_tools, audit, rule):
    tools, _ = make_tools([rule])
    resp = await handle_tool_call(tools, audit, "lookup_booking", LOOKUP, CONV)
    assert resp["error"] == "airline_unavailable"


@pytest.mark.xfail(strict=True, reason="known gap 2: a lost confirm reply is reported as a failure")
async def test_gap_lost_write_is_reported_as_rebooked(make_tools, audit, conn):
    tools, _ = make_tools([FaultRule("timeout_after_send", method="PATCH")], dry_run=False)
    await handle_tool_call(tools, audit, "quote_rebook", QUOTE, CONV)
    confirm = await handle_tool_call(tools, audit, "confirm_rebook", {"confirmation_id": "q1"}, CONV)
    assert booked_flight(conn) == "WS104"
    assert confirm["ok"] is True
    assert confirm["result"]["status"] == "rebooked"
