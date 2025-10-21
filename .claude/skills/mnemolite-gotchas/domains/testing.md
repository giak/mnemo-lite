# Testing Gotchas

**Purpose**: Testing patterns, fixtures, and test configuration gotchas

**When to reference**: Writing tests, debugging test failures, or configuring test environment

---

## 🟡 TEST-01: AsyncClient Configuration

**Rule**: Use `ASGITransport(app)` for pytest AsyncClient, NOT `app=app`

```python
# ✅ CORRECT
from httpx import AsyncClient, ASGITransport
from api.main import app

async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
    response = await client.get("/health")

# ❌ WRONG - Deprecated, may fail
async with AsyncClient(app=app, base_url="http://test") as client:
    response = await client.get("/health")
```

**Why**: Newer HTTPX versions require explicit transport

**Detection**: Deprecation warnings, test failures

---

## 🟡 TEST-02: Fixture Scope

**Rule**: Database fixtures should be `function` scope for isolation

```python
# ✅ CORRECT - Each test gets clean DB
@pytest.fixture(scope="function")
async def async_engine():
    # Create engine for this test
    engine = create_async_engine(TEST_DATABASE_URL)
    yield engine
    await engine.dispose()

# ❌ WRONG - Tests share state, cause flaky failures
@pytest.fixture(scope="module")  # Shared across tests!
async def async_engine():
    ...
```

**Why**: Tests should be isolated. Shared DB state causes flaky tests.

**Exception**: Read-only fixtures can use `session` or `module` scope for performance

---

## 🟡 TEST-03: Test Execution Order

**Rule**: Tests must pass in ANY order (no dependencies)

```python
# ✅ CORRECT - Self-contained test
async def test_create_chunk():
    chunk = await create_test_chunk()  # Creates its own data
    assert chunk.id is not None

# ❌ WRONG - Depends on other test running first
async def test_update_chunk():
    chunk = await get_chunk_from_db()  # Assumes chunk exists!
    # Fails if test_create_chunk didn't run first
```

**Detection**: Tests pass when run individually, fail when run together

**Fix**: Each test creates its own fixtures, cleans up after

---

**Total Testing Gotchas**: 3
