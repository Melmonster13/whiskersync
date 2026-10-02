"""Drill 5 — LRU cache.                                         Target: 25 min

Build a fixed-capacity cache that evicts the least recently used key when full.

    cache = LRUCache(2)
    cache.put("a", 1); cache.put("b", 2)
    cache.get("a")          ->  1        # "a" is now most recent
    cache.put("c", 3)                    # evicts "b"
    cache.get("b")          ->  None
    len(cache)              ->  2

Constraints:
- get(key, default=None) returns the value and marks the key as most recently used.
- put(key, value) inserts or updates, and marks the key as most recently used.
- capacity < 1 raises ValueError.
- Build it from a dict and your own doubly linked list: no OrderedDict, no functools.lru_cache.

Expected: O(1) get and put.
"""


class LRUCache:
    def __init__(self, capacity: int):
        raise NotImplementedError("solve me")

    def get(self, key, default=None):
        raise NotImplementedError("solve me")

    def put(self, key, value) -> None:
        raise NotImplementedError("solve me")

    def __len__(self) -> int:
        raise NotImplementedError("solve me")
