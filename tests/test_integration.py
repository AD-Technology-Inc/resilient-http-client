import pytest
from httpx import Response

from resilient_http_client import (
    FailureStore,
    ResilienceConfig,
    ResilientHttpClient,
)


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

    async def rpush(self, key, value):
        if key not in self.db:
            self.db[key] = []
        self.db[key].append(value)
        return len(self.db[key])

    async def ltrim(self, key, start, stop):
        if key in self.db and isinstance(self.db[key], list):
            lst = self.db[key]
            n = len(lst)
            s = start if start >= 0 else max(0, n + start)
            e = stop + 1 if stop >= 0 else max(0, n + stop + 1)
            self.db[key] = lst[s:e]
        return True

    async def lrange(self, key, start, stop):
        if key not in self.db:
            return []
        lst = self.db[key]
        n = len(lst)
        s = start if start >= 0 else max(0, n + start)
        e = stop + 1 if stop >= 0 else (max(0, n + stop + 1) if stop != -1 else n)
        return lst[s:e]

    async def zadd(self, key, mapping):
        if key not in self.db or not isinstance(self.db[key], dict):
            self.db[key] = {}
        for member, score in mapping.items():
            self.db[key][member] = float(score)
        return len(mapping)

    async def zremrangebyscore(self, key, min_val, max_val):
        if key not in self.db or not isinstance(self.db[key], dict):
            return 0
        f_min = -float("inf") if min_val == "-inf" else float(min_val)
        f_max = float("inf") if max_val == "+inf" else float(max_val)

        to_remove = [member for member, score in self.db[key].items() if f_min <= score <= f_max]
        for member in to_remove:
            self.db[key].pop(member)
        return len(to_remove)

    async def zrangebyscore(self, key, min_val, max_val):
        if key not in self.db or not isinstance(self.db[key], dict):
            return []
        f_min = -float("inf") if min_val == "-inf" else float(min_val)
        f_max = float("inf") if max_val == "+inf" else float(max_val)

        items = [
            (member, score) for member, score in self.db[key].items() if f_min <= score <= f_max
        ]
        items.sort(key=lambda x: x[1])
        return [member for member, score in items]


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


class FakeResponse(Response):
    def __init__(self, status_code=200):
        self._data = {"ok": True} if 200 <= status_code < 300 else {"error": "failed"}
        super().__init__(status_code, json=self._data)

    def json(self):
        return self._data


@pytest.mark.asyncio
async def test_successful_request():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    client = ResilientHttpClient(service="stripe", store=store)

    client.http = FakeHttpExecutor()

    result = await client.request("GET", "https://api.example.com")

    assert result.json()["ok"] is True


@pytest.mark.asyncio
async def test_fallback_on_failure():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    # Set retries to 0 for faster test
    config = ResilienceConfig(max_retries=0)
    client = ResilientHttpClient(service="stripe", store=store, config=config)

    client.http = FakeHttpExecutor(should_fail=True)

    result = await client.request("GET", "https://api.example.com")

    assert result.status_code == 503
    assert result.json()["statusCode"] == 503
    assert result.json()["message"] == "upstream_failure"


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
    assert executor.calls == 2  # Initial + 1 retry


@pytest.mark.asyncio
async def test_upstream_500_returns_actual_response_when_no_fallback():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    config = ResilienceConfig(max_retries=0)
    client = ResilientHttpClient(service="stripe", store=store, config=config)

    executor = FakeHttpExecutor(status_code=500)
    client.http = executor

    result = await client.request("GET", "https://api.example.com")

    # Should return the actual HTTP 500 response from the server directly
    assert result.status_code == 500
    assert result.json()["error"] == "failed"


@pytest.mark.asyncio
async def test_custom_fallback_receives_response_object():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    config = ResilienceConfig(max_retries=0)
    client = ResilientHttpClient(service="stripe", store=store, config=config)

    executor = FakeHttpExecutor(status_code=500)
    client.http = executor

    received_response = None

    def my_fallback(error):
        nonlocal received_response
        received_response = error
        resp = FakeResponse(status_code=503)
        resp._data = {"custom_fallback": True}
        return resp

    client.fallback.register(my_fallback)

    result = await client.request("GET", "https://api.example.com")

    assert result.status_code == 503
    assert result.json()["custom_fallback"] is True
    assert received_response is not None
    assert getattr(received_response, "status_code", None) == 500


@pytest.mark.asyncio
async def test_custom_fallback_can_return_any_type():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    config = ResilienceConfig(max_retries=0)
    client = ResilientHttpClient(service="stripe", store=store, config=config)

    executor = FakeHttpExecutor(status_code=500)
    client.http = executor

    # Registers a fallback that returns a plain dictionary instead of a response
    client.fallback.register(lambda error: {"not_a_response": True})

    result = await client.request("GET", "https://api.example.com")
    assert result == {"not_a_response": True}


@pytest.mark.asyncio
async def test_circuit_open_returns_cb_open_code():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    config = ResilienceConfig(max_retries=0)
    client = ResilientHttpClient(service="stripe", store=store, config=config)

    # Force the circuit open
    await client.circuit.trip_open()

    result = await client.request("GET", "https://api.example.com")

    assert result.status_code == 503
    assert result.json()["statusCode"] == 503
    assert result.json()["message"] == "circuit_open"


@pytest.mark.asyncio
async def test_client_validation_error_422_ignores_circuit_failure_and_returns_actual_response():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    config = ResilienceConfig(max_retries=0)
    client = ResilientHttpClient(service="stripe", store=store, config=config)

    executor = FakeHttpExecutor(status_code=422)
    client.http = executor

    result = await client.request("GET", "https://api.example.com")

    # Should return the actual HTTP 422 response directly
    assert result.status_code == 422
    assert result.json()["error"] == "failed"

    # Circuit breaker should not record failure or trip
    assert await store.get_failures() == 0
    assert await client.circuit.is_open() is False


@pytest.mark.asyncio
async def test_client_retry_on_429_but_no_circuit_failure():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    config = ResilienceConfig(max_retries=1)
    client = ResilientHttpClient(service="stripe", store=store, config=config)

    executor = FakeHttpExecutor(status_code=429)
    client.http = executor

    result = await client.request("GET", "https://api.example.com")

    # Should retry (1 initial + 1 retry = 2 calls)
    assert executor.calls == 2
    # Should return the actual HTTP 429 response directly after retries
    assert result.status_code == 429

    # Circuit breaker should not record failure
    assert await store.get_failures() == 0


@pytest.mark.asyncio
async def test_client_custom_circuit_failure_and_retry_status_codes():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    config = ResilienceConfig(
        max_retries=1,
        retry_status_codes={418},
        circuit_failure_status_codes={418},
    )
    client = ResilientHttpClient(service="stripe", store=store, config=config)

    # 1. 418 Teapot should retry and record circuit failure
    executor_418 = FakeHttpExecutor(status_code=418)
    client.http = executor_418
    result = await client.request("GET", "https://api.example.com")
    assert executor_418.calls == 2
    assert result.status_code == 418
    assert await store.get_failures() == 2  # 2 failures recorded

    await store.reset_failures()

    # 2. 500 error should NOT retry and NOT record failure (since it's not in the custom sets)
    executor_500 = FakeHttpExecutor(status_code=500)
    client.http = executor_500
    result = await client.request("GET", "https://api.example.com")
    assert executor_500.calls == 1  # No retry
    assert result.status_code == 500
    assert await store.get_failures() == 0  # 0 failures recorded


@pytest.mark.asyncio
async def test_client_count_based_sliding_window_tripping():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    config = ResilienceConfig(
        max_retries=0,
        sliding_window_type="COUNT_BASED",
        sliding_window_size=4,
        minimum_number_of_calls=4,
        failure_rate_threshold=50.0,
    )
    client = ResilientHttpClient(service="stripe", store=store, config=config)

    # 1. 1st failure (500) -> total calls = 1 < 4 (min calls) -> not tripped
    client.http = FakeHttpExecutor(status_code=500)
    res = await client.request("GET", "https://api.example.com")
    assert res.status_code == 500
    assert await client.circuit.is_open() is False

    # 2. 2nd and 3rd calls (200 successes) -> total calls = 3 < 4 -> not tripped
    client.http = FakeHttpExecutor(status_code=200)
    await client.request("GET", "https://api.example.com")
    await client.request("GET", "https://api.example.com")
    assert await client.circuit.is_open() is False

    # 3. 4th call (500 failure) -> total calls = 4, failures = 2/4 = 50% -> trips!
    client.http = FakeHttpExecutor(status_code=500)
    res = await client.request("GET", "https://api.example.com")
    assert res.status_code == 500
    assert await client.circuit.is_open() is True

    # 4. 5th call should be blocked and return circuit_open fallback
    client.http = FakeHttpExecutor(status_code=200)
    res = await client.request("GET", "https://api.example.com")
    assert res.status_code == 503
    assert res.json()["message"] == "circuit_open"


@pytest.mark.asyncio
async def test_client_time_based_sliding_window_tripping():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    config = ResilienceConfig(
        max_retries=0,
        sliding_window_type="TIME_BASED",
        sliding_window_size=5,
        minimum_number_of_calls=3,
        failure_rate_threshold=50.0,
    )
    client = ResilientHttpClient(service="stripe", store=store, config=config)

    # 1. Success call (200)
    client.http = FakeHttpExecutor(status_code=200)
    await client.request("GET", "https://api.example.com")
    assert await client.circuit.is_open() is False

    # 2. Two failures (500) -> total calls = 3, failures = 2/3 = 66% -> trips!
    client.http = FakeHttpExecutor(status_code=500)
    await client.request("GET", "https://api.example.com")
    await client.request("GET", "https://api.example.com")
    assert await client.circuit.is_open() is True

    # 3. Call blocked
    client.http = FakeHttpExecutor(status_code=200)
    res = await client.request("GET", "https://api.example.com")
    assert res.status_code == 503
    assert res.json()["message"] == "circuit_open"


@pytest.mark.asyncio
async def test_per_request_max_retries_and_fallback_override():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    # Base config: 0 retries
    config = ResilienceConfig(max_retries=0)
    client = ResilientHttpClient(service="stripe", store=store, config=config)

    executor = FakeHttpExecutor(status_code=500)
    client.http = executor

    # Per-request fallback override directly in request()
    result = await client.request(
        "GET",
        "https://api.example.com",
        fallback=lambda err: {"per_request_fallback": True, "err": str(err)},
    )
    assert result["per_request_fallback"] is True
    assert "500" in str(result["err"])

    # Per-request max_retries override directly in request() (overriding 0 to 2)
    executor.calls = 0
    await client.request("GET", "https://api.example.com", max_retries=2)
    assert executor.calls == 3  # Initial + 2 retries


@pytest.mark.asyncio
async def test_per_request_timeout_override():
    redis = FakeRedis()
    store = FailureStore(redis, "stripe")
    config = ResilienceConfig(timeout=10.0)
    client = ResilientHttpClient(service="stripe", store=store, config=config)

    captured_kwargs = {}

    class TimeoutCaptureExecutor:
        async def send(self, method, url, **kwargs):
            nonlocal captured_kwargs
            captured_kwargs = kwargs
            return FakeResponse(status_code=200)

        async def close(self):
            pass

    client.http = TimeoutCaptureExecutor()

    # Per-request timeout override
    await client.request("GET", "https://api.example.com", timeout=2.5)
    assert captured_kwargs.get("timeout") == 2.5
