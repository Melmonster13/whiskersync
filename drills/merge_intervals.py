"""Drill 1 — Merge overlapping intervals.                       Target: 15 min

Given a list of closed intervals (start, end), merge every group that overlaps or touches
and return the merged intervals sorted by start.

    merge_intervals([(1, 3), (2, 6), (8, 10), (10, 12)])  ->  [(1, 6), (8, 12)]
    merge_intervals([(5, 7), (1, 2)])                     ->  [(1, 2), (5, 7)]

Constraints:
- Input may be unsorted and may contain duplicates or nested intervals.
- Touching intervals merge: (1, 2) and (2, 3) -> (1, 3).
- start > end is invalid: raise ValueError.
- Don't modify the input list.

Expected: O(n log n) time, O(n) extra space.
"""


def merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    raise NotImplementedError("solve me")
