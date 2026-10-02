import random
from collections import deque

import pytest

from drills.sliding_percentile import SlidingPercentile
from harness.evals.metrics import percentile

# Remove this marker once the drill is solved.
pytestmark = pytest.mark.xfail(raises=NotImplementedError, reason="drill not solved yet")


def test_empty_is_none():
    assert SlidingPercentile(window=3, p=50).value() is None


def test_example_from_docstring():
    tracker = SlidingPercentile(window=3, p=50)
    for x in (30, 10, 20):
        tracker.add(x)
    assert tracker.value() == 20
    tracker.add(40)
    assert tracker.value() == 20


@pytest.mark.parametrize(
    "window, p, samples, expected",
    [
        (5, 50, [7], 7),                            # one sample
        (5, 95, [7], 7),
        (10, 95, list(range(1, 11)), 10),           # p95 of 10 -> 10th
        (10, 50, list(range(1, 11)), 5),            # p50 of 10 -> 5th
        (100, 95, list(range(1, 101)), 95),
        (3, 100, [5, 1, 9, 2], 9),                  # p100 = max of window [1, 9, 2]
        (2, 50, [1, 2, 3, 4], 3),                   # window [3, 4] -> 1st
        (4, 50, [5, 5, 5, 1], 5),                   # duplicates
        (1, 95, [8, 3, 6], 6),                      # window of one = latest
    ],
)
def test_percentile_over_window(window, p, samples, expected):
    tracker = SlidingPercentile(window, p)
    for x in samples:
        tracker.add(x)
    assert tracker.value() == expected


def test_matches_reference_on_random_stream():
    rng = random.Random(11)
    tracker = SlidingPercentile(window=20, p=95)
    recent = deque(maxlen=20)
    for _ in range(500):
        x = rng.uniform(50, 2000)
        tracker.add(x)
        recent.append(x)
        assert tracker.value() == percentile(list(recent), 95)


def test_duplicates_evict_one_at_a_time():
    tracker = SlidingPercentile(window=3, p=100)
    for x in (9, 9, 1, 1):
        tracker.add(x)
    assert tracker.value() == 9          # window [9, 1, 1]
    tracker.add(1)
    assert tracker.value() == 1          # window [1, 1, 1]


@pytest.mark.parametrize("window, p", [(0, 50), (-1, 50), (5, 0), (5, -10), (5, 100.1)])
def test_invalid_construction_raises(window, p):
    with pytest.raises(ValueError):
        SlidingPercentile(window, p)
