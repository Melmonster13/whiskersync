import inspect

import pytest

import drills.lru_cache as module
from drills.lru_cache import LRUCache

# Remove this marker once the drill is solved.
pytestmark = pytest.mark.xfail(raises=NotImplementedError, reason="drill not solved yet")


def test_basic_eviction():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    cache.put("c", 3)                 # "b" is least recent
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3
    assert len(cache) == 2


def test_put_existing_updates_and_refreshes():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("a", 10)                # update refreshes "a"
    cache.put("c", 3)                 # evicts "b", not "a"
    assert cache.get("a") == 10
    assert cache.get("b") is None
    assert len(cache) == 2


def test_get_missing_returns_default_without_side_effects():
    cache = LRUCache(1)
    assert cache.get("x") is None
    assert cache.get("x", "fallback") == "fallback"
    assert len(cache) == 0


def test_capacity_one():
    cache = LRUCache(1)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") is None
    assert cache.get("b") == 2


def test_falsy_values_are_stored():
    cache = LRUCache(2)
    cache.put("zero", 0)
    cache.put("none", None)
    assert cache.get("zero", "missing") == 0
    assert cache.get("none", "missing") is None


def test_eviction_order_over_many_operations():
    cache = LRUCache(3)
    for k in "abc":
        cache.put(k, k.upper())
    cache.get("a")                    # order now b, c, a
    cache.put("d", "D")               # evicts b
    cache.get("c")                    # order now a, d, c
    cache.put("e", "E")               # evicts a
    assert [k for k in "abcde" if cache.get(k) is not None] == ["c", "d", "e"]


@pytest.mark.parametrize("capacity", [0, -1])
def test_invalid_capacity_raises(capacity):
    with pytest.raises(ValueError):
        LRUCache(capacity)


def test_does_not_use_ordered_dict_or_functools():
    source = inspect.getsource(module)
    assert "OrderedDict" not in source.split('"""', 2)[-1]
    assert "lru_cache" not in source.split('"""', 2)[-1].replace("drills.lru_cache", "")
    LRUCache(1)   # still has to be implemented to pass
