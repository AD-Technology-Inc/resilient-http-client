import inspect
from typing import Callable

from httpx import Response


class FallbackHandler:
    def __init__(self):
        self._fn: Callable[[Response | str], Response] | None = None

    def register(self, fn: Callable[[Response | str], Response]):
        self._fn = fn

    async def run(self, error: Response | str) -> Response:
        if self._fn:
            return (
                await self._fn(error)
                if inspect.iscoroutinefunction(self._fn)
                else self._fn(error)
            )

        if isinstance(error, Response):
            return error

        # Coerce non-string errors (e.g. mock response objects in tests) to str
        # so the JSON body never fails to serialize.
        message = error if isinstance(error, str) else str(error)
        return Response(
            503,
            json={
                "statusCode": 503,
                "message": message,
            },
        )
