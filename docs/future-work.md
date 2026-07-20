# 🔮 Future Work & Roadmap

Planned enhancements for future releases:

---

## 🛣️ Features Roadmap

### 1. 📊 Telemetry & Event Hooks
Add explicit callback hooks on `ResilientHttpClient` for Prometheus/Datadog metric exporters:
```python
client.on_state_change(lambda service, old_state, new_state: ...)
client.on_retry(lambda service, attempt, error: ...)
```

### 2. 🚦 Bulkhead & Concurrency Limiter
Implement concurrency semaphores to cap maximum active HTTP requests per service instance (`max_concurrent_requests=20`).

### 3. 🗄️ Multi-Region Redis Cluster Failover
Support dual-write / multi-cluster Redis backends for multi-region fault tolerance.
