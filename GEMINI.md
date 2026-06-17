# 🛡️ Resilient HTTP Client - Project Instructions

This file provides foundational guidance for AI agents working on the `resilient-http-client` project.

## 🏗️ Architectural Core
This library is built on the principle of **strict state management** for resilience patterns.
- **State Machine**: All circuit breaker logic must strictly follow the `CLOSED`, `OPEN`, `HALF-OPEN` transitions.
- **Async First**: All network and storage operations MUST be asynchronous and properly awaited.
- **Pluggable Storage**: The `FailureStore` is the source of truth. Ensure any changes maintain compatibility with distributed backends (like Redis).

## 🛠️ Tech Stack & Tooling
- **Language**: Python 3.12+
- **HTTP Engine**: `httpx` (Asynchronous)
- **Dependency Management**: `uv`
- **Testing**: `pytest` with `pytest-asyncio`
- **Quality**: Adhere to PEP 8; use explicit type hints for all public APIs.

## 🧪 Testing Mandates
A change is not complete without verification.
- **Unit Tests**: Every new resilience logic must have 100% branch coverage in `tests/`.
- **Chaos Testing**: When modifying `CircuitBreaker` or `RetryPolicy`, you must run or update `tests/test_flaky_resilience.py` to simulate real-world failure modes.
- **Integration**: Verify changes against the Redis backend if storage logic is modified.

## 🔄 Workflows
- **Specialized Guidance**: Always activate the `resilience-expert` skill (`activate_skill(name="resilience-expert")`) before making architectural changes.
- **Environment**: Always run commands with `PYTHONPATH=.` or via `uv run` to ensure local modules are discoverable.
- **Validation**: Before finishing a task, run `pytest` to ensure no regressions.

## 📚 References
- Architecture: `docs/diagrams/architecture.mmd`
- State Machine: `docs/diagrams/state_machine.mmd`
- Core Implementation: `src/client.py`
