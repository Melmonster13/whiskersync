"""Drill 7 — Sliding-window percentile.                         Target: 25 min

Track a stream of latency samples and report a percentile over only the most recent
`window` samples, the way a live p95 latency panel works.

    tracker = SlidingPercentile(window=3, p=50)
    tracker.value()   ->  None
    tracker.add(30); tracker.add(10); tracker.add(20)
    tracker.value()   ->  20
    tracker.add(40)                  # 30 drops out of the window
    tracker.value()   ->  20         # window is now [10, 20, 40]

Constraints:
- Use the nearest-rank percentile: sort the window and take the item at position
  ceil(p / 100 * n), counting from 1 (at least the 1st). This matches
  harness/evals/metrics.py.
- value() is None when no samples have been added.
- window < 1, or p outside (0, 100], raises ValueError.

Expected: O(w) per add with a sorted window (insert plus remove); stretch goal O(log w).
"""


class SlidingPercentile:
    def __init__(self, window: int, p: float):
        raise NotImplementedError("solve me")

    def add(self, sample: float) -> None:
        raise NotImplementedError("solve me")

    def value(self) -> float | None:
        raise NotImplementedError("solve me")
