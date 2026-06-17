class CircuitOpenError(Exception):
    """Raised when the circuit is open and blocking requests."""

    pass


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted."""

    pass
