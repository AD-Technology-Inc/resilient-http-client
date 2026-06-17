# Resilient HTTP Client Architecture

The library is designed around the **Orchestrator** pattern where `ResilientHttpClient` coordinates several specialized components.

## Component Coordination

1.  **ResilientHttpClient**: The entry point. It manages the lifecycle of the request.
2.  **CircuitBreaker**: Consulted before every request. Updates state based on success/failure.
3.  **FailureStore**: Persistent storage (e.g., Redis) for failure metrics and circuit state.
4.  **RetryPolicy**: Determines if and when to retry based on exponential backoff.
5.  **HttpExecutor**: Wraps `httpx` and normalizes responses into `HttpResponse`.
6.  **FallbackHandler**: Executes registered fallback logic when all else fails.

## Request Flow

1.  Check `circuit.allow_request()`.
2.  If blocked, return `fallback.run("circuit_open")`.
3.  Loop for retries:
    a. Execute `http.send()`.
    b. If success, `circuit.on_success()` and return data.
    c. If failure, `circuit.on_failure()`.
    d. Check `retry.can_retry()`. If yes, `retry.wait()` and continue.
4.  If loop exits, return `fallback.run(last_error)`.
