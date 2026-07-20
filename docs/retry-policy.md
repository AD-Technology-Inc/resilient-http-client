# 🔁 Exponential Retry Policy

The retry subsystem automatically retries transient HTTP errors and network failures using exponential backoff with configurable caps.

---

## 📐 Exponential Backoff Formula

The delay before attempt $k$ is calculated as:

$$\text{delay} = \min\left(\text{retry\_max\_delay}, \text{retry\_backoff\_base} \times 2^{k - 1}\right)$$

### Default Backoff Sequence (`retry_backoff_base=0.1`, `retry_max_delay=10.0`):
- **Attempt 1**: Immediate call
- **Attempt 2**: $0.1 \times 2^0 = 0.1\text{s}$
- **Attempt 3**: $0.1 \times 2^1 = 0.2\text{s}$
- **Attempt 4**: $0.1 \times 2^2 = 0.4\text{s}$
- **Attempt 5**: $0.1 \times 2^3 = 0.8\text{s}$

---

## ⚙️ Retry Configuration

```python
from resilient_http_client import ResilienceConfig

config = ResilienceConfig(
    max_retries=3,                             # Max retry attempts
    retry_status_codes={408, 429, 500, 503},  # Eligible status codes
    retry_backoff_base=0.1,                    # Initial delay in seconds
    retry_max_delay=10.0,                      # Maximum delay cap
)
```

---

## 🎛️ Per-Request Retry Limit Overrides

You can override `max_retries` per-request without mutating global client configuration:

```python
response = await client.request(
    "POST",
    "https://api.stripe.com/v1/payment_intents",
    max_retries=5,  # Overrides config.max_retries for this specific call
)
```
