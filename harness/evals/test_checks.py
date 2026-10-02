import queue
from types import SimpleNamespace

import pytest

from harness.evals.checks import check
from harness.evals.runner import CostGuardError, check_low_cost_tts, wait_for_agent_turn, wait_for_analysis
from harness.evals.scenarios import SCENARIOS, Scenario, select_scenarios
from modules.m4_agent.agent import TOOL_PARAMS
from modules.m4_agent.config import EVALUATION_CRITERIA, LOW_COST_TTS_MODELS


def call(tool, outcome="ok", dry_run=True, **args):
    return {"tool": tool, "args": args, "outcome": outcome, "dry_run": dry_run, "error": None}


SCENARIO = Scenario(
    name="t",
    user_turns=("hi",),
    must_succeed=frozenset({"lookup_booking"}),
    must_not_succeed=frozenset({"quote_rebook"}),
    must_not_call=frozenset({"confirm_rebook"}),
    forbidden_args=(("quote_rebook", "new_flight_id", "WS102"),),
)


@pytest.mark.parametrize(
    "entries, final_flight, judge, expected",
    [
        ([call("lookup_booking")], "WS100", {}, []),
        ([], "WS100", {}, ["lookup_booking never succeeded"]),
        ([call("lookup_booking", "error")], "WS100", {}, ["lookup_booking never succeeded"]),
        (
            [call("lookup_booking"), call("quote_rebook", "error", new_flight_id="WS104")],
            "WS100", {}, [],                               # tried and failed is fine
        ),
        (
            [call("lookup_booking"), call("quote_rebook", new_flight_id="WS104")],
            "WS100", {}, ["quote_rebook succeeded but must not"],
        ),
        (
            [call("lookup_booking"), call("confirm_rebook", "rejected")],
            "WS100", {}, ["confirm_rebook was called but must not be"],   # even a rejected call counts
        ),
        (
            [call("lookup_booking"), call("quote_rebook", "error", new_flight_id="WS102")],
            "WS100", {}, ["quote_rebook called with new_flight_id=WS102"],
        ),
        ([call("lookup_booking", dry_run=False)], "WS100", {}, ["calls not in dry-run: ['lookup_booking']"]),
        ([call("lookup_booking")], "WS104", {}, ["booking ended on WS104, expected WS100"]),
        ([call("lookup_booking")], "WS100", {"a": "success", "b": "unknown"}, []),
        ([call("lookup_booking")], "WS100", {"stayed_in_scope": "failure"}, ["judge failed: stayed_in_scope"]),
        (
            [call("lookup_booking"), {"tool": "session_end", "args": {}, "outcome": "ok", "dry_run": True}],
            "WS100", {}, [],                               # session marker isn't a tool call
        ),
    ],
)
def test_check(entries, final_flight, judge, expected):
    assert check(SCENARIO, entries, final_flight, judge) == expected


def test_scenarios_are_consistent():
    names = [s.name for s in SCENARIOS]
    assert len(names) == len(set(names))
    for s in SCENARIOS:
        tools = s.must_succeed | s.must_not_succeed | s.must_not_call | {t for t, _, _ in s.forbidden_args}
        assert tools <= TOOL_PARAMS.keys(), s.name
        assert not (s.must_succeed & (s.must_not_succeed | s.must_not_call)), s.name
        assert s.user_turns, s.name


@pytest.mark.parametrize(
    "spec, expected",
    [
        (None, [s.name for s in SCENARIOS]),
        ("", [s.name for s in SCENARIOS]),
        (" , ", [s.name for s in SCENARIOS]),
        ("different_route,out_of_scope", ["out_of_scope", "different_route"]),   # scenario order, not spec order
        (" happy_path , happy_path ", ["happy_path"]),                          # spaces and duplicates
    ],
)
def test_select_scenarios(spec, expected):
    assert [s.name for s in select_scenarios(spec)] == expected


@pytest.mark.parametrize("spec", ["happy_pth", "happy_path,nope"])
def test_select_scenarios_unknown_name_raises(spec):
    with pytest.raises(ValueError, match="choose from") as exc:
        select_scenarios(spec)
    assert "happy_path" in str(exc.value)          # lists the valid names


def test_evaluation_criteria_are_described():
    assert all(goal.strip() for goal in EVALUATION_CRITERIA.values())


def test_wait_for_agent_turn_collects_until_quiet():
    replies = queue.Queue()
    for text in ["Let me check.", "You're on WS100."]:
        replies.put(text)
    assert wait_for_agent_turn(replies, first_timeout=1, quiet=0.05) == ["Let me check.", "You're on WS100."]


def test_wait_for_agent_turn_times_out_without_reply():
    with pytest.raises(queue.Empty):
        wait_for_agent_turn(queue.Queue(), first_timeout=0.05, quiet=0.05)


class FakeConversations:
    def __init__(self, statuses):
        self.statuses = list(statuses)

    def get(self, conversation_id):
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        return type("Resp", (), {"model_dump": lambda self, mode: {"status": status}})()


def fake_client(statuses):
    return type("C", (), {"conversational_ai": type("A", (), {"conversations": FakeConversations(statuses)})()})()


def test_wait_for_analysis_polls_until_done():
    sleeps = []
    details = wait_for_analysis(fake_client(["processing", "processing", "done"]), "c1", sleep=sleeps.append)
    assert details["status"] == "done"
    assert len(sleeps) == 2


def agent_client(model_id):
    agent = SimpleNamespace(conversation_config=SimpleNamespace(tts=SimpleNamespace(model_id=model_id)))
    agents = SimpleNamespace(get=lambda agent_id: agent)
    return SimpleNamespace(conversational_ai=SimpleNamespace(agents=agents))


@pytest.mark.parametrize("model", sorted(LOW_COST_TTS_MODELS))
def test_cost_guard_allows_low_cost_models(model):
    assert check_low_cost_tts(agent_client(model), "agent_1") == model


@pytest.mark.parametrize(
    "model", ["eleven_flash_v2", "eleven_turbo_v2", "eleven_multilingual_v2", "eleven_v3_conversational", None]
)
def test_cost_guard_blocks_other_models(model):
    with pytest.raises(CostGuardError, match="make agent"):
        check_low_cost_tts(agent_client(model), "agent_1")


def test_wait_for_analysis_times_out():
    with pytest.raises(TimeoutError):
        wait_for_analysis(fake_client(["processing"]), "c1", timeout=0, sleep=lambda s: None)
