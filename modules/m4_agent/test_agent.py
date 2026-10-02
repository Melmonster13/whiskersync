import httpx
import pytest

from modules.m4_agent.agent import handle_tool_call
from modules.m4_agent.audit import AuditLog
from modules.m4_agent.tools import AirlineTools, dry_run_from_env

CONV = "conv-test-1"


@pytest.fixture
def audit(tmp_path):
    return AuditLog(tmp_path / "audit.jsonl")


@pytest.mark.asyncio
async def test_successful_call_is_audited(tools, audit):
    params = {"confirmation_code": "ABC123", "last_name": "Sample"}
    resp = await handle_tool_call(tools, audit, "lookup_booking", params, CONV)
    assert resp["ok"] is True
    assert resp["result"]["flight"]["id"] == "WS100"

    [entry] = audit.entries()
    assert entry["conversation_id"] == CONV
    assert entry["tool"] == "lookup_booking"
    assert entry["args"] == params
    assert entry["outcome"] == "ok"
    assert entry["error"] is None
    assert entry["dry_run"] is True
    assert entry["ts"]


@pytest.mark.asyncio
async def test_tool_error_is_returned_and_audited(tools, audit):
    params = {"confirmation_code": "ABC123", "last_name": "Wrong"}
    resp = await handle_tool_call(tools, audit, "lookup_booking", params, CONV)
    assert resp["ok"] is False
    assert resp["error"] == "booking_not_found"
    assert resp["message"]
    [entry] = audit.entries()
    assert (entry["outcome"], entry["error"]) == ("error", "booking_not_found")


@pytest.mark.asyncio
async def test_unknown_tool_is_rejected(tools, audit):
    resp = await handle_tool_call(tools, audit, "cancel_booking", {}, CONV)
    assert resp["error"] == "unknown_tool"
    [entry] = audit.entries()
    assert (entry["outcome"], entry["error"]) == ("rejected", "unknown_tool")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"confirmation_id": "abc", "extra": 1},   # unexpected key
        {},                                       # missing key
        {"confirmation_id": 123},                 # wrong type
        ["abc"],                                  # not an object
    ],
)
async def test_invalid_arguments_are_rejected(tools, audit, params):
    resp = await handle_tool_call(tools, audit, "confirm_rebook", params, CONV)
    assert resp["error"] == "invalid_arguments"
    [entry] = audit.entries()
    assert (entry["outcome"], entry["error"]) == ("rejected", "invalid_arguments")


@pytest.mark.asyncio
async def test_airline_unavailable(audit):
    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(refuse), base_url="http://airline") as c:
        tools = AirlineTools(c)
        params = {"origin": "SFO", "destination": "JFK", "date": "2026-11-02"}
        resp = await handle_tool_call(tools, audit, "search_flights", params, CONV)
    assert resp["error"] == "airline_unavailable"
    [entry] = audit.entries()
    assert (entry["outcome"], entry["error"]) == ("error", "airline_unavailable")


@pytest.mark.asyncio
async def test_quote_then_confirm_audits_every_call(tools, audit, conn):
    quote = await handle_tool_call(
        tools, audit, "quote_rebook",
        {"confirmation_code": "ABC123", "last_name": "Sample", "new_flight_id": "WS104"}, CONV,
    )
    confirm = await handle_tool_call(
        tools, audit, "confirm_rebook",
        {"confirmation_id": quote["result"]["confirmation_id"]}, CONV,
    )
    assert confirm["result"]["status"] == "dry_run"
    assert [(e["tool"], e["outcome"], e["dry_run"]) for e in audit.entries()] == [
        ("quote_rebook", "ok", True),
        ("confirm_rebook", "ok", True),
    ]


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, True),       # unset -> dry run
        ("true", True),
        ("", True),
        ("yes", True),
        ("false", False),
        ("FALSE", False),
        (" 0 ", False),
        ("no", False),
    ],
)
def test_dry_run_from_env(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("DRY_RUN", raising=False)
    else:
        monkeypatch.setenv("DRY_RUN", value)
    assert dry_run_from_env() is expected
