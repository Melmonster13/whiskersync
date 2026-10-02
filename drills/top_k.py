"""Drill 8 — Top-k most frequent.                               Target: 15 min

Given a list of items (say, error codes from an audit log), return the k most frequent.
Order by count, highest first; break ties alphabetically so the answer is unique.

    top_k_frequent(["flight_full", "booking_not_found", "flight_full", "airline_unavailable",
                    "booking_not_found", "flight_full"], 2)
        ->  ["flight_full", "booking_not_found"]

Constraints:
- k larger than the number of distinct items returns all of them.
- k == 0 returns []; k < 0 raises ValueError.

Expected: O(n log k) with a heap, or O(n) with bucket sort (ties still need sorting).
"""


def top_k_frequent(items: list[str], k: int) -> list[str]:
    raise NotImplementedError("solve me")
