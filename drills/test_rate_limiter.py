import pytest

from drills.rate_limiter import TokenBucket

# Remove this marker once the drill is solved.
pytestmark = pytest.mark.xfail(raises=NotImplementedError, reason="drill not solved yet")


class FakeClock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


def test_starts_full_then_empties(clock):
    bucket = TokenBucket(capacity=2, refill_per_sec=1, clock=clock)
    assert [bucket.allow() for _ in range(3)] == [True, True, False]


def test_refills_continuously(clock):
    bucket = TokenBucket(capacity=2, refill_per_sec=1, clock=clock)
    bucket.allow(2)
    clock.now += 0.5
    assert bucket.allow() is False      # half a token
    clock.now += 0.5
    assert bucket.allow() is True


def test_never_exceeds_capacity(clock):
    bucket = TokenBucket(capacity=3, refill_per_sec=10, clock=clock)
    clock.now += 1000
    assert [bucket.allow() for _ in range(4)] == [True, True, True, False]


def test_failed_allow_spends_nothing(clock):
    bucket = TokenBucket(capacity=3, refill_per_sec=0, clock=clock)
    assert bucket.allow(2) is True
    assert bucket.allow(2) is False     # only 1 left
    assert bucket.allow(1) is True      # the failed call didn't spend it


def test_cost_above_capacity_never_succeeds(clock):
    bucket = TokenBucket(capacity=2, refill_per_sec=1, clock=clock)
    clock.now += 100
    assert bucket.allow(3) is False
    assert bucket.allow(2) is True


def test_zero_refill_rate(clock):
    bucket = TokenBucket(capacity=1, refill_per_sec=0, clock=clock)
    assert bucket.allow() is True
    clock.now += 10_000
    assert bucket.allow() is False


def test_clock_going_backwards_adds_nothing(clock):
    bucket = TokenBucket(capacity=1, refill_per_sec=1, clock=clock)
    bucket.allow()
    clock.now -= 50
    assert bucket.allow() is False
    clock.now += 1                      # 1s after the backwards jump
    assert bucket.allow() is True


def test_fractional_costs(clock):
    bucket = TokenBucket(capacity=1, refill_per_sec=0, clock=clock)
    assert [bucket.allow(0.25) for _ in range(5)] == [True, True, True, True, False]


@pytest.mark.parametrize(
    "capacity, rate",
    [(0, 1), (-1, 1), (1, -0.1)],
)
def test_invalid_construction_raises(clock, capacity, rate):
    with pytest.raises(ValueError):
        TokenBucket(capacity, rate, clock=clock)


@pytest.mark.parametrize("cost", [0, -1])
def test_invalid_cost_raises(clock, cost):
    bucket = TokenBucket(capacity=1, refill_per_sec=1, clock=clock)
    with pytest.raises(ValueError):
        bucket.allow(cost)
