import bisect
import inspect
import random

import pytest

import drills.lower_bound as module
from drills.lower_bound import lower_bound

# Remove this marker once the drill is solved.
pytestmark = pytest.mark.xfail(raises=NotImplementedError, reason="drill not solved yet")


@pytest.mark.parametrize(
    "values, target, expected",
    [
        ([], 5, 0),
        ([4], 3, 0),
        ([4], 4, 0),
        ([4], 5, 1),
        ([1, 3, 3, 5], 3, 1),           # first of duplicates
        ([1, 3, 3, 5], 4, 3),           # between values
        ([1, 3, 3, 5], 0, 0),           # before all
        ([1, 3, 3, 5], 9, 4),           # after all
        ([2, 2, 2, 2], 2, 0),           # all equal
        ([0.5, 1.5, 2.5], 1.5, 1),      # floats
        ([-3, -1, 0, 2], -2, 1),        # negatives
    ],
)
def test_lower_bound(values, target, expected):
    assert lower_bound(values, target) == expected


def test_matches_bisect_on_random_inputs():
    rng = random.Random(7)
    for _ in range(300):
        values = sorted(rng.randint(-20, 20) for _ in range(rng.randint(0, 30)))
        target = rng.randint(-25, 25)
        assert lower_bound(values, target) == bisect.bisect_left(values, target)


def test_does_not_use_bisect_module():
    source = inspect.getsource(module)
    assert "import bisect" not in source and "from bisect" not in source
    lower_bound([1, 2, 3], 2)   # still has to be implemented to pass
