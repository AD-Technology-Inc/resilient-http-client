import logging
import time
import uuid

from redis.asyncio import Redis

from .types import CircuitState

logger = logging.getLogger(__name__)


class FailureStore:
    def __init__(self, redis: Redis, service: str):
        self.redis = redis
        self.service = service

    def _key(self, suffix: str):
        return f"resilience:{self.service}:{suffix}"

    async def get_state(self) -> str:
        try:
            val = await self.redis.get(self._key("state"))

            if isinstance(val, bytes):
                val = val.decode("utf-8")

            return CircuitState(val).value

        except (ValueError, TypeError):
            return CircuitState.CLOSED.value

        except Exception as e:
            logger.error(f"Redis error in get_state: {e}")
            return CircuitState.CLOSED.value  # Fallback to closed if Redis is down

    async def set_state(self, state: str, ttl: int | None = None):
        try:
            key_state = self._key("state")
            key_cd = self._key("open_cooldown")

            if state == CircuitState.OPEN.value and ttl:
                # issue: model is not atomic - what if this block is interrupted?
                await self.redis.set(key_state, CircuitState.OPEN.value)
                await self.redis.set(key_cd, "1", ex=ttl, nx=True)
            else:
                await self.redis.set(key_state, state)
                await self.redis.delete(key_cd)
        except Exception as e:
            logger.error(f"Redis error in set_state: {e}")

    async def increment_failures(self, window: int = 60):
        try:
            key = self._key("failures")

            count = await self.redis.incr(key)

            if count == 1:
                await self.redis.expire(key, window, nx=True)
        except Exception as e:
            logger.error(f"Redis error in increment_failures: {e}")

    async def get_failures(self) -> int:
        try:
            val = await self.redis.get(self._key("failures"))
            return int(val or 0)
        except Exception as e:
            logger.error(f"Redis error in get_failures: {e}")
            return 0

    async def reset_failures(self):
        try:
            await self.redis.delete(self._key("failures"))
        except Exception as e:
            logger.error(f"Redis error in reset_failures: {e}")

    # Half-open support
    async def get_half_open_calls(self) -> int:
        try:
            val = await self.redis.get(self._key("half_open_calls"))
            return int(val or 0)
        except Exception as e:
            logger.error(f"Redis error in get_half_open_calls: {e}")
            return 0

    async def increment_half_open_calls(self):
        try:
            key = self._key("half_open_calls")
            await self.redis.incr(key)
            await self.redis.expire(key, 60)
        except Exception as e:
            logger.error(f"Redis error in increment_half_open_calls: {e}")

    async def get_half_open_successes(self) -> int:
        try:
            val = await self.redis.get(self._key("half_open_successes"))
            return int(val or 0)
        except Exception as e:
            logger.error(f"Redis error in get_half_open_successes: {e}")
            return 0

    async def increment_half_open_success(self):
        try:
            key = self._key("half_open_successes")
            await self.redis.incr(key)
            await self.redis.expire(key, 60)
        except Exception as e:
            logger.error(f"Redis error in increment_half_open_success: {e}")

    async def reset_half_open(self):
        try:
            await self.redis.delete(self._key("half_open_calls"))
            await self.redis.delete(self._key("half_open_successes"))
        except Exception as e:
            logger.error(f"Redis error in reset_half_open: {e}")

    async def is_open_expired(self) -> bool:
        try:
            state = await self.get_state()

            if state != CircuitState.OPEN.value:
                return False

            cooldown = await self.redis.get(self._key("open_cooldown"))
            return not cooldown
        except Exception as e:
            logger.error(f"Redis error in is_open_expired: {e}")
            return False

    async def record_call(self, success: bool, window_type: str, window_size: int):
        try:
            key = self._key("window")
            val_char = "S" if success else "F"

            if window_type == "TIME_BASED":
                now = time.time()
                val = f"{now}:{uuid.uuid4().hex}:{val_char}"
                await self.redis.zadd(key, {val: now})
                await self.redis.zremrangebyscore(key, "-inf", now - window_size)
                await self.redis.expire(key, window_size + 60)
            else:  # COUNT_BASED
                await self.redis.rpush(key, val_char)
                await self.redis.ltrim(key, -window_size, -1)
                await self.redis.expire(key, 86400)
        except Exception as e:
            logger.error(f"Redis error in record_call: {e}")

    async def get_failure_rate_and_calls(
        self, window_type: str, window_size: int
    ) -> tuple[float, int]:
        try:
            key = self._key("window")

            if window_type == "TIME_BASED":
                now = time.time()
                await self.redis.zremrangebyscore(key, "-inf", now - window_size)
                elements = await self.redis.zrangebyscore(key, now - window_size, now)

                total_calls = len(elements)
                if total_calls == 0:
                    return 0.0, 0

                failures = 0
                for elem in elements:
                    elem_str: str = elem.decode("utf-8") if isinstance(elem, bytes) else str(elem)
                    if elem_str.split(":")[-1] == "F":
                        failures += 1

                failure_rate = (failures / total_calls) * 100.0
                return failure_rate, total_calls
            else:  # COUNT_BASED
                elements = await self.redis.lrange(key, 0, -1)

                total_calls = len(elements)
                if total_calls == 0:
                    return 0.0, 0

                failures = 0
                for elem in elements:
                    elem_str: str = elem.decode("utf-8") if isinstance(elem, bytes) else str(elem)
                    if elem_str == "F":
                        failures += 1

                failure_rate = (failures / total_calls) * 100.0
                return failure_rate, total_calls
        except Exception as e:
            logger.error(f"Redis error in get_failure_rate_and_calls: {e}")
            return 0.0, 0


    async def reset_window(self):
        try:
            await self.redis.delete(self._key("window"))
        except Exception as e:
            logger.error(f"Redis error in reset_window: {e}")

