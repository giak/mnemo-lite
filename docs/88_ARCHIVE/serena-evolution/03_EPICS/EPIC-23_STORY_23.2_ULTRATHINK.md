# EPIC-23 Story 23.2: Code Search Resources - ULTRATHINK

**Date**: 2025-10-27
**Status**: 🧠 BRAINSTORM & ANALYSIS
**Story Points**: 3 pts
**Estimated Time**: ~12h
**Dependencies**: Story 23.1 ✅ Complete

---

## 📋 Story Overview

### Objective
Implement `code://search/{query}` MCP resource to expose MnemoLite's hybrid code search (EPIC-11) to Claude Desktop and other LLM clients via Model Context Protocol.

### Sub-stories (6)
1. **23.2.1**: Search Pydantic models (1.5h)
2. **23.2.2**: `code://search` resource (2h)
3. **23.2.3**: Pagination & filters (1.5h)
4. **23.2.4**: Resource links (MCP 2025-06-18) (2h)
5. **23.2.5**: Cache integration (2h)
6. **23.2.6**: Search tests + MCP Inspector validation (2.5h)

### Deliverables
- `api/mnemo_mcp/resources/search_resources.py` (SearchResource class)
- Pydantic models: `CodeSearchQuery`, `CodeSearchResult`, `CodeSearchResponse`
- Resource registration in `server.py`
- Redis L2 cache integration (SHA256 keys, 5-min TTL)
- Pagination support (limit, offset)
- Filters support (language, chunk_type, repository, file_path, return_type, param_type)
- Resource links (MCP 2025-06-18 spec)
- 10+ unit tests
- MCP Inspector validation

---

## 🔍 Technical Analysis

### 1. Existing Code Analysis

#### HybridCodeSearchService (api/services/hybrid_code_search_service.py)

**Key Method**: `search()`
```python
async def search(
    self,
    query: str,
    embedding_text: Optional[List[float]] = None,
    embedding_code: Optional[List[float]] = None,
    filters: Optional[SearchFilters] = None,
    top_k: int = 10,
    enable_lexical: bool = True,
    enable_vector: bool = True,
    lexical_weight: float = 0.4,
    vector_weight: float = 0.6,
    candidate_pool_size: int = 100,
) -> HybridSearchResponse
```

**Input**:
- `query` (str): Keywords for lexical search
- `embedding_text` (768D vector): TEXT domain embedding
- `embedding_code` (768D vector): CODE domain embedding (preferred)
- `filters` (SearchFilters): language, chunk_type, repository, file_path, return_type, param_type
- `top_k` (int): Number of results (default: 10)
- Weights, enable flags

**Output**: `HybridSearchResponse`
```python
@dataclass
class HybridSearchResponse:
    results: List[HybridSearchResult]  # Fused results with RRF scores
    metadata: SearchMetadata           # Timing, counts, weights
```

**HybridSearchResult**:
```python
@dataclass
class HybridSearchResult:
    chunk_id: str
    rrf_score: float
    rank: int
    source_code: str
    name: str
    name_path: Optional[str]  # EPIC-11 hierarchical name
    language: str
    chunk_type: str
    file_path: str
    metadata: Dict[str, Any]
    lexical_score: Optional[float]
    vector_similarity: Optional[float]
    vector_distance: Optional[float]
    contribution: Dict[str, float]
    related_nodes: List[str]
```

**Performance**:
- L2 Redis cache: 30s TTL for search results
- Cache key: `cache_keys.search_result_key(query, repository, limit)`
- Target: <50ms P95 on 10k chunks (with cache)
- Parallel execution: lexical + vector searches

#### Existing Filters (SearchFilters dataclass)
```python
@dataclass
class SearchFilters:
    language: Optional[str] = None
    chunk_type: Optional[str] = None
    repository: Optional[str] = None
    file_path: Optional[str] = None
    return_type: Optional[str] = None   # EPIC-14 Story 14.4
    param_type: Optional[str] = None    # EPIC-14 Story 14.4
```

---

### 2. MCP Resource Pattern (Story 23.1 Reference)

#### Resource Registration Pattern
```python
# In server.py
@mcp.resource("health://status")
async def get_health_status() -> dict:
    """Get MCP server health status."""
    # Note: Resources DON'T get Context parameter (FastMCP design)
    response = await health_resource.get(None)
    return response.model_dump()
```

#### Resource Class Pattern (BaseMCPComponent)
```python
class HealthStatusResource(BaseMCPComponent):
    def get_name(self) -> str:
        return "health://status"

    async def get(self, ctx: Context) -> HealthStatus:
        # Access services via self._services
        db_pool = self._services.get("db")
        redis_client = self._services.get("redis")
        # ... implementation
        return HealthStatus(...)
```

**Key Patterns**:
1. **No Context in registration**: Resources registered without `ctx` parameter
2. **Service injection**: Services injected via `inject_services()` in lifespan
3. **Pydantic response**: All responses are Pydantic models with `.model_dump()`
4. **Error handling**: Try/except with graceful degradation

---

### 3. MCP 2025-06-18 Resource Specification

#### Resource URIs
- **URI Template**: `code://search/{query}` (dynamic parameter)
- **Alternative**: `code://search` with query in request body (preferred for complex queries)

#### Resource Links (MCP 2025-06-18 New Feature)
Resources can return links to related resources:
```python
{
    "uri": "code://search",
    "name": "Search Results",
    "description": "Semantic code search",
    "mime_type": "application/json",
    "links": [
        {"uri": "graph://nodes/{chunk_id}", "rel": "code_graph"},
        {"uri": "code://chunk/{chunk_id}", "rel": "details"},
        {"uri": "memories://search/related", "rel": "related_memories"}
    ]
}
```

**Link Relations** (standard):
- `self`: Current resource
- `related`: Related resources
- `next`: Pagination next page
- `prev`: Pagination previous page
- Custom: `code_graph`, `details`, `related_memories`

#### Pydantic Structured Output (Required)
```python
from pydantic import BaseModel, Field

class CodeSearchResult(BaseModel):
    chunk_id: str = Field(..., description="Unique chunk identifier")
    name: str = Field(..., description="Symbol name (function, class, etc.)")
    # ... all fields with descriptions for MCP Inspector
```

---

### 4. Pagination Strategy

#### Option 1: Offset-based (Simple)
```python
# Request
{
    "query": "authentication",
    "limit": 10,
    "offset": 0
}

# Response includes pagination metadata
{
    "results": [...],
    "pagination": {
        "total": 156,
        "limit": 10,
        "offset": 0,
        "has_next": true,
        "next_offset": 10
    },
    "links": [
        {"uri": "code://search?query=auth&offset=10&limit=10", "rel": "next"}
    ]
}
```

**Pros**: Simple, stateless
**Cons**: Performance degrades for large offsets (OFFSET 10000 is slow)

#### Option 2: Cursor-based (Production-grade)
```python
# Request
{
    "query": "authentication",
    "limit": 10,
    "cursor": "eyJjaHVua19pZCI6ImFiYzEyMyIsInJhbmsiOjEwfQ=="  # Base64 encoded
}

# Response
{
    "results": [...],
    "pagination": {
        "has_next": true,
        "next_cursor": "eyJjaHVua19pZCI6ImRlZjQ1NiIsInJhbmsiOjIwfQ=="
    }
}
```

**Pros**: Constant performance, handles deep pagination
**Cons**: More complex, requires cursor encoding/decoding

#### Recommendation: **Offset-based for MVP** (Story 23.2), Cursor-based for Phase 2 optimization

**Rationale**:
- Most queries return <100 results (top_k=10-50 typical)
- Deep pagination rare for code search (users refine query instead)
- Offset-based simpler to implement and test
- Can add cursor-based later without breaking API

---

### 5. Cache Strategy (Redis L2)

#### Cache Key Generation (SHA256)
```python
import hashlib
import json

def generate_cache_key(
    query: str,
    filters: Optional[SearchFilters],
    limit: int,
    offset: int
) -> str:
    """Generate deterministic cache key for search query."""
    cache_data = {
        "query": query,
        "filters": filters.dict() if filters else {},
        "limit": limit,
        "offset": offset,
    }
    cache_str = json.dumps(cache_data, sort_keys=True)
    cache_hash = hashlib.sha256(cache_str.encode()).hexdigest()[:16]
    return f"mcp:search:{cache_hash}"
```

**Example**: `mcp:search:a1b2c3d4e5f6g7h8`

#### TTL Strategy
- **Search results**: 5 minutes (300s)
  - Rationale: Code changes infrequently, but new indexed files should appear
- **Cache invalidation**: Manual via `clear_cache` tool (Story 23.6)

#### Cache Miss Handling
```python
# Try cache first
cached = await redis_cache.get(cache_key)
if cached:
    logger.info("L2 cache HIT", query=query[:50])
    return deserialize(cached)

# Cache miss: execute search
logger.debug("L2 cache MISS", query=query[:50])
response = await hybrid_search_service.search(...)

# Populate cache
await redis_cache.set(cache_key, serialize(response), ttl_seconds=300)
```

---

### 6. Embedding Generation (Critical Decision)

#### Problem
`HybridCodeSearchService.search()` requires embeddings:
- `embedding_text` (768D vector)
- `embedding_code` (768D vector)

**Question**: How does MCP resource get embeddings?

#### Option 1: Generate in Resource (Recommended ✅)
```python
# In search_resources.py
from services.dual_embedding_service import DualEmbeddingService, EmbeddingDomain

class SearchResource(BaseMCPComponent):
    async def search(self, query: str, ...) -> CodeSearchResponse:
        # Get embedding service from injected services
        embedding_service = self._services.get("embedding_service")

        # Generate embeddings
        embedding_text = await embedding_service.embed(query, EmbeddingDomain.TEXT)
        embedding_code = await embedding_service.embed(query, EmbeddingDomain.CODE)

        # Search with embeddings
        response = await hybrid_search_service.search(
            query=query,
            embedding_text=embedding_text,
            embedding_code=embedding_code,
            ...
        )
```

**Pros**:
- Self-contained, no external dependencies
- Works with any embedding provider
- Consistent with FastAPI routes

**Cons**:
- Adds 100-200ms for embedding generation (uncached)
- Model loading overhead (~1-2GB RAM)

#### Option 2: Lazy Load Embeddings (Future Optimization)
```python
# Cache embeddings for common queries
embedding_cache_key = f"embed:text:{sha256(query)[:16]}"
cached_embedding = await redis_cache.get(embedding_cache_key)

if not cached_embedding:
    embedding_text = await embedding_service.embed(query, EmbeddingDomain.TEXT)
    await redis_cache.set(embedding_cache_key, embedding_text, ttl_seconds=3600)
```

**Recommendation**: Option 1 for MVP (Story 23.2), add embedding cache in EPIC-23 Phase 2

---

### 7. Error Handling Strategy

#### Graceful Degradation Patterns

**1. Embedding Service Failure**
```python
try:
    embedding_text = await embedding_service.embed(query, EmbeddingDomain.TEXT)
except Exception as e:
    logger.warning("Embedding generation failed, using lexical-only", error=str(e))
    embedding_text = None  # Fallback to lexical-only search
```

**2. Redis Cache Failure**
```python
try:
    cached = await redis_cache.get(cache_key)
except Exception as e:
    logger.warning("Redis cache read failed, continuing without cache", error=str(e))
    cached = None  # Continue without cache
```

**3. Search Service Failure**
```python
try:
    response = await hybrid_search_service.search(...)
except ValueError as e:
    # User error (empty query, invalid params)
    raise ValueError(f"Invalid search parameters: {e}")
except Exception as e:
    # Service error
    logger.error("Hybrid search service failed", error=str(e))
    return CodeSearchResponse(
        results=[],
        total=0,
        error="Search service temporarily unavailable",
        metadata={"error": str(e)}
    )
```

---

### 8. Pydantic Models Design

#### Input Model
```python
from pydantic import BaseModel, Field
from typing import Optional

class CodeSearchQuery(BaseModel):
    """Code search query parameters."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query (keywords or natural language)"
    )

    # Pagination
    limit: int = Field(
        10,
        ge=1,
        le=100,
        description="Number of results to return (1-100)"
    )

    offset: int = Field(
        0,
        ge=0,
        description="Offset for pagination (0-indexed)"
    )

    # Filters
    language: Optional[str] = Field(
        None,
        description="Filter by programming language (e.g., 'python', 'javascript')"
    )

    chunk_type: Optional[str] = Field(
        None,
        description="Filter by chunk type (e.g., 'function', 'class', 'method')"
    )

    repository: Optional[str] = Field(
        None,
        description="Filter by repository name"
    )

    file_path: Optional[str] = Field(
        None,
        description="Filter by file path (supports wildcards)"
    )

    return_type: Optional[str] = Field(
        None,
        description="Filter by LSP return type (e.g., 'str', 'int', 'bool')"
    )

    param_type: Optional[str] = Field(
        None,
        description="Filter by LSP parameter type"
    )

    # Search options
    enable_lexical: bool = Field(
        True,
        description="Enable lexical (keyword) search"
    )

    enable_vector: bool = Field(
        True,
        description="Enable semantic (vector) search"
    )

    lexical_weight: float = Field(
        0.4,
        ge=0.0,
        le=1.0,
        description="Weight for lexical results (0.0-1.0)"
    )

    vector_weight: float = Field(
        0.6,
        ge=0.0,
        le=1.0,
        description="Weight for vector results (0.0-1.0)"
    )
```

#### Output Model
```python
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class CodeChunkResult(BaseModel):
    """Single code search result."""

    chunk_id: str = Field(..., description="Unique chunk identifier (UUID)")

    name: str = Field(..., description="Symbol name (function, class, variable)")

    name_path: Optional[str] = Field(
        None,
        description="Hierarchical qualified name (e.g., 'auth.routes.login')"
    )

    language: str = Field(..., description="Programming language")

    chunk_type: str = Field(..., description="Chunk type (function, class, method, etc.)")

    file_path: str = Field(..., description="File path relative to repository root")

    source_code: str = Field(..., description="Source code content")

    # Search scores
    rrf_score: float = Field(..., description="RRF fusion score (0.0-1.0)")

    rank: int = Field(..., description="Result rank (1-indexed)")

    lexical_score: Optional[float] = Field(
        None,
        description="Lexical similarity score (0.0-1.0)"
    )

    vector_similarity: Optional[float] = Field(
        None,
        description="Vector cosine similarity (0.0-1.0)"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (LSP types, documentation, etc.)"
    )

    # Resource links (MCP 2025-06-18)
    links: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Related resource links"
    )

class SearchMetadata(BaseModel):
    """Search execution metadata."""

    total_results: int = Field(..., description="Total number of results")

    execution_time_ms: float = Field(..., description="Search execution time (ms)")

    lexical_enabled: bool = Field(..., description="Lexical search enabled")

    vector_enabled: bool = Field(..., description="Vector search enabled")

    lexical_count: int = Field(..., description="Lexical candidates count")

    vector_count: int = Field(..., description="Vector candidates count")

    lexical_weight: float = Field(..., description="Lexical weight used")

    vector_weight: float = Field(..., description="Vector weight used")

    cache_hit: bool = Field(default=False, description="L2 cache hit")

class CodeSearchPagination(BaseModel):
    """Pagination information."""

    total: int = Field(..., description="Total results available")

    limit: int = Field(..., description="Results per page")

    offset: int = Field(..., description="Current offset")

    has_next: bool = Field(..., description="Has next page")

    has_prev: bool = Field(..., description="Has previous page")

    next_offset: Optional[int] = Field(None, description="Next page offset")

    prev_offset: Optional[int] = Field(None, description="Previous page offset")

class CodeSearchResponse(BaseModel):
    """Complete code search response."""

    results: List[CodeChunkResult] = Field(..., description="Search results")

    pagination: CodeSearchPagination = Field(..., description="Pagination info")

    metadata: SearchMetadata = Field(..., description="Search metadata")

    # Resource links (MCP 2025-06-18)
    links: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Top-level resource links"
    )
```

---

### 9. Resource Links Implementation

#### Links for Each Result
```python
def build_result_links(chunk_id: str) -> List[Dict[str, str]]:
    """Build resource links for a code chunk."""
    return [
        {
            "uri": f"graph://nodes/{chunk_id}",
            "rel": "code_graph",
            "description": "View code graph for this chunk"
        },
        {
            "uri": f"code://chunk/{chunk_id}",
            "rel": "details",
            "description": "Get detailed chunk information"
        },
        {
            "uri": f"memories://search?related_chunk={chunk_id}",
            "rel": "related_memories",
            "description": "Find related project memories"
        }
    ]
```

#### Top-level Response Links
```python
def build_response_links(
    query: str,
    pagination: CodeSearchPagination
) -> List[Dict[str, str]]:
    """Build top-level resource links."""
    links = [
        {
            "uri": "code://search",
            "rel": "self",
            "description": "Current search"
        }
    ]

    if pagination.has_next:
        next_uri = f"code://search?query={query}&offset={pagination.next_offset}&limit={pagination.limit}"
        links.append({
            "uri": next_uri,
            "rel": "next",
            "description": "Next page of results"
        })

    if pagination.has_prev:
        prev_uri = f"code://search?query={query}&offset={pagination.prev_offset}&limit={pagination.limit}"
        links.append({
            "uri": prev_uri,
            "rel": "prev",
            "description": "Previous page of results"
        })

    return links
```

---

## 🧪 Testing Strategy

### Unit Tests (10+ tests)

**File**: `tests/mnemo_mcp/test_search_resources.py`

```python
import pytest
from mnemo_mcp.resources.search_resources import SearchResource
from mnemo_mcp.models import CodeSearchQuery, CodeSearchResponse

class TestSearchResource:
    """Test suite for SearchResource."""

    @pytest.fixture
    async def search_resource(self, mock_services):
        """Create SearchResource with mocked services."""
        resource = SearchResource()
        resource.inject_services(mock_services)
        return resource

    async def test_search_basic_query(self, search_resource):
        """Test basic search with query only."""
        query = CodeSearchQuery(query="authentication")
        response = await search_resource.search(query)

        assert isinstance(response, CodeSearchResponse)
        assert len(response.results) > 0
        assert response.pagination.total >= len(response.results)

    async def test_search_with_filters(self, search_resource):
        """Test search with language filter."""
        query = CodeSearchQuery(
            query="login",
            language="python",
            chunk_type="function"
        )
        response = await search_resource.search(query)

        # All results should be Python functions
        for result in response.results:
            assert result.language == "python"
            assert result.chunk_type == "function"

    async def test_search_pagination(self, search_resource):
        """Test pagination (limit & offset)."""
        # Page 1
        query = CodeSearchQuery(query="test", limit=5, offset=0)
        page1 = await search_resource.search(query)

        # Page 2
        query2 = CodeSearchQuery(query="test", limit=5, offset=5)
        page2 = await search_resource.search(query2)

        # Results should be different
        page1_ids = {r.chunk_id for r in page1.results}
        page2_ids = {r.chunk_id for r in page2.results}
        assert page1_ids.isdisjoint(page2_ids)

    async def test_search_empty_results(self, search_resource):
        """Test search with no results."""
        query = CodeSearchQuery(query="xyzneverexists12345")
        response = await search_resource.search(query)

        assert len(response.results) == 0
        assert response.pagination.total == 0
        assert not response.pagination.has_next

    async def test_search_resource_links(self, search_resource):
        """Test resource links in response."""
        query = CodeSearchQuery(query="function")
        response = await search_resource.search(query)

        if len(response.results) > 0:
            result = response.results[0]
            assert len(result.links) > 0
            # Check for expected link relations
            link_rels = {link["rel"] for link in result.links}
            assert "code_graph" in link_rels or "details" in link_rels

    async def test_search_cache_hit(self, search_resource, mock_redis):
        """Test L2 cache hit."""
        query = CodeSearchQuery(query="cached_query")

        # First call (cache miss)
        response1 = await search_resource.search(query)
        assert response1.metadata.cache_hit is False

        # Second call (cache hit)
        response2 = await search_resource.search(query)
        assert response2.metadata.cache_hit is True
        assert response1.results == response2.results

    async def test_search_invalid_query(self, search_resource):
        """Test validation error for empty query."""
        with pytest.raises(ValueError):
            query = CodeSearchQuery(query="")
            await search_resource.search(query)

    async def test_search_lexical_only(self, search_resource):
        """Test lexical-only search (no embeddings)."""
        query = CodeSearchQuery(
            query="test",
            enable_lexical=True,
            enable_vector=False
        )
        response = await search_resource.search(query)

        assert response.metadata.lexical_enabled is True
        assert response.metadata.vector_enabled is False
        assert len(response.results) > 0

    async def test_search_vector_only(self, search_resource):
        """Test vector-only search."""
        query = CodeSearchQuery(
            query="authentication logic",
            enable_lexical=False,
            enable_vector=True
        )
        response = await search_resource.search(query)

        assert response.metadata.lexical_enabled is False
        assert response.metadata.vector_enabled is True

    async def test_search_graceful_degradation(self, search_resource, mock_services_failing):
        """Test graceful degradation when services fail."""
        resource = SearchResource()
        resource.inject_services(mock_services_failing)

        query = CodeSearchQuery(query="test")
        response = await resource.search(query)

        # Should return empty results with error, not crash
        assert len(response.results) == 0
        assert "error" in response.metadata or hasattr(response, "error")
```

### Integration Tests (MCP Inspector)

**Manual Testing Checklist**:
1. Start MCP server: `docker compose exec api python -m mnemo_mcp.server`
2. Open MCP Inspector: http://127.0.0.1:6274
3. Register MnemoLite MCP server
4. Test resource:
   - URI: `code://search`
   - Parameters: `{"query": "authentication", "limit": 10}`
   - Expected: JSON response with results
5. Verify resource links in results
6. Test pagination with `offset` parameter
7. Test filters (language, chunk_type)
8. Verify cache hit (second identical query)

---

## ⚠️ Critical Decisions & Trade-offs

### Decision 1: URI Pattern

**Options**:
- A: `code://search/{query}` (path parameter)
- B: `code://search` with query in body (chosen ✅)

**Rationale**: Option B chosen because:
- Query string can contain special characters, spaces, quotes
- URI encoding complex for path parameters
- Body parameters support complex filters (JSON object)
- Consistent with REST API patterns
- MCP Inspector easier to test with JSON body

**Trade-off**: Less "RESTful" URI, but more practical

---

### Decision 2: Pagination Strategy

**Chosen**: Offset-based (MVP)

**Rationale**:
- Simple to implement and test (1.5h estimated)
- Sufficient for typical code search use cases (<100 results)
- Deep pagination rare (users refine query instead)
- Can add cursor-based later without API break

**Trade-off**: Performance degrades for large offsets (acceptable for MVP)

---

### Decision 3: Embedding Generation Location

**Chosen**: Generate in MCP resource (not pre-computed)

**Rationale**:
- Self-contained, works with any query
- Consistent with FastAPI routes
- No need to store/cache all possible query embeddings
- Embedding cache can be added later (EPIC-23 Phase 2)

**Trade-off**: +100-200ms per query (uncached), but acceptable with L2 cache

---

### Decision 4: Cache TTL

**Chosen**: 5 minutes (300s)

**Rationale**:
- Code changes infrequently (minutes to hours)
- New indexed files should appear within minutes
- Balance between freshness and performance
- Shorter than HybridCodeSearchService (30s) to ensure consistency

**Trade-off**: Stale results for 5 min after code changes (acceptable)

---

### Decision 5: Error Handling

**Chosen**: Graceful degradation (fallback to lexical-only, empty results with error)

**Rationale**:
- Never crash the MCP server
- Provide partial results when possible
- Clear error messages for debugging
- Consistent with EPIC-12 robustness patterns

**Trade-off**: User may get unexpected lexical-only results (log warning)

---

## 📝 Implementation Plan (Sub-story Breakdown)

### Sub-story 23.2.1: Search Pydantic Models (1.5h)

**File**: `api/mnemo_mcp/models.py` (extend existing)

**Tasks**:
1. Create `CodeSearchQuery` model (input)
   - All query parameters with validation
   - Field descriptions for MCP Inspector
   - Default values
2. Create `CodeChunkResult` model (single result)
   - Convert from `HybridSearchResult`
   - Add resource links field
3. Create `CodeSearchPagination` model
4. Create `SearchMetadata` model
   - Convert from `SearchMetadata` (different name)
   - Add `cache_hit` field
5. Create `CodeSearchResponse` model (complete response)
6. Write unit tests for model validation

**Acceptance Criteria**:
- All models inherit from `BaseModel` (Pydantic)
- All fields have descriptions (for MCP Inspector)
- Validation rules enforced (min/max, ranges)
- Models can serialize/deserialize to JSON
- 5+ validation tests pass

---

### Sub-story 23.2.2: code://search Resource (2h)

**File**: `api/mnemo_mcp/resources/search_resources.py` (new)

**Tasks**:
1. Create `SearchResource` class (extends `BaseMCPComponent`)
2. Implement `get_name()` → `"code://search"`
3. Implement `async search(query: CodeSearchQuery) -> CodeSearchResponse`:
   - Get services from `self._services`
   - Generate embeddings (TEXT + CODE domains)
   - Convert query to `SearchFilters`
   - Call `HybridCodeSearchService.search()`
   - Convert `HybridSearchResponse` to `CodeSearchResponse`
4. Register resource in `server.py`:
   ```python
   @mcp.resource("code://search")
   async def code_search() -> dict:
       # TODO: Extract query from context somehow?
       # FastMCP resources don't get Context - need to investigate
       response = await search_resource.search(query)
       return response.model_dump()
   ```
5. Test with simple query

**Acceptance Criteria**:
- Resource registered and discoverable
- Basic search returns results
- Service injection works
- Error handling (graceful degradation)

**BLOCKER**: How to pass query parameters to resource? FastMCP resources don't get Context.

**Resolution Options**:
- A: Use tool instead of resource (tools get Context)
- B: Use HTTP query parameters (requires HTTP transport)
- C: Investigate FastMCP docs for resource parameters

**Action**: Research FastMCP resource parameters before implementing

---

### Sub-story 23.2.3: Pagination & Filters (1.5h)

**Tasks**:
1. Implement pagination logic:
   - Calculate `has_next`, `has_prev`, `next_offset`, `prev_offset`
   - Slice results based on `limit` and `offset`
2. Implement filter conversion:
   - Convert `CodeSearchQuery` filters to `SearchFilters`
   - Pass to `HybridCodeSearchService.search()`
3. Add pagination tests (5+ tests)

**Acceptance Criteria**:
- Pagination works for limit=10, offset=0/10/20
- Filters applied correctly (language, chunk_type, repository)
- Empty results handled gracefully
- Pagination metadata accurate

---

### Sub-story 23.2.4: Resource Links (2h)

**Tasks**:
1. Implement `build_result_links(chunk_id) -> List[Dict]`
   - Link to `graph://nodes/{chunk_id}`
   - Link to `code://chunk/{chunk_id}` (future)
   - Link to `memories://search?related_chunk={chunk_id}` (future)
2. Implement `build_response_links(query, pagination) -> List[Dict]`
   - `self` link
   - `next` link (if has_next)
   - `prev` link (if has_prev)
3. Add links to `CodeChunkResult` and `CodeSearchResponse`
4. Test links in MCP Inspector (verify URIs valid)

**Acceptance Criteria**:
- Each result has 2-3 resource links
- Response has self + pagination links
- Links follow MCP 2025-06-18 spec
- MCP Inspector displays links correctly

---

### Sub-story 23.2.5: Cache Integration (2h)

**Tasks**:
1. Implement cache key generation:
   - SHA256 hash of query + filters + pagination
   - Format: `mcp:search:{hash}`
2. Implement cache lookup (before search):
   - Try Redis GET
   - Deserialize if found
   - Log cache HIT/MISS
3. Implement cache population (after search):
   - Serialize response to JSON
   - Redis SET with TTL=300s
4. Add `cache_hit` field to `SearchMetadata`
5. Test cache hit (second identical query)
6. Test cache expiration (wait 5 min)

**Acceptance Criteria**:
- First query: cache MISS, populates cache
- Second query: cache HIT, same results
- Cache TTL=300s enforced
- Graceful degradation if Redis fails

---

### Sub-story 23.2.6: Tests + MCP Inspector (2.5h)

**Tasks**:
1. Write 10+ unit tests (see Testing Strategy above)
2. Write integration test (full search flow)
3. Manual testing with MCP Inspector:
   - Basic query
   - Pagination
   - Filters
   - Resource links
   - Cache hit
4. Fix any bugs found during testing
5. Document in Getting Started guide

**Acceptance Criteria**:
- 10+ unit tests passing
- Integration test passing
- MCP Inspector validation successful
- Documentation updated

---

## 🚨 Blockers & Risks

### BLOCKER 1: FastMCP Resource Parameters

**Issue**: FastMCP resources don't receive `Context` parameter (Story 23.1 finding). How to pass query parameters?

**Impact**: High - Cannot implement resource without query input

**Resolution Options**:
1. **Use Tool instead**: Tools receive Context with parameters ✅ (RECOMMENDED)
2. **Use HTTP query params**: Requires HTTP transport (Story 23.8)
3. **Use request body**: Investigate FastMCP resource body params

**Action**: Research FastMCP docs + Serena implementation before proceeding

---

### ✅ BLOCKER 1 RESOLUTION (2025-10-27)

**Research Findings**:

1. **FastMCP URI Templates (CONFIRMED)**: Resources support RFC 6570 URI templates with automatic parameter extraction
   ```python
   @mcp.resource("file://documents/{name}")
   def read_document(name: str) -> str:
       return f"Content of {name}"
   ```
   Source: MCP Python SDK README, Pocket Flow FastMCP docs

2. **Parameter Extraction**: FastMCP automatically maps URI template parameters `{param_name}` to function arguments
   - Client requests: `file://documents/readme.md`
   - FastMCP extracts: `{"name": "readme.md"}`
   - Calls: `read_document(name="readme.md")`

3. **Multiple Parameters**: Supported via multi-segment URIs
   ```python
   @mcp.resource("weather://forecast/{city_name}/{date}")
   def get_weather(city_name: str, date: str) -> str:
   ```

**Problem Analysis**:

Our code search requires **complex parameters**:
- `query` (str) - Simple, fits in URI ✅
- `filters` (SearchFilters) - 6 fields: language, chunk_type, repository, file_path, return_type, param_type ❌
- Pagination: `limit`, `offset` ❌
- Search config: `enable_lexical`, `enable_vector`, `lexical_weight`, `vector_weight` ❌

**URI with all parameters would be**:
```
code://search/{query}/{language}/{chunk_type}/{repository}/{file_path}/{return_type}/{param_type}/{limit}/{offset}/{enable_lexical}/{enable_vector}
```
→ **Unwieldy, inflexible, violates REST best practices**

**Solution Options**:

### Option A: Simple Resource (Query Only) ⚠️ LIMITED
```python
@mcp.resource("code://search/{query}")
async def search_code(query: str) -> CodeSearchResponse:
    # Use all defaults: limit=10, offset=0, no filters
    return await hybrid_search_service.search(query, ...)
```
**Pros**: Simple, cacheable, matches EPIC design
**Cons**: No filters, no pagination, limited usefulness

### Option B: Tool with JSON Arguments ✅ RECOMMENDED
```python
@mcp.tool()
async def search_code(
    ctx: Context,
    query: str,
    filters: Optional[SearchFilters] = None,
    limit: int = 10,
    offset: int = 0
) -> CodeSearchResponse:
    # Full flexibility with Pydantic validation
```
**Pros**:
- Supports complex JSON arguments
- Pydantic validation
- Optional parameters with defaults
- Flexible for future additions
**Cons**:
- Tools imply "actions" (but search is read-only)
- Contradicts EPIC design (specified as Resource)

### Option C: Hybrid Approach (Resource + Tool) 🎯 PRAGMATIC
1. **Resource** `code://search/{query}`: Simple search, default params, cacheable, for quick LLM queries
2. **Tool** `search_code`: Advanced search with all filters/pagination, for complex queries

**Pros**:
- Best of both worlds
- Resource for 80% of use cases (simple queries)
- Tool for 20% of advanced use cases (filtering, pagination)
- Both cacheable (Resource via MCP, Tool via Redis)
**Cons**:
- Two implementations (BUT share same service call)
- Slight complexity

---

**FINAL DECISION**: **Option B - Tool Only** (for MVP simplicity)

**Rationale**:
1. Code search **requires** filters and pagination for real-world use
2. Simple query-only resource would be a tech demo, not production-ready
3. Tools are **semantically appropriate**: "search" is an action verb
4. MCP Tools can be read-only (no side effects required)
5. Serena MCP uses Tools extensively for read operations
6. Simpler to implement/maintain one interface
7. Can add Resource later in Phase 2 if needed (for caching optimization)

**Implementation**:
- Change from `@mcp.resource("code://search/{query}")` to `@mcp.tool()`
- Use `CodeSearchQuery` Pydantic model for arguments
- Context receives full JSON: `{"query": "auth", "filters": {"language": "python"}, "limit": 10}`
- Update EPIC-23_README.md to reflect Tool instead of Resource

**Trade-off**: Contradicts initial EPIC design (Resource), but gains flexibility and production-readiness

**Decision**: ✅ **APPROVED by User (2025-10-27)** - Proceed with Option A (Tool)

---

### RISK 1: Embedding Generation Performance

**Issue**: Generating embeddings adds 100-200ms per query

**Impact**: Medium - Total latency 150-300ms (uncached)

**Mitigation**:
- L2 cache (5-min TTL) reduces impact for repeated queries
- Consider embedding cache for common queries (Phase 2)
- Lazy loading: generate CODE embedding only if needed

**Acceptance**: Acceptable for MVP, optimize in Phase 2

---

### RISK 2: Pagination Performance

**Issue**: Large offsets (OFFSET 10000) are slow in PostgreSQL

**Impact**: Low - Rare for code search (users refine query)

**Mitigation**:
- Limit max offset (e.g., 1000)
- Document cursor-based pagination for Phase 2
- Most queries return <100 results

**Acceptance**: Acceptable for MVP

---

### RISK 3: Cache Invalidation

**Issue**: Stale results for 5 min after code changes

**Impact**: Low-Medium - Users may see outdated results

**Mitigation**:
- TTL=5min (balance freshness vs performance)
- `clear_cache` tool (Story 23.6) for manual invalidation
- Document cache behavior in user guide

**Acceptance**: Acceptable - code changes infrequent

---

## 📚 References

### Internal
- **Story 23.1**: `EPIC-23_STORY_23.1_COMPLETION_REPORT.md`
- **HybridCodeSearchService**: `api/services/hybrid_code_search_service.py`
- **EPIC-11**: Hybrid code search implementation
- **EPIC-10**: Redis L2 cache patterns
- **EPIC-14**: LSP filter implementation

### External
- **MCP Spec 2025-06-18**: https://spec.modelcontextprotocol.io/2025-06-18/
- **FastMCP Resources**: https://github.com/modelcontextprotocol/python-sdk
- **Pydantic Validation**: https://docs.pydantic.dev/latest/
- **Redis Caching**: https://redis.io/docs/manual/patterns/

---

## ✅ Next Steps

1. ~~**Resolve BLOCKER 1**: Research FastMCP resource parameter handling~~ ✅ **RESOLVED** (2025-10-27)
   - ✅ Read FastMCP docs (URI templates confirmed)
   - ✅ Analyzed problem (complex parameters don't fit URI)
   - ✅ Decided: **Option B - Tool** (awaiting user validation)
2. **Get user validation**: Confirm Tool vs Resource decision before implementing
3. **Create implementation plan**: Detailed task breakdown with Tool approach
4. **Begin Sub-story 23.2.1**: Pydantic models (CodeSearchQuery for tool arguments)
5. **Progressive implementation**: One sub-story at a time, test each

---

**END OF ULTRATHINK**

**Status**: ✅ **Ready for Implementation** - BLOCKER 1 resolved, Option A (Tool) approved by user
**Estimated Duration**: 12h (6 sub-stories × 1.5-2.5h each)
**Confidence**: 95% (FastMCP mechanisms validated, architecture decision finalized)

---

## 📝 ULTRATHINK Summary (2025-10-27)

### What Was Analyzed
1. ✅ **HybridCodeSearchService** integration requirements
2. ✅ **MCP Resource patterns** from Story 23.1
3. ✅ **FastMCP URI templates** (web research)
4. ✅ **Pagination strategies** (offset vs cursor)
5. ✅ **Cache design** (SHA256 keys, 5-min TTL)
6. ✅ **Pydantic models** structure
7. ✅ **Resource links** (MCP 2025-06-18)

### Critical Finding
**BLOCKER 1 RESOLVED**: FastMCP Resources support URI templates, but complex search parameters (filters, pagination) don't fit URI paradigm. **Recommended: Use Tool instead of Resource** for production-ready implementation.

### User Decision: ✅ APPROVED
**Question**: Accept Tool-based implementation instead of Resource for code search?
- ✅ **Option A**: Tool only - Full flexibility, production-ready **(SELECTED)**
- ❌ **Option B**: Simple Resource - Limited, query-only, no filters/pagination
- ❌ **Option C**: Hybrid (Resource + Tool) - More complex, both interfaces

**Final Decision**: **Option A (Tool)** approved by user on 2025-10-27
**Impact**: Story 23.2 deliverables updated from Resource to Tool implementation
