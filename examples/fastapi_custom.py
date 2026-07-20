import asyncio

import httpx
import redis.asyncio as redis
from fastapi import Depends, FastAPI

from resilient_http_client import (
    FailureStore,
    FailureStoreProtocol,
    ResilienceConfig,
    ResilientHttpClient,
)

app = FastAPI(title="Custom Resilient FastAPI Service")


# ---------------------------------------------------------------------------
# Custom Components satisfying Protocol interfaces
# ---------------------------------------------------------------------------


class CustomHttpExecutor:
    """Custom HTTP executor implementing HttpExecutorProtocol."""

    def __init__(self, timeout: float = 5.0):
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    async def send(self, method: str, url: str, **kwargs) -> httpx.Response:
        return await self._client.request(method, url, **kwargs)

    async def close(self) -> None:
        await self._client.aclose()


class CustomLinearRetryPolicy:
    """Custom retry policy implementing RetryPolicyProtocol."""

    def __init__(self, max_retries: int = 3, delay: float = 0.5):
        self.max_retries = max_retries
        self.delay = delay

    def can_retry(self, attempt: int) -> bool:
        return attempt <= self.max_retries

    async def wait(self, attempt: int) -> None:
        await asyncio.sleep(self.delay * attempt)


# ---------------------------------------------------------------------------
# FastAPI Dependency & Setup
# ---------------------------------------------------------------------------


async def get_custom_http_client():
    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True,
    )

    service = "advanced_payment"

    # 1. Pluggable FailureStore typed against FailureStoreProtocol
    store: FailureStoreProtocol = FailureStore(redis_client, service)

    # 2. Comprehensive ResilienceConfig Tuning
    config = ResilienceConfig(
        cooldown=30,
        max_retries=3,
        timeout=5.0,
        half_open_max_calls=3,
        half_open_successes_needed=2,
        sliding_window_type="TIME_BASED",
        sliding_window_size=10,
        minimum_number_of_calls=5,
        failure_rate_threshold=50.0,
        retry_status_codes={408, 429, 500, 503},
        circuit_failure_status_codes={500, 503},
        retry_backoff_base=0.1,
        retry_max_delay=10.0,
    )

    async with ResilientHttpClient(
        service=service,
        store=store,
        config=config,
    ) as client:
        # 3. Swap in custom components satisfying Protocol contracts
        client.http = CustomHttpExecutor(timeout=config.timeout)
        client.retry = CustomLinearRetryPolicy(max_retries=config.max_retries)

        # 4. Custom Fallback Registration
        client.fallback.register(
            lambda error: {
                "status": "degraded",
                "service": service,
                "reason": str(error),
            }
        )

        yield client


@app.post("/charge")
async def create_charge(client: ResilientHttpClient = Depends(get_custom_http_client)):
    response = await client.request(
        method="POST",
        url="https://api.stripe.com/v1/payment_intents",
        headers={"Authorization": "Bearer sk_test_xxx"},
        data={
            "amount": 1000,
            "currency": "usd",
        },
    )

    if hasattr(response, "json"):
        return response.json()
    return response
