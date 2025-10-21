# Architecture Gotchas

**Purpose**: Architectural patterns, DIP principles, and code organization gotchas

**When to reference**: Building new features, refactoring, or ensuring pattern consistency

---

## 🟡 ARCH-01: EXTEND > REBUILD Principle

**Rule**: When adding features, COPY existing pattern and adapt (don't rebuild)

```python
# ✅ CORRECT - Copy graph.html → code_graph.html
# File: templates/code_graph.html
{% extends "base.html" %}
<!-- Copied from graph.html, adapted for code -->

# ❌ WRONG - Rebuild from scratch
# File: templates/code_graph.html
<!-- New implementation, different patterns -->
```

**Why**:
- ~10× faster development
- Consistent patterns across codebase
- Easier maintenance (familiar structure)

**Examples**:
- `graph.html` → `code_graph.html` (UI)
- `event_repository.py` → `code_chunk_repository.py` (Backend)
- `test_event_routes.py` → `test_code_routes.py` (Tests)

---

## 🟡 ARCH-02: Service Method Naming

**Rule**: Service method names must match conventions (not arbitrary)

```python
# ✅ CORRECT
class GraphConstructionService:
    async def build_graph_for_repository(self, repo: str):
        ...

# ❌ WRONG - Wrong method name
class GraphConstructionService:
    async def build_repository_graph(self, repo: str):  # Breaks DI!
        ...
```

**Why**: Dependency injection expects specific method names from protocol

**Detection**: `AttributeError: 'GraphConstructionService' object has no attribute 'build_graph_for_repository'`

**Fix**: Check protocol definition, match method name exactly

---

## 🟡 ARCH-03: Repository Layer Boundaries

**Rule**: Repositories use SQLAlchemy Core (NOT ORM)

```python
# ✅ CORRECT - Core (text + execute)
from sqlalchemy import text

async with conn.execute(text("""
    SELECT * FROM code_chunks WHERE id = :chunk_id
"""), {"chunk_id": chunk_id}) as result:
    row = result.fetchone()

# ❌ WRONG - ORM (Session, declarative models)
from sqlalchemy.orm import Session
session.query(CodeChunkORM).filter_by(id=chunk_id).first()
```

**Why**:
- Core = explicit SQL, better performance, async-first
- ORM = implicit SQL, more overhead, sync-biased

**Exception**: None. MnemoLite uses Core exclusively.

---

**Total Architecture Gotchas**: 3
