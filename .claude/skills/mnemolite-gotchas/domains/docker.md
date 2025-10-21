# Docker & Environment Gotchas

**Purpose**: Docker configuration, environment variables, and deployment gotchas

**When to reference**: Configuring Docker, debugging container issues, or managing environments

---

## 🟡 DOCKER-01: Volume Mounting for Live Reload

**Rule**: API and tests directories mounted for live reload

```yaml
# ✅ CORRECT - docker-compose.yml
volumes:
  - ./api:/app
  - ./tests:/app/tests  # Tests also mounted!

# ❌ WRONG - Tests not mounted
volumes:
  - ./api:/app
```

**Why**: Without test volume, changes to tests require rebuild

---

## 🟡 DOCKER-02: Redis Memory Limit

**Rule**: Redis configured with 2GB max memory + LRU eviction

```yaml
# docker-compose.yml
redis:
  command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
```

**Why**: Prevents Redis from consuming all system memory

**Monitoring**:
```bash
docker exec mnemo-redis redis-cli INFO memory | grep maxmemory
```

---

## 🟡 DOCKER-03: API Port Mapping

**Rule**: External port 8001, internal port 8000

```yaml
# docker-compose.yml
api:
  ports:
    - "8001:8000"  # Host:Container
```

**Access**:
- From host: `http://localhost:8001`
- From container: `http://api:8000`
- Docs: `http://localhost:8001/docs`

---

**Total Docker Gotchas**: 3
