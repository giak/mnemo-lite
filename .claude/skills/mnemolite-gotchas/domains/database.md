# Database Gotchas

**Purpose**: Database-specific patterns, schema, migrations, and optimization gotchas

**When to reference**: Working with PostgreSQL, migrations, or database performance

---

## 🟡 DB-01: Partitioning Currently Disabled

**Status**: Partitioning POSTPONED until 500k+ events

**Why**: Overhead > benefit at current scale (~50k events)

**When to enable**:
```bash
# Monitor events table size
SELECT count(*) FROM events;  # Enable at 500k+

# Activate partitioning
psql < db/scripts/enable_partitioning.sql
```

**Important**: After enabling partitioning:
1. Update PK to composite: `(id, timestamp)`
2. Create vector indexes per partition (not global)
3. Queries will auto-prune partitions (faster)

**Migration**: `db/scripts/enable_partitioning.sql` handles migration

---

## 🟡 DB-02: Vector Index Tuning

**Current**: HNSW indexes use `m=16, ef_construction=64`

**Tuning guidance**:
```sql
-- For recall > performance (research, high-quality results)
CREATE INDEX idx_embedding_high_recall ON events
USING hnsw (embedding vector_cosine_ops)
WITH (m = 32, ef_construction = 128);

-- For performance > recall (production, fast results)
CREATE INDEX idx_embedding_fast ON events
USING hnsw (embedding vector_cosine_ops)
WITH (m = 8, ef_construction = 32);

-- Current (balanced)
m=16, ef_construction=64
```

**Trade-off**:
- Higher `m` = better recall, larger index, slower build
- Higher `ef_construction` = better recall, much slower build
- Adjust based on use case

---

## 🟡 DB-03: SQL Complexity Calculation

**Rule**: Cast order matters for JSONB nested numeric extraction

```sql
-- ✅ CORRECT - Cast order: jsonb -> text -> numeric
SELECT AVG(((metadata->>'complexity')::jsonb->>'cyclomatic')::float)
FROM code_chunks;

-- ❌ WRONG - Will fail with type errors
SELECT AVG((metadata->>'complexity')->>'cyclomatic')::float)
```

**Why**: PostgreSQL requires explicit type conversions for nested JSONB

**Pattern**:
1. Extract with `->>` (returns text)
2. Cast to `::jsonb` if nested
3. Extract nested with `->>`
4. Cast final value to target type (`::float`, `::int`, etc.)

---

## 🟡 DB-04: Column Name Exactness

**Rule**: Schema column names must match EXACTLY (no abbreviations)

```sql
-- ✅ CORRECT
SELECT properties, relation_type FROM edges;

-- ❌ WRONG - Will fail
SELECT props, relationship FROM edges;
```

**Schema reference**:
- `nodes.properties` (NOT `props`)
- `edges.relation_type` (NOT `relationship` or `type`)
- `code_chunks.name_path` (NOT `qualified_name`)

**Detection**: "column does not exist" errors

**Fix**: Check schema in `db/init/01-init.sql` or `docs/bdd_schema.md`

---

## 🟡 DB-05: Migration Sequence

**Rule**: Migrations must be applied in order

**Current migration path**:
```
v1 (initial) → v2_to_v3.sql (content_hash) → v3_to_v4.sql (name_path) → v4_to_v5.sql (performance indexes)
```

**How to apply**:
```bash
# Check current version
psql -d mnemolite -c "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1;"

# Apply next migration
psql -d mnemolite < db/migrations/v3_to_v4.sql

# Verify
psql -d mnemolite -c "SELECT version, applied_at FROM schema_version;"
```

**Important**: Migrations are backward-compatible (can rollback)

---

**Total Database Gotchas**: 5
