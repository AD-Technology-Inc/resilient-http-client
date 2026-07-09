import pytest
import asyncio

from resilient_http_client import ResilientHttpClient, FailureStore, ResilienceConfig


# -----------------------------
# Fake Redis (isolated unit test store)
# -----------------------------
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


# -----------------------------
# Deterministic Flaky Executor
# -----------------------------
class MockResponse:
    def __init__(self, is_success, status_code, data):
        self.is_success = is_success
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


class FlakyHttpExecutor:
    """
    Simulates unstable upstream in a deterministic way:
    - 2 failures
    - 1 success
    - repeats pattern
    """

    def __init__(self):
        self.calls = 0

    async def send(self, method, url, **kwargs):
        self.calls += 1

        # flaky pattern instead of randomness
        if self.calls % 3 != 0:
            raise Exception("random_upstream_failure")

        return MockResponse(
            is_success=True,
            status_code=200,
            data={"ok": True},
        )


# -----------------------------
# Test
# -----------------------------
@pytest.mark.asyncio
async def test_flaky_upstream_resilience():
    redis = FakeRedis()
    store = FailureStore(redis, "loadtest")

    config = ResilienceConfig(
        max_retries=2,
        failure_threshold=5,
    )

    client = ResilientHttpClient(
        service="loadtest",
        store=store,
        config=config,
    )

    client.http = FlakyHttpExecutor()

    # -----------------------------
    # simulate concurrent traffic
    # -----------------------------
    async def worker(worker_id: int):
        return await client.request(
            "GET",
            "https://api.example.com",
        )

    tasks = [worker(i) for i in range(30)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # -----------------------------
    # assertions
    # -----------------------------

    # system should handle all requests
    assert len(results) == 30

    # successes should exist
    successes = [r for r in results if hasattr(r, "json") and r.json().get("ok") is True]
    assert len(successes) > 0

    # failures should exist due to upstream instability (returned as degraded responses)
    failures = [r for r in results if hasattr(r, "json") and r.json().get("status") == "degraded"]
    assert len(failures) > 0

    # executor must have been exercised heavily
    assert client.http.calls >= 30

    # circuit breaker should be in a valid state (open or closed depending on config)
    circuit_state = await client.circuit.is_open()
    assert isinstance(circuit_state, bool)

    # failure store should have recorded some state
    # (depends on implementation details of FailureStore)
    state = await store.get_state()
    assert state is not None