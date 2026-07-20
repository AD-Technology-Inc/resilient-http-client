# 🧪 Testing Strategy & Verification

The testing suite guarantees 100% branch coverage across circuit breaker state transitions, retry policies, fallback execution, and distributed failure stores.

---

## 🔬 Test Suite Layout

```text
tests/
├── test_circuit_breaker.py   # State machine, thresholds, probe locks
├── test_failure_store.py     # Redis state persistence, counters, sliding window
├── test_fallback.py          # Sync and async fallback handlers
├── test_flaky_resilience.py   # Chaos testing: delay spikes, failure rate floods
├── test_integration.py       # End-to-end client integration & per-request overrides
├── test_protocols.py         # Type checking & Protocol validation
└── test_retry_policy.py      # Exponential backoff calculation & delay caps
```

---

## 🏃 Running Tests

```bash
# Run full pytest suite
uv run pytest -v

# Run with coverage report
uv run pytest --cov=src/resilient_http_client
```

---

## 🐳 Docker Chaos Harness

The repository includes a containerized Chaos Harness (`chaos_mock` + `chaos_test_runner` + `redis`):

```bash
# Run containerized chaos harness
docker compose up --build --exit-code-from chaos_test_runner
```

This harness injects 500 errors and network delay spikes under concurrent load to verify that the circuit breaker trips exactly on threshold and drops subsequent requests without latency degradation.
