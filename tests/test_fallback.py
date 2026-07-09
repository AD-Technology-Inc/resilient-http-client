import pytest
from httpx import Response
from resilient_http_client import FallbackHandler


@pytest.mark.asyncio
async def test_default_fallback():
    fallback = FallbackHandler()

    result = await fallback.run("timeout")

    assert result.status_code == 503
    assert result.json()["statusCode"] == 503
    assert result.json()["message"] == "timeout"


@pytest.mark.asyncio
async def test_custom_fallback_sync():
    fallback = FallbackHandler()

    fallback.register(
        lambda reason: Response(503, json={
            "custom": True,
            "reason": reason,
        })
    )

    result = await fallback.run("circuit_open")

    assert result.status_code == 503
    assert result.json()["custom"] is True
    assert result.json()["reason"] == "circuit_open"


@pytest.mark.asyncio
async def test_custom_fallback_async():
    fallback = FallbackHandler()

    async def async_fallback(reason):
        return Response(503, json={"async": True, "reason": reason})

    fallback.register(async_fallback)

    result = await fallback.run("circuit_open")

    assert result.status_code == 503
    assert result.json()["async"] is True
    assert result.json()["reason"] == "circuit_open"
