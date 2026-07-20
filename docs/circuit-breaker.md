# 🔌 Circuit Breaker Pattern

The Circuit Breaker pattern prevents cascading failures by stopping execution when downstream services become unresponsive or unhealthy.

![Circuit Breaker State Machine](diagrams/state-machine.png)

---

## ⚙️ Configuration Parameters

```python
from resilient_http_client import ResilienceConfig

config = ResilienceConfig(
    cooldown=30,                        # Cooldown duration (seconds) before HALF-OPEN
    sliding_window_type="COUNT_BASED",  # "COUNT_BASED" or "TIME_BASED"
    sliding_window_size=10,             # Number of calls or seconds in window
    minimum_number_of_calls=5,          # Minimum calls required before evaluating failure rate
    failure_rate_threshold=50.0,        # Percentage threshold to trip OPEN (>= 50%)
    half_open_max_calls=1,              # Maximum probe calls allowed in HALF-OPEN
    half_open_successes_needed=1,       # Required successful probes to CLOSE circuit
)
```

---

## 📊 Sliding Window Types

The circuit breaker supports two sliding window algorithms modeled after Resilience4j:

### 1. Count-Based Window (`COUNT_BASED`)
- Evaluates the outcome of the last `N` requests (e.g. `sliding_window_size=10`).
- If at least `minimum_number_of_calls` have been made, calculates the failure percentage:
  $$\text{Failure Rate} = \frac{\text{Failures in Window}}{\text{Total Calls in Window}} \times 100$$
- Trips `OPEN` if $\text{Failure Rate} \ge \text{failure\_rate\_threshold}$.

### 2. Time-Based Window (`TIME_BASED`)
- Evaluates calls made within the last $T$ seconds (e.g. `sliding_window_size=10`).
- Uses Redis sorted sets (`ZADD` with millisecond timestamps) to dynamically prune outdated calls outside the time window.

---

## 🔒 Half-Open Stampede Protection

When the cooldown timer expires, the circuit breaker enters `HALF-OPEN`. To prevent a herd of concurrent requests from overwhelming the recovering service:

1. The client calls `store.acquire_probe_token(ttl=cooldown)`.
2. Redis executes an atomic `SETNX` probe lock.
3. **Winner**: Exactly one (or `half_open_max_calls`) worker acquires the probe token and dispatches a test request.
4. **Losers**: All other concurrent workers receive `False`, block execution, and return fallbacks immediately.
5. Upon response:
   - **Probe Success**: Clears the probe lock, calls `store.increment_half_open_successes()`, and transitions to `CLOSED`.
   - **Probe Failure**: Clears the probe lock, calls `store.set_state("open")`, and resets the cooldown timer.
