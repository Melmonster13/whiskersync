"""Per-stage latency (STT, LLM, TTS) from ElevenLabs conversation details, as p50/p95.

STAGE_METRICS maps stages to per-turn metric keys. The SDK doesn't define these names;
they're unverified until checked against a real response. Unmapped keys are always
reported so the mapping can be fixed. Values are assumed to be seconds.
"""

import math

STAGE_METRICS = {
    "stt": "convai_asr_trailing_service_latency",
    "llm": "convai_llm_service_ttfb",
    "tts": "convai_tts_service_ttfb",
}


def turn_metrics(details: dict) -> list[dict[str, float]]:
    turns = []
    for entry in details.get("transcript") or []:
        metrics = ((entry.get("conversation_turn_metrics") or {}).get("metrics")) or {}
        if metrics:
            turns.append({key: record["elapsed_time"] for key, record in metrics.items()})
    return turns


def stage_latencies_ms(details_list: list[dict]) -> dict[str, list[float]]:
    samples = {stage: [] for stage in STAGE_METRICS}
    for details in details_list:
        for turn in turn_metrics(details):
            for stage, key in STAGE_METRICS.items():
                if key in turn:
                    samples[stage].append(turn[key] * 1000)
    return samples


def unmapped_keys(details_list: list[dict]) -> list[str]:
    seen = {key for details in details_list for turn in turn_metrics(details) for key in turn}
    return sorted(seen - set(STAGE_METRICS.values()))


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

    lines = [f"{'stage':<6}{'n':>5}{'p50':>12}{'p95':>12}"]
    for stage, s in summary.items():
        lines.append(f"{stage:<6}{s['n']:>5}{ms(s['p50']):>12}{ms(s['p95']):>12}")
    return "\n".join(lines)
