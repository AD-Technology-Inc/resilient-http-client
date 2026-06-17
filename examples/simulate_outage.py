"""
Simulates an upstream outage and demonstrates:

1. failure accumulation
2. circuit breaker opening
3. fast-fail behavior
4. fallback activation
"""

import asyncio
import redis.asyncio as redis

from src.client import ResilientHttpClient
from src.failure_store import FailureStore


class AlwaysFailHttpExecutor:
    async def send(self, method, url, **kwargs):
        raise Exception("upstream_timeout")


async def main():
    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True,
    )

    store = FailureStore(redis_client, "stripe")

    client = ResilientHttpClient(
        service="stripe",
        store=store,
    )

    # Replace real HTTP layer with failing one
    client.http = AlwaysFailHttpExecutor()

    client.fallback.register(
        lambda reason: {
            "status": "degraded",
            "reason": reason,
        }
    )

    for i in range(1, 10):
        print(f"\n--- Request {i} ---")

        response = await client.request(
            "POST",
            "https://api.stripe.com/v1/payment_intents",
        )

        state = store.get_state()
        failures = store.get_failures()

        print("Circuit State:", state)
        print("Failures:", failures)
        print("Response:", response)

        await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())
