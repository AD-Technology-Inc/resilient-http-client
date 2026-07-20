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

    service = "slack"
    store = FailureStore(redis_client, service)

    async with ResilientHttpClient(
        service=service,
        store=store,
    ) as client:
        client.fallback.register(
            lambda reason: {
                "status": "queued",
                "message": "Slack unavailable, message queued",
                "reason": str(reason),
            }
        )

        response = await client.request(
            method="POST",
            url="https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": "Bearer xoxb-token",
            },
            json={
                "channel": "#alerts",
                "text": "Deployment completed",
            },
        )

        if hasattr(response, "json"):
            print("Response JSON:", response.json())
        else:
            print("Response:", response)


if __name__ == "__main__":
    asyncio.run(main())
