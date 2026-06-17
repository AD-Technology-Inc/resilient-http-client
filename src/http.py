import httpx
import logging

logger = logging.getLogger(__name__)


class HttpExecutor:
    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self._client = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def send(self, method: str, url: str, **kwargs):
        client = await self.get_client()
        try:
            response = await client.request(method, url, **kwargs)
            return HttpResponse(response)
        except httpx.RequestError as exc:
            logger.error(f"An error occurred while requesting {exc.request.url!r}.")
            raise

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class HttpResponse:
    def __init__(self, response: httpx.Response):
        self._response = response

    @property
    def is_success(self):
        return 200 <= self._response.status_code < 300

    @property
    def status_code(self):
        return self._response.status_code

    @property
    def data(self):
        try:
            return self._response.json()
        except Exception:
            return self._response.text
