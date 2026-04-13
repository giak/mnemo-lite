# Outcome Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add outcome feedback system (rate_memory tool + outcome-based decay modulation) to MnemoLite

**Architecture:** Add columns to memories table (outcome_positive, outcome_negative, outcome_score, last_outcome_at), new MCP tool `rate_memory`, modify decay calculation to include outcome factor, update search_memory and get_memory_health.

**Tech Stack:** Python (FastMCP), PostgreSQL, asyncpg, SQLAlchemy

---

## File Structure Overview

```
api/alembic/versions/                          # Migration
  └── 20260410_0000_add_outcome_tracking.py    # NEW

api/db/repositories/
  └── memory_repository.py                      # MODIFY: add rate method

api/services/
  └── memory_decay_service.py                  # MODIFY: outcome factor

api/mnemo_mcp/
  ├── tools/
  │   └── memory_tools.py                      # MODIFY: add RateMemoryTool
  ├── models/
  │   └── memory_models.py                     # MODIFY: add outcome fields to response
  └── server.py                                # MODIFY: register new tool

tests/
  └── test_memory_decay_service.py             # NEW: test outcome factor
```

---

## Task 1: Alembic Migration

**Files:**
- Create: `api/alembic/versions/20260410_0000_add_outcome_tracking.py`

- [ ] **Step 1: Create migration file**

```python
# api/alembic/versions/20260410_0000_add_outcome_tracking.py
"""add_outcome_tracking_to_memories

Revision ID: 20260410_0000
Revises: 20260404_0000
Create Date: 2026-04-10
"""

from typing import Sequence, Union
from alembic import op


revision: str = "20260410_0000"
down_revision: Union[str, Sequence[str], None] = "20260404_0000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add outcome tracking columns to memories table."""
    op.execute("""
        ALTER TABLE memories 
        ADD COLUMN IF NOT EXISTS outcome_positive INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS outcome_negative INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS outcome_score FLOAT,
        ADD COLUMN IF NOT EXISTS last_outcome_at TIMESTAMPTZ
    """)
    
    # Index for frequent queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_outcome_score 
        ON memories(outcome_score) WHERE outcome_score IS NOT NULL
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_last_outcome 
        ON memories(last_outcome_at) WHERE last_outcome_at IS NOT NULL
    """)


def downgrade() -> None:
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

- [ ] **Step 2: Verify migration syntax**

Run: `python -c "import api.alembic.versions." 2>/dev/null || echo "Check manually"`
Expected: No syntax errors

- [ ] **Step 3: Commit**

```bash
git add api/alembic/versions/20260410_0000_add_outcome_tracking.py
git commit -m "feat: add outcome tracking columns to memories"
```

---

## Task 2: Memory Repository - rate method

**Files:**
- Modify: `api/db/repositories/memory_repository.py` (add new method after line 350)

- [ ] **Step 1: Add rate_memory method to repository**

```python
async def rate_memory(
    self,
    memory_id: str,
    helpful: bool,
    score: float | None = None,
) -> dict:
    """
    Rate a memory's helpfulness outcome.
    
    Args:
        memory_id: UUID of the memory to rate
        helpful: True = positive, False = negative
        score: Optional explicit score (-1.0 to 1.0)
    
    Returns:
        Dict with outcome fields after update
    """
    try:
        async with self.engine.begin() as conn:
            # Compute outcome_score if not provided explicitly
            explicit_score = score
            if explicit_score is None:
                explicit_score = 1.0 if helpful else -1.0
            
            result = await conn.execute(
                text("""
                    UPDATE memories
                    SET outcome_positive = outcome_positive + :positive_inc,
                        outcome_negative = outcome_negative + :negative_inc,
                        outcome_score = :score,
                        last_outcome_at = NOW()
                    WHERE id = :id
                      AND deleted_at IS NULL
                    RETURNING id, outcome_positive, outcome_negative, outcome_score, last_outcome_at
                """),
                {
                    "id": memory_id,
                    "positive_inc": 1 if helpful else 0,
                    "negative_inc": 0 if helpful else 1,
                    "score": explicit_score,
                }
            )
            
            row = result.fetchone()
            if not row:
                raise RepositoryError(f"Memory not found: {memory_id}")
            
            return {
                "id": str(row.id),
                "outcome_positive": row.outcome_positive,
                "outcome_negative": row.outcome_negative,
                "outcome_score": row.outcome_score,
                "last_outcome_at": row.last_outcome_at.isoformat() if row.last_outcome_at else None,
            }
    except RepositoryError:
        raise
    except Exception as e:
        raise RepositoryError(f"Failed to rate memory: {e}") from e
```

- [ ] **Step 2: Commit**

```bash
git add api/db/repositories/memory_repository.py
git commit -m "feat: add rate_memory method to MemoryRepository"
```

---

## Task 3: Memory Decay Service - outcome factor

**Files:**
- Modify: `api/services/memory_decay_service.py` (add outcome_factor method, use in compute_decay)

- [ ] **Step 1: Add outcome_factor method**

Add after line 54 (after `DEFAULT_DECAY_RATE`):

```python
def compute_outcome_factor(
    outcome_positive: int,
    outcome_negative: int,
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
    if outcome_positive == 0 and outcome_negative == 0:
        return 1.0
    
    total = outcome_positive + outcome_negative + 1
    ratio = (outcome_positive - outcome_negative) / total
    return 1 + 0.5 * ratio
```

- [ ] **Step 2: Modify apply_decay to accept outcome params**

Change signature of `apply_decay` to include optional outcome params:

```python
def apply_decay(
    self,
    relevance_score: float,
    created_at: datetime,
    decay_rate: Optional[float] = None,
    now: Optional[datetime] = None,
    outcome_positive: int = 0,
    outcome_negative: int = 0,
) -> float:
    # ... existing code ...
    
    # Get outcome factor
    outcome_factor = compute_outcome_factor(outcome_positive, outcome_negative)
    
    # Apply decay with outcome modulation
    decay = self.compute_decay(age_days, decay_rate)
    return relevance_score * decay * outcome_factor
```

- [ ] **Step 3: Commit**

```bash
git add api/services/memory_decay_service.py
git commit -m "feat: add outcome factor to decay calculation"
```

---

## Task 4: RateMemoryTool

**Files:**
- Modify: `api/mnemo_mcp/tools/memory_tools.py` (add RateMemoryTool class)

- [ ] **Step 1: Add RateMemoryTool class**

Add after MarkConsumedTool (around line 1185):

```python
class RateMemoryTool(BaseMCPComponent):
    """
    Tool for rating a memory's helpfulness outcome.
    
    Modulates the memory's decay rate based on outcome feedback.
    Memories with positive outcomes decay slower (stay relevant longer).
    Memories with negative outcomes decay faster (disappear quicker).
    
    Usage:
        # After retrieving a memory and using it successfully
        rate_memory(id="...", helpful=True)
        
        # After retrieving a memory that was not helpful
        rate_memory(id="...", helpful=False)
        
        # With explicit score
        rate_memory(id="...", helpful=True, score=0.8)
    """

    def get_name(self) -> str:
        return "rate_memory"

    async def execute(self, ctx: Context, **params) -> dict:
        """
        Rate a memory's helpfulness.

        Args:
            id: Memory UUID to rate
            helpful: True = positive outcome, False = negative outcome
            score: Optional explicit score (-1.0 to 1.0)

        Returns:
            Dict with id, outcome_positive, outcome_negative, outcome_score, last_outcome_at
        """
        memory_id = params.get("id")
        helpful = params.get("helpful")
        score = params.get("score")

        if not memory_id:
            raise ValueError("id is required")

        if helpful is None:
            raise ValueError("helpful is required")

        # Validate score range if provided
        if score is not None and (score < -1.0 or score > 1.0):
            raise ValueError("score must be between -1.0 and 1.0")

        try:
            # Get repository from services
            memory_repo = self._services.get("memory_repository")
            if not memory_repo:
                raise RuntimeError("Memory repository not available")

            result = await memory_repo.rate_memory(
                memory_id=memory_id,
                helpful=helpful,
                score=score,
            )

            logger.info(
                "memories.rate_memory",
                memory_id=memory_id,
                helpful=helpful,
                score=score,
                outcome_positive=result.get("outcome_positive"),
                outcome_negative=result.get("outcome_negative"),
            )

            return result

        except Exception as e:
            logger.error("Failed to rate memory", error=str(e), memory_id=memory_id)
            raise RuntimeError(f"Failed to rate memory: {e}") from e
```

- [ ] **Step 2: Create singleton and export**

Find where `mark_consumed_tool` is defined and add after it:

```python
# At module level, after other tool singletons
rate_memory_tool = RateMemoryTool(
    memory_repository=memory_repository,
    embedding_service=embedding_service,
)
```

- [ ] **Step 3: Commit**

```bash
git add api/mnemo_mcp/tools/memory_tools.py
git commit -m "feat: add RateMemoryTool for outcome feedback"
```

---

## Task 5: Register rate_memory in server.py

**Files:**
- Modify: `api/mnemo_mcp/server.py` (register the new tool)

- [ ] **Step 1: Import rate_memory_tool**

Find the import section (around line 37-58) and add:

```python
from mnemo_mcp.tools.memory_tools import (
    write_memory_tool,
    update_memory_tool,
    delete_memory_tool,
    search_memory_tool,
    read_memory_tool,
    consolidate_memory_tool,
    mark_consumed_tool,
    rate_memory_tool,  # NEW
)
```

- [ ] **Step 2: Add rate_memory endpoint**

Find where mark_consumed is registered (around line 1238) and add after it:

```python
@mcp.tool()
async def rate_memory(
    ctx: Context,
    id: str,
    helpful: bool,
    score: float | None = None,
) -> dict:
    """
    Rate a memory's helpfulness.

    Modulates the memory's decay rate based on outcome feedback.
    Memories with positive outcomes decay slower, negative outcomes decay faster.

    Args:
        id: Memory UUID to rate
        helpful: True = positive outcome, False = negative outcome
        score: Optional explicit score (-1.0 to 1.0)

    Returns:
        Dict with id, outcome_positive, outcome_negative, outcome_score, last_outcome_at

    Examples:
        - rate_memory(id="...", helpful=True)
        - rate_memory(id="...", helpful=False)
        - rate_memory(id="...", helpful=True, score=0.8)
    """
    return await rate_memory_tool.execute(
        ctx=ctx,
        id=id,
        helpful=helpful,
        score=score,
    )
```

- [ ] **Step 3: Commit**

```bash
git add api/mnemo_mcp/server.py
git commit -m "feat: register rate_memory tool in MCP server"
```

---

## Task 6: Modify search_memory to include outcome

**Files:**
- Modify: `api/mnemo_mcp/server.py` (add include_outcome param to search_memory)

- [ ] **Step 1: Add include_outcome param to search_memory**

Find the search_memory function (around line 1106) and add parameter:

```python
async def search_memory(
    ctx: Context,
    query: str | None = None,
    limit: int = 10,
    offset: int = 0,
    memory_type: str | None = None,
    tags: str | list[str] | None = None,
    consumed: bool | None = None,
    lifecycle_state: str | None = None,
    include_outcome: bool = False,  # NEW
) -> dict:
```

- [ ] **Step 2: Pass include_outcome to tool**

In the execute call, add the parameter:

```python
response = await search_memory_tool.execute(
    ctx=ctx,
    query=query,
    limit=limit,
    offset=offset,
    memory_type=memory_type,
    tags=tags,
    consumed=consumed,
    lifecycle_state=lifecycle_state,
    include_outcome=include_outcome,  # NEW
)
```

- [ ] **Step 3: Commit**

```bash
git add api/mnemo_mcp/server.py
git commit -m "feat: add include_outcome to search_memory"
```

---

## Task 7: Modify get_memory_health to include outcome metrics

**Files:**
- Modify: `api/mnemo_mcp/tools/analytics_tools.py`

- [ ] **Step 1: Update get_memory_health to query outcome stats**

Find get_memory_health_tool and modify the SQL query to include outcome stats:

```python
# In the SQL query that returns health stats, add:
outcome_stats = await conn.fetchrow("""
    SELECT 
        COUNT(*) FILTER (WHERE outcome_positive > 0 OR outcome_negative > 0) as rated_count,
        AVG(outcome_score) FILTER (WHERE outcome_score IS NOT NULL) as avg_score,
        COUNT(*) FILTER (WHERE outcome_positive > outcome_negative + 2) as positive_count,
        COUNT(*) FILTER (WHERE outcome_negative > outcome_positive + 2) as negative_count
    FROM memories 
    WHERE deleted_at IS NULL
""")

# Add to return dict:
result["outcome_metrics"] = {
    "rated_memories": outcome_stats["rated_count"],
    "avg_outcome_score": round(outcome_stats["avg_score"], 2) if outcome_stats["avg_score"] else None,
    "positive_count": outcome_stats["positive_count"],
    "negative_count": outcome_stats["negative_count"],
    "positive_rate": f"{round(100 * outcome_stats['positive_count'] / max(1, outcome_stats['rated_count']))}%" if outcome_stats["rated_count"] > 0 else "N/A",
}
```

- [ ] **Step 2: Commit**

```bash
git add api/mnemo_mcp/tools/analytics_tools.py
git commit -m "feat: add outcome metrics to get_memory_health"
```

---

## Task 8: Tests

**Files:**
- Create: `tests/test_memory_outcome.py`

- [ ] **Step 1: Write tests for compute_outcome_factor**

```python
import pytest
from services.memory_decay_service import MemoryDecayService


class TestComputeOutcomeFactor:
    def test_no_feedback_returns_1_0(self):
        result = MemoryDecayService.compute_outcome_factor(0, 0)
        assert result == 1.0
    
    def test_positive_feedback_increases_factor(self):
        result = MemoryDecayService.compute_outcome_factor(5, 0)
        assert 1.2 < result < 1.4
    
    def test_negative_feedback_decreases_factor(self):
        result = MemoryDecayService.compute_outcome_factor(0, 5)
        assert 0.6 < result < 0.8
    
    def test_mixed_feedback_balanced(self):
        result = MemoryDecayService.compute_outcome_factor(3, 2)
        assert 1.0 < result < 1.2
    
    def test_factor_bounds(self):
        # Maximum positive
        result = MemoryDecayService.compute_outcome_factor(100, 0)
        assert result < 1.5
        
        # Maximum negative
        result = MemoryDecayService.compute_outcome_factor(0, 100)
        assert result > 0.5
```

- [ ] **Step 2: Write test for rate_memory tool**

```python
import pytest
from mnemo_mcp.tools.memory_tools import RateMemoryTool


@pytest.fixture
def rate_memory_tool(memory_repository, embedding_service):
    return RateMemoryTool(
        memory_repository=memory_repository,
        embedding_service=embedding_service,
    )


@pytest.mark.asyncio
async def test_rate_memory_positive(rate_memory_tool, ctx):
    # First create a memory
    memory_id = "test-memory-uuid"
    
    result = await rate_memory_tool.execute(
        ctx=ctx,
        id=memory_id,
        helpful=True,
    )
    
    assert result["outcome_positive"] == 1
    assert result["outcome_negative"] == 0
    assert result["outcome_score"] == 1.0


@pytest.mark.asyncio
async def test_rate_memory_negative(rate_memory_tool, ctx):
    memory_id = "test-memory-uuid"
    
    result = await rate_memory_tool.execute(
        ctx=ctx,
        id=memory_id,
        helpful=False,
    )
    
    assert result["outcome_positive"] == 0
    assert result["outcome_negative"] == 1
    assert result["outcome_score"] == -1.0


@pytest.mark.asyncio
async def test_rate_memory_explicit_score(rate_memory_tool, ctx):
    memory_id = "test-memory-uuid"
    
    result = await rate_memory_tool.execute(
        ctx=ctx,
        id=memory_id,
        helpful=True,
        score=0.8,
    )
    
    assert result["outcome_score"] == 0.8


@pytest.mark.asyncio
async def test_rate_memory_invalid_score(rate_memory_tool, ctx):
    with pytest.raises(ValueError, match="score must be between"):
        await rate_memory_tool.execute(
            ctx=ctx,
            id="test",
            helpful=True,
            score=1.5,
        )
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_memory_outcome.py -v`
Expected: Tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_memory_outcome.py
git commit -m "test: add outcome feedback tests"
```

---

## Implementation Complete Checklist

- [ ] Task 1: Alembic Migration
- [ ] Task 2: Memory Repository - rate method
- [ ] Task 3: Memory Decay Service - outcome factor
- [ ] Task 4: RateMemoryTool
- [ ] Task 5: Register rate_memory in server.py
- [ ] Task 6: Modify search_memory to include outcome
- [ ] Task 7: Modify get_memory_health to include outcome metrics
- [ ] Task 8: Tests

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-10-outcome-feedback-plan.md`.**

**Two execution options:**

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?