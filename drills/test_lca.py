import pytest

from drills.lca import lowest_common_ancestor

# Remove this marker once the drill is solved.
pytestmark = pytest.mark.xfail(raises=NotImplementedError, reason="drill not solved yet")

#        ws                 other
#      /    \                 |
#    f1      f2             o1
#   /  \       \
#  p1   p2      p3
#  |
#  c1
PARENTS = {
    "ws": None, "f1": "ws", "f2": "ws",
    "p1": "f1", "p2": "f1", "p3": "f2", "c1": "p1",
    "other": None, "o1": "other",
}


@pytest.mark.parametrize(
    "a, b, expected",
    [
        ("p1", "p2", "f1"),        # siblings
        ("p1", "f2", "ws"),        # different depths
        ("c1", "p3", "ws"),        # deep vs. other branch
        ("c1", "p2", "f1"),
        ("f1", "p1", "f1"),        # ancestor of the other
        ("p1", "f1", "f1"),        # same, reversed
        ("p2", "p2", "p2"),        # same node
        ("ws", "ws", "ws"),        # root with itself
        ("c1", "o1", None),        # different trees
        ("ws", "other", None),     # two roots
    ],
)
def test_lca(a, b, expected):
    assert lowest_common_ancestor(PARENTS, a, b) == expected


@pytest.mark.parametrize("a, b", [("ghost", "p1"), ("p1", "ghost")])
def test_unknown_node_raises(a, b):
    with pytest.raises(KeyError):
        lowest_common_ancestor(PARENTS, a, b)
