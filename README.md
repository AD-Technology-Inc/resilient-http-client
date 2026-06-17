# 🛡️ Resilient HTTP Client

A production-grade, asynchronous HTTP client for Python engineered to tolerate downstream service outages, network instability, and latency spikes. It implements proven resilience patterns including **Circuit Breakers**, **Retry Policies**, **Fallback Mechanisms**, and a **Distributed Failure Store** to enable reliable service-to-service communication.

Built on top of `httpx`, the library is designed for modern distributed systems where resilience is a first-class requirement.

---

## 🚀 Features

* **Circuit Breaker Pattern** — Prevents cascading failures using a strict state machine (`CLOSED`, `OPEN`, `HALF-OPEN`).
* **Distributed Failure Store** — Share circuit state and failure metrics across workers and service instances.
* **Automatic Retries** — Configurable retry budgets with exponential backoff for transient failures.
* **Graceful Fallbacks** — Return degraded responses or execute alternative logic instead of surfacing raw exceptions.
* **Fully Asynchronous** — Built on `httpx` for high-concurrency, non-blocking I/O.
* **Pluggable Components** — Storage and resilience behavior can be customized to fit different deployment environments.
* **Production Ready** — Suitable for microservices, containerized workloads, and distributed deployments.

---

## 📐 System Architecture

The following diagram illustrates how the components of `resilient-http-client` coordinate request delivery, state checking, retries, and fallback execution.

```mermaid
flowchart TD
    classDef main fill:#1E88E5,stroke:#1565C0,stroke-width:2px,color:#fff;
    classDef support fill:#43A047,stroke:#2E7D32,stroke-width:2px,color:#fff;
    classDef store fill:#E53935,stroke:#C62828,stroke-width:2px,color:#fff;

    Client["ResilientHttpClient"]:::main
    CB["CircuitBreaker"]:::main
    Store["FailureStore"]:::store
    Retry["RetryPolicy"]:::support
    Fallback["FallbackHandler"]:::support
    Executor["HttpExecutor (httpx)"]:::support

    Client -->|1. Check state / record metrics| CB
    Client -->|2. Manage retry attempts| Retry
    Client -->|3. Fallback on final error| Fallback
    Client -->|4. Dispatch requests| Executor
    CB -->|Query & persist state / counters| Store
```

---

## 🔄 Circuit Breaker State Machine

The client implements a fully compliant circuit breaker state machine with lazy cooldown transitions and probe request gating.

```mermaid
stateDiagram-v2
    [*] --> Closed : Initial State

    Closed --> Open : failures >= threshold
    Closed --> Closed : success

    Open --> HalfOpen : cooldown expired
    Open --> Open : block requests

    HalfOpen --> Closed : success >= successes_needed
    HalfOpen --> Open : any failure
```

### State Behavior

#### CLOSED

Requests flow normally.

* Successful requests reset failure counters.
* Consecutive failures are tracked.
* Reaching the configured threshold transitions the circuit to **OPEN**.

#### OPEN

Requests fail immediately without contacting the downstream service.

* Prevents latency amplification and resource exhaustion.
* Remains open for the configured cooldown period.
* Automatically transitions to **HALF-OPEN** after cooldown expires.

#### HALF-OPEN

Allows a limited number of probe requests.

* Successful probes close the circuit.
* Any failed probe immediately reopens the circuit.
* Prevents unstable services from causing repeated outages.

---

## ⚡ Quick Start

```python
import asyncio
import redis.asyncio as redis

from resilient_http_client import (
    FailureStore,
    ResilientHttpClient,
)

async def main():
    # Example using Redis-backed storage
    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True,
    )

    store = FailureStore(
        redis=redis_client,
        service="stripe_payment",
    )

    async with ResilientHttpClient(
        service="stripe_payment",
        store=store,
    ) as client:

        response = await client.request(
            method="POST",
            url="https://api.stripe.com/v1/charges",
            json={
                "amount": 2000,
                "currency": "usd",
            },
        )

        print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## ⚙️ Configuration

Customize resilience behavior through `ResilienceConfig`.

```python
from resilient_http_client import ResilienceConfig

config = ResilienceConfig(
    failure_threshold=5,
    cooldown=30,
    max_retries=3,
    timeout=5.0,
    half_open_max_calls=1,
    half_open_successes_needed=1,
)

client = ResilientHttpClient(
    service="my-api",
    store=store,
    config=config,
)
```

### Configuration Reference

| Parameter                    | Type    | Default | Description                                             |
| ---------------------------- | ------- | ------- | ------------------------------------------------------- |
| `failure_threshold`          | `int`   | `5`     | Consecutive failures required to open the circuit       |
| `cooldown`                   | `int`   | `30`    | Seconds before an open circuit transitions to half-open |
| `max_retries`                | `int`   | `3`     | Number of retry attempts before failure                 |
| `timeout`                    | `float` | `5.0`   | Request timeout in seconds                              |
| `half_open_max_calls`        | `int`   | `1`     | Maximum probe requests allowed while half-open          |
| `half_open_successes_needed` | `int`   | `1`     | Successful probes required to close the circuit         |

---

## 🧩 Components

### Circuit Breaker

Prevents repeated requests to unhealthy downstream services.

States:

* **Closed** — Requests flow normally.
* **Open** — Requests fail immediately.
* **Half-Open** — Limited recovery probes are allowed.

### Retry Policy

Automatically retries transient failures using configurable exponential backoff.

Typical retry conditions include:

* HTTP 5xx responses
* Connection failures
* Network timeouts

### Fallback Handler

Fallbacks are executed when:

* The circuit is open.
* Retry attempts are exhausted.
* A non-retryable failure occurs.

### Failure Store

Persists resilience state used by the circuit breaker.

Responsibilities include:

* Failure counters
* Circuit state
* Cooldown timestamps
* Cross-worker coordination

The library includes a Redis-backed implementation and can be extended with custom storage backends.

---

## 🛠️ Project Structure

```text
src/
├── client.py
├── circuit_breaker.py
├── config.py
├── failure_store.py
├── fallback.py
├── retry.py
├── types.py
└── executor.py

tests/
├── test_circuit_breaker.py
├── test_retry.py
├── test_failure_store.py
└── ...
```

### Module Overview

* 🛰️ `client.py` — Main orchestration layer.
* 🔌 `circuit_breaker.py` — Circuit breaker state machine.
* 🗄️ `failure_store.py` — Distributed state management.
* 🔁 `retry.py` — Retry policy implementation.
* 🎭 `fallback.py` — Fallback registration and execution.
* ⚙️ `config.py` — Configuration definitions.
* 📘 `types.py` — Shared enums and type definitions.

---

## 🧪 Running the Tests

Run the full test suite:

```bash
PYTHONPATH=. uv run pytest tests
```

Or:

```bash
pytest
```

### Coverage Includes

* Failure tracking
* Circuit opening thresholds
* Cooldown transitions
* Half-open probe gating
* Recovery behavior
* Retry policies
* Distributed state persistence
* Fallback execution paths

---

## 📚 Examples

The `examples/` directory contains complete demonstrations and integrations.

### How to run examples

1. Start Redis:
   ```bash
   docker compose up -d
   ```

2. Run the example:
   ```bash
   PYTHONPATH=. uv run python examples/slack_example.py
   ```

Available examples:
* `fastapi_integration.py`
* `simulate_outage.py`
* `slack_example.py`
* `stripe_example.py`

---

## 🎯 Use Cases

* Service-to-service communication
* Third-party API integrations
* Payment gateways
* Authentication providers
* Event-driven systems
* Containerized applications
* Kubernetes deployments
* Any environment where downstream dependencies may become unavailable

---

## License

MIT
