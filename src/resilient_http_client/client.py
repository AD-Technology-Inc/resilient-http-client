import logging

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

    issue: it should be possible to customize HttpExecutor failure handling (is_success)
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

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        # 1. Check Circuit Breaker
        if not await self.circuit.allow_request():
            logger.warning(
                f"Request blocked by Circuit Breaker for {self.service}"
            )
            return await self.fallback.run("circuit_open")

        attempt = 0
        last_error = ""

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

                if is_retryable and self.retry.can_retry(attempt):
                    await self.retry.wait(attempt)
                    continue

                # Final failure: either not retryable or retries exhausted
                return await self.fallback.run(last_error)

            except Exception as e:
                logger.error(f"Request error: {str(e)}")
                last_error = str(e)

                await self.circuit.on_failure()

                if self.retry.can_retry(attempt):
                    await self.retry.wait(attempt)
                    continue

                # Final failure after retries
                logger.error(f"All retry attempts exhausted for {self.service}")
                return await self.fallback.run(last_error)
