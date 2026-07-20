import logging

import httpx

logger = logging.getLogger(__name__)


class HttpExecutor:
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self._client = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def send(self, method: str, url: str, **kwargs) -> httpx.Response:
        client = await self.get_client()
        try:
            return await client.request(method, url, **kwargs)
        except httpx.RequestError as exc:
            logger.error(f"An error occurred while requesting {exc.request.url!r}.")
            raise

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
