import pytest
from resilient_http_client import FallbackHandler


@pytest.mark.asyncio
async def test_default_fallback():
    fallback = FallbackHandler()

    result = await fallback.run("timeout")

    assert result["status"] == "degraded"
    assert result["reason"] == "timeout"


@pytest.mark.asyncio
async def test_custom_fallback_sync():
    fallback = FallbackHandler()

    fallback.register(
        lambda reason: {
            "custom": True,
            "reason": reason,
        }
    )

    result = await fallback.run("circuit_open")

    assert result["custom"] is True
    assert result["reason"] == "circuit_open"


@pytest.mark.asyncio
async def test_custom_fallback_async():
    fallback = FallbackHandler()

    async def async_fallback(reason):
        return {"async": True, "reason": reason}

    fallback.register(async_fallback)

    result = await fallback.run("circuit_open")

    assert result["async"] is True
    assert result["reason"] == "circuit_open"
