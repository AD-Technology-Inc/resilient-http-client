from typing import Protocol, runtime_checkable

import httpx


@runtime_checkable
class HttpExecutorProtocol(Protocol):
    """Structural protocol for HTTP executors, enabling test mocks and custom
    HTTP engine wrappers to satisfy the type checking without explicit inheritance.
    """

    async def send(self, method: str, url: str, **kwargs) -> httpx.Response: ...

    async def close(self) -> None: ...
