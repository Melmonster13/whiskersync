"""Replays a recorded-format conversation through the real SDK message handling.

Uses Conversation._handle_message (SDK-private) so tool calls take the same path as a
live session: SDK parses client_tool_call -> ClientTools runs our handler on its own
loop -> result goes back over the (fake) websocket.
"""

import json
import queue
from pathlib import Path

import httpx
import pytest
from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import ClientTools, Conversation

from modules.m4_agent.audit import AuditLog
from modules.m4_agent.session import ToolBridge
from modules.m4_agent.tools import AirlineTools
from sandbox.mock_airline.app import create_app

FIXTURE = Path(__file__).parents[2] / "harness" / "replay" / "rebook_conversation.jsonl"
SESSION = "local-test-session"


class FakeWebSocket:
    def __init__(self):
        self.sent = queue.Queue()

    def send(self, message):
        self.sent.put(json.loads(message))


def replay(conn, tmp_path, dry_run):
    airline = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(conn)), base_url="http://airline"
    )
    tools = AirlineTools(airline, dry_run=dry_run, new_id=lambda: "replay-quote-1")
    audit = AuditLog(tmp_path / "audit.jsonl")
    bridge = ToolBridge(tools, audit, SESSION)
    client_tools = ClientTools()
    bridge.register(client_tools)
    conversation = Conversation(
        ElevenLabs(api_key="offline"), "agent_replay", requires_auth=False, client_tools=client_tools
    )
    ws = FakeWebSocket()
    responses = []
    try:
        for line in FIXTURE.read_text().splitlines():
            message = json.loads(line)
            conversation._handle_message(message, ws)
            if message["type"] == "client_tool_call":
                responses.append(ws.sent.get(timeout=5))   # the agent waits for each result
    finally:
        bridge.close(airline)
        client_tools.stop()
    return conversation, responses, audit


def booked_flight(conn):
    return conn.execute(
        "SELECT flight_id FROM bookings WHERE confirmation_code = 'ABC123'"
    ).fetchone()[0]


@pytest.mark.parametrize("dry_run, final_status, final_flight", [
    (True, "dry_run", "WS100"),
    (False, "rebooked", "WS104"),
])
def test_replay_rebook_conversation(conn, tmp_path, dry_run, final_status, final_flight):
    conversation, responses, audit = replay(conn, tmp_path, dry_run)

    assert conversation._conversation_id == "conv_replay_0001"
    assert [r["tool_call_id"] for r in responses] == ["call_1", "call_2", "call_3", "call_4"]
    assert all(r["type"] == "client_tool_result" and r["is_error"] is False for r in responses)

    lookup, search, quote, confirm = (json.loads(r["result"]) for r in responses)
    assert lookup["ok"] and lookup["result"]["flight"]["id"] == "WS100"
    assert [f["id"] for f in search["result"]] == ["WS100", "WS104"]
    assert quote["result"]["confirmation_id"] == "replay-quote-1"
    assert confirm["result"]["status"] == final_status
    assert booked_flight(conn) == final_flight

    entries = audit.entries()
    assert [e["tool"] for e in entries] == [
        "lookup_booking", "search_flights", "quote_rebook", "confirm_rebook",
    ]
    assert all(e["conversation_id"] == SESSION and e["outcome"] == "ok" for e in entries)
    assert all("tool_call_id" not in e["args"] for e in entries)
    assert all(e["dry_run"] is dry_run for e in entries)


@pytest.mark.asyncio
async def test_bridge_returns_errors_as_results(tools, tmp_path):
    audit = AuditLog(tmp_path / "audit.jsonl")
    bridge = ToolBridge(tools, audit, SESSION)
    result = json.loads(await bridge.call(
        "lookup_booking",
        {"tool_call_id": "call_9", "confirmation_code": "ABC123", "last_name": "Wrong"},
    ))
    assert result == {
        "ok": False,
        "error": "booking_not_found",
        "message": "booking not found",
    }
    [entry] = audit.entries()
    assert entry["args"] == {"confirmation_code": "ABC123", "last_name": "Wrong"}
