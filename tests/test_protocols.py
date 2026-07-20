"""
Tests for all structural runtime-checkable Protocols (interfaces).

Verifies that:
1. Built-in implementations satisfy their corresponding Protocols at runtime (isinstance).
2. Conforming custom classes are recognized as Protocol matches.
3. Incomplete implementations are rejected at runtime.
"""

from typing import Callable

import httpx
import pytest
from test_circuit_breaker import FakeStore

from resilient_http_client import (
    FailureStoreProtocol,
    FallbackHandler,
    FallbackHandlerProtocol,
    HttpExecutor,
    HttpExecutorProtocol,
    ResilienceConfig,
    ResilientHttpClient,
    RetryPolicy,
    RetryPolicyProtocol,
)

# ---------------------------------------------------------------------------
# Test Mocks for Conformance Checks
# ---------------------------------------------------------------------------


class ValidCustomExecutor:
    async def send(self, method: str, url: str, **kwargs) -> httpx.Response:
        return httpx.Response(200)

    async def close(self) -> None:
        pass


class ValidCustomRetryPolicy:
    def can_retry(self, attempt: int) -> bool:
        return True

    async def wait(self, attempt: int) -> None:
        pass


class ValidCustomFallbackHandler:
    def register(self, fn: Callable[[httpx.Response | str], httpx.Response]) -> None:
        pass

    async def run(self, error: httpx.Response | str) -> httpx.Response:
        return httpx.Response(500)


# ---------------------------------------------------------------------------
# Protocol Tests
# ---------------------------------------------------------------------------


def test_http_executor_protocol():
    # Built-in conformance
    executor = HttpExecutor(timeout=1.0)
    assert isinstance(executor, HttpExecutorProtocol)

    # Custom conformance
    assert isinstance(ValidCustomExecutor(), HttpExecutorProtocol)

    # Incomplete conformance
    class BrokenExecutor:
        async def send(self, method: str, url: str, **kwargs) -> httpx.Response:
            return httpx.Response(200)

        # missing close

    assert not isinstance(BrokenExecutor(), HttpExecutorProtocol)


def test_failure_store_protocol():
    # FakeStore conforms
    assert isinstance(FakeStore(), FailureStoreProtocol)

    # Incomplete conformance
    class BrokenStore:
        service: str = "broken"
        # missing get_state/set_state etc.

    assert not isinstance(BrokenStore(), FailureStoreProtocol)


def test_retry_policy_protocol():
    # Built-in conformance
    policy = RetryPolicy()
    assert isinstance(policy, RetryPolicyProtocol)

    # Custom conformance
    assert isinstance(ValidCustomRetryPolicy(), RetryPolicyProtocol)

    # Incomplete conformance
    class BrokenRetryPolicy:
        def can_retry(self, attempt: int) -> bool:
            return True

        # missing wait

    assert not isinstance(BrokenRetryPolicy(), RetryPolicyProtocol)


def test_fallback_handler_protocol():
    # Built-in conformance
    handler = FallbackHandler()
    assert isinstance(handler, FallbackHandlerProtocol)

    # Custom conformance
    assert isinstance(ValidCustomFallbackHandler(), FallbackHandlerProtocol)

    # Incomplete conformance
    class BrokenFallbackHandler:
        async def run(self, error: httpx.Response | str) -> httpx.Response:
            return httpx.Response(500)

        # missing register

    assert not isinstance(BrokenFallbackHandler(), FallbackHandlerProtocol)


# ---------------------------------------------------------------------------
# End-to-End client substitution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_accepts_custom_interfaces():
    # client expects FailureStoreProtocol
    store = FakeStore()
    config = ResilienceConfig(max_retries=0)
    client = ResilientHttpClient(service="test-custom-interfaces", store=store, config=config)

    # client accepts custom implementations
    client.http = ValidCustomExecutor()
    client.retry = ValidCustomRetryPolicy()
    client.fallback = ValidCustomFallbackHandler()

    assert isinstance(client.http, HttpExecutorProtocol)
    assert isinstance(client.retry, RetryPolicyProtocol)
    assert isinstance(client.fallback, FallbackHandlerProtocol)
