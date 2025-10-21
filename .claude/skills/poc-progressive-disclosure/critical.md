# Critical Gotchas - Level 3 Content

This file tests if Claude Code can load Level 3 references via @filename.md pattern.

---

## #TEST-01: Database Connection Fails

**Symptom**: `asyncpg.exceptions.InvalidCatalogNameError: database "mnemolite_test" does not exist`

**Root Cause**: Test database not created or TEST_DATABASE_URL not set

**Fix**:
```bash
make db-test-reset
grep TEST_DATABASE_URL .env
```

**Why This Matters**: Without separate test DB, tests pollute development data

---

## #TEST-02: Cache Initialization Errors

**Symptom**: `redis.exceptions.ConnectionError: Error 111 connecting to redis:6379`

**Root Cause**: Redis not running or connection string incorrect

**Fix**:
```bash
docker compose ps | grep redis
docker compose restart redis
curl http://localhost:8001/health
```

---

## #TEST-03: Async/Await Issues

**Symptom**: `RuntimeWarning: coroutine was never awaited`

**Root Cause**: Forgot to await async function

**Fix**: Always use `await` with async functions:
```python
# ❌ Wrong
result = async_function()

# ✅ Correct
result = await async_function()
```

**Critical**: ALL database operations in MnemoLite MUST be awaited

---

**If you can read this content, Level 3 loading works!**
