import inspect


class FallbackHandler:
    def __init__(self):
        self._fn = None

    def register(self, fn):
        self._fn = fn

    async def run(self, reason: str):
        if self._fn:
            if inspect.iscoroutinefunction(self._fn):
                return await self._fn(reason)
            return self._fn(reason)

        return {
            "status": "degraded",
            "error": "service_unavailable",
            "reason": reason,
        }
