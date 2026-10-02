"""m4 tools and dispatcher under injected airline faults.

The non-JSON and lost-write tests started as strict xfails (gaps found by this harness)
and were fixed afterwards.
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


@pytest.mark.parametrize(
    "rule",
    [
        FaultRule("bad_json", path=r"/bookings/.+"),
        FaultRule("status", status_code=404, path=r"/bookings/.+"),   # HTML 404 from a proxy
        FaultRule("bad_json", path=r"/flights/.+"),                    # second request of the lookup
    ],
    ids=["bad_json_200", "non_json_404", "bad_json_flight"],
)
async def test_non_json_reply_is_airline_unavailable(make_tools, audit, rule):
    tools, _ = make_tools([rule])
    resp = await handle_tool_call(tools, audit, "lookup_booking", LOOKUP, CONV)
    assert resp["error"] == "airline_unavailable"
    [entry] = audit.entries()
    assert (entry["outcome"], entry["error"]) == ("error", "airline_unavailable")


async def test_non_json_search_reply_is_airline_unavailable(make_tools, audit):
    tools, _ = make_tools([FaultRule("bad_json", path="/flights")])
    params = {"origin": "SFO", "destination": "JFK", "date": "2026-11-02"}
    resp = await handle_tool_call(tools, audit, "search_flights", params, CONV)
    assert resp["error"] == "airline_unavailable"


async def test_lost_write_is_reconciled_as_rebooked(make_tools, audit, conn):
    tools, _ = make_tools([FaultRule("timeout_after_send", method="PATCH")], dry_run=False)
    await handle_tool_call(tools, audit, "quote_rebook", QUOTE, CONV)
    confirm = await handle_tool_call(tools, audit, "confirm_rebook", {"confirmation_id": "q1"}, CONV)
    assert booked_flight(conn) == "WS104"
    assert confirm["ok"] is True
    assert confirm["result"]["status"] == "rebooked"
    assert confirm["result"]["reconciled"] is True
    assert confirm["result"]["booking"]["flight_id"] == "WS104"


async def test_lost_write_with_failed_recheck_is_status_unknown(make_tools, audit, conn):
    tools, transport = make_tools([FaultRule("timeout_after_send", method="PATCH")], dry_run=False)
    await handle_tool_call(tools, audit, "quote_rebook", QUOTE, CONV)
    transport.add_rule(FaultRule("connect_error", method="GET"))     # airline goes down after the quote
    confirm = await handle_tool_call(tools, audit, "confirm_rebook", {"confirmation_id": "q1"}, CONV)
    assert confirm["error"] == "rebook_status_unknown"
    assert "Don't confirm again" in confirm["message"]
    assert booked_flight(conn) == "WS104"                          # it did go through
    assert audit.entries()[-1]["error"] == "rebook_status_unknown"


UNCLEAR_CONFIRMS = pytest.mark.parametrize(
    "rule",
    [
        FaultRule("bad_json", method="PATCH"),                  # unreadable reply, change not applied
        FaultRule("status", status_code=502, method="PATCH"),   # gateway error, change not applied
        FaultRule("timeout", method="PATCH"),                   # timed out before reaching the airline
    ],
    ids=["bad_json", "502", "timeout"],
)


@UNCLEAR_CONFIRMS
async def test_unclear_confirm_not_applied_is_airline_unavailable(make_tools, audit, conn, rule):
    tools, _ = make_tools([rule], dry_run=False)
    await handle_tool_call(tools, audit, "quote_rebook", QUOTE, CONV)
    confirm = await handle_tool_call(tools, audit, "confirm_rebook", {"confirmation_id": "q1"}, CONV)
    assert confirm["error"] == "airline_unavailable"
    assert booked_flight(conn) == "WS100"


@UNCLEAR_CONFIRMS
async def test_unclear_confirm_is_rechecked(make_tools, audit, conn, rule):
    """If the re-check fails too, the answer becomes status-unknown: proof the re-check ran."""
    tools, transport = make_tools([rule], dry_run=False)
    await handle_tool_call(tools, audit, "quote_rebook", QUOTE, CONV)
    transport.add_rule(FaultRule("connect_error", method="GET"))
    confirm = await handle_tool_call(tools, audit, "confirm_rebook", {"confirmation_id": "q1"}, CONV)
    assert confirm["error"] == "rebook_status_unknown"
    assert ("connect_error", "GET", "/bookings/ABC123") in transport.log


async def test_confirm_connect_error_skips_recheck(make_tools, audit, conn):
    tools, transport = make_tools([FaultRule("connect_error", method="PATCH")], dry_run=False)
    await handle_tool_call(tools, audit, "quote_rebook", QUOTE, CONV)
    transport.add_rule(FaultRule("connect_error", method="GET"))     # a re-check would fail
    confirm = await handle_tool_call(tools, audit, "confirm_rebook", {"confirmation_id": "q1"}, CONV)
    assert confirm["error"] == "airline_unavailable"                # never sent, so not "unknown"
    assert [(k, m) for k, m, _ in transport.log] == [("connect_error", "PATCH")]
    assert booked_flight(conn) == "WS100"


async def test_confirm_other_4xx_is_not_rechecked(make_tools, audit, conn):
    tools, transport = make_tools([FaultRule("status", status_code=400, method="PATCH")], dry_run=False)
    await handle_tool_call(tools, audit, "quote_rebook", QUOTE, CONV)
    transport.add_rule(FaultRule("connect_error", method="GET"))     # a re-check would fail
    confirm = await handle_tool_call(tools, audit, "confirm_rebook", {"confirmation_id": "q1"}, CONV)
    assert confirm["error"] == "airline_unavailable"
    assert booked_flight(conn) == "WS100"
