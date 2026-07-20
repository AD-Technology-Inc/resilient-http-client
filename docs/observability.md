# 📊 Observability & Diagnostics

`resilient-http-client` produces structured diagnostic logs and maintains queryable Redis state keys for monitoring.

---

## 🪵 Log Formats

All log messages include the service name context (`[service_name]`):

```text
# Circuit Breaker Blocked Request (OPEN State)
WARNING:resilient_http_client.client:[stripe] Request blocked by Circuit Breaker for https://api.stripe.com/v1/charges

# Request Failure Log
ERROR:resilient_http_client.client:[stripe] POST https://api.stripe.com/v1/charges -> HTTP 500 (attempt 1)

# Retry Exhaustion Log
ERROR:resilient_http_client.client:[stripe] All retry attempts exhausted for https://api.stripe.com/v1/charges

# State Machine Transition
WARNING:resilient_http_client.circuit_breaker:Circuit breaker tripping OPEN for service stripe
```

---

## 🗄️ Redis State Key Schema

For a service configured as `service="payment_service"`:

| Redis Key | Type | Description | TTL |
| :--- | :--- | :--- | :--- |
| `resilient_http:payment_service:state` | `String` | Current state (`"closed"`, `"open"`, `"half_open"`) | Cooldown duration |
| `resilient_http:payment_service:failures` | `String` | Counter for consecutive failures | None |
| `resilient_http:payment_service:calls` | `ZSet` / `List` | Sliding window call history | Window TTL |
| `resilient_http:payment_service:probe_lock` | `String` | Atomic `SETNX` lock token for probe requests | Cooldown duration |

---

## 📈 Monitoring Recommendations

We recommend monitoring:
1. **Circuit State Gauge**: Alert when `resilient_http:<service>:state` equals `"open"`.
2. **Failure Rate Counter**: Track requests resulting in degraded fallbacks.
3. **Retry Count Counter**: Monitor frequency of transient retries per service.
