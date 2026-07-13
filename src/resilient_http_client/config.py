from dataclasses import dataclass, field
from typing import Set

DEFAULT_RETRY_STATUS_CODES = {408, 429, 500, 502, 503, 504}
DEFAULT_CIRCUIT_FAILURE_STATUS_CODES = {500, 502, 503, 504}


@dataclass
class ResilienceConfig:
    failure_threshold: int = 5
    cooldown: int = 30
    half_open_max_calls: int = 1
    half_open_successes_needed: int = 1
    max_retries: int = 2
    timeout: float = 5.0
    retry_status_codes: Set[int] = field(
        default_factory=lambda: set(DEFAULT_RETRY_STATUS_CODES)
    )
    circuit_failure_status_codes: Set[int] = field(
        default_factory=lambda: set(DEFAULT_CIRCUIT_FAILURE_STATUS_CODES)
    )
    sliding_window_type: str = "COUNT_BASED"  # "COUNT_BASED" or "TIME_BASED"
    sliding_window_size: int = 10
    minimum_number_of_calls: int = 5
    failure_rate_threshold: float = 50.0
    retry_backoff_base: float = 0.1
    retry_max_delay: float = 10.0

