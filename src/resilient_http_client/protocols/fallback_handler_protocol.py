from typing import Callable, Protocol, runtime_checkable

import httpx


@runtime_checkable
class FallbackHandlerProtocol(Protocol):
    """Structural protocol for fallback handlers.

    Implement this to supply custom fallback responses or handle errors
    before returning.
    """

    def register(self, fn: Callable[[httpx.Response | str], httpx.Response]) -> None: ...

    async def run(self, error: httpx.Response | str) -> httpx.Response: ...
