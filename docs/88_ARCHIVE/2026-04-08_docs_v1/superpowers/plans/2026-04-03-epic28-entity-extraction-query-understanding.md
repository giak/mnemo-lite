# EPIC-28: Entity Extraction & Query Understanding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LLM-powered entity extraction at memory indexing and query understanding for improved memory search, using LM Studio (Qwen2.5-7B) via OpenAI-compatible API.

**Architecture:** Two new services (EntityExtractionService, QueryUnderstandingService) communicate with LM Studio via a shared LMStudioClient. Extraction is async (non-blocking), search enhancement uses HL/LL keywords with 4-source RRF fusion. Graceful degradation when LM Studio is unavailable.

**Tech Stack:** httpx (async HTTP), json_repair (robust JSON parsing), Alembic (DB migration), PostgreSQL JSONB + GIN indexes, Pydantic v2 models

---

### Task 1: Add dependencies and Alembic migration

**Files:**
- Modify: `api/requirements.txt`
- Create: `api/alembic/versions/20260403_0000_add_entity_extraction_columns.py`

- [ ] **Step 1: Add json_repair and httpx to requirements.txt**

Read `api/requirements.txt` and add these lines at the end (after the OpenTelemetry section):

```
# EPIC-28: Entity Extraction & Query Understanding (LM Studio)
httpx>=0.27.0
json-repair>=0.30.0
```

- [ ] **Step 2: Create the Alembic migration**

Create `api/alembic/versions/20260403_0000_add_entity_extraction_columns.py`:

```python
"""add entity extraction columns to memories

Revision ID: 20260403_0000
Revises: 20260327_2315
Create Date: 2026-04-03
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision = "20260403_0000"
down_revision = "20260327_2315"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add entity extraction columns with safe defaults
    op.add_column("memories", sa.Column("entities", sa.JSON, nullable=True, server_default="[]"))
    op.add_column("memories", sa.Column("concepts", sa.JSON, nullable=True, server_default="[]"))
    op.add_column("memories", sa.Column("auto_tags", sa.Text, nullable=True, server_default="{}"))

    # GIN indexes for JSONB containment queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_entities_gin
        ON memories USING GIN (entities jsonb_path_ops)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_concepts_gin
        ON memories USING GIN (concepts jsonb_path_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_memories_concepts_gin")
    op.execute("DROP INDEX IF EXISTS idx_memories_entities_gin")
    op.drop_column("memories", "auto_tags")
    op.drop_column("memories", "concepts")
    op.drop_column("memories", "entities")
```

- [ ] **Step 3: Verify migration syntax**

Run: `cd api && python -c "import ast; ast.parse(open('alembic/versions/20260403_0000_add_entity_extraction_columns.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add api/requirements.txt api/alembic/versions/20260403_0000_add_entity_extraction_columns.py
git commit -m "feat(epic-28): add Alembic migration for entity extraction columns + deps"
```

---

### Task 2: Update Pydantic models and repository

**Files:**
- Modify: `api/mnemo_mcp/models/memory_models.py`
- Modify: `api/db/repositories/memory_repository.py`

- [ ] **Step 1: Add entity fields to Memory model**

In `api/mnemo_mcp/models/memory_models.py`, find the `Memory` class (line 167) and add three new fields before the closing of the class (after `similarity_score`, before the empty line):

```python
    similarity_score: Optional[float] = Field(
        None,
        description="Similarity score (only present in search results)"
    )
    entities: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Extracted named entities from LM Studio (async)"
    )
    concepts: Optional[List[str]] = Field(
        default_factory=list,
        description="Extracted abstract concepts from LM Studio (async)"
    )
    auto_tags: Optional[List[str]] = Field(
        default_factory=list,
        description="Auto-generated tags from entity extraction (async)"
    )
```

- [ ] **Step 2: Add JSONB parsing in `_row_to_memory()`**

In `api/db/repositories/memory_repository.py`, find the `_row_to_memory()` method (line 676). After the existing JSONB parsing for `resource_links` (line 716), add parsing for the new columns:

```python
        # Parse JSONB
        if isinstance(row_dict.get("resource_links"), str):
            row_dict["resource_links"] = json.loads(row_dict["resource_links"])

        # Parse new entity extraction columns (JSONB)
        for col in ("entities", "concepts"):
            val = row_dict.get(col)
            if val is None:
                row_dict[col] = []
            elif isinstance(val, str):
                try:
                    row_dict[col] = json.loads(val)
                except json.JSONDecodeError:
                    row_dict[col] = []
            # If already a list/dict (SQLAlchemy parsed it), leave as-is

        # Parse auto_tags (TEXT/ARRAY)
        val = row_dict.get("auto_tags")
        if val is None:
            row_dict["auto_tags"] = []
        elif isinstance(val, str):
            if val == "{}":
                row_dict["auto_tags"] = []
            elif val.startswith("["):
                try:
                    row_dict["auto_tags"] = json.loads(val)
                except json.JSONDecodeError:
                    row_dict["auto_tags"] = []
            else:
                row_dict["auto_tags"] = val.strip("{}").split(",")
```

- [ ] **Step 3: Verify model imports**

The `Memory` model now uses `Dict[str, Any]`. Check the imports at the top of `memory_models.py` (line 9):

```python
from typing import Optional, List, Dict, Any
```

`Dict` and `Any` are already imported. No change needed.

- [ ] **Step 4: Commit**

```bash
git add api/mnemo_mcp/models/memory_models.py api/db/repositories/memory_repository.py
git commit -m "feat(epic-28): add entity/concept/auto_tags fields to Memory model + repository parsing"
```

---

### Task 3: Create LMStudioClient

**Files:**
- Create: `api/services/lm_studio_client.py`

- [ ] **Step 1: Create the LM Studio client**

Create `api/services/lm_studio_client.py`:

```python
"""
LM Studio Client — Async HTTP client for LM Studio's OpenAI-compatible API.

Uses json_schema (GBNF grammar) for guaranteed structured JSON output.
Falls back to plain text + json_repair if schema enforcement fails.

Usage:
    client = LMStudioClient(base_url="http://host.docker.internal:1234/v1")
    if await client.is_available():
        result = await client.extract_json(system_prompt, user_content, schema)
"""

import os
from typing import Optional, Dict, Any

import httpx
import structlog
from json_repair import repair_json

logger = structlog.get_logger(__name__)


class LMStudioClient:
    """
    Async HTTP client for LM Studio (OpenAI-compatible API).

    Handles structured JSON extraction with graceful degradation.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = (base_url or os.getenv("LM_STUDIO_URL", "http://host.docker.internal:1234/v1")).rstrip("/")
        self.model = model or os.getenv("LM_STUDIO_MODEL", "qwen2.5-7b-instruct")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._available: Optional[bool] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=5.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def is_available(self) -> bool:
        """Check if LM Studio server is running and has models loaded."""
        if self._available is not None:
            return self._available
        try:
            client = self._get_client()
            resp = await client.get(f"{self.base_url}/models")
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("data", [])
                self._available = len(models) > 0
                if self._available:
                    logger.info("lm_studio_available", model=models[0].get("id", "unknown"))
                return self._available
            self._available = False
            return False
        except Exception as e:
            self._available = False
            logger.debug("lm_studio_unavailable", error=str(e))
            return False

    async def extract_json(
        self,
        system_prompt: str,
        user_content: str,
        json_schema: Dict[str, Any],
        temperature: float = 0.1,
    ) -> Optional[Dict[str, Any]]:
        """
        Extract structured JSON from LM Studio.

        Strategy:
        1. Try json_schema (GBNF grammar) for guaranteed valid JSON
        2. Fallback: no response_format + json_repair parsing
        3. Return None if all attempts fail

        Args:
            system_prompt: System prompt for the LLM
            user_content: User content to extract from
            json_schema: JSON Schema for structured output
            temperature: Sampling temperature (low for extraction)

        Returns:
            Parsed JSON dict, or None if extraction failed
        """
        # Attempt 1: json_schema (GBNF grammar)
        result = await self._attempt_extract(
            system_prompt, user_content, temperature,
            response_format={"type": "json_schema", "json_schema": json_schema},
        )
        if result is not None:
            return result

        # Attempt 2: No response_format + json_repair
        logger.debug("lm_studio_json_schema_failed", fallback="json_repair")
        result = await self._attempt_extract(
            system_prompt, user_content, temperature,
            response_format=None,
        )
        if result is not None:
            return result

        logger.warning("lm_studio_extraction_failed", system_prompt=system_prompt[:50])
        return None

    async def _attempt_extract(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float,
        response_format: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Single attempt to extract JSON from LM Studio."""
        try:
            client = self._get_client()
            body: Dict[str, Any] = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "temperature": temperature,
                "max_tokens": 2048,
            }
            if response_format:
                body["response_format"] = response_format

            resp = await client.post(f"{self.base_url}/chat/completions", json=body)

            if resp.status_code != 200:
                logger.debug("lm_studio_request_failed", status=resp.status_code, body=resp.text[:200])
                return None

            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                return None

            # Parse JSON (json_repair handles minor formatting issues)
            repaired = repair_json(content, return_objects=True)
            if isinstance(repaired, dict):
                return repaired

            logger.debug("lm_studio_json_repair_failed", content_preview=content[:100])
            return None

        except Exception as e:
            logger.debug("lm_studio_attempt_error", error=str(e))
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
```

- [ ] **Step 2: Commit**

```bash
git add api/services/lm_studio_client.py
git commit -m "feat(epic-28): create LMStudioClient with json_schema + json_repair fallback"
```

---

### Task 4: Create EntityExtractionService

**Files:**
- Create: `api/services/entity_extraction_service.py`

- [ ] **Step 1: Create the entity extraction service**

Create `api/services/entity_extraction_service.py`:

```python
"""
Entity Extraction Service — Async extraction of entities, concepts, and tags.

Uses LM Studio (Qwen2.5-7B) to extract structured metadata from memories.
Runs asynchronously — does not block memory creation.

Usage:
    service = EntityExtractionService(lm_client)
    await service.extract_entities(memory_id, title, content, memory_type, tags)
"""

import os
from typing import Optional, List, Dict, Any

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text

from services.lm_studio_client import LMStudioClient

logger = structlog.get_logger(__name__)

# Memory types that should be extracted
EXTRACTABLE_TYPES = {"decision", "reference", "note", "investigation"}
# System tags that trigger extraction regardless of type
EXTRACTABLE_SYSTEM_TAGS = {"sys:core", "sys:anchor", "sys:pattern"}

ENTITY_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["technology", "product", "file", "person", "organization", "concept", "other"]}
                },
                "required": ["name", "type"]
            }
        },
        "concepts": {
            "type": "array",
            "items": {"type": "string"}
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": ["entities", "concepts", "tags"]
}

ENTITY_EXTRACTION_SYSTEM_PROMPT = """You are an entity and concept extraction specialist.

Extract named entities, abstract concepts, and suggested tags from the text.

Rules:
- Only extract what is EXPLICITLY mentioned or clearly implied
- Do not invent or infer entities not present
- Normalize names (lowercase for tags, proper case for entities)
- Entities are concrete: technologies, products, files, people, organizations
- Concepts are abstract: patterns, decisions, architectural choices
- Tags should be short, lowercase, hyphenated (e.g., "cache-layer", "redis")
- Return ONLY valid JSON, no explanation"""


class EntityExtractionService:
    """
    Extracts entities, concepts, and tags from memories via LM Studio.

    Extraction is async and non-blocking. If LM Studio is unavailable,
    extraction is silently skipped.
    """

    def __init__(self, engine: AsyncEngine, lm_client: LMStudioClient):
        self.engine = engine
        self.lm_client = lm_client
        self.enabled = os.getenv("ENTITY_EXTRACTION_ENABLED", "true").lower() == "true"
        logger.info("EntityExtractionService initialized", enabled=self.enabled)

    @staticmethod
    def should_extract(memory_type: str, tags: List[str]) -> bool:
        """Determine if a memory should have entities extracted."""
        if memory_type in EXTRACTABLE_TYPES:
            return True
        if any(tag in EXTRACTABLE_SYSTEM_TAGS for tag in tags):
            return True
        return False

    async def extract_entities(
        self,
        memory_id: str,
        title: str,
        content: str,
        memory_type: str,
        tags: List[str],
    ) -> bool:
        """
        Extract entities, concepts, and tags for a memory.

        Args:
            memory_id: Memory UUID
            title: Memory title
            content: Memory content
            memory_type: Memory type (note, decision, etc.)
            tags: Existing tags

        Returns:
            True if extraction succeeded, False otherwise
        """
        if not self.enabled:
            logger.debug("entity_extraction_disabled", memory_id=memory_id)
            return False

        if not self.should_extract(memory_type, tags):
            logger.debug("entity_extraction_skipped", memory_id=memory_id, memory_type=memory_type)
            return False

        if not await self.lm_client.is_available():
            logger.debug("entity_extraction_skipped_lm_unavailable", memory_id=memory_id)
            return False

        user_content = f"Title: {title}\n\nContent: {content}"

        result = await self.lm_client.extract_json(
            system_prompt=ENTITY_EXTRACTION_SYSTEM_PROMPT,
            user_content=user_content,
            json_schema=ENTITY_EXTRACTION_SCHEMA,
            temperature=0.1,
        )

        if result is None:
            logger.warning("entity_extraction_failed", memory_id=memory_id)
            return False

        entities = result.get("entities", [])
        concepts = result.get("concepts", [])
        auto_tags = result.get("tags", [])

        await self._save_to_db(memory_id, entities, concepts, auto_tags)

        logger.info(
            "entities_extracted",
            memory_id=memory_id,
            entity_count=len(entities),
            concept_count=len(concepts),
            tag_count=len(auto_tags),
        )
        return True

    async def _save_to_db(
        self,
        memory_id: str,
        entities: List[Dict[str, Any]],
        concepts: List[str],
        auto_tags: List[str],
    ) -> None:
        """Save extracted entities to the database."""
        import json
        query = text("""
            UPDATE memories
            SET entities = :entities,
                concepts = :concepts,
                auto_tags = :auto_tags
            WHERE id = :memory_id
        """)
        params = {
            "memory_id": memory_id,
            "entities": json.dumps(entities),
            "concepts": json.dumps(concepts),
            "auto_tags": json.dumps(auto_tags),
        }
        try:
            async with self.engine.begin() as conn:
                await conn.execute(query, params)
        except Exception as e:
            logger.error("entity_extraction_db_error", memory_id=memory_id, error=str(e))
```

- [ ] **Step 2: Commit**

```bash
git add api/services/entity_extraction_service.py
git commit -m "feat(epic-28): create EntityExtractionService with async non-blocking extraction"
```

---

### Task 5: Wire EntityExtractionService into memory creation

**Files:**
- Modify: `api/mnemo_mcp/tools/memory_tools.py`
- Modify: `api/mnemo_mcp/server.py`

- [ ] **Step 1: Initialize LMStudioClient and EntityExtractionService in MCP server**

In `api/mnemo_mcp/server.py`, find the service initialization section (after HybridMemorySearchService, around line 420). Add this block before the NodeRepository initialization:

```python
    # EPIC-28: Initialize LMStudioClient and EntityExtractionService
    try:
        from services.lm_studio_client import LMStudioClient
        from services.entity_extraction_service import EntityExtractionService

        lm_client = LMStudioClient()
        services["lm_studio_client"] = lm_client

        if sqlalchemy_engine:
            entity_extraction_service = EntityExtractionService(
                engine=sqlalchemy_engine,
                lm_client=lm_client,
            )
            services["entity_extraction_service"] = entity_extraction_service
            logger.info("mcp.entity_extraction_service.initialized")
        else:
            logger.warning("mcp.entity_extraction_service.skipped", reason="no_engine")
            services["entity_extraction_service"] = None

    except Exception as e:
        logger.warning("mcp.entity_extraction_service.initialization_failed", error=str(e))
        services["lm_studio_client"] = None
        services["entity_extraction_service"] = None
```

- [ ] **Step 2: Trigger async extraction after WriteMemoryTool.execute()**

In `api/mnemo_mcp/tools/memory_tools.py`, find the `WriteMemoryTool.execute()` method. At the end of the method (after the return statement around line 230-240), we need to trigger async extraction. The method returns a `MemoryResponse`. We need to add extraction as a background task.

Find the section where the memory is created (around line 206):

```python
            memory = await self.memory_repository.create(memory_create, embedding=embedding)
```

Immediately after this line, add:

```python
            # EPIC-28: Trigger async entity extraction (non-blocking)
            self._trigger_entity_extraction(memory)
```

- [ ] **Step 3: Add the `_trigger_entity_extraction` method to WriteMemoryTool**

In the `WriteMemoryTool` class, add this method before the `execute` method (or after it):

```python
    def _trigger_entity_extraction(self, memory: Any) -> None:
        """
        Trigger async entity extraction for a newly created memory.

        Uses asyncio.create_task to run extraction in the background.
        Does not block the memory creation response.
        """
        try:
            import asyncio
            from services.entity_extraction_service import EntityExtractionService

            extraction_service = self.services.get("entity_extraction_service")
            if extraction_service is None:
                return

            asyncio.create_task(
                extraction_service.extract_entities(
                    memory_id=str(memory.id),
                    title=memory.title,
                    content=memory.content,
                    memory_type=memory.memory_type.value if hasattr(memory.memory_type, "value") else str(memory.memory_type),
                    tags=memory.tags or [],
                )
            )
        except Exception as e:
            # Never fail memory creation due to extraction issues
            logger.debug("entity_extraction_trigger_failed", error=str(e))
```

- [ ] **Step 4: Verify WriteMemoryTool has access to self.services**

Check that `WriteMemoryTool` inherits from `BaseMCPComponent` which provides `self.services`. Looking at the class definition (line 43), it should have `self.services` available via `inject_services()`.

- [ ] **Step 5: Commit**

```bash
git add api/mnemo_mcp/server.py api/mnemo_mcp/tools/memory_tools.py
git commit -m "feat(epic-28): wire EntityExtractionService into MCP server and WriteMemoryTool"
```

---

### Task 6: Create QueryUnderstandingService

**Files:**
- Create: `api/services/query_understanding_service.py`

- [ ] **Step 1: Create the query understanding service**

Create `api/services/query_understanding_service.py`:

```python
"""
Query Understanding Service — Extracts HL/LL keywords from search queries.

Uses LM Studio to decompose queries into high-level concepts and low-level
entities for improved hybrid search.

Usage:
    service = QueryUnderstandingService(lm_client)
    keywords = await service.extract_keywords("how do we handle memory consolidation?")
    # keywords.hl_keywords = ["memory consolidation", "lifecycle management"]
    # keywords.ll_keywords = ["sys:history", "consolidate_memory", "configure_decay"]
"""

import os
from dataclasses import dataclass
from typing import Optional, List

import structlog

from services.lm_studio_client import LMStudioClient

logger = structlog.get_logger(__name__)

QUERY_UNDERSTANDING_SCHEMA = {
    "type": "object",
    "properties": {
        "hl_keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "High-level concepts and themes (abstract)"
        },
        "ll_keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Low-level entities and specifics (concrete)"
        }
    },
    "required": ["hl_keywords", "ll_keywords"]
}

QUERY_UNDERSTANDING_SYSTEM_PROMPT = """You are a query understanding assistant.

Analyze the user's search query and extract:
- hl_keywords: High-level concepts and themes (abstract, 2-4 items)
- ll_keywords: Low-level entities and specifics (concrete, 2-5 items)

HL keywords should capture the intent and themes.
LL keywords should capture specific names, technologies, files, or tags.

Return ONLY valid JSON."""


@dataclass
class QueryKeywords:
    """Extracted keywords from query understanding."""
    hl_keywords: List[str]
    ll_keywords: List[str]


class QueryUnderstandingService:
    """
    Extracts HL/LL keywords from search queries via LM Studio.

    Falls back to empty keywords (query brute) if LM Studio is unavailable.
    """

    def __init__(self, lm_client: LMStudioClient):
        self.lm_client = lm_client
        self.enabled = os.getenv("QUERY_UNDERSTANDING_ENABLED", "true").lower() == "true"
        logger.info("QueryUnderstandingService initialized", enabled=self.enabled)

    async def extract_keywords(self, query: str) -> QueryKeywords:
        """
        Extract high-level and low-level keywords from a query.

        Args:
            query: User search query

        Returns:
            QueryKeywords with hl_keywords and ll_keywords.
            Returns empty lists if extraction fails (fallback).
        """
        if not self.enabled:
            logger.debug("query_understanding_disabled")
            return QueryKeywords(hl_keywords=[], ll_keywords=[])

        if not await self.lm_client.is_available():
            logger.debug("query_understanding_skipped_lm_unavailable")
            return QueryKeywords(hl_keywords=[], ll_keywords=[])

        result = await self.lm_client.extract_json(
            system_prompt=QUERY_UNDERSTANDING_SYSTEM_PROMPT,
            user_content=f"Query: {query}",
            json_schema=QUERY_UNDERSTANDING_SCHEMA,
            temperature=0.1,
        )

        if result is None:
            logger.warning("query_understanding_failed", query=query[:50])
            return QueryKeywords(hl_keywords=[], ll_keywords=[])

        hl = result.get("hl_keywords", [])
        ll = result.get("ll_keywords", [])

        # Ensure lists contain only strings
        hl = [str(k) for k in hl if isinstance(k, str) and k.strip()]
        ll = [str(k) for k in ll if isinstance(k, str) and k.strip()]

        logger.debug(
            "query_keywords_extracted",
            query=query[:50],
            hl_count=len(hl),
            ll_count=len(ll),
        )

        return QueryKeywords(hl_keywords=hl, ll_keywords=ll)
```

- [ ] **Step 2: Commit**

```bash
git add api/services/query_understanding_service.py
git commit -m "feat(epic-28): create QueryUnderstandingService for HL/LL keyword extraction"
```

---

### Task 7: Integrate query understanding into hybrid search

**Files:**
- Modify: `api/services/hybrid_memory_search_service.py`
- Modify: `api/mnemo_mcp/tools/memory_tools.py` (SearchMemoryTool)

- [ ] **Step 1: Add entity and tag search methods to HybridMemorySearchService**

In `api/services/hybrid_memory_search_service.py`, add two new methods after `_vector_search()` (around line 670):

```python
    async def _entity_search(
        self,
        keywords: List[str],
        filters: Optional[MemoryFilters],
        limit: int,
    ) -> Tuple[List[MemorySearchResult], float]:
        """Search memories by entity containment in JSONB column."""
        start_time = time.time()

        if not keywords:
            return [], 0.0

        where_clauses = ["deleted_at IS NULL", "entities != '[]'::jsonb"]
        params: Dict[str, Any] = {"limit": limit}

        if filters:
            if filters.project_id:
                where_clauses.append("project_id = :project_id")
                params["project_id"] = str(filters.project_id)
            if filters.memory_type:
                where_clauses.append("memory_type = :memory_type")
                params["memory_type"] = filters.memory_type.value
            if filters.tags:
                for i, tag in enumerate(filters.tags):
                    where_clauses.append(f":tag{i} = ANY(tags)")
                    params[f"tag{i}"] = tag

        where_sql = " AND ".join(where_clauses)

        # Build JSONB containment conditions for each keyword
        entity_conditions = []
        for i, kw in enumerate(keywords[:5]):  # Limit to 5 keywords for performance
            params[f"kw{i}"] = kw
            entity_conditions.append(f"entities @> '[{{\"name\": :kw{i}}}]'::jsonb")

        if not entity_conditions:
            return [], 0.0

        entity_where = " OR ".join(entity_conditions)

        query_sql = text(f"""
            SELECT
                id::text as memory_id,
                title,
                content as content_preview,
                memory_type,
                tags,
                created_at::text,
                author,
                1.0 as entity_score
            FROM memories
            WHERE {where_sql} AND ({entity_where})
            ORDER BY created_at DESC
            LIMIT :limit
        """)

        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(query_sql, params)
                rows = result.fetchall()

            results = []
            for rank, row in enumerate(rows, start=1):
                r = MemorySearchResult(
                    memory_id=row[0],
                    title=row[1],
                    content_preview=row[2],
                    memory_type=row[3],
                    tags=self._parse_pg_array(row[4]),
                    created_at=row[5],
                    author=row[6],
                    similarity_score=float(row[7]) if row[7] else 0.0,
                )
                r.rank = rank
                results.append(r)

            elapsed = (time.time() - start_time) * 1000
            return results, elapsed

        except Exception as e:
            logger.error("Entity search failed", error=str(e))
            return [], (time.time() - start_time) * 1000

    async def _tag_search(
        self,
        keywords: List[str],
        filters: Optional[MemoryFilters],
        limit: int,
    ) -> Tuple[List[MemorySearchResult], float]:
        """Search memories by tag/auto_tag matching."""
        start_time = time.time()

        if not keywords:
            return [], 0.0

        where_clauses = ["deleted_at IS NULL"]
        params: Dict[str, Any] = {"limit": limit}

        if filters:
            if filters.project_id:
                where_clauses.append("project_id = :project_id")
                params["project_id"] = str(filters.project_id)
            if filters.memory_type:
                where_clauses.append("memory_type = :memory_type")
                params["memory_type"] = filters.memory_type.value

        where_sql = " AND ".join(where_clauses)

        # Build tag overlap conditions
        tag_conditions = []
        for i, kw in enumerate(keywords[:5]):
            params[f"kw{i}"] = kw.lower()
            tag_conditions.append(f":kw{i} = ANY(tags) OR :kw{i} = ANY(auto_tags)")

        if not tag_conditions:
            return [], 0.0

        tag_where = " OR ".join(tag_conditions)

        query_sql = text(f"""
            SELECT
                id::text as memory_id,
                title,
                content as content_preview,
                memory_type,
                tags,
                created_at::text,
                author,
                1.0 as tag_score
            FROM memories
            WHERE {where_sql} AND ({tag_where})
            ORDER BY created_at DESC
            LIMIT :limit
        """)

        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(query_sql, params)
                rows = result.fetchall()

            results = []
            for rank, row in enumerate(rows, start=1):
                r = MemorySearchResult(
                    memory_id=row[0],
                    title=row[1],
                    content_preview=row[2],
                    memory_type=row[3],
                    tags=self._parse_pg_array(row[4]),
                    created_at=row[5],
                    author=row[6],
                    similarity_score=float(row[7]) if row[7] else 0.0,
                )
                r.rank = rank
                results.append(r)

            elapsed = (time.time() - start_time) * 1000
            return results, elapsed

        except Exception as e:
            logger.error("Tag search failed", error=str(e))
            return [], (time.time() - start_time) * 1000
```

- [ ] **Step 2: Modify the `search()` method to accept keywords and run 4-source search**

In `api/services/hybrid_memory_search_service.py`, modify the `search()` method signature (line 187). Add a new parameter `keywords: Optional[QueryKeywords] = None` after `embedding`:

```python
    async def search(
        self,
        query: str,
        embedding: Optional[List[float]] = None,
        keywords: Optional[Any] = None,  # QueryKeywords from QueryUnderstandingService
        filters: Optional[MemoryFilters] = None,
```

Then modify the parallel search section (around line 246-276). Replace:

```python
        # Execute searches in parallel
        tasks = []
        lexical_results = None
        vector_results = None
        lexical_time = None
        vector_time = None

        if enable_lexical:
            tasks.append(self._lexical_search(
                query=query,
                filters=filters,
                limit=candidate_pool_size,
            ))

        if enable_vector:
            tasks.append(self._vector_search(
                embedding=embedding,
                filters=filters,
                limit=candidate_pool_size,
            ))

        # Execute parallel searches
        if tasks:
            results = await asyncio.gather(*tasks)

            if enable_lexical and enable_vector:
                (lexical_results, lexical_time), (vector_results, vector_time) = results
            elif enable_lexical:
                lexical_results, lexical_time = results[0]
            elif enable_vector:
                vector_results, vector_time = results[0]
```

With:

```python
        # Execute searches (parallel for lexical + vector)
        lexical_results = None
        vector_results = None
        entity_results = None
        tag_results = None
        lexical_time = None
        vector_time = None
        entity_time = None
        tag_time = None

        # Build search tasks
        search_tasks = []
        task_map = {}
        task_idx = 0

        if enable_lexical:
            search_tasks.append(self._lexical_search(query=query, filters=filters, limit=candidate_pool_size))
            task_map[task_idx] = "lexical"
            task_idx += 1

        if enable_vector:
            search_tasks.append(self._vector_search(embedding=embedding, filters=filters, limit=candidate_pool_size))
            task_map[task_idx] = "vector"
            task_idx += 1

        # Entity and tag search only if keywords available
        ll_keywords = keywords.ll_keywords if keywords else []
        if enable_lexical and ll_keywords:
            search_tasks.append(self._entity_search(keywords=ll_keywords, filters=filters, limit=candidate_pool_size))
            task_map[task_idx] = "entity"
            task_idx += 1

        if ll_keywords:
            search_tasks.append(self._tag_search(keywords=ll_keywords, filters=filters, limit=candidate_pool_size))
            task_map[task_idx] = "tag"
            task_idx += 1

        # Execute all searches in parallel
        if search_tasks:
            results = await asyncio.gather(*search_tasks)
            for i, (search_results, search_time) in enumerate(results):
                method = task_map.get(i)
                if method == "lexical":
                    lexical_results, lexical_time = search_results, search_time
                elif method == "vector":
                    vector_results, vector_time = search_results, search_time
                elif method == "entity":
                    entity_results, entity_time = search_results, search_time
                elif method == "tag":
                    tag_results, tag_time = search_results, search_time
```

- [ ] **Step 3: Update RRF fusion to support 4 sources**

After the vector filtering section (around line 297), find the RRF Fusion section. The current fusion code handles lexical + vector. We need to extend it for entity + tag results.

Find the RRF fusion call (around line 298-310). It currently looks like:

```python
        fusion_start = time.time()
        fused_results = self.fusion_service.fuse(
            results=[lexical_results, vector_results],
            weights=[lexical_weight, vector_weight],
        )
```

Replace with:

```python
        fusion_start = time.time()

        # Build results and weights lists dynamically
        fusion_results = []
        fusion_weights = []

        if lexical_results:
            fusion_results.append(lexical_results)
            fusion_weights.append(lexical_weight)
        if vector_results:
            fusion_results.append(vector_results)
            fusion_weights.append(vector_weight)
        if entity_results:
            fusion_results.append(entity_results)
            entity_w = 0.15 if (lexical_results and vector_results) else 0.3
            fusion_weights.append(entity_w)
        if tag_results:
            fusion_results.append(tag_results)
            tag_w = 0.15 if (lexical_results and vector_results) else 0.3
            fusion_weights.append(tag_w)

        # Normalize weights
        total_w = sum(fusion_weights)
        if total_w > 0:
            fusion_weights = [w / total_w for w in fusion_weights]

        if fusion_results:
            fused_results = self.fusion_service.fuse(
                results=fusion_results,
                weights=fusion_weights,
            )
        else:
            fused_results = []
```

- [ ] **Step 4: Update metadata to include entity/tag counts**

Find the metadata construction (around line 340-360). Add entity and tag counts:

```python
        metadata = HybridMemorySearchMetadata(
            total_results=len(fused_results),
            lexical_count=len(lexical_results) if lexical_results else 0,
            vector_count=len(vector_results) if vector_results else 0,
            unique_after_fusion=len(fused_results),
            lexical_enabled=enable_lexical,
            vector_enabled=enable_vector,
            lexical_weight=lexical_weight,
            vector_weight=vector_weight,
            execution_time_ms=total_time,
            lexical_time_ms=lexical_time,
            vector_time_ms=vector_time,
            entity_count=len(entity_results) if entity_results else 0,
            tag_count=len(tag_results) if tag_results else 0,
            entity_time_ms=entity_time,
            tag_time_ms=tag_time,
            keywords_extracted=bool(keywords and (keywords.hl_keywords or keywords.ll_keywords)),
        )
```

Note: `HybridMemorySearchMetadata` dataclass needs new fields. Add them:

In the `HybridMemorySearchMetadata` dataclass (line 98), add after the existing optional fields:

```python
    entity_count: int = 0
    tag_count: int = 0
    entity_time_ms: Optional[float] = None
    tag_time_ms: Optional[float] = None
    keywords_extracted: bool = False
```

- [ ] **Step 5: Commit**

```bash
git add api/services/hybrid_memory_search_service.py
git commit -m "feat(epic-28): add entity/tag search and 4-source RRF fusion to hybrid search"
```

---

### Task 8: Wire QueryUnderstandingService into SearchMemoryTool

**Files:**
- Modify: `api/mnemo_mcp/tools/memory_tools.py`
- Modify: `api/mnemo_mcp/server.py`

- [ ] **Step 1: Initialize QueryUnderstandingService in MCP server**

In `api/mnemo_mcp/server.py`, after the EntityExtractionService initialization (the block added in Task 5), add:

```python
        # EPIC-28: Initialize QueryUnderstandingService
        try:
            from services.query_understanding_service import QueryUnderstandingService

            if services.get("lm_studio_client"):
                query_understanding_service = QueryUnderstandingService(
                    lm_client=services["lm_studio_client"],
                )
                services["query_understanding_service"] = query_understanding_service
                logger.info("mcp.query_understanding_service.initialized")
            else:
                services["query_understanding_service"] = None

        except Exception as e:
            logger.warning("mcp.query_understanding_service.initialization_failed", error=str(e))
            services["query_understanding_service"] = None
```

- [ ] **Step 2: Modify SearchMemoryTool to use query understanding**

In `api/mnemo_mcp/tools/memory_tools.py`, find the `SearchMemoryTool.execute()` method (line 599). In the hybrid search path (around line 700-750), before calling `hybrid_memory_search_service.search()`, add query understanding:

Find the section where the search is called (look for `hybrid_memory_search_service.search`). Before that call, add:

```python
            # EPIC-28: Extract HL/LL keywords for improved search
            keywords = None
            query_understanding = self.services.get("query_understanding_service")
            if query_understanding:
                keywords = await query_understanding.extract_keywords(query)

            # Execute hybrid search
            search_result = await self.hybrid_memory_search_service.search(
                query=query,
                embedding=query_embedding,
                keywords=keywords,
                filters=filters,
                limit=limit,
                offset=offset,
            )
```

- [ ] **Step 3: Add import for QueryKeywords type**

At the top of the search section in `memory_tools.py`, ensure the import is available. The `keywords` parameter passes a `QueryKeywords` object. Since we use `Any` in the search method signature, no new import is needed in the tool.

- [ ] **Step 4: Commit**

```bash
git add api/mnemo_mcp/server.py api/mnemo_mcp/tools/memory_tools.py
git commit -m "feat(epic-28): wire QueryUnderstandingService into SearchMemoryTool"
```

---

### Task 9: Add LM Studio env vars to docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add LM Studio environment variables to API service**

In `docker-compose.yml`, find the `api` service's `environment` block. Add these lines:

```yaml
      - LM_STUDIO_URL=http://host.docker.internal:1234/v1
      - LM_STUDIO_MODEL=qwen2.5-7b-instruct
      - LM_STUDIO_TIMEOUT=30
      - ENTITY_EXTRACTION_ENABLED=${ENTITY_EXTRACTION_ENABLED:-true}
      - ENTITY_EXTRACTION_MEMORY_TYPES=${ENTITY_EXTRACTION_MEMORY_TYPES:-decision,reference,note,investigation}
      - ENTITY_EXTRACTION_SYSTEM_TAGS=${ENTITY_EXTRACTION_SYSTEM_TAGS:-sys:core,sys:anchor,sys:pattern}
      - QUERY_UNDERSTANDING_ENABLED=${QUERY_UNDERSTANDING_ENABLED:-true}
      - QUERY_UNDERSTANDING_FALLBACK=${QUERY_UNDERSTANDING_FALLBACK:-true}
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(epic-28): add LM Studio environment variables to docker-compose"
```

---

### Task 10: Build, migrate, and verify

**Files:**
- No file changes — verification task

- [ ] **Step 1: Rebuild containers**

```bash
make build
```

- [ ] **Step 2: Run Alembic migration**

```bash
docker compose exec api alembic upgrade head
```

Expected: Output showing migration applied successfully.

- [ ] **Step 3: Start services**

```bash
make up
```

- [ ] **Step 4: Verify API health**

```bash
curl http://localhost:8001/health
```

Expected: `{"status": "healthy", ...}`

- [ ] **Step 5: Verify MCP health**

```bash
curl http://localhost:8002/mcp
```

Expected: MCP server responds.

- [ ] **Step 6: Verify entity columns exist**

```bash
docker compose exec api python -c "
from sqlalchemy import create_engine, text
import os
url = os.getenv('DATABASE_URL', 'postgresql+psycopg2://mnemo:mnemo@postgres:5432/mnemo')
engine = create_engine(url)
with engine.connect() as conn:
    result = conn.execute(text(\"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='memories' AND column_name IN ('entities','concepts','auto_tags') ORDER BY column_name\"))
    for row in result:
        print(row)
"
```

Expected:
```
('auto_tags', 'text')
('concepts', 'json')
('entities', 'json')
```

- [ ] **Step 7: Test memory creation with entity extraction (LM Studio running)**

Ensure LM Studio is running with Qwen2.5-7B loaded on port 1234.

```bash
curl -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "write_memory",
      "arguments": {
        "title": "Decision: Use Redis for L2 cache",
        "content": "We decided to use Redis as our L2 cache layer. PostgreSQL is our source of truth but Redis provides fast access for frequently accessed data. The cache uses a write-through strategy with 5-minute TTL.",
        "memory_type": "decision",
        "tags": ["architecture", "cache"]
      }
    }
  }'
```

Wait 5-10 seconds, then check if entities were extracted:

```bash
docker compose exec api python -c "
from sqlalchemy import create_engine, text
import os, json
url = os.getenv('DATABASE_URL', 'postgresql+psycopg2://mnemo:mnemo@postgres:5432/mnemo')
engine = create_engine(url)
with engine.connect() as conn:
    result = conn.execute(text(\"SELECT title, entities, concepts, auto_tags FROM memories WHERE title LIKE '%Redis%' ORDER BY created_at DESC LIMIT 1\"))
    row = result.fetchone()
    if row:
        print(f'Title: {row[0]}')
        print(f'Entities: {row[1]}')
        print(f'Concepts: {row[2]}')
        print(f'Auto-tags: {row[3]}')
    else:
        print('No memory found')
"
```

- [ ] **Step 8: Test search with query understanding (LM Studio running)**

```bash
curl -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search_memory",
      "arguments": {
        "query": "why did we choose Redis for caching?",
        "limit": 5
      }
    }
  }'
```

- [ ] **Step 9: Test graceful degradation (LM Studio NOT running)**

Stop LM Studio. Create a memory and search. Both should work normally (fallback behavior).

```bash
# Create memory
curl -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "write_memory",
      "arguments": {
        "title": "Test without LM Studio",
        "content": "This memory was created while LM Studio was offline.",
        "memory_type": "note"
      }
    }
  }'

# Search
curl -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "search_memory",
      "arguments": {
        "query": "LM Studio offline",
        "limit": 5
      }
    }
  }'
```

Both should succeed with fallback behavior (no entities extracted, search uses brute query).

- [ ] **Step 10: Commit (no changes needed if all passes)**

---

### Task 11: Create MCP tools for entity management

**Files:**
- Create: `api/mnemo_mcp/tools/entity_extraction_tool.py`
- Modify: `api/mnemo_mcp/server.py`

- [ ] **Step 1: Create the entity extraction MCP tool**

Create `api/mnemo_mcp/tools/entity_extraction_tool.py`:

```python
"""
Entity Extraction MCP Tool — Manual entity extraction and search.

Provides tools for:
- extract_entities: Re-extract entities from an existing memory
- search_by_entity: Search memories containing a specific entity
"""

from typing import Optional, Dict, Any, List
import structlog
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text

from services.lm_studio_client import LMStudioClient
from services.entity_extraction_service import EntityExtractionService

logger = structlog.get_logger()


class ExtractEntitiesTool:
    """MCP tool to manually trigger entity extraction on an existing memory."""

    def __init__(self, engine: AsyncEngine, lm_client: LMStudioClient):
        self.engine = engine
        self.extraction_service = EntityExtractionService(engine=engine, lm_client=lm_client)

    async def execute(
        self,
        memory_id: str,
    ) -> Dict[str, Any]:
        """
        Re-extract entities for a memory.

        Args:
            memory_id: Memory UUID

        Returns:
            Dict with extraction result
        """
        # Fetch memory from DB
        query = text("""
            SELECT id::text, title, content, memory_type, tags
            FROM memories WHERE id = :memory_id AND deleted_at IS NULL
        """)
        async with self.engine.begin() as conn:
            result = await conn.execute(query, {"memory_id": memory_id})
            row = result.fetchone()

        if not row:
            return {"error": f"Memory {memory_id} not found", "success": False}

        memory_id_str, title, content, memory_type, tags = row

        # Parse tags if string
        if isinstance(tags, str):
            tags = tags.strip("{}").split(",") if tags != "{}" else []

        success = await self.extraction_service.extract_entities(
            memory_id=memory_id_str,
            title=title,
            content=content,
            memory_type=memory_type,
            tags=tags or [],
        )

        return {
            "success": success,
            "memory_id": memory_id,
            "message": "Entities extracted" if success else "Extraction failed or skipped",
        }


class SearchByEntityTool:
    """MCP tool to search memories by entity name."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def execute(
        self,
        entity_name: str,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Search memories containing a specific entity.

        Args:
            entity_name: Entity name to search for
            limit: Max results

        Returns:
            Dict with matching memories
        """
        query = text("""
            SELECT id::text, title, memory_type, tags, created_at::text, entities
            FROM memories
            WHERE deleted_at IS NULL
              AND entities @> '[{"name": :entity_name}]'::jsonb
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        async with self.engine.begin() as conn:
            result = await conn.execute(query, {"entity_name": entity_name, "limit": limit})
            rows = result.fetchall()

        memories = []
        for row in rows:
            memories.append({
                "id": row[0],
                "title": row[1],
                "memory_type": row[2],
                "tags": row[3],
                "created_at": row[4],
                "entities": row[5],
            })

        return {
            "query": entity_name,
            "memories": memories,
            "total": len(memories),
        }
```

- [ ] **Step 2: Register the new tools in MCP server**

In `api/mnemo_mcp/server.py`, find the tool registration section (around line 514-566 where tools are created). After the existing tools, add:

```python
    # EPIC-28: Register entity extraction tools
    try:
        from mnemo_mcp.tools.entity_extraction_tool import ExtractEntitiesTool, SearchByEntityTool

        if sqlalchemy_engine and services.get("lm_studio_client"):
            extract_tool = ExtractEntitiesTool(
                engine=sqlalchemy_engine,
                lm_client=services["lm_studio_client"],
            )
            search_entity_tool = SearchByEntityTool(engine=sqlalchemy_engine)

            @mcp.tool()
            async def extract_entities(memory_id: str) -> Dict[str, Any]:
                """Re-extract entities from an existing memory using LM Studio."""
                return await extract_tool.execute(memory_id=memory_id)

            @mcp.tool()
            async def search_by_entity(entity_name: str, limit: int = 10) -> Dict[str, Any]:
                """Search memories containing a specific entity name."""
                return await search_entity_tool.execute(entity_name=entity_name, limit=limit)

            logger.info("mcp.entity_tools.registered")
        else:
            logger.warning("mcp.entity_tools.skipped", reason="no_engine_or_lm_studio")

    except Exception as e:
        logger.warning("mcp.entity_tools.registration_failed", error=str(e))
```

- [ ] **Step 3: Commit**

```bash
git add api/mnemo_mcp/tools/entity_extraction_tool.py api/mnemo_mcp/server.py
git commit -m "feat(epic-28): add extract_entities and search_by_entity MCP tools"
```
