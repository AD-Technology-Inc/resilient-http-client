# 💡 Architectural Design Decisions

This document outlines key engineering trade-offs and design decisions behind `resilient-http-client`.

---

## 1. Single-Class Orchestrator vs. Builder Pattern

### Context
Initial designs explored a builder pattern (`client.with_options(max_retries=5).request(...)`) to create request-specific options.

### Decision
We eliminated the builder pattern (`RequestWithOptions`) and consolidated all functionality directly into `ResilientHttpClient.request(...)` via keyword parameters (`max_retries`, `timeout`, `fallback`, `ignore_circuit`).

### Rationale
- **Zero Allocation**: Avoids creating short-lived wrapper instances per request.
- **Python Asyncio Concurrency Model**: Python asyncio operates within a single long-lived process event loop. Passing per-request overrides as arguments is 100% thread-safe, task-safe, and race-condition free.
- **API Simplicity**: Developers interact with a single predictable class (`ResilientHttpClient`).

---

## 2. Distributed State Management (Redis FailureStore)

### Context
In containerized Kubernetes deployments, microservice instances run across multiple pods. An in-memory circuit breaker only protects a single pod, allowing upstream outages to hammer backends across $N$ pods.

### Decision
We decoupled state storage into a dedicated `FailureStore` backed by Redis.

### Rationale
- **Cross-Pod Synchronization**: When one pod detects a downstream outage and trips the circuit to `OPEN`, all other pods sharing the Redis key instantly benefit from fast-failing.
- **Fault-Tolerant Fallback**: If Redis itself experiences an outage, `FailureStore` safely catches connection errors, logs warnings, assumes `CLOSED` state, and allows traffic to flow safely.

---

## 3. Half-Open Stampede Protection (Atomic `SETNX` Probe Locking)

### Context
When an `OPEN` circuit cooldown expires, the breaker enters `HALF-OPEN`. If hundreds of concurrent requests arrive simultaneously, they could all attempt probe requests, overwhelming a recovering downstream service (thundering herd).

### Decision
We implemented atomic probe token locking using Redis `SETNX` (`acquire_probe_token` / `release_probe_token`).

### Rationale
- Exactly `half_open_max_calls` requests acquire probe permission token during `HALF-OPEN`.
- Concurrent requests that fail to acquire the probe token are immediately blocked and served fallbacks without hitting the upstream service.

---

## 4. Python `@runtime_checkable` Protocols over Abstract Base Classes (ABCs)

### Context
Extensibility is required for custom storage backends, HTTP executors, retry policies, and fallback handlers.

### Decision
We defined structural typing interfaces using `typing.Protocol` in `src/resilient_http_client/protocols/`.

### Rationale
- **Structural Subtyping (Duck Typing)**: Custom components do not need to explicitly inherit from library base classes—they only need to implement the required async method signatures.
- **Runtime Validation**: `@runtime_checkable` allows `isinstance(custom_store, FailureStoreProtocol)` checks during dependency injection.
