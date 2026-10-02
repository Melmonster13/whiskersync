"""Drill 6 — Token-bucket rate limiter.                         Target: 20 min

A bucket holds up to `capacity` tokens and refills continuously at `refill_per_sec`.
allow(cost) spends `cost` tokens and returns True if there are enough; otherwise it
returns False and spends nothing. The bucket starts full.

    clock = FakeClock()            # returns clock.now
    bucket = TokenBucket(capacity=2, refill_per_sec=1, clock=clock)
    bucket.allow()  ->  True
    bucket.allow()  ->  True
    bucket.allow()  ->  False      # empty
    clock.now += 0.5
    bucket.allow()  ->  False      # only half a token
    clock.now += 0.5
    bucket.allow()  ->  True

Constraints:
- Tokens never exceed capacity, however long the bucket sits idle.
- The clock is injected (a zero-argument callable returning seconds); use it, not time.
- If the clock goes backwards, add no tokens and measure future refills from the new reading.
- capacity <= 0, refill_per_sec < 0, or cost <= 0 raise ValueError.
- cost > capacity can never succeed: return False.

Expected: O(1) per call, no background threads.
"""

import time


class TokenBucket:
    def __init__(self, capacity: float, refill_per_sec: float, clock=time.monotonic):
        raise NotImplementedError("solve me")

    def allow(self, cost: float = 1) -> bool:
        raise NotImplementedError("solve me")
