"""Drill 2 — Lower bound by hand.                               Target: 15 min

Given a sorted list of numbers and a target, return the index of the first value that is
>= target. If every value is smaller, return len(values).

    lower_bound([1, 3, 3, 5], 3)  ->  1
    lower_bound([1, 3, 3, 5], 4)  ->  3
    lower_bound([1, 3, 3, 5], 9)  ->  4

Constraints:
- Write the binary search yourself: no `bisect` module.
- values is sorted ascending and may contain duplicates; return the first match.
- Works for an empty list (returns 0).

Expected: O(log n) time, O(1) space.
"""


def lower_bound(values: list[float], target: float) -> int:
    raise NotImplementedError("solve me")
