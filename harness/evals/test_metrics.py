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

# Recorded from a live `make chat` session; see its _fixture_note.
FIXTURE = Path(__file__).parents[1] / "replay" / "conversation_details.json"


@pytest.fixture
def details():
    raw = json.loads(FIXTURE.read_text())
    raw.pop("_fixture_note")
    # Round-trip through the SDK model, as the runner does with live responses.
    return GetConversationResponseModel.model_validate(raw).model_dump(mode="json")


def turn(**metrics):
    return {"conversation_turn_metrics": {"metrics": {k: {"elapsed_time": v} for k, v in metrics.items()}}}


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
    assert len(details["transcript"]) == 17
    assert len(turns) == 9
    assert turns[0]["convai_tts_service_ttfb"] == pytest.approx(0.0787, abs=1e-4)


def test_recorded_stages(details):
    samples = stage_latencies_ms([details])
    assert samples["stt"] == []                                   # text session: no speech-to-text
    assert samples["llm"] == pytest.approx([181.6, 189.1, 268.9, 188.3], abs=0.1)
    assert samples["llm_tool"] == pytest.approx([364.7, 628.8, 437.8, 517.0], abs=0.1)
    assert samples["tts"] == pytest.approx([78.7, 89.8, 78.6, 91.3, 88.6], abs=0.1)
    assert samples["e2e"] == pytest.approx([895.2, 1134.1, 1266.6, 1033.3], abs=0.1)


def test_recorded_summary_and_table(details):
    summary = summarize(stage_latencies_ms([details]))
    assert summary["llm"]["p50"] == pytest.approx(188.3, abs=0.1)
    assert summary["llm_tool"]["p95"] == pytest.approx(628.8, abs=0.1)
    assert summary["e2e"] == {"n": 4, "p50": pytest.approx(1033.3, abs=0.1), "p95": pytest.approx(1266.6, abs=0.1)}
    assert summary["stt"] == {"n": 0, "p50": None, "p95": None}
    table = format_table(summary)
    assert "n/a" in table
    assert "1033 ms" in table
    assert "average" not in table.lower()


def test_recorded_conversation_has_no_unmapped_keys(details):
    assert unmapped_keys([details]) == []


@pytest.mark.parametrize(
    "t, stage",
    [
        (turn(convai_llm_service_ttfb=0.2, convai_llm_tool_request_generation_latency=0.4), "llm_tool"),
        (turn(convai_llm_service_ttfb=0.2), "llm"),
    ],
)
def test_tool_call_turns_are_not_counted_as_llm(t, stage):
    samples = stage_latencies_ms([{"transcript": [t]}])
    assert len(samples[stage]) == 1
    assert sum(len(v) for v in samples.values()) == 1


@pytest.mark.parametrize(
    "t, counted",
    [
        (turn(convai_tts_service_ttfb=0.08, convai_ttf_audio_since_silence=0.09), False),   # scripted first message
        (turn(convai_llm_service_ttfb=0.2, convai_llm_tool_request_generation_latency=0.2,
              convai_ttf_audio_since_silence=0.5), False),                                   # tool-call turn
        (turn(convai_llm_service_ttfb=0.2, convai_ttf_audio_since_silence=0.9), True),        # generated reply
    ],
)
def test_e2e_only_counts_generated_replies(t, counted):
    assert (len(stage_latencies_ms([{"transcript": [t]}])["e2e"]) == 1) is counted


def test_stt_is_picked_up_when_present():
    samples = stage_latencies_ms([{"transcript": [turn(convai_asr_trailing_service_latency=0.15)]}])
    assert samples["stt"] == pytest.approx([150])


def test_voice_session_turns_count_stt_once():
    """Shape seen in a live voice session: STT on its own turn, repeated as turn_asr_latency on the reply."""
    voice = {"transcript": [
        turn(convai_asr_trailing_service_latency=0.051),
        turn(convai_llm_service_ttfb=0.262, convai_tts_service_ttfb=0.111,
             convai_ttf_audio_since_silence=0.851, convai_turn_asr_latency=0.051),
    ]}
    samples = stage_latencies_ms([voice])
    assert samples["stt"] == pytest.approx([51])
    assert unmapped_keys([voice]) == []


def test_stages_pool_across_conversations(details):
    assert len(stage_latencies_ms([details, details])["llm"]) == 8


def test_new_metric_names_are_reported(details):
    extra = {"transcript": [turn(convai_new_thing=0.1, convai_llm_service_ttf_sentence=0.2)]}
    assert unmapped_keys([details, extra]) == ["convai_new_thing"]   # known-but-unreported names stay quiet


def test_judge_results(details):
    assert judge_results(details) == {
        "confirmed_after_explicit_yes": "success",
        "no_invented_details": "success",
        "stayed_in_scope": "success",
        "clear_error_handling": "success",
    }


def test_judge_results_missing_analysis():
    assert judge_results({"analysis": None}) == {}
