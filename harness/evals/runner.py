"""Live eval driver: scripted text caller -> real agent session -> local tools -> checks.

Each scenario gets a fresh in-memory airline and always runs dry-run. Costs credits.
"""

import json
import queue
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
from elevenlabs.conversational_ai.conversation import ClientTools, Conversation

from harness.evals.checks import check
from harness.evals.metrics import format_table, stage_latencies_ms, summarize, unmapped_keys
from harness.evals.scenarios import BOOKING, Scenario
from modules.m4_agent.audit import AuditLog
from modules.m4_agent.session import ToolBridge
from modules.m4_agent.tools import AirlineTools
from sandbox.mock_airline.app import create_app
from sandbox.mock_airline.db import connect, init_db

FIRST_REPLY_TIMEOUT_S = 60
QUIET_S = 4
ANALYSIS_TIMEOUT_S = 180
POLL_S = 3


@dataclass
class ScenarioResult:
    name: str
    conversation_id: str | None
    failures: list[str]
    judge: dict[str, str]
    details: dict

    @property
    def passed(self) -> bool:
        return not self.failures


def wait_for_agent_turn(replies: queue.Queue, first_timeout=FIRST_REPLY_TIMEOUT_S, quiet=QUIET_S) -> list[str]:
    """Collect the agent's replies to one user turn: wait for the first, then until quiet."""
    texts = [replies.get(timeout=first_timeout)]
    while True:
        try:
            texts.append(replies.get(timeout=quiet))
        except queue.Empty:
            return texts


def wait_for_analysis(client, conversation_id: str, timeout=ANALYSIS_TIMEOUT_S, poll=POLL_S, sleep=time.sleep) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        details = client.conversational_ai.conversations.get(conversation_id).model_dump(mode="json")
        if details["status"] in ("done", "failed"):
            return details
        if time.monotonic() >= deadline:
            raise TimeoutError(f"conversation {conversation_id} still {details['status']}")
        sleep(poll)


def judge_results(details: dict) -> dict[str, str]:
    results = (details.get("analysis") or {}).get("evaluation_criteria_results") or {}
    return {cid: r["result"] for cid, r in results.items()}


def run_scenario(client, agent_id: str, scenario: Scenario, out_dir: Path) -> ScenarioResult:
    conn = connect()
    init_db(conn)
    airline = httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(conn)), base_url="http://airline")
    audit = AuditLog(out_dir / f"{scenario.name}.audit.jsonl")
    bridge = ToolBridge(AirlineTools(airline, dry_run=True), audit, f"eval-{scenario.name}-{uuid.uuid4().hex[:8]}")
    client_tools = ClientTools()
    bridge.register(client_tools)

    replies: queue.Queue = queue.Queue()
    conversation = Conversation(
        client, agent_id, requires_auth=True, audio_interface=None,
        client_tools=client_tools, callback_agent_response=replies.put,
    )
    conversation.start_session()
    try:
        wait_for_agent_turn(replies)   # first message
        for turn in scenario.user_turns:
            conversation.send_user_message(turn)
            wait_for_agent_turn(replies)
    finally:
        bridge.close(airline)
        conversation.end_session()
        conversation_id = conversation.wait_for_session_end()

    details = wait_for_analysis(client, conversation_id)
    judge = judge_results(details)
    final_flight = conn.execute(
        "SELECT flight_id FROM bookings WHERE confirmation_code = ?", (BOOKING,)
    ).fetchone()[0]
    failures = check(scenario, audit.entries(), final_flight, judge)
    return ScenarioResult(scenario.name, conversation_id, failures, judge, details)


def write_report(results: list[ScenarioResult], out_dir: Path) -> str:
    details = [r.details for r in results]
    summary = summarize(stage_latencies_ms(details))
    report = {
        "scenarios": [
            {k: v for k, v in asdict(r).items() if k != "details"} | {"passed": r.passed}
            for r in results
        ],
        "latency_ms": summary,
        "unmapped_metric_keys": unmapped_keys(details),
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))
    for r in results:
        (out_dir / f"{r.name}.details.json").write_text(json.dumps(r.details, indent=2))

    lines = [f"{'PASS' if r.passed else 'FAIL'}  {r.name}" + "".join(f"\n      - {f}" for f in r.failures) for r in results]
    lines += ["", format_table(summary)]
    if report["unmapped_metric_keys"]:
        lines.append(f"unmapped metric keys: {report['unmapped_metric_keys']}")
    return "\n".join(lines)


def new_results_dir(root: Path = Path("harness/evals/results")) -> Path:
    out = root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=True)
    return out


def main() -> None:
    """Latency report for existing conversations, e.g. voice sessions from `make talk`.

    python -m harness.evals.runner CONVERSATION_ID [...]
    """
    import os
    import sys

    from dotenv import load_dotenv
    from elevenlabs import ElevenLabs

    load_dotenv()
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    details = [wait_for_analysis(client, cid) for cid in sys.argv[1:]]
    print(format_table(summarize(stage_latencies_ms(details))))
    if keys := unmapped_keys(details):
        print(f"unmapped metric keys: {keys}")


if __name__ == "__main__":
    main()
