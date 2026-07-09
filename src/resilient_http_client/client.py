import logging

import httpx

from .circuit_breaker import CircuitBreaker
from .config import ResilienceConfig
from .failure_store import FailureStore
from .fallback import FallbackHandler
from .http import HttpExecutor
from .retry import RetryPolicy

logger = logging.getLogger(__name__)


class ResilientHttpClient:
    """
    Wrapper around an HTTP client that implements resilience patterns such as Circuit Breaker, Retry, and Fallback. It uses the provided FailureStore to track failures and manage the state of the circuit breaker.

    issue: it should be possible to customize HttpExecutor failure handling (is_success)
    """

    def __init__(
        self,
        service: str,
        store: FailureStore,
        config: ResilienceConfig = ResilienceConfig(),
    ):
        self.service = service
        self.store = store
        self.config = config

        self.circuit = CircuitBreaker(store, config)
        self.http = HttpExecutor(timeout=config.timeout)
        self.retry = RetryPolicy(config)
        self.fallback = FallbackHandler()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def close(self):
        await self.http.close()

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        # 1. Check Circuit Breaker
        if not await self.circuit.allow_request():
            logger.warning(f"Request blocked by Circuit Breaker for {self.service}")
            return await self.fallback.run("circuit_open")

        attempt = 0
        last_error = ""

        while True:
            attempt += 1
            try:
                # 2. Execute Request
                response = await self.http.send(method, url, **kwargs)

                if response.is_success:
                    await self.circuit.on_success()
                    return response

                # Non-success response (e.g., 5xx)
                logger.error(f"Request failed with status {response.status_code}")
                last_error = response

                # We only retry on 5xx or specific errors
                if response.status_code < 500:
                    await self.circuit.on_failure()
                    return await self.fallback.run(last_error)

            except Exception as e:
                logger.error(f"Request error: {str(e)}")
                last_error = str(e)

            # 3. Handle Failure & Retry
            await self.circuit.on_failure()

            if self.retry.can_retry(attempt):
                await self.retry.wait(attempt)
                continue

            # Final failure after retries
            logger.error(f"All retry attempts exhausted for {self.service}")
            return await self.fallback.run(last_error)
