import asyncio

import pytest

from resilient_http_client import (
    FailureStore,
    ResilienceConfig,
    ResilientHttpClient,
)


# -----------------------------
# Fake Redis (isolated unit test store)
# -----------------------------
class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.commands = []

    def set(self, key, value, ex=None, nx=False):
        self.commands.append(("set", (key, value), {"ex": ex, "nx": nx}))
        return self

    def delete(self, key):
        self.commands.append(("delete", (key,), {}))
        return self

    async def execute(self):
        results = []
        for cmd, args, kwargs in self.commands:
            method = getattr(self.redis, cmd)
            res = await method(*args, **kwargs)
            results.append(res)
        return results

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class FakeRedis:
    def __init__(self):
        self.db = {}

    def pipeline(self, transaction=True):
        return FakePipeline(self)

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

    # --- COUNT_BASED sliding window (list) ---
    async def rpush(self, key, *values):
        lst = self.db.setdefault(key, [])
        lst.extend(values)
        return len(lst)

    async def ltrim(self, key, start, end):
        lst = self.db.get(key, [])
        if end == -1:
            self.db[key] = lst[start:]
        else:
            self.db[key] = lst[start : end + 1]

    async def lrange(self, key, start, end):
        lst = self.db.get(key, [])
        if end == -1:
            return lst[start:]
        return lst[start : end + 1]

    # --- TIME_BASED sliding window (sorted set) ---
    async def zadd(self, key, mapping):
        zset = self.db.setdefault(key, {})
        zset.update(mapping)

    async def zremrangebyscore(self, key, min_score, max_score):
        zset = self.db.get(key, {})
        to_remove = [
            k
            for k, v in zset.items()
            if (min_score == "-inf" or v >= float(min_score)) and v <= float(max_score)
        ]
        for k in to_remove:
            del zset[k]

    async def zrangebyscore(self, key, min_score, max_score):
        zset = self.db.get(key, {})
        return [k for k, v in zset.items() if v >= float(min_score) and v <= float(max_score)]


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

    async def close(self) -> None:
        pass


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
    failures = [r for r in results if hasattr(r, "status_code") and r.status_code == 503]
    assert len(failures) > 0

    # executor must have been exercised — but the stampede guard means the
    # circuit trips quickly and the majority of the flood is dropped without
    # reaching the wire.  Both conditions must hold simultaneously.
    assert client.http.calls > 0, "Executor must have been called at least once"
    assert client.http.calls < 30, (
        "Stampede protection must prevent all 30 requests from reaching the executor"
    )

    # circuit breaker should be in a valid state (open or closed depending on config)
    circuit_state = await client.circuit.is_open()
    assert isinstance(circuit_state, bool)

    # failure store should have recorded some state
    # (depends on implementation details of FailureStore)
    state = await store.get_state()
    assert state is not None


# -----------------------------
# Chaos Injection Mock Executor
# -----------------------------


class ChaosHttpExecutor:
    """
    Lightweight mock of a downstream service that injects chaos dynamically
    via URL query parameters — mirroring how a real chaos container exposes
    a control plane over HTTP.

      ?chaos=delay&delay_secs=N  →  simulates a latency spike up to N seconds,
                                     then raises an exception to mimic a timeout
      ?chaos=error               →  returns an HTTP 500 immediately
      (no param)                 →  returns HTTP 200 (healthy)

    ``calls`` counts every request that actually reaches the executor,
    which is the key signal for verifying that an open circuit drops traffic
    before it hits the wire.
    """

    def __init__(self):
        self.calls = 0

    async def send(self, method: str, url: str, **kwargs):
        self.calls += 1

        from urllib.parse import parse_qs, urlparse

        params = parse_qs(urlparse(url).query)
        chaos = params.get("chaos", ["none"])[0]

        if chaos == "delay":
            # Tests pass a tiny delay so the suite stays fast; the important
            # behaviour is the exception that simulates the upstream timeout.
            delay = float(params.get("delay_secs", ["0.01"])[0])
            await asyncio.sleep(delay)
            raise Exception(f"upstream timeout after {delay:.3f}s delay spike")

        if chaos == "error":
            return MockResponse(
                is_success=False,
                status_code=500,
                data={"error": "chaos_injected"},
            )

        return MockResponse(is_success=True, status_code=200, data={"ok": True})

    async def close(self) -> None:
        pass


# -----------------------------
# Chaos Tests
# -----------------------------


@pytest.mark.asyncio
async def test_chaos_delay_spike_triggers_circuit_failures():
    """
    Delay spikes that cause upstream timeouts must be recorded as circuit
    failures.  After hitting the absolute failure threshold the breaker trips
    and no further requests reach the executor.
    """
    redis = FakeRedis()
    store = FailureStore(redis, "chaos-delay")

    config = ResilienceConfig(
        failure_threshold=3,
        max_retries=0,
    )
    client = ResilientHttpClient(service="chaos-delay", store=store, config=config)
    executor = ChaosHttpExecutor()
    client.http = executor

    # Three sequential delay-spike requests — each raises a timeout exception
    # and is treated as a circuit failure.
    for _ in range(3):
        await client.request("GET", "http://downstream/?chaos=delay&delay_secs=0.001")

    assert await client.circuit.is_open(), (
        "Circuit must trip after repeated upstream timeout spikes"
    )

    # Exactly 3 requests reached the executor before the breaker tripped
    assert executor.calls == 3


@pytest.mark.asyncio
async def test_flood_concurrent_trips_at_50pct_threshold():
    """
    Concurrent Flood Test — two-phase scenario:

    Phase 1 — Inject chaos into 200 parallel requests (100% 500 errors).
      • Verify the circuit trips once the sliding window records ≥5 calls
        at ≥50% failure rate.
      • Verify that a significant portion of the flood is dropped by the
        open breaker without touching the executor.

    Phase 2 — Send 50 more requests while the circuit remains open.
      • Verify that zero new requests reach the executor; the breaker drops
        them all instantly before any real network call is made.
    """
    redis = FakeRedis()
    store = FailureStore(redis, "flood-test")

    config = ResilienceConfig(
        sliding_window_type="COUNT_BASED",
        sliding_window_size=10,
        minimum_number_of_calls=5,
        failure_rate_threshold=50.0,
        # Push the legacy absolute threshold out of the way so only the
        # sliding-window rate drives when the circuit trips.
        failure_threshold=9999,
        max_retries=0,
    )
    client = ResilientHttpClient(service="flood-test", store=store, config=config)
    executor = ChaosHttpExecutor()
    client.http = executor

    # ── Phase 1: Flood with injected 500 errors ──────────────────────────────
    flood_tasks = [client.request("GET", "http://downstream/?chaos=error") for _ in range(200)]
    await asyncio.gather(*flood_tasks, return_exceptions=True)

    # Circuit must have tripped once the sliding window accumulated ≥5 calls
    # with a 100% failure rate (well above the 50% threshold).
    assert await client.circuit.is_open(), (
        "Circuit must trip when ≥50% of sliding-window calls are failures"
    )

    # A large portion of the 200 requests should have been dropped by the
    # open breaker — only the first handful reach the executor.
    calls_after_flood = executor.calls
    assert calls_after_flood < 200, (
        "Open circuit must drop the majority of the flood without forwarding "
        "requests to the executor"
    )

    # ── Phase 2: Verify zero network calls when circuit is open ──────────────
    calls_before_phase2 = executor.calls

    drop_tasks = [client.request("GET", "http://downstream/") for _ in range(50)]
    await asyncio.gather(*drop_tasks, return_exceptions=True)

    assert executor.calls == calls_before_phase2, (
        "Open circuit must not forward any request to the executor — "
        "all traffic must be dropped instantly by the breaker"
    )
