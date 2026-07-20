import inspect
import logging
from typing import Any, Callable

import httpx

from .circuit_breaker import CircuitBreaker
from .config import ResilienceConfig
from .fallback import FallbackHandler
from .http import HttpExecutor
from .protocols import (
    FailureStoreProtocol,
    FallbackHandlerProtocol,
    HttpExecutorProtocol,
    RetryPolicyProtocol,
)
from .retry import RetryPolicy

logger = logging.getLogger(__name__)


class ResilientHttpClient:
    """
    Wrapper around an HTTP client that implements resilience patterns such as 
    Circuit Breaker, Retry, and Fallback. It uses the provided FailureStore to track failures 
    and manage the state of the circuit breaker.
    """

    def __init__(
        self,
        service: str,
        store: FailureStoreProtocol,
        config: ResilienceConfig = ResilienceConfig(),
    ):
        self.service = service
        self.store = store
        self.config = config

        self.circuit = CircuitBreaker(store, config)
        self.http: HttpExecutorProtocol = HttpExecutor(timeout=config.timeout)
        self.retry: RetryPolicyProtocol = RetryPolicy(config)
        self.fallback: FallbackHandlerProtocol = FallbackHandler()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def close(self):
        await self.http.close()

    async def _run_fallback(
        self,
        error: httpx.Response | str,
        custom_fallback: Callable[[httpx.Response | str], Any] | None = None,
    ) -> Any:
        if custom_fallback is not None:
            return (
                await custom_fallback(error)
                if inspect.iscoroutinefunction(custom_fallback)
                else custom_fallback(error)
            )
        return await self.fallback.run(error)

    async def request(
        self,
        method: str,
        url: str,
        max_retries: int | None = None,
        timeout: float | httpx.Timeout | None = None,
        fallback: Callable[[httpx.Response | str], Any] | None = None,
        ignore_circuit: bool = False,
        **kwargs,
    ) -> Any:
        """
        Execute an asynchronous HTTP request with resilience guarantees.

        Parameters
        ----------
        method : str
            HTTP method (GET, POST, PUT, DELETE, etc.)
        url : str
            Target URL
        max_retries : int | None
            Per-request retry count override.
        timeout : float | httpx.Timeout | None
            Per-request socket timeout override.
        fallback : Callable | None
            Per-request fallback handler override.
        ignore_circuit : bool
            If True, bypasses the circuit breaker state check.
        **kwargs
            Keyword arguments passed directly to the HTTP executor (json, headers, etc.).
        """
        if timeout is not None:
            kwargs["timeout"] = timeout

        allow = await self.circuit.allow_request()
        if not ignore_circuit and not allow:
            logger.warning(
                f"Request blocked by Circuit Breaker for {self.service}"
            )
            return await self._run_fallback("circuit_open", fallback)

        attempt = 0

        def _can_retry(curr_attempt: int) -> bool:
            if max_retries is not None:
                return curr_attempt <= max_retries
            return self.retry.can_retry(curr_attempt)

        while True:
            attempt += 1
            try:
                # 2. Execute Request
                response = await self.http.send(method, url, **kwargs)

                # Determine if this response represents a circuit failure or retryable error
                is_circuit_failure = (
                    response.status_code
                    in self.config.circuit_failure_status_codes
                )
                is_retryable = (
                    response.status_code in self.config.retry_status_codes
                )

                if not is_circuit_failure and not is_retryable:
                    await self.circuit.on_success()
                    return response

                # Non-success/failure response
                logger.error(
                    f"Request failed with status {response.status_code}"
                )
                last_error = response

                if is_circuit_failure:
                    await self.circuit.on_failure()

                if is_retryable and _can_retry(attempt):
                    await self.retry.wait(attempt)
                    continue

                # Final failure: either not retryable or retries exhausted
                return await self._run_fallback(last_error, fallback)

            except Exception as e:
                logger.error(f"Request error: {str(e)}")
                last_error = str(e)

                await self.circuit.on_failure()

                if _can_retry(attempt):
                    await self.retry.wait(attempt)
                    continue

                # Final failure after retries
                logger.error(f"All retry attempts exhausted for {self.service}")
                return await self._run_fallback(last_error, fallback)






