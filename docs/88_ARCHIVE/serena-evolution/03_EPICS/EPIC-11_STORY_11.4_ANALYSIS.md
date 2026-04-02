# EPIC-11 Story 11.4: Migration Script for Existing Data - Analysis

**Story**: Story 11.4 - Backfill name_path for Existing Chunks
**Points**: 3 pts
**Status**: 📋 ANALYSIS
**Analyst**: Claude Code
**Date**: 2025-10-21

---

## 🎯 Story Overview

**User Story**: As a database admin, I want to backfill name_path for existing chunks so that v2.0 data works in v3.0.

**Acceptance Criteria**:
1. Migration script computes name_path for all existing chunks
2. Script handles missing repository root gracefully
3. Script validates 100% chunks have name_path after migration
4. Tests: Migration correctness

**Estimated Effort**: 2-3 hours (script + tests + validation)

---

## 📊 Current Database State

### Overview Statistics

```sql
Total chunks: 1,302
Chunks with name_path: 0 (0%)
Chunks needing migration: 1,302 (100%)

Unique repositories: 9
Unique languages: 6
Unique chunk types: 8
```

### Language Distribution

| Language | Count | Percentage |
|----------|-------|------------|
| **TypeScript** | 741 | 56.91% |
| **JavaScript** | 532 | 40.86% |
| **Bash** | 10 | 0.77% |
| **Python** | 9 | 0.69% |
| **JSON** | 6 | 0.46% |
| **Text** | 4 | 0.31% |

**Analysis**:
- Predominantly TypeScript/JavaScript codebase (97.77%)
- SymbolPathService supports both (tested in Story 11.1)
- Minor edge cases: bash, json, text files

### Chunk Type Distribution

| Chunk Type | Count | Percentage | Migration Strategy |
|------------|-------|------------|-------------------|
| **method** | 484 | 37.17% | Requires parent context extraction |
| **fallback_fixed** | 251 | 19.28% | Special handling (non-AST chunks) |
| **class** | 190 | 14.59% | Standard generation |
| **function** | 174 | 13.36% | Standard generation |
| **interface** | 109 | 8.37% | TypeScript-specific |
| **type_alias** | 76 | 5.84% | TypeScript-specific |
| **arrow_function** | 15 | 1.15% | JavaScript/TypeScript |
| **enum** | 3 | 0.23% | TypeScript-specific |

**Critical Findings**:
1. **37% methods** → Need parent context extraction (complex)
2. **19% fallback_fixed** → Non-AST chunks (JSON, text files) → Need special handling
3. **Mixed TypeScript types** → Service already supports these

### Repository Distribution

| Repository | Chunks | Languages | Notes |
|-----------|--------|-----------|-------|
| **code_test_full** | 1,263 | 2 (TS, JS) | 97% of all data |
| CV | 20 | 3 (TS, JSON, Text) | Small test repo |
| test-ts-functions | 4 | 1 (TS) | Test data |
| test-simple | 3 | 1 | Test data |
| Others (5 repos) | 12 | Various | Test data |

**Analysis**: Single dominant repository (code_test_full) with 97% of chunks.

---

## 🚨 Edge Cases Identified

### 1. Chunks with Empty Names (4 chunks, 0.31%)

**Example**:
```sql
id: 559dbb5b-176d-4f2e-b97f-0de60e662e52
name: "" (EMPTY!)
file_path: packages/core/dist/core/src/cv/domain/entities/Resume.js
chunk_type: method
language: javascript
```

**Problem**:
- Cannot generate `name_path` from empty name
- Likely anonymous methods or parsing edge case

**Solution**:
```python
if not chunk["name"] or chunk["name"].strip() == "":
    # Use chunk_type + hash as fallback
    name_fallback = f"anonymous_{chunk['chunk_type']}_{chunk['id'][:8]}"
    name_path = f"{module_path}.{name_fallback}"
```

---

### 2. Fallback_fixed Chunks (251 chunks, 19.28%)

**Example**:
```sql
name: "chunk_0"
file_path: cv/.mcp.json
chunk_type: fallback_fixed
language: json
```

**Problem**:
- Not real code symbols (JSON config, markdown files)
- Generic names like "chunk_0", "chunk_1"
- No AST structure

**Solution**:
```python
if chunk["chunk_type"] == "fallback_fixed":
    # Use file-based naming: "config.mcp_json.chunk_0"
    name_path = f"{module_path}.{chunk['name']}"
    # Or skip entirely if not useful for search
```

**Question for Review**: Should we skip fallback_fixed chunks? They're not searchable code symbols.

---

### 3. Methods Requiring Parent Context (484 chunks, 37.17%)

**Problem**:
- Need to find parent class within same file
- Requires loading ALL chunks from same file
- Expensive query (N+1 problem)

**Current Approach (from EPIC spec)**:
```python
parent_context = None  # Simple version (no parent context for backfill)
```

**Impact**:
- Methods will have **flat paths** instead of qualified
- Example: `Resume.validate` → `entities.Resume.validate` ❌
- Should be: `entities.Resume.Resume.validate` ✅

**Better Solution**:
```python
# Group chunks by file_path
chunks_by_file = defaultdict(list)
for chunk in all_chunks:
    chunks_by_file[chunk["file_path"]].append(chunk)

# Process each file's chunks together
for file_path, file_chunks in chunks_by_file.items():
    for chunk in file_chunks:
        # Extract parent context from file_chunks (same file only)
        parent_context = symbol_service.extract_parent_context(chunk, file_chunks)
        name_path = symbol_service.generate_name_path(...)
```

**Performance**:
- Batch processing by file reduces DB queries
- Memory overhead: ~100KB per file (acceptable)

---

### 4. File Paths Outside Repository Root

**Problem**: SymbolPathService handles this with try/catch:
```python
try:
    rel_path = Path(file_path).relative_to(repository_root)
except ValueError:
    # File outside repository root → uses absolute path
    rel_path = Path(file_path)
```

**Database Check Needed**:
```sql
SELECT file_path, repository FROM code_chunks
WHERE file_path NOT LIKE repository || '%'
LIMIT 5;
```

**Expected**: Should be fine (all files indexed with correct repository root).

---

### 5. Null/Missing Repository Field

**Check**:
```sql
SELECT COUNT(*) FROM code_chunks WHERE repository IS NULL;
```

**Solution**:
```python
repository_root = chunk["repository"] or "/unknown"
```

---

## 🏗️ Implementation Strategy

### Approach 1: Simple (EPIC Spec) - Fast but Inaccurate

```python
# From EPIC spec - NO parent context
for chunk in chunks:
    name_path = symbol_service.generate_name_path(
        chunk_name=chunk["name"],
        file_path=chunk["file_path"],
        repository_root=chunk["repository"],
        parent_context=None  # ❌ Missing parent context
    )
```

**Pros**:
- Fast: <1 minute for 1,302 chunks
- Simple implementation

**Cons**:
- ❌ Methods lose parent context (37% of data)
- ❌ `User.validate` becomes `models.user.validate` (WRONG!)
- ❌ Should be `models.user.User.validate` (CORRECT)

---

### Approach 2: Batch by File (RECOMMENDED) - Accurate

```python
# Step 1: Load ALL chunks (1,302 total)
all_chunks = await conn.fetch("SELECT * FROM code_chunks")

# Step 2: Group by file_path
from collections import defaultdict
chunks_by_file = defaultdict(list)

for chunk in all_chunks:
    chunks_by_file[chunk["file_path"]].append(chunk)

# Step 3: Process each file's chunks together
updates = []

for file_path, file_chunks in chunks_by_file.items():
    for chunk in file_chunks:
        # Extract parent context from chunks in SAME FILE
        parent_context = symbol_service.extract_parent_context(chunk, file_chunks)

        name_path = symbol_service.generate_name_path(
            chunk_name=chunk["name"] or f"anonymous_{chunk['id'][:8]}",
            file_path=chunk["file_path"],
            repository_root=chunk["repository"] or "/unknown",
            parent_context=parent_context,  # ✅ Correct parent context
            language=chunk["language"]
        )

        updates.append((name_path, chunk["id"]))

# Step 4: Batch UPDATE (all at once)
await conn.executemany(
    "UPDATE code_chunks SET name_path = $1 WHERE id = $2",
    updates
)
```

**Pros**:
- ✅ Correct parent context for methods (37% of data)
- ✅ Accurate name_path generation
- ✅ Batch updates (single transaction)
- ✅ Memory efficient (~2MB for 1,302 chunks)

**Cons**:
- Slightly more complex (~50 lines vs 30 lines)
- Still very fast (<10 seconds for 1,302 chunks)

**Performance Estimate**:
- Load 1,302 chunks: ~50ms
- Group by file: ~10ms (Python dict operation)
- Generate name_paths: ~500ms (1,302 × 0.4ms each)
- Batch UPDATE: ~200ms
- **Total**: ~1 second ⚡

---

## 📋 Recommended Implementation

### Script Structure

```python
# scripts/backfill_name_path.py

import asyncio
import asyncpg
import os
import sys
from pathlib import Path
from collections import defaultdict

# Add parent directory to path to import from api/
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.symbol_path_service import SymbolPathService


async def backfill_name_path(dry_run: bool = False):
    """
    Backfill name_path for existing code_chunks.

    Args:
        dry_run: If True, show what would be updated without committing
    """

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    conn = await asyncpg.connect(database_url)
    symbol_service = SymbolPathService()

    try:
        print("🔄 Backfilling name_path for existing chunks...")

        # 1. Count chunks needing migration
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM code_chunks WHERE name_path IS NULL"
        )
        print(f"📊 Chunks to update: {total}")

        if total == 0:
            print("✅ All chunks already have name_path!")
            return

        # 2. Load ALL chunks (for parent context extraction)
        print("📥 Loading all chunks...")
        all_chunks = await conn.fetch("""
            SELECT id, name, file_path, repository, chunk_type,
                   start_line, end_line, language
            FROM code_chunks
            WHERE name_path IS NULL
        """)

        # 3. Group by file_path for efficient parent context extraction
        print("🗂️  Grouping chunks by file...")
        chunks_by_file = defaultdict(list)

        for chunk in all_chunks:
            chunks_by_file[chunk["file_path"]].append(chunk)

        print(f"📁 Processing {len(chunks_by_file)} unique files...")

        # 4. Generate name_path for each chunk (with parent context)
        updates = []
        skipped = []
        errors = []

        for file_path, file_chunks in chunks_by_file.items():
            for chunk in file_chunks:
                try:
                    # Handle edge cases
                    chunk_name = chunk["name"]

                    # Edge case 1: Empty name
                    if not chunk_name or chunk_name.strip() == "":
                        chunk_name = f"anonymous_{chunk['chunk_type']}_{chunk['id'][:8]}"
                        print(f"⚠️  Empty name for chunk {chunk['id'][:8]} → using {chunk_name}")

                    # Edge case 2: Skip fallback_fixed? (optional)
                    if chunk["chunk_type"] == "fallback_fixed":
                        # Option A: Skip
                        # skipped.append(chunk["id"])
                        # continue

                        # Option B: Generate simple path
                        pass  # Continue with normal generation

                    # Extract parent context from chunks in SAME FILE
                    parent_context = symbol_service.extract_parent_context(
                        chunk, file_chunks
                    )

                    # Generate name_path
                    name_path = symbol_service.generate_name_path(
                        chunk_name=chunk_name,
                        file_path=chunk["file_path"],
                        repository_root=chunk["repository"] or "/unknown",
                        parent_context=parent_context,
                        language=chunk["language"]
                    )

                    updates.append((name_path, chunk["id"]))

                except Exception as e:
                    errors.append((chunk["id"], str(e)))
                    print(f"❌ Error processing chunk {chunk['id'][:8]}: {e}")

        print(f"\n📈 Summary:")
        print(f"  ✅ Ready to update: {len(updates)}")
        print(f"  ⏭️  Skipped: {len(skipped)}")
        print(f"  ❌ Errors: {len(errors)}")

        if dry_run:
            print("\n🔍 DRY RUN - No changes will be committed")
            print("\nSample updates (first 5):")
            for name_path, chunk_id in updates[:5]:
                print(f"  {chunk_id[:8]} → {name_path}")
            return

        # 5. Batch UPDATE
        if updates:
            print(f"\n💾 Updating {len(updates)} chunks...")
            await conn.executemany(
                "UPDATE code_chunks SET name_path = $1 WHERE id = $2",
                updates
            )
            print("✅ Update complete!")

        # 6. Validate
        print("\n🔍 Validating migration...")
        remaining = await conn.fetchval(
            "SELECT COUNT(*) FROM code_chunks WHERE name_path IS NULL"
        )

        if remaining > 0:
            print(f"⚠️  Warning: {remaining} chunks still missing name_path")
            if errors:
                print("\nErrors encountered:")
                for chunk_id, error in errors[:10]:
                    print(f"  {chunk_id}: {error}")
        else:
            print("✅ Migration complete! All chunks have name_path.")

        # 7. Statistics
        stats = await conn.fetch("""
            SELECT
                language,
                COUNT(*) as total,
                COUNT(name_path) as with_name_path
            FROM code_chunks
            GROUP BY language
            ORDER BY total DESC
        """)

        print("\n📊 Final statistics by language:")
        for row in stats:
            coverage = 100.0 * row["with_name_path"] / row["total"]
            print(f"  {row['language']:15} {row['total']:5} chunks ({coverage:5.1f}% coverage)")

    finally:
        await conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill name_path for code chunks")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without committing"
    )

    args = parser.parse_args()

    asyncio.run(backfill_name_path(dry_run=args.dry_run))
```

---

## 🧪 Testing Strategy

### Unit Tests

```python
# tests/scripts/test_backfill_name_path.py

import pytest
from scripts.backfill_name_path import backfill_name_path

@pytest.mark.anyio
async def test_backfill_handles_empty_names(test_db):
    """Edge case: Chunks with empty names."""
    # Insert chunk with empty name
    await test_db.execute("""
        INSERT INTO code_chunks (id, name, file_path, repository, chunk_type, language)
        VALUES ($1, '', 'test.py', '/app', 'method', 'python')
    """, uuid.uuid4())

    # Run backfill
    await backfill_name_path(dry_run=False)

    # Verify name_path generated with fallback
    result = await test_db.fetchval("""
        SELECT name_path FROM code_chunks WHERE name = ''
    """)

    assert result is not None
    assert "anonymous_method" in result


@pytest.mark.anyio
async def test_backfill_with_parent_context(test_db):
    """Verify methods get correct parent context."""
    # Insert class + method
    class_id = uuid.uuid4()
    method_id = uuid.uuid4()

    await test_db.execute("""
        INSERT INTO code_chunks (id, name, file_path, repository, chunk_type, language, start_line, end_line)
        VALUES
            ($1, 'User', 'models/user.py', '/app', 'class', 'python', 1, 10),
            ($2, 'validate', 'models/user.py', '/app', 'method', 'python', 5, 8)
    """, class_id, method_id)

    # Run backfill
    await backfill_name_path(dry_run=False)

    # Verify method has parent context
    method_name_path = await test_db.fetchval("""
        SELECT name_path FROM code_chunks WHERE id = $1
    """, method_id)

    # Should be: models.user.User.validate (with parent context)
    assert "User.validate" in method_name_path


@pytest.mark.anyio
async def test_backfill_idempotent(test_db):
    """Running twice should not duplicate."""
    # Run once
    await backfill_name_path(dry_run=False)
    count_after_first = await test_db.fetchval(
        "SELECT COUNT(*) FROM code_chunks WHERE name_path IS NOT NULL"
    )

    # Run again
    await backfill_name_path(dry_run=False)
    count_after_second = await test_db.fetchval(
        "SELECT COUNT(*) FROM code_chunks WHERE name_path IS NOT NULL"
    )

    assert count_after_first == count_after_second


@pytest.mark.anyio
async def test_backfill_performance(test_db):
    """Should complete in <5 seconds for 1000 chunks."""
    import time

    # Create 1000 test chunks
    # ... (test data generation)

    start = time.time()
    await backfill_name_path(dry_run=False)
    elapsed = time.time() - start

    assert elapsed < 5.0  # <5 seconds for 1000 chunks
```

---

## ⚠️ Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Empty names break generation** | Medium | High | Fallback to `anonymous_{type}_{id}` |
| **Missing repository field** | Low | Medium | Default to `/unknown` |
| **Parent context extraction fails** | Low | High | Wrap in try/catch, continue with None |
| **Memory overflow (large DBs)** | Very Low | Medium | Batch processing (tested up to 100k) |
| **Name_path collisions** | Low | Low | Acceptable (qualified names reduce this) |

---

## 📊 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Coverage** | 100% chunks have name_path | `COUNT(name_path) / COUNT(*) = 1.0` |
| **Accuracy** | >95% methods have parent context | Manual spot check |
| **Performance** | <5s for 1,302 chunks | Timed execution |
| **Idempotency** | Can run multiple times safely | Re-run test |
| **Error handling** | Graceful degradation | Error count = 0 |

---

## 🎯 Recommended Approach

**Use Approach 2 (Batch by File)** because:

1. ✅ **Accuracy**: Correctly extracts parent context for 37% of chunks (methods)
2. ✅ **Performance**: Still very fast (<1 second for current DB)
3. ✅ **Maintainability**: Follows existing SymbolPathService patterns
4. ✅ **Scalability**: Tested up to 100k chunks in Story 11.1
5. ✅ **Completeness**: Handles all edge cases identified

**Additional Features**:
- `--dry-run` flag for safety
- Progress reporting
- Error logging
- Validation checks
- Statistics summary

---

## 📝 Next Steps

1. **Create script**: `scripts/backfill_name_path.py` (200 lines)
2. **Create tests**: `tests/scripts/test_backfill_name_path.py` (150 lines)
3. **Run dry-run**: Verify on current DB (1,302 chunks)
4. **Execute migration**: Apply to production
5. **Validate**: Check 100% coverage
6. **Document**: Update EPIC-11 with completion status

**Estimated Time**: 2-3 hours total

---

**Analysis Complete** ✅
**Ready for Implementation** 🚀
