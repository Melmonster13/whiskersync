import pytest

from drills.merge_intervals import merge_intervals

# Remove this marker once the drill is solved.
pytestmark = pytest.mark.xfail(raises=NotImplementedError, reason="drill not solved yet")


@pytest.mark.parametrize(
    "intervals, expected",
    [
        ([], []),
        ([(1, 3)], [(1, 3)]),
        ([(1, 3), (2, 6), (8, 10), (10, 12)], [(1, 6), (8, 12)]),
        ([(5, 7), (1, 2)], [(1, 2), (5, 7)]),               # unsorted, no overlap
        ([(1, 2), (2, 3)], [(1, 3)]),                       # touching
        ([(1, 10), (2, 3), (4, 5)], [(1, 10)]),             # nested
        ([(1, 4), (1, 4)], [(1, 4)]),                       # duplicates
        ([(3, 3), (3, 3)], [(3, 3)]),                       # zero-length
        ([(0, 1), (5, 6), (1, 5)], [(0, 6)]),               # bridge joins two
        ([(-5, -1), (-2, 0)], [(-5, 0)]),                   # negatives
        ([(1.5, 2.5), (2.5, 3.0)], [(1.5, 3.0)]),           # floats
    ],
)
def test_merge_intervals(intervals, expected):
    assert merge_intervals(intervals) == expected


def test_does_not_modify_input():
    intervals = [(5, 7), (1, 3), (2, 4)]
    merge_intervals(intervals)
    assert intervals == [(5, 7), (1, 3), (2, 4)]


def test_invalid_interval_raises():
    with pytest.raises(ValueError):
        merge_intervals([(1, 2), (5, 4)])
