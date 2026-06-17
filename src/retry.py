import asyncio
import random
import logging
from .config import ResilienceConfig

logger = logging.getLogger(__name__)


class RetryPolicy:
    def __init__(self, config: ResilienceConfig = ResilienceConfig()):
        self.config = config

    def can_retry(self, attempt: int) -> bool:
        return attempt <= self.config.max_retries

    async def wait(self, attempt: int):
        # Exponential backoff: 0.1, 0.2, 0.4, 0.8...
        base = 0.1 * (2 ** (attempt - 1))
        jitter = random.uniform(0, 0.1)
        delay = min(base + jitter, 10)  # Cap at 10s
        logger.info(f"Retrying after {delay:.2f}s (attempt {attempt})")
        await asyncio.sleep(delay)
