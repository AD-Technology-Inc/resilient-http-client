## 🧪 Running the Tests
Ensure you have your environment set up and execute the pytest suite: 
```bash
# Verify all transitions, retries, store structures, and fallbacks
PYTHONPATH=. uv run pytest tests
```
### Test Coverage Breakdown
The unit and integration tests validate the following:
1. **Failure Tracking**: Asserting failure counters increment accurately on exception loops.
2. **Threshold Violations**: Verifying that the circuit trips open exactly when reaching the threshold and remains closed beforehand.
3. **Lazy Cooldown Transition**: Assuring an open circuit correctly progresses to `half-open` once cooldown times out.
4. **Half-Open Gates**: Guaranteeing probe request limits and immediate fail-back to `open` upon any probe failure.
5. **Fallback Routing**: Confirming degraded payloads are gracefully routed.
asd