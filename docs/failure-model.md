# 🛑 Failure Classification Model

`resilient-http-client` differentiates between client errors (4xx), transient upstream server errors (5xx), and network connection failures.

---

## 📊 Status Code Matrix

| Status Code / Exception | Category | Triggers Retry? | Trips Circuit Breaker? | Notes |
| :--- | :--- | :---: | :---: | :--- |
| `HTTP 2xx / 3xx` | **Success** | ❌ No | ❌ Reset counters | Clears failures & closes circuit |
| `HTTP 400 - Bad Request` | **Client Error** | ❌ No | ❌ No | Returned directly to application |
| `HTTP 404 - Not Found` | **Client Error** | ❌ No | ❌ No | Returned directly to application |
| `HTTP 422 - Validation` | **Client Error** | ❌ No | ❌ No | Ignored by circuit breaker |
| `HTTP 429 - Rate Limit` | **Transient** | ✅ Yes | ❌ No (Default) | In `retry_status_codes`, not circuit failure |
| `HTTP 408 - Timeout` | **Transient** | ✅ Yes | ✅ Yes | In both retry & circuit failure sets |
| `HTTP 500 - Server Error` | **Server Outage** | ✅ Yes | ✅ Yes | In both retry & circuit failure sets |
| `HTTP 502 / 503 / 504` | **Upstream Outage** | ✅ Yes | ✅ Yes | In both retry & circuit failure sets |
| `httpx.ConnectError` | **Network Error** | ✅ Yes | ✅ Yes | Exception caught & counted as failure |
| `httpx.TimeoutException` | **Network Error** | ✅ Yes | ✅ Yes | Exception caught & counted as failure |

---

## ⚙️ Customizing Failure Sets

You can independently configure status codes that trigger retries vs status codes that trip the circuit breaker:

```python
config = ResilienceConfig(
    # Status codes that trigger retries (e.g. rate limits & server errors)
    retry_status_codes={408, 429, 500, 502, 503, 504},
    # Status codes that count towards circuit breaker threshold
    circuit_failure_status_codes={500, 502, 503, 504},
)
```
