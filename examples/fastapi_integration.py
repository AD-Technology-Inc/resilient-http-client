import redis.asyncio as redis

from fastapi import FastAPI, Depends

from resilient_http_client import ResilientHttpClient, FailureStore


app = FastAPI()


async def http_client():
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
                "message": "Payment provider unavailable",
                "reason": reason,
            }
        )

        yield client


@app.post("/charge")
async def create_charge(http: ResilientHttpClient = Depends(http_client)):
    response = await http.request(
        method="POST",
        url="https://api.stripe.com/v1/payment_intents",
        headers={"Authorization": "Bearer sk_test_xxx"},
        data={
            "amount": 1000,
            "currency": "usd",
        },
    )

    return response
