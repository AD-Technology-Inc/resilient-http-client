import pytest
from src.failure_store import FailureStore
from src.types import CircuitState


class FakeRedis:
    def __init__(self):
        self.db = {}

    async def get(self, key):
        return self.db.get(key)

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.db:
            return False
        self.db[key] = value
        return True

    async def incr(self, key):
        self.db[key] = int(self.db.get(key, 0)) + 1
        return self.db[key]

    async def expire(self, key, ttl, nx=False):
        pass

    async def delete(self, key):
        self.db.pop(key, None)


@pytest.mark.asyncio
async def test_failure_counter():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")

    await store.increment_failures()
    await store.increment_failures()

    assert await store.get_failures() == 2


@pytest.mark.asyncio
async def test_reset_failures():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")

    await store.increment_failures()
    await store.reset_failures()

    assert await store.get_failures() == 0


@pytest.mark.asyncio
async def test_state_storage():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")

    await store.set_state(CircuitState.OPEN.value, ttl=30)

    assert await store.get_state() == CircuitState.OPEN.value
    # cooldown key should be set
    assert await redis.get("resilience:stripe:open_cooldown") == "1"


@pytest.mark.asyncio
async def test_is_open_expired():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")

    # Not open
    await store.set_state(CircuitState.CLOSED.value)
    assert await store.is_open_expired() is False

    # Open with cooldown active
    await store.set_state(CircuitState.OPEN.value, ttl=30)
    assert await store.is_open_expired() is False

    # Open with cooldown expired (key deleted)
    await redis.delete("resilience:stripe:open_cooldown")
    assert await store.is_open_expired() is True


@pytest.mark.asyncio
async def test_half_open_metrics():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")

    await store.increment_half_open_calls()
    await store.increment_half_open_success()

    assert await store.get_half_open_calls() == 1
    assert await store.get_half_open_successes() == 1

    await store.reset_half_open()
    assert await store.get_half_open_calls() == 0
    assert await store.get_half_open_successes() == 0
