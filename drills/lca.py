"""Drill 4 — Lowest common ancestor with parent pointers.       Target: 15 min

A forest is given as {node: parent}, where roots have parent None. Return the lowest
node that is an ancestor of both a and b. A node counts as its own ancestor.
If a and b are in different trees, return None.

    parents = {"ws": None, "f1": "ws", "f2": "ws", "p1": "f1", "p2": "f1"}
    lowest_common_ancestor(parents, "p1", "p2")  ->  "f1"
    lowest_common_ancestor(parents, "p1", "f2")  ->  "ws"
    lowest_common_ancestor(parents, "f1", "p1")  ->  "f1"

Constraints:
- The forest has no cycles.
- An unknown node raises KeyError.

Expected: O(depth) time, O(depth) space.
"""


def lowest_common_ancestor(parents: dict[str, str | None], a: str, b: str) -> str | None:
    raise NotImplementedError("solve me")
