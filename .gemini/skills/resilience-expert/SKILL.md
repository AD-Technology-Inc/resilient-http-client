---
name: resilience-expert
description: Expert guidance for maintaining, extending, and debugging the Resilient HTTP Client library. Use when adding resilience patterns, new storage backends, or fixing integration bugs in examples and tests.
---

# Resilience Expert

Expert guidance for the `resilient-http-client` library.

## Core Concepts

- **Architecture**: See [architecture.md](references/architecture.md) for how components coordinate.
- **Testing**: See [testing-patterns.md](references/testing-patterns.md) for standardized mocks.

## Workflows

### Extending the Library

1.  **New Resilience Pattern**: Implement the logic in a new module, integrate it into `ResilientHttpClient.request()`, and add configuration to `ResilienceConfig`.
2.  **New Storage Backend**: Inherit from the same interface used by `FailureStore` (methods like `get_state`, `set_state`, `increment_failures`).

### Debugging Issues

1.  **Verify State**: Check the `FailureStore` state in Redis using `redis-cli`.
2.  **Check Transitions**: Use `simulate_outage.py` to verify Circuit Breaker transitions (CLOSED -> OPEN -> HALF-OPEN -> CLOSED).
3.  **Await Everything**: Ensure all async methods in `FailureStore` and `Client` are properly awaited.

### Testing Requirements

- Always add unit tests in `tests/`.
- Use `pytest-asyncio` for async tests.
- Maintain consistency with `FakeRedis` and `MockResponse` mocks.
- Ensure `PYTHONPATH=.` is set when running tests.

## Rules

- Use `CircuitState` enum for all state-related logic.
- Prefer `async with` context managers for `ResilientHttpClient`.
- Maintain docstrings for public interfaces in `src/client.py`.
