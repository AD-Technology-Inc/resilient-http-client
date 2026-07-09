import pytest
from resilient_http_client import CircuitBreaker, ResilienceConfig, CircuitState


# -------------------------
# FIXTURES
# -------------------------

class FakeStore:
    def __init__(self, service="test-service"):
        self.service = service
        self.state = CircuitState.CLOSED.value
        self.failures = 0
        self.ttl = None
        self.half_open_calls = 0
        self.half_open_successes = 0
        self.expired = False

    async def get_state(self):
        return self.state

    async def set_state(self, state, ttl=None):
        self.state = state
        self.ttl = ttl

    async def increment_failures(self, window=60):
        self.failures += 1

    async def get_failures(self):
        return self.failures

    async def reset_failures(self):
        self.failures = 0

    async def increment_half_open_calls(self):
        self.half_open_calls += 1

    async def get_half_open_calls(self):
        return self.half_open_calls

    async def increment_half_open_success(self):
        self.half_open_successes += 1

    async def get_half_open_successes(self):
        return self.half_open_successes

    async def reset_half_open(self):
        self.half_open_calls = 0
        self.half_open_successes = 0

    async def is_open_expired(self):
        return self.expired


@pytest.fixture
def store():
    return FakeStore()


@pytest.fixture
def breaker(store):
    return CircuitBreaker(store)


@pytest.fixture
def breaker_with_threshold(store):
    config = ResilienceConfig(failure_threshold=2)
    return CircuitBreaker(store, config=config)


# -------------------------
# TESTS - FAILURE TRACKING
# -------------------------

@pytest.mark.asyncio
async def test_failure_tracking(breaker, store):
    await breaker.on_failure()
    assert await store.get_failures() == 1


@pytest.mark.asyncio
async def test_success_resets_failures_and_state(breaker_with_threshold, store):
    await breaker_with_threshold.on_failure()
    # threshold is 2, so 1 failure doesn't trip it yet
    await breaker_with_threshold.on_success()

    assert store.failures == 0
    assert store.state == CircuitState.CLOSED.value


# -------------------------
# THRESHOLD BEHAVIOR
# -------------------------

@pytest.mark.asyncio
async def test_does_not_open_before_threshold(breaker_with_threshold, store):
    await breaker_with_threshold.on_failure()
    # maybe_open is called inside on_failure now

    assert await breaker_with_threshold.is_open() is False
    assert store.state == CircuitState.CLOSED.value


@pytest.mark.asyncio
async def test_opens_at_threshold(breaker_with_threshold, store):
    await breaker_with_threshold.on_failure()
    assert await breaker_with_threshold.is_open() is False

    await breaker_with_threshold.on_failure()
    assert await breaker_with_threshold.is_open() is True


# -------------------------
# OPEN STATE
# -------------------------

@pytest.mark.asyncio
async def test_remains_open_after_trigger(breaker_with_threshold):
    await breaker_with_threshold.on_failure()
    await breaker_with_threshold.on_failure()

    assert await breaker_with_threshold.is_open() is True

    await breaker_with_threshold.on_failure()
    assert await breaker_with_threshold.is_open() is True


@pytest.mark.asyncio
async def test_open_prevents_requests_if_not_expired(store, breaker):
    store.state = CircuitState.OPEN.value
    store.expired = False
    assert await breaker.allow_request() is False


@pytest.mark.asyncio
async def test_open_allows_requests_if_expired(store, breaker):
    store.state = CircuitState.OPEN.value
    store.expired = True
    assert await breaker.allow_request() is True
    assert await breaker.is_half_open() is True


@pytest.mark.asyncio
async def test_open_sets_ttl(store, breaker):
    await store.set_state(CircuitState.OPEN.value, ttl=10)

    assert store.state == CircuitState.OPEN.value
    assert store.ttl == 10


# -------------------------
# HALF-OPEN STATE
# -------------------------

@pytest.mark.asyncio
async def test_transition_to_half_open(store, breaker):
    store.state = CircuitState.OPEN.value
    await breaker.transition_to_half_open()

    assert await breaker.is_half_open()
    assert store.state == CircuitState.HALF_OPEN.value


@pytest.mark.asyncio
async def test_half_open_allows_limited_requests(store, breaker):
    store.state = CircuitState.HALF_OPEN.value
    breaker.config.half_open_max_calls = 2

    assert await breaker.allow_request() is True
    assert await breaker.allow_request() is True
    assert await breaker.allow_request() is False


@pytest.mark.asyncio
async def test_half_open_success_closes_circuit(store, breaker):
    store.state = CircuitState.HALF_OPEN.value
    breaker.config.half_open_successes_needed = 1

    await breaker.on_success()

    assert store.state == CircuitState.CLOSED.value
    assert store.failures == 0


@pytest.mark.asyncio
async def test_half_open_failure_reopens_circuit(store, breaker):
    store.state = CircuitState.HALF_OPEN.value

    await breaker.on_failure()

    assert await breaker.is_open()
    assert store.state == CircuitState.OPEN.value
