# ⏱️ Timeout Strategy

Timeouts prevent slow upstream dependencies from holding open HTTP sockets and consuming server thread/task pools.

---

## 🎯 Timeout Resolution Hierarchy

When executing `client.request(...)`, the socket timeout is resolved in order of precedence:

1. **Per-Request Override**: Value passed to `client.request("GET", url, timeout=2.5)`.
2. **Client Configuration**: `config.timeout` configured on `ResilienceConfig(timeout=5.0)`.
3. **HTTPX Default**: `httpx.AsyncClient(timeout=...)` baseline.

```text
┌────────────────────────────────────────────────────────┐
│ 1. Per-Request Parameter (client.request(timeout=2.5)) │  (Highest Priority)
└──────────────────────────┬─────────────────────────────┘
                           │ If None
┌──────────────────────────▼─────────────────────────────┐
│ 2. ResilienceConfig (config.timeout = 5.0)            │
└──────────────────────────┬─────────────────────────────┘
                           │ Default
┌──────────────────────────▼─────────────────────────────┐
│ 3. HTTPX Client Baseline                              │  (Lowest Priority)
└────────────────────────────────────────────────────────┘
```

---

## ⚡ Network Exception Handling

If a timeout occurs (raising `httpx.TimeoutException`), `ResilientHttpClient`:
1. Records a circuit failure in `FailureStore`.
2. Evaluates whether retries remain (`attempt <= max_retries`).
3. Retries or executes the registered fallback handler.
