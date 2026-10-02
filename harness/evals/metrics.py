"""Per-stage latency from ElevenLabs conversation details, as p50/p95.

Metric names verified against a live conversation on 2026-10-02 (values in seconds),
except STT, which a text session doesn't produce. Unmapped keys are always reported
so new metric names don't go unnoticed.
"""

import math

STT = "convai_asr_trailing_service_latency"          # unverified: needs a voice session
LLM = "convai_llm_service_ttfb"
LLM_TOOL = "convai_llm_tool_request_generation_latency"
TTS = "convai_tts_service_ttfb"
E2E = "convai_ttf_audio_since_silence"               # caller goes quiet -> first agent audio

STAGES = ("stt", "llm", "llm_tool", "tts", "e2e")

# Seen in live data but not reported as a stage.
KNOWN_UNREPORTED = {
    "convai_llm_service_ttf_sentence",
    "convai_llm_service_tt_last_sentence",
    "convai_turn_silence_before_initiation",
}


def turn_metrics(details: dict) -> list[dict[str, float]]:
    turns = []
    for entry in details.get("transcript") or []:
        metrics = ((entry.get("conversation_turn_metrics") or {}).get("metrics")) or {}
        if metrics:
            turns.append({key: record["elapsed_time"] for key, record in metrics.items()})
    return turns


def stage_latencies_ms(details_list: list[dict]) -> dict[str, list[float]]:
    samples = {stage: [] for stage in STAGES}
    for details in details_list:
        for turn in turn_metrics(details):
            if STT in turn:
                samples["stt"].append(turn[STT] * 1000)
            # A tool-call turn also reports LLM TTFB; count it as llm_tool only, so the
            # llm stage reflects spoken replies.
            if LLM_TOOL in turn:
                samples["llm_tool"].append(turn[LLM_TOOL] * 1000)
            elif LLM in turn:
                samples["llm"].append(turn[LLM] * 1000)
            if TTS in turn:
                samples["tts"].append(turn[TTS] * 1000)
            # Only generated replies: the scripted first message isn't a response to the caller.
            if E2E in turn and LLM in turn and LLM_TOOL not in turn:
                samples["e2e"].append(turn[E2E] * 1000)
    return samples


def unmapped_keys(details_list: list[dict]) -> list[str]:
    seen = {key for details in details_list for turn in turn_metrics(details) for key in turn}
    return sorted(seen - {STT, LLM, LLM_TOOL, TTS, E2E} - KNOWN_UNREPORTED)


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile; None for no samples."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def summarize(samples: dict[str, list[float]]) -> dict[str, dict]:
    return {
        stage: {"n": len(values), "p50": percentile(values, 50), "p95": percentile(values, 95)}
        for stage, values in samples.items()
    }


def format_table(summary: dict[str, dict]) -> str:
    def ms(v):
        return "n/a" if v is None else f"{v:.0f} ms"

    lines = [f"{'stage':<9}{'n':>5}{'p50':>12}{'p95':>12}"]
    for stage, s in summary.items():
        lines.append(f"{stage:<9}{s['n']:>5}{ms(s['p50']):>12}{ms(s['p95']):>12}")
    return "\n".join(lines)
