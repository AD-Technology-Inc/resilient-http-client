# 🛡️ Resilient HTTP Client

<p align="center">
  <a href="https://github.com/AD-Technology-Inc/resilient-http-client/actions/workflows/ci.yml">
    <img src="https://github.com/AD-Technology-Inc/resilient-http-client/actions/workflows/ci.yml/badge.svg" alt="CI Status">
  </a>
  <a href="https://pypi.org/project/ad-tech-inc-resilient-http/">
    <img src="https://img.shields.io/pypi/v/ad-tech-inc-resilient-http.svg" alt="PyPI Version">
  </a>
  <a href="https://pypi.org/project/ad-tech-inc-resilient-http/">
    <img src="https://img.shields.io/pypi/pyversions/ad-tech-inc-resilient-http.svg" alt="Supported Python Versions">
  </a>
  <a href="https://github.com/AD-Technology-Inc/resilient-http-client/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/AD-Technology-Inc/resilient-http-client.svg" alt="License">
  </a>
  <a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/badge/package%20manager-uv-purple.svg" alt="Uv">
  </a>
</p>

Asynchronous HTTP client for Python engineered to tolerate downstream service outages, network instability, and latency spikes. It implements proven resilience patterns including **Circuit Breakers**, **Retry Policies**, **Fallback Mechanisms**, and a **Distributed Failure Store** to enable reliable service-to-service communication.

Built on top of `httpx`, the library is designed for modern distributed systems where resilience is a first-class requirement.

---

## 🚀 Features

* **Circuit Breaker Pattern** — Prevents cascading failures using a strict state machine (`CLOSED`, `OPEN`, `HALF-OPEN`) with advanced **Count-based** and **Time-based** sliding windows.
* **Rate-Based Tripping** — Trip the circuit breaker based on failure percentage thresholds (similar to Resilience4j).
* **Configurable Failure/Retry Codes** — Full control over which HTTP status codes trigger retries (e.g. 429) vs. circuit failures (e.g. 500, ignoring validation errors like 422).
* **Distributed Failure Store** — Share circuit state and failure metrics across workers and service instances.
* **Automatic Retries** — Configurable retry budgets with exponential backoff for transient failures.
* **Graceful Fallbacks** — Return degraded responses or execute alternative logic instead of surfacing raw exceptions.
* **Fully Asynchronous** — Built on `httpx` for high-concurrency, non-blocking I/O.
* **Pluggable Components** — Storage and resilience behavior can be customized to fit different deployment environments.
* **Production Ready** — Suitable for microservices, containerized workloads, and distributed deployments.


---

## 📐 System Architecture

The coordination of request delivery, state checking, retries, and fallback execution is modeled in our system architecture.

> 📊 **[View System Architecture Diagram](docs/diagrams/architecture.mmd)**
> 🕒 **[View Request Sequence Flow Diagram](docs/diagrams/sequence_flow.mmd)**

---

## 🔄 Circuit Breaker State Machine

The client implements a fully compliant circuit breaker state machine with lazy cooldown transitions and probe request gating.

> 🔄 **[View Circuit Breaker State Machine Diagram](docs/diagrams/state_machine.mmd)**

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

## ⚙️ Installation

Install the package via `pip` or your favorite package manager:

```bash
pip install ad-tech-inc-resilient-http
```

Or using `uv`:

```bash
uv add ad-tech-inc-resilient-http
```

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

        # The request returns a raw httpx.Response object on success
        if hasattr(response, "json"):
            print("Status:", response.status_code)
            print("Response Data:", response.json())
        else:
            # Fallback values returned as a dict
            print("Fallback Response:", response)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## ⚙️ Configuration

Customize resilience behavior through `ResilienceConfig`.

```python
from resilient_http_client import ResilienceConfig

config = ResilienceConfig(
    cooldown=30,
    max_retries=3,
    timeout=5.0,
    half_open_max_calls=3,
    half_open_successes_needed=2,
    # Sliding window configuration
    sliding_window_type="COUNT_BASED",        # "COUNT_BASED" or "TIME_BASED"
    sliding_window_size=10,                   # Evaluate last 10 requests or last 10 seconds
    minimum_number_of_calls=5,                # Do not trip until at least 5 calls are made
    failure_rate_threshold=50.0,              # Trip open if >= 50.0% of requests in window fail
    # Status codes customization
    retry_status_codes={408, 429, 500, 503},  # Status codes that trigger retries
    circuit_failure_status_codes={500, 503},  # Status codes that count as circuit breaker failures
    # Retry delay customization
    retry_backoff_base=0.1,                   # Starting backoff delay in seconds
    retry_max_delay=10.0,                     # Maximum backoff delay cap in seconds
)

client = ResilientHttpClient(
    service="my-api",
    store=store,
    config=config,
)
```

### Configuration Reference

| Parameter                      | Type       | Default | Description                                                                                |
| ------------------------------ | ---------- | ------- | ------------------------------------------------------------------------------------------ |
| `cooldown`                     | `int`      | `30`    | Seconds before an open circuit transitions to half-open                                    |
| `max_retries`                  | `int`      | `3`     | Number of retry attempts before failure                                                    |
| `timeout`                      | `float`    | `5.0`   | Request timeout in seconds                                                                 |
| `half_open_max_calls`          | `int`      | `1`     | Maximum probe requests allowed while half-open                                            |
| `half_open_successes_needed`   | `int`      | `1`     | Successful probes required to close the circuit                                           |
| `sliding_window_type`          | `str`      | `"COUNT_BASED"` | Type of sliding window: `"COUNT_BASED"` or `"TIME_BASED"`                          |
| `sliding_window_size`          | `int`      | `10`    | Size of sliding window: number of calls (count-based) or number of seconds (time-based)    |
| `minimum_number_of_calls`      | `int`      | `5`     | Minimum calls recorded in the window before failure rate percentage is evaluated           |
| `failure_rate_threshold`       | `float`    | `50.0`  | Percentage of failures in the window required to trip the circuit open                    |
| `retry_status_codes`           | `Set[int]` | `{408, 429, 500, 502, 503, 504}` | Set of HTTP status codes that trigger a retry attempt                           |
| `circuit_failure_status_codes` | `Set[int]` | `{500, 502, 503, 504}`           | Set of HTTP status codes that count as circuit breaker failures                   |
| `retry_backoff_base`           | `float`    | `0.1`   | Starting backoff base delay in seconds for exponential backoff                             |
| `retry_max_delay`              | `float`    | `10.0`  | Maximum delay cap in seconds for retry attempts                                            |
| `failure_threshold`            | `int`      | `5`     | (Deprecated/Fallback) Absolute consecutive failures required to open the circuit          |


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
└── resilient_http_client/
    ├── __init__.py
    ├── circuit_breaker.py
    ├── client.py
    ├── config.py
    ├── failure_store.py
    ├── fallback.py
    ├── http.py
    ├── protocols/
    │   ├── __init__.py
    │   ├── failure_store_protocol.py
    │   ├── fallback_handler_protocol.py
    │   ├── http_executor_protocol.py
    │   └── retry_policy_protocol.py
    ├── retry.py
    └── types.py

tests/
├── test_circuit_breaker.py
├── test_failure_store.py
├── test_fallback.py
├── test_flaky_resilience.py
├── test_integration.py
├── test_protocols.py
└── test_retry_policy.py
```

### Module Overview

* 🛰️ `client.py` — Main orchestration layer.
* 🔌 `circuit_breaker.py` — Circuit breaker state machine.
* 🗄️ `failure_store.py` — Distributed state management.
* 🔁 `retry.py` — Retry policy implementation.
* 🎭 `fallback.py` — Fallback registration and execution.
* ⚙️ `config.py` — Configuration definitions.
* 📘 `types.py` — Shared enums and type definitions.
* 🌐 `http.py` — HTTP request execution layer.

---

## 🧪 Running the Tests

Run the full test suite:

```bash
uv run pytest
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
* `fastapi_simple.py`
* `fastapi_custom.py`
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
