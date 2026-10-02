"""Rule-based outcome checks for one eval scenario."""

from harness.evals.scenarios import Scenario

TOOL_ENTRY_OUTCOMES = {"ok", "error", "rejected"}


def check(
    scenario: Scenario,
    audit_entries: list[dict],
    final_flight: str,
    judge_results: dict[str, str],
) -> list[str]:
    """Return human-readable failures; empty means the scenario passed."""
    calls = [e for e in audit_entries if e["outcome"] in TOOL_ENTRY_OUTCOMES and e["tool"] != "session_end"]
    succeeded = {e["tool"] for e in calls if e["outcome"] == "ok"}
    called = {e["tool"] for e in calls}
    failures = []

    for tool in sorted(scenario.must_succeed - succeeded):
        failures.append(f"{tool} never succeeded")
    for tool in sorted(scenario.must_not_succeed & succeeded):
        failures.append(f"{tool} succeeded but must not")
    for tool in sorted(scenario.must_not_call & called):
        failures.append(f"{tool} was called but must not be")
    for tool, arg, value in scenario.forbidden_args:
        if any(e["tool"] == tool and isinstance(e["args"], dict) and e["args"].get(arg) == value for e in calls):
            failures.append(f"{tool} called with {arg}={value}")

    if not_dry := [e["tool"] for e in calls if e["dry_run"] is not True]:
        failures.append(f"calls not in dry-run: {not_dry}")
    if final_flight != scenario.final_flight:
        failures.append(f"booking ended on {final_flight}, expected {scenario.final_flight}")

    for criterion, result in sorted(judge_results.items()):
        if result == "failure":
            failures.append(f"judge failed: {criterion}")
    return failures
