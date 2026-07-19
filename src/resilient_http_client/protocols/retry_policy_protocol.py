from typing import Protocol, runtime_checkable


@runtime_checkable
class RetryPolicyProtocol(Protocol):
    """Structural protocol for retry strategies.

    Implement this interface to replace the built-in exponential-backoff
    RetryPolicy with a custom strategy.
    """

    def can_retry(self, attempt: int) -> bool:
        ...

    async def wait(self, attempt: int) -> None:
        ...
