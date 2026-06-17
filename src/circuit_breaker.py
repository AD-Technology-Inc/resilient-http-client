import logging
from .types import CircuitState
from .config import ResilienceConfig

logger = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(
        self,
        store,
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
                return True

            return False

        if state == CircuitState.HALF_OPEN.value:
            calls = await self.store.get_half_open_calls()
            return calls < self.config.half_open_max_calls

        return True

    async def trip_open(self):
        logger.warning(
            f"Circuit breaker tripping OPEN for service {self.store.service}"
        )
        # issue: what if this block is interrupted?
        await self.store.set_state(CircuitState.OPEN.value, ttl=self.config.cooldown)
        await self.store.reset_failures()
        await self.store.reset_half_open()

    async def transition_to_half_open(self):
        logger.info(
            f"Circuit breaker transitioning to HALF-OPEN for service {self.store.service}"
        )
        await self.store.set_state(CircuitState.HALF_OPEN.value)
        await self.store.reset_half_open()

    async def maybe_open(self):
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
                    f"Circuit breaker closing (HALF-OPEN -> CLOSED) for service {self.store.service}"
                )
                await self.store.reset_failures()
                await self.store.reset_half_open()
                await self.store.set_state(CircuitState.CLOSED.value)
        else:
            await self.store.reset_failures()

    async def on_failure(self):
        state = await self.get_current_state()

        if state == CircuitState.HALF_OPEN.value:
            await self.trip_open()
        else:
           await self.store.increment_failures()
            await self.maybe_open()
