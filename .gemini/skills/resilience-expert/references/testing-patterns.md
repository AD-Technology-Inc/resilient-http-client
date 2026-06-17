# Testing Patterns

Consistency in testing is critical to ensure mocks correctly simulate the production components.

## FakeRedis Mock

Always use the standardized `FakeRedis` for unit and integration tests. It must support `nx` and `ex` arguments.

```python
class FakeRedis:
    def __init__(self):
        self.db = {}

    async def get(self, key):
        return self.db.get(key)

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.db:
            return False
        self.db[key] = value
        return True

    async def incr(self, key):
        self.db[key] = int(self.db.get(key, 0)) + 1
        return self.db[key]

    async def expire(self, key, ttl, nx=False):
        pass # Optional: implement for TTL specific tests

    async def delete(self, key):
        self.db.pop(key, None)
```

## Mocking HTTP Responses

When mocking `HttpExecutor`, return a `MockResponse` object that implements `is_success`, `status_code`, and `data`.

```python
class MockResponse:
    def __init__(self, is_success, status_code, data):
        self.is_success = is_success
        self.status_code = status_code
        self.data = data
```
