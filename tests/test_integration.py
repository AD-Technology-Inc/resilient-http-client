import pytest
from resilient_http_client import ResilientHttpClient, FailureStore, ResilienceConfig


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


class FakeHttpExecutor:
    def __init__(self, should_fail=False, status_code=200):
        self.should_fail = should_fail
        self.status_code = status_code
        self.calls = 0

    async def send(self, method, url, **kwargs):
        self.calls += 1
        if self.should_fail:
            raise Exception("upstream_failure")

        return FakeResponse(status_code=self.status_code)

    async def close(self):
        pass


class FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300
        self.data = {"ok": True} if self.is_success else {"error": "failed"}


@pytest.mark.asyncio
async def test_successful_request():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    client = ResilientHttpClient(service="stripe", store=store)

    client.http = FakeHttpExecutor()

    result = await client.request("GET", "https://api.example.com")

    assert result["ok"] is True


@pytest.mark.asyncio
async def test_fallback_on_failure():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    # Set retries to 0 for faster test
    config = ResilienceConfig(max_retries=0)
    client = ResilientHttpClient(service="stripe", store=store, config=config)

    client.http = FakeHttpExecutor(should_fail=True)

    result = await client.request("GET", "https://api.example.com")

    assert result["status"] == "degraded"
    assert result["reason"] == "upstream_failure"


@pytest.mark.asyncio
async def test_circuit_trips_after_retries():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    # threshold=1, retries=1 -> 1 call + 1 retry = 2 failures total
    config = ResilienceConfig(failure_threshold=1, max_retries=1)
    client = ResilientHttpClient(service="stripe", store=store, config=config)

    executor = FakeHttpExecutor(should_fail=True)
    client.http = executor

    await client.request("GET", "https://api.example.com")

    # The circuit should now be open
    assert await client.circuit.is_open() is True
    assert executor.calls == 2 # Initial + 1 retry
