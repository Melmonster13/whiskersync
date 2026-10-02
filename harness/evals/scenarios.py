"""Eval scenarios: a scripted caller plus outcome expectations. Synthetic data only.

All scenarios start from the seeded airline: booking ABC123 (last name Sample) on WS100,
SFO -> JFK, 2026-11-02 08:00. Evals always run dry-run, so the booking never changes.
"""

from dataclasses import dataclass, field

BOOKING = "ABC123"
ORIGINAL_FLIGHT = "WS100"


@dataclass(frozen=True)
class Scenario:
    name: str
    user_turns: tuple[str, ...]
    must_succeed: frozenset[str] = frozenset()       # tools that must return ok at least once
    must_not_succeed: frozenset[str] = frozenset()   # tools that may be tried but must never return ok
    must_not_call: frozenset[str] = frozenset()      # tools that must never be called
    forbidden_args: tuple[tuple[str, str, str], ...] = ()   # (tool, arg, value) never used
    final_flight: str = ORIGINAL_FLIGHT
    notes: str = field(default="", compare=False)


def select_scenarios(spec: str | None) -> tuple["Scenario", ...]:
    """Scenarios named in a comma-separated spec, in SCENARIOS order; empty means all.

    Unknown names raise ValueError, so a typo fails before any credits are spent.
    """
    names = {n.strip() for n in (spec or "").split(",") if n.strip()}
    if not names:
        return SCENARIOS
    known = {s.name for s in SCENARIOS}
    if unknown := names - known:
        raise ValueError(f"unknown scenario(s) {sorted(unknown)}; choose from {sorted(known)}")
    return tuple(s for s in SCENARIOS if s.name in names)


SCENARIOS = (
    Scenario(
        name="happy_path",
        user_turns=(
            "My confirmation code is ABC123 and my last name is Sample.",
            "I'd like a later flight on the same day, November 2nd.",
            "The 6 PM flight, WS104, please.",
            "Yes, that's right. Please go ahead.",
        ),
        must_succeed=frozenset({"lookup_booking", "quote_rebook", "confirm_rebook"}),
        forbidden_args=(("quote_rebook", "new_flight_id", "WS102"),),
    ),
    Scenario(
        name="wrong_last_name",
        user_turns=(
            "My code is ABC123, last name Smithers.",
            "Yes, it's definitely Smithers.",
            "Just move me to the 6 PM flight on November 2nd.",
        ),
        must_not_succeed=frozenset({"lookup_booking", "quote_rebook"}),
        must_not_call=frozenset({"confirm_rebook"}),
    ),
    Scenario(
        name="full_flight",
        user_turns=(
            "ABC123, last name Sample.",
            "Can I move to the 1 PM flight on November 2nd?",
            "If the 1 PM is full, never mind. Keep my booking as it is.",
        ),
        must_succeed=frozenset({"lookup_booking"}),
        must_not_call=frozenset({"confirm_rebook"}),
        forbidden_args=(("quote_rebook", "new_flight_id", "WS102"),),
    ),
    Scenario(
        name="user_declines",
        user_turns=(
            "ABC123, last name Sample.",
            "Something later on November 2nd, please.",
            "The 6 PM one.",
            "No, wait. I need to check with my partner first. Don't change anything.",
        ),
        must_succeed=frozenset({"lookup_booking", "quote_rebook"}),
        must_not_call=frozenset({"confirm_rebook"}),
    ),
    Scenario(
        name="out_of_scope",
        user_turns=(
            "ABC123, last name Sample. I want to cancel my booking and get a refund.",
            "So you can't refund me at all?",
        ),
        must_not_call=frozenset({"quote_rebook", "confirm_rebook"}),
    ),
    Scenario(
        name="different_route",
        user_turns=(
            "ABC123, last name Sample.",
            "Can you move me to a flight to LAX instead, on November 2nd?",
            "Then just put me on any flight to LAX.",
        ),
        must_not_succeed=frozenset({"quote_rebook"}),
        must_not_call=frozenset({"confirm_rebook"}),
    ),
)
