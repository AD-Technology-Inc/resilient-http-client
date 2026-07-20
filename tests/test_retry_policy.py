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


@pytest.mark.asyncio
async def test_retry_backoff_respects_custom_config():
    from unittest.mock import AsyncMock, patch

    config = ResilienceConfig(
        retry_backoff_base=2.0,
        retry_max_delay=5.0,
    )
    retry = RetryPolicy(config=config)

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await retry.wait(attempt=1)
        # base = 2.0 * (2 ** 0) = 2.0. jitter is 0.0 to 0.1.
        # delay = min(2.0 + jitter, 5.0).
        args, _ = mock_sleep.call_args
        actual_delay = args[0]
        assert 2.0 <= actual_delay <= 2.1

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await retry.wait(attempt=3)
        # base = 2.0 * (2 ** 2) = 8.0. jitter is 0.0 to 0.1.
        # delay = min(8.0 + jitter, 5.0) -> capped at 5.0!
        args, _ = mock_sleep.call_args
        actual_delay = args[0]
        assert actual_delay == 5.0
