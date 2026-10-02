import json
from pathlib import Path

import pytest
from elevenlabs.types import GetConversationResponseModel

from harness.evals.metrics import (
    format_table,
    percentile,
    stage_latencies_ms,
    summarize,
    turn_metrics,
    unmapped_keys,
)
from harness.evals.runner import judge_results

FIXTURE = Path(__file__).parents[1] / "replay" / "conversation_details.json"


@pytest.fixture
def details():
    raw = json.loads(FIXTURE.read_text())
    raw.pop("_fixture_note")
    # Round-trip through the SDK model, as the runner does with live responses.
    return GetConversationResponseModel.model_validate(raw).model_dump(mode="json")


@pytest.mark.parametrize(
    "values, p, expected",
    [
        ([], 50, None),
        ([7.0], 50, 7.0),
        ([7.0], 95, 7.0),
        ([3, 1, 2], 50, 2),                 # unsorted input
        (list(range(1, 11)), 50, 5),
        (list(range(1, 11)), 95, 10),
        (list(range(1, 101)), 95, 95),
        ([1, 2], 50, 1),                    # nearest rank: ceil(0.5 * 2) = 1st
    ],
)
def test_percentile(values, p, expected):
    assert percentile(values, p) == expected


def test_turn_metrics_skips_turns_without_metrics(details):
    turns = turn_metrics(details)
    assert len(turns) == 3
    assert turns[0]["convai_llm_service_ttfb"] == 0.41


def test_stage_latencies_text_session_has_no_stt(details):
    samples = stage_latencies_ms([details])
    assert samples["stt"] == []
    assert samples["llm"] == pytest.approx([410, 620, 1350])
    assert samples["tts"] == pytest.approx([180, 210, 160])


def test_stage_latencies_pool_across_conversations(details):
    samples = stage_latencies_ms([details, details])
    assert len(samples["llm"]) == 6


def test_unmapped_keys_are_reported(details):
    assert unmapped_keys([details]) == ["convai_rag_latency"]


def test_summarize_and_table(details):
    summary = summarize(stage_latencies_ms([details]))
    assert summary["llm"] == {"n": 3, "p50": pytest.approx(620), "p95": pytest.approx(1350)}
    assert summary["stt"] == {"n": 0, "p50": None, "p95": None}
    table = format_table(summary)
    assert "n/a" in table           # stt in a text session
    assert "620 ms" in table
    assert "average" not in table.lower()


def test_judge_results(details):
    assert judge_results(details) == {
        "confirmed_after_explicit_yes": "success",
        "no_invented_details": "success",
        "stayed_in_scope": "unknown",
        "clear_error_handling": "success",
    }


def test_judge_results_missing_analysis():
    assert judge_results({"analysis": None}) == {}
