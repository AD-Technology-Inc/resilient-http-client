import asyncio
import os

import redis.asyncio as redis

from resilient_http_client import FailureStore, ResilientHttpClient


async def main():
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))

    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        decode_responses=True,
    )

    service = "stripe"
    store = FailureStore(redis_client, service)

    async with ResilientHttpClient(
        service=service,
        store=store,
    ) as client:
        client.fallback.register(
            lambda reason: {
                "status": "degraded",
                "provider": "stripe",
                "message": "Stripe temporarily unavailable",
                "reason": str(reason),
            }
        )

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
            print("Response JSON:", response.json())
        else:
            print("Response:", response)


if __name__ == "__main__":
    asyncio.run(main())
