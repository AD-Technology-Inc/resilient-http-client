import logging

from .config import ResilienceConfig
from .protocols import FailureStoreProtocol
from .types import CircuitState

logger = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(
        self,
        store: FailureStoreProtocol,
        config: ResilienceConfig = ResilienceConfig(),
    ):
        self.store = store
        self.config = config

    async def get_current_state(self) -> str:
        return await self.store.get_state()

    async def is_open(self) -> bool:
        state = await self.get_current_state()
        return state == CircuitState.OPEN.value

    async def is_half_open(self) -> bool:
        state = await self.get_current_state()
        return state == CircuitState.HALF_OPEN.value

    async def is_closed(self) -> bool:
        state = await self.get_current_state()
        return state == CircuitState.CLOSED.value

    async def allow_request(self) -> bool:
        state = await self.get_current_state()

        if state == CircuitState.OPEN.value:
            # Check for lazy transition
            if await self.store.is_open_expired():
                await self.transition_to_half_open()
                # Fall through to HALF_OPEN handling below
                state = CircuitState.HALF_OPEN.value
            else:
                return False

        if state == CircuitState.HALF_OPEN.value:
            # Atomic SETNX probe lock: only the first worker across all
            # containers claims the token; all others go directly to fallback.
            # This prevents a stampede from knocking a barely-recovering
            # downstream service back down.
            if not await self.store.acquire_probe_token(ttl=self.config.cooldown):
                return False
            await self.store.increment_half_open_calls()
            return True

        return True

    async def trip_open(self):
        logger.warning(f"Circuit breaker tripping OPEN for service {self.store.service}")
        # issue: what if this block is interrupted?
        await self.store.set_state(CircuitState.OPEN.value, ttl=self.config.cooldown)
        await self.store.reset_failures()
        await self.store.reset_half_open()
        await self.store.reset_window()
        # Release any stale probe token so the next cooldown cycle is not blocked
        await self.store.release_probe_token()

    async def transition_to_half_open(self):
        logger.info(f"Circuit breaker transitioning to HALF-OPEN for service {self.store.service}")
        await self.store.set_state(CircuitState.HALF_OPEN.value)
        await self.store.reset_half_open()

    async def maybe_open(self):
        # 1. Evaluate sliding window
        rate, calls = await self.store.get_failure_rate_and_calls(
            self.config.sliding_window_type, self.config.sliding_window_size
        )
        if calls >= self.config.minimum_number_of_calls:
            if rate >= self.config.failure_rate_threshold:
                await self.trip_open()
                return

        # 2. Fallback to absolute failures threshold for backward compatibility
        failures = await self.store.get_failures()
        if failures >= self.config.failure_threshold:
            await self.trip_open()

    async def on_success(self):
        state = await self.get_current_state()

        if state == CircuitState.HALF_OPEN.value:
            await self.store.increment_half_open_success()
            successes = await self.store.get_half_open_successes()

            if successes >= self.config.half_open_successes_needed:
                logger.info(
                    f"Circuit breaker closing \
                    (HALF-OPEN -> CLOSED) for service {self.store.service}"
                )
                await self.store.reset_failures()
                await self.store.reset_half_open()
                await self.store.reset_window()
                await self.store.set_state(CircuitState.CLOSED.value)
        else:
            await self.store.reset_failures()
            await self.store.record_call(
                success=True,
                window_type=self.config.sliding_window_type,
                window_size=self.config.sliding_window_size,
            )
            await self.maybe_open()

    async def on_failure(self):
        state = await self.get_current_state()

        if state == CircuitState.HALF_OPEN.value:
            await self.trip_open()
        else:
            await self.store.increment_failures()
            await self.store.record_call(
                success=False,
                window_type=self.config.sliding_window_type,
                window_size=self.config.sliding_window_size,
            )
            await self.maybe_open()
