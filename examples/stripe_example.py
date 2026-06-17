import asyncio
import redis.asyncio as redis

from src.client import ResilientHttpClient
from src.failure_store import FailureStore


async def main():
    redis_client = redis.Redis(
        host="localhost",
        port=6379,
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
                "reason": reason,
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

        print(response)


if __name__ == "__main__":
    asyncio.run(main())
