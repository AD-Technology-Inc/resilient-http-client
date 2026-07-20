import os

import redis.asyncio as redis
from fastapi import Depends, FastAPI

from resilient_http_client import FailureStore, ResilientHttpClient

app = FastAPI(title="Simple Resilient FastAPI Service")


async def get_http_client():
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))

    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        decode_responses=True,
    )

    service = "payment_service"
    store = FailureStore(redis_client, service)

    async with ResilientHttpClient(service=service, store=store) as client:
        client.fallback.register(
            lambda reason: {
                "status": "degraded",
                "message": "Payment service temporarily unavailable",
                "reason": str(reason),
            }
        )
        yield client


@app.post("/charge")
async def create_charge(client: ResilientHttpClient = Depends(get_http_client)):
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
