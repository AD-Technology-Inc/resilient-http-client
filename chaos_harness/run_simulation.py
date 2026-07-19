import asyncio
import logging
import os
import sys

from redis.asyncio import Redis

from resilient_http_client import (
    FailureStore,
    ResilienceConfig,
    ResilientHttpClient,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [simulation-runner] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
MOCK_HOST = os.getenv("MOCK_HOST", "chaos_mock")
MOCK_URL = f"http://{MOCK_HOST}:8080/resource"


async def main():
    logger.info("Initializing connection to Redis at %s", REDIS_HOST)
    redis_client = Redis(host=REDIS_HOST, port=6379, decode_responses=False)
    store = FailureStore(redis_client, "simulation-service")

    # Clear state from any previous run
    await redis_client.flushall()

    config = ResilienceConfig(
        sliding_window_type="COUNT_BASED",
        sliding_window_size=10,
        minimum_number_of_calls=5,
        failure_rate_threshold=50.0,
        failure_threshold=9999,  # enforce sliding window logic
        cooldown=10,
        max_retries=0,
    )

    client = ResilientHttpClient(
        service="simulation-service",
        store=store,
        config=config,
    )

    logger.info("Running Concurrent Flood Simulation...")
    logger.info("Sending 10 parallel requests with injected errors to trip the circuit...")

    # Phase 1: Fire concurrent requests requesting errors
    async def make_request(i):
        try:
            resp = await client.request("GET", f"{MOCK_URL}?chaos=error")
            return resp.status_code
        except Exception as e:
            return str(e)

    tasks = [make_request(i) for i in range(10)]
    results = await asyncio.gather(*tasks)
    logger.info("Flood requests complete. Statuses received: %s", results)

    # Verify circuit status
    circuit_state = await client.circuit.get_current_state()
    logger.info("Circuit state after flood: %s", circuit_state)

    if circuit_state.upper() != "OPEN":
        logger.error("TEST FAILED: Circuit did not transition to OPEN state!")
        sys.exit(1)

    logger.info("Phase 2: Sending requests while circuit is OPEN to verify drops...")
    # These should be rejected instantly without hitting the downstream server
    open_tasks = [make_request(i) for i in range(5)]
    open_results = await asyncio.gather(*open_tasks)
    logger.info("Requests during open circuit received: %s", open_results)

    # Fallback should return 503 for all dropped requests
    if not all(status == 503 for status in open_results):
        logger.error(
            "TEST FAILED: Some requests were not intercepted by the circuit breaker!"
        )
        sys.exit(1)

    logger.info(
        "TEST SUCCESS: Circuit tripped exactly on threshold and "
        "dropped subsequent concurrent requests!"
    )
    await client.close()
    await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
