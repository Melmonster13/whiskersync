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

# Recorded from live sessions; see each file's _fixture_note.
REPLAY = Path(__file__).parents[1] / "replay"
FIXTURE = REPLAY / "conversation_details.json"              # `make chat` (text)
VOICE_FIXTURE = REPLAY / "voice_conversation_details.json"  # `make talk` with headphones


def load(path):
    raw = json.loads(path.read_text())
    raw.pop("_fixture_note")
    # Round-trip through the SDK model, as the runner does with live responses.
    return GetConversationResponseModel.model_validate(raw).model_dump(mode="json")


@pytest.fixture
def details():
    return load(FIXTURE)


@pytest.fixture
def voice():
    return load(VOICE_FIXTURE)


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


def test_recorded_voice_stages(voice):
    samples = stage_latencies_ms([voice])
    assert samples["stt"] == pytest.approx([56.1, 70.8, 71.6, 46.8, 88.3], abs=0.1)
    assert samples["tts"] == pytest.approx([72.2, 85.0, 87.6, 94.3, 87.5, 90.3, 82.7], abs=0.1)
    assert samples["e2e"] == pytest.approx([2593.9, 2184.0, 1902.4, 1539.2, 842.9], abs=0.1)
    summary = summarize(samples)
    assert summary["e2e"]["p50"] == pytest.approx(1902.4, abs=0.1)
    assert summary["e2e"]["p95"] == pytest.approx(2593.9, abs=0.1)
    assert unmapped_keys([voice]) == []


def test_idle_prompt_after_silence_is_not_counted_as_e2e(voice):
    # Live: the caller said nothing for 12 s ("..."), and the agent asked "Are you still there?".
    # That turn's e2e (12.5 s) is silence, not response time.
    silent = next(i for i, t in enumerate(voice["transcript"]) if t["role"] == "user" and t["message"] == "...")
    prompt = voice["transcript"][silent + 1]
    assert prompt["message"].startswith("Are you still there?")
    assert prompt["conversation_turn_metrics"]["metrics"]["convai_ttf_audio_since_silence"]["elapsed_time"] > 12
    assert max(stage_latencies_ms([voice])["e2e"]) < 3000


@pytest.mark.parametrize(
    "caller_message, counted",
    [("...", False), ("", False), ("…", False), (None, False), ("Yes, go ahead.", True)],
)
def test_e2e_after_caller_turn(caller_message, counted):
    reply = turn(convai_llm_service_ttfb=0.2, convai_ttf_audio_since_silence=0.9)
    transcript = [{"role": "user", "message": caller_message}, {"role": "agent", **reply}]
    assert (len(stage_latencies_ms([{"transcript": transcript}])["e2e"]) == 1) is counted


def test_judge_results(details):
    assert judge_results(details) == {
        "confirmed_after_explicit_yes": "success",
        "no_invented_details": "success",
        "stayed_in_scope": "success",
        "clear_error_handling": "success",
    }


def test_judge_results_missing_analysis():
    assert judge_results({"analysis": None}) == {}
