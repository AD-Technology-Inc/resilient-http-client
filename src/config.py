from dataclasses import dataclass


@dataclass
class ResilienceConfig:
    failure_threshold: int = 5
    cooldown: int = 30
    half_open_max_calls: int = 1
    half_open_successes_needed: int = 1
    max_retries: int = 2
    timeout: float = 5.0
