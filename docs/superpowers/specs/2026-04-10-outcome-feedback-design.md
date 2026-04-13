# SPEC: Outcome Feedback System for MnemoLite

> **Date:** 2026-04-10
> **Feature:** Outcome Feedback (rate_memory)
> **Inspired by:** Hippo Memory outcome feedback loop
> **Priority:** High — aligné avec Expanse usage

---

## 1. Overview

### Problem Statement

MnemoLite currently tracks:
- **Consumption** (`consumed_at`, `consumed_by`) — when a memory was used
- **Decay configuration** (per-tag decay rates via `configure_decay`)

But it does **not track quality** — whether the retrieved memory was actually helpful to the agent.

### Solution

Add **outcome feedback** mechanism:
1. New MCP tool: `rate_memory(id, helpful, score)`
2. New columns in `memories` table: outcome counters and scores
3. Modified decay calculation: outcome factor modulates decay rate
4. Expanse integration: auto-rate memories based on user signals

### Benefits

- Memories with positive outcomes decay **slower** (stay relevant longer)
- Memories with negative outcomes decay **faster** (disappear quicker)
- Enables analytics: `avg_outcome_score`, `positive_rate`
- Aligns with Hippo Memory's outcome feedback innovation

---

## 2. Data Model

### New Columns in `memories` Table

```sql
ALTER TABLE memories ADD COLUMN:
  outcome_positive INTEGER DEFAULT 0,
  outcome_negative INTEGER DEFAULT 0,
  outcome_score FLOAT,
  last_outcome_at TIMESTAMPTZ;
```

### Schema

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `outcome_positive` | INTEGER | 0 | Cumulatif: nombre de ratings positifs |
| `outcome_negative` | INTEGER | 0 | Cumulatif: nombre de ratings négatifs |
| `outcome_score` | FLOAT | NULL | Dernier rating explicite (-1.0 à 1.0), nullable |
| `last_outcome_at` | TIMESTAMPTZ | NULL | Timestamp du dernier feedback |

### Indexes

```sql
CREATE INDEX idx_memories_outcome_score 
ON memories(outcome_score) WHERE outcome_score IS NOT NULL;

CREATE INDEX idx_memories_last_outcome 
ON memories(last_outcome_at) WHERE last_outcome_at IS NOT NULL;
```

### Rationale

Follows existing pattern (`consumed_at`, `consumed_by`):
- Simple, no JOIN needed for queries
- Counters are cumulative (like consumption tracking)
- Backward compatible: existing memories have neutral outcome (factor=1.0)

---

## 3. MCP Tools

### 3.1 New Tool: `rate_memory`

```python
@tool()
async def rate_memory(
    ctx: Context,
    id: str,                    # Memory UUID
    helpful: bool,               # True = positive, False = negative
    score: float | None = None,  # Optional: explicit score (-1.0 to 1.0)
) -> dict:
    """
    Rate a memory's helpfulness.
    
    Modulates the memory's decay rate based on outcome feedback.
    Memories with positive outcomes decay slower, negative outcomes decay faster.
    
    Args:
        id: Memory UUID to rate
        helpful: True = positive outcome, False = negative outcome  
        score: Optional explicit score (-1.0 = very unhelpful, 1.0 = very helpful)
               If provided, overrides the implicit score from `helpful`.
    
    Returns:
        Dict with:
        - id: memory UUID
        - outcome_positive: updated count
        - outcome_negative: updated count
        - outcome_score: explicit score or computed (-1.0 to 1.0)
        - last_outcome_at: timestamp
    
    Examples:
        - rate_memory(id="...", helpful=True)  # Implicit +1.0
        - rate_memory(id="...", helpful=False)  # Implicit -1.0
        - rate_memory(id="...", helpful=True, score=0.8)  # Explicit override
    """
```

### 3.2 Modified: `search_memory`

Add optional parameter `include_outcome: bool = False`.

When `True`, response includes:
```json
{
  "results": [
    {
      "id": "...",
      "outcome_positive": 5,
      "outcome_negative": 1,
      "outcome_score": 0.83,
      "last_outcome_at": "2026-04-10T12:00:00Z"
    }
  ]
}
```

### 3.3 Modified: `get_memory_health`

Add new metrics:
```json
{
  "avg_outcome_score": 0.73,
  "positive_count": 42,
  "negative_count": 8,
  "positive_rate": "84%"
}
```

---

## 4. Decay Calculation

### Formula

```python
def compute_outcome_factor(
    outcome_positive: int, 
    outcome_negative: int
) -> float:
    """
    Calculate reward factor based on outcome feedback.
    
    Formula: 1 + 0.5 * (pos - neg) / (pos + neg + 1)
    Range: (0.5, 1.5)
    
    Examples:
        (0, 0)  → 1.0   (no feedback, neutral)
        (5, 0)  → 1.33  (positive)
        (0, 5)  → 0.67  (negative)
        (10, 2) → 1.17  (mostly positive)
    """
    total = outcome_positive + outcome_negative + 1
    ratio = (outcome_positive - outcome_negative) / total
    return 1 + 0.5 * ratio
```

### Integration with Tag-Based Decay

```python
def compute_effective_decay_rate(
    base_decay_rate: float,  # From tag config
    outcome_positive: int,
    outcome_negative: int
) -> float:
    outcome_factor = compute_outcome_factor(outcome_positive, outcome_negative)
    return base_decay_rate * outcome_factor
```

### Examples

| Tag | Base Decay | Outcome | Effective Decay | Half-life |
|-----|------------|---------|-----------------|-----------|
| sys:anchor | 0.001 | (5, 0) → 1.33 | 0.00075 | ~924 days (3x longer) |
| sys:anchor | 0.001 | (0, 5) → 0.67 | 0.0015 | ~462 days (2x shorter) |
| trace:fresh | 0.08 | (3, 0) → 1.2 | 0.067 | ~10 days |
| trace:fresh | 0.08 | (0, 3) → 0.8 | 0.1 | ~7 days |

---

## 5. Expanse Integration

### 5.1 Workflow

**Current (without outcome):**
```
1. search_memory(query=Σ_input, limit=3)
2. Response with Ω
3. Si "merci/ok" → mark_consumed(memory_ids=[...])
```

**With outcome feedback:**
```
1. search_memory(query=Σ_input, limit=3)
2. Response with Ω
3. Si "merci/ok" → rate_memory(id, helpful=True)
4. Si "non/faux/pas ça" → rate_memory(id, helpful=False)
```

### 5.2 Auto-Tagging

Based on outcome ratio:

```python
def get_outcome_tags(outcome_positive: int, outcome_negative: int) -> list[str]:
    diff = outcome_positive - outcome_negative
    
    if outcome_positive > 0 and diff >= 3:
        return ["sys:outcome:positive"]
    elif outcome_negative > 0 and diff <= -3:
        return ["sys:outcome:negative"]
    return []
```

### 5.3 Dashboard Updates

In `expanse-dashboard.html`, add to Mnemolite metrics:

```html
<div class="m"><span class="l">Avg Outcome</span><span class="v">{AVG_OUTCOME_SCORE}</span></div>
<div class="m"><span class="l">Positive Rate</span><span class="v ok">{POSITIVE_RATE}</span></div>
```

---

## 6. Migration

### Alembic Migration

```python
# api/alembic/versions/20260410_0000_add_outcome_tracking.py

revision = "20260410_0000"
down_revision = "20260404_0000"


def upgrade():
    # Add outcome tracking columns
    op.execute("""
        ALTER TABLE memories 
        ADD COLUMN outcome_positive INTEGER DEFAULT 0,
        ADD COLUMN outcome_negative INTEGER DEFAULT 0,
        ADD COLUMN outcome_score FLOAT,
        ADD COLUMN last_outcome_at TIMESTAMPTZ
    """)
    
    # Indexes for frequent queries
    op.execute("""
        CREATE INDEX idx_memories_outcome_score 
        ON memories(outcome_score) WHERE outcome_score IS NOT NULL
    """)
    
    op.execute("""
        CREATE INDEX idx_memories_last_outcome 
        ON memories(last_outcome_at) WHERE last_outcome_at IS NOT NULL
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_memories_last_outcome")
    op.execute("DROP INDEX IF EXISTS idx_memories_outcome_score")
    
    op.execute("""
        ALTER TABLE memories 
        DROP COLUMN IF EXISTS last_outcome_at,
        DROP COLUMN IF EXISTS outcome_score,
        DROP COLUMN IF EXISTS outcome_negative,
        DROP COLUMN IF EXISTS outcome_positive
    """)
```

### Backward Compatibility

- **Zero breaking changes** — All new columns are nullable with defaults
- **Existing memories** — `outcome_positive=0, outcome_negative=0` → outcome_factor=1.0
- **API compatible** — Returns new columns only if requested

---

## 7. Error Handling

### Error Cases

| Scenario | Behavior |
|----------|----------|
| Memory not found | Raise `ValueError("Memory not found or deleted")` |
| Invalid score range | Raise `ValueError("score must be between -1.0 and 1.0")` |
| Rating consumed memory | Allow (memory can have multiple ratings over time) |
| Rating soft-deleted memory | Allow (can still rate deleted memories) |

### Rate Limiting

- Maximum **100 ratings** per memory per day
- Log warning if exceeded

### Self-Rating Prevention

- Agent cannot rate memories it created (if `author` matches)
- Silently ignore self-ratings

---

## 8. Implementation Checklist

- [ ] Create Alembic migration
- [ ] Add columns to Memory model
- [ ] Implement `rate_memory` tool
- [ ] Update `search_memory` with `include_outcome`
- [ ] Update `get_memory_health` with outcome metrics
- [ ] Modify `MemoryDecayService` with outcome factor
- [ ] Add auto-tagging logic
- [ ] Update Expanse documentation for new workflow
- [ ] Write tests

---

## 9. References

- Hippo Memory: `src/memory.ts` — outcome tracking implementation
- MnemoLite: `api/services/memory_decay_service.py` — existing decay logic
- Expanse: `v16/runtime/expanse-dream.md` — Dream workflow
- Previous migration: `20260327_2315-c4d7f2a8e102_add_consumption_tracking_to_memories.py`

---

*End of SPEC*