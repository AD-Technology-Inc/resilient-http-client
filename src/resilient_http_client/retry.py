import asyncio
import logging
import random

from .config import ResilienceConfig

logger = logging.getLogger(__name__)


class RetryPolicy:
    def __init__(self, config: ResilienceConfig = ResilienceConfig()):
        self.config = config

    def can_retry(self, attempt: int) -> bool:
        return attempt <= self.config.max_retries

    async def wait(self, attempt: int):
        # Exponential backoff base
        base = self.config.retry_backoff_base * (2 ** (attempt - 1))
        jitter = random.uniform(0, 0.1)
        delay = min(base + jitter, self.config.retry_max_delay)
        logger.info(f"Retrying after {delay:.2f}s (attempt {attempt})")
        await asyncio.sleep(delay)

