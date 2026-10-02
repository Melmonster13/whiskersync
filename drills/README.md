# Drills

Timed practice problems. Each file is a **stub**: the docstring has the problem, examples, constraints, a target time and the expected complexity, and the function raises `NotImplementedError`. Every test file has a full table of cases, already checked against a reference solution that isn't committed.

## Workflow

1. Start a timer, open the drill, and implement it from the docstring alone.
2. Run its tests:
   ```bash
   .venv/bin/pytest drills/test_merge_intervals.py
   ```
   While it's a stub, the tests show as `xfailed`. A wrong answer shows as a normal **failure**, because the marker only tolerates `NotImplementedError`.
3. Once it passes, delete the `pytestmark = pytest.mark.xfail(...)` line at the top of the test file, so CI holds it to the full suite from then on.

## Drills

| # | Drill | Pattern | Target | Ties to |
|---|---|---|---|---|
| 1 | [merge_intervals](merge_intervals.py) | sort + sweep | 15 min | m1 speaker segments |
| 2 | [lower_bound](lower_bound.py) | binary search, no `bisect` | 15 min | m1 active-word lookup |
| 3 | [task_order](task_order.py) | topological sort (Kahn) with a heap | 25 min | m2 pipeline stages |
| 4 | [lca](lca.py) | parent-pointer walk + set | 15 min | m3 resource tree |
| 5 | [lru_cache](lru_cache.py) | dict + doubly linked list | 25 min | caching API responses |
| 6 | [rate_limiter](rate_limiter.py) | token bucket, injected clock | 20 min | rate-limiting agent tool calls |
| 7 | [sliding_percentile](sliding_percentile.py) | sorted window (stretch: O(log w)) | 25 min | m4 live p95 latency |
| 8 | [top_k](top_k.py) | counting + heap or bucket sort | 15 min | most frequent errors in the audit log |

## Notes

- `lower_bound` and `lru_cache` have tests that fail if you use `bisect`, or `OrderedDict` / `functools.lru_cache`.
- `sliding_percentile` is checked against `harness/evals/metrics.percentile`, so it uses the same nearest-rank definition as the eval reports.
- `rate_limiter` takes an injected clock, so its tests never sleep.
