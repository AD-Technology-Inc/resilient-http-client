import asyncio
import redis.asyncio as redis

from resilient_http_client import ResilientHttpClient, FailureStore


async def main():
    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True,
    )

    service = "slack"
    store = FailureStore(redis_client, service)

    async with ResilientHttpClient(
        service=service,
        store=store,
    ) as client:
        # custom fallback response 
        client.fallback.register(
            lambda reason: {
                "status": "queued",
                "message": "Slack unavailable, message queued",
                "reason": reason,
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
            print(response.json())
        else:
            print(response)


if __name__ == "__main__":
    asyncio.run(main())
