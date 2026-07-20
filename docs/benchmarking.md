# ⚡ Benchmarking & Performance

`resilient-http-client` is engineered to add minimal overhead to raw `httpx` request execution.

---

## 🚀 Overhead Profile

| Operation | Overhead | Optimization |
| :--- | :---: | :--- |
| **Circuit Check (`CLOSED`)** | $< 0.8\text{ms}$ | Single async Redis `get` call (or pipeline) |
| **Circuit Block (`OPEN`)** | $< 0.1\text{ms}$ | Instant local fast-fail without network roundtrip |
| **Per-Request Overrides** | $0.0\text{ms}$ | Kwarg passing without object allocations |
| **Probe Token Lock** | $< 1.0\text{ms}$ | Single atomic Redis `SETNX` call |

---

## 💡 Performance Guidelines

1. **Connection Pooling**: Always reuse `ResilientHttpClient` instances or use the `async with` context manager to benefit from HTTP connection pooling.
2. **Redis Co-location**: Deploy Redis in the same cloud region or cluster network as your application pods to ensure sub-millisecond state check latencies.
