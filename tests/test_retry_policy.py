import pytest

from resilient_http_client import ResilienceConfig, RetryPolicy


@pytest.mark.asyncio
async def test_retry_allows_attempts():
    config = ResilienceConfig(max_retries=2)
    retry = RetryPolicy(config=config)

    assert retry.can_retry(1) is True
    assert retry.can_retry(2) is True
    assert retry.can_retry(3) is False


@pytest.mark.asyncio
async def test_retry_backoff_waits():
    # If using pytest-mock, we could spy on asyncio.sleep
    # For now, we'll just check it doesn't crash
    retry = RetryPolicy()
    await retry.wait(1)
