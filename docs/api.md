# 📖 API Reference

API reference for all public classes, protocols, and data structures in `resilient_http_client`.

---

## 🛰️ `ResilientHttpClient`

```python
class ResilientHttpClient:
    def __init__(
        self,
        service: str,
        store: FailureStoreProtocol,
        config: ResilienceConfig = ResilienceConfig(),
    ): ...
```

### Methods

#### `async request(...)`
```python
async def request(
    self,
    method: str,
    url: str,
    max_retries: int | None = None,
    timeout: float | httpx.Timeout | None = None,
    fallback: Callable[[httpx.Response | str], Any] | None = None,
    ignore_circuit: bool = False,
    **kwargs,
) -> Any: ...
```
Executes an HTTP request wrapped in circuit breaker checks, exponential retries, and fallback handling.

#### `async close()`
Closes the underlying HTTP executor.

---

## ⚙️ `ResilienceConfig`

```python
@dataclass
class ResilienceConfig:
    failure_threshold: int = 5
    cooldown: int = 30
    half_open_max_calls: int = 1
    half_open_successes_needed: int = 1
    max_retries: int = 2
    timeout: float = 5.0
    retry_status_codes: Set[int] = {408, 429, 500, 502, 503, 504}
    circuit_failure_status_codes: Set[int] = {500, 502, 503, 504}
    sliding_window_type: str = "COUNT_BASED"  # "COUNT_BASED" or "TIME_BASED"
    sliding_window_size: int = 10
    minimum_number_of_calls: int = 5
    failure_rate_threshold: float = 50.0
    retry_backoff_base: float = 0.1
    retry_max_delay: float = 10.0
```

---

## 🗄️ `FailureStore`

```python
class FailureStore:
    def __init__(self, redis: Redis, service: str): ...

    async def get_state(self) -> str: ...
    async def set_state(self, state: str) -> None: ...
    async def get_failures(self) -> int: ...
    async def increment_failures(self) -> int: ...
    async def reset_failures(self) -> None: ...
    async def acquire_probe_token(self, ttl: int = 30) -> bool: ...
    async def release_probe_token(self) -> None: ...
```

---

## 🔌 Protocol Interfaces

Importable from `resilient_http_client` or `resilient_http_client.protocols`:

- `FailureStoreProtocol`
- `HttpExecutorProtocol`
- `RetryPolicyProtocol`
- `FallbackHandlerProtocol`
