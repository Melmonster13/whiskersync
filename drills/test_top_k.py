import pytest

from drills.top_k import top_k_frequent

# Remove this marker once the drill is solved.
pytestmark = pytest.mark.xfail(raises=NotImplementedError, reason="drill not solved yet")

ERRORS = [
    "flight_full", "booking_not_found", "flight_full", "airline_unavailable",
    "booking_not_found", "flight_full",
]


@pytest.mark.parametrize(
    "items, k, expected",
    [
        (ERRORS, 2, ["flight_full", "booking_not_found"]),
        (ERRORS, 1, ["flight_full"]),
        (ERRORS, 10, ["flight_full", "booking_not_found", "airline_unavailable"]),   # k > distinct
        (ERRORS, 0, []),
        ([], 3, []),
        (["b", "a", "c"], 2, ["a", "b"]),                       # all tied: alphabetical
        (["x", "y", "y", "x", "z"], 2, ["x", "y"]),             # tie at the top
        (["x", "y", "y", "z", "z", "w"], 2, ["y", "z"]),         # two-way tie for first
        (["x", "y", "y", "z", "z", "w"], 1, ["y"]),              # tie cut off at k
        (["solo"] * 5, 1, ["solo"]),
    ],
)
def test_top_k_frequent(items, k, expected):
    assert top_k_frequent(items, k) == expected


def test_does_not_modify_input():
    items = ["b", "a", "b"]
    top_k_frequent(items, 1)
    assert items == ["b", "a", "b"]


def test_negative_k_raises():
    with pytest.raises(ValueError):
        top_k_frequent(["a"], -1)
