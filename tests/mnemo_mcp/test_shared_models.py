"""
Tests for MCP Shared Models (EPIC-23).

Tests Pydantic models used across multiple MCP components including
ResourceLink, CacheMetadata, CodeChunk, Memory, CodeGraph, Project, and Analytics models.
"""

import json
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from mnemo_mcp.shared_models import (
    CacheMetadata,
    CacheStats,
    CodeChunk,
    CodeGraphEdge,
    CodeGraphNode,
    Memory,
    ProjectInfo,
    ResourceLink,
)


# ============================================================================
# ResourceLink Tests
# ============================================================================


class TestResourceLink:
    """Test ResourceLink model (MCP 2025-06-18)."""

    def test_minimal_link(self):
        """Test creating link with required fields only."""
        link = ResourceLink(
            uri="graph://nodes/550e8400-e29b-41d4-a716-446655440000",
            title="View code graph"
        )

        assert link.uri == "graph://nodes/550e8400-e29b-41d4-a716-446655440000"
        assert link.title == "View code graph"
        assert link.description is None

    def test_link_with_description(self):
        """Test link with optional description."""
        link = ResourceLink(
            uri="memories://search/auth",
            title="Related memories",
            description="Search memories related to authentication"
        )

        assert link.description == "Search memories related to authentication"

    def test_various_uri_formats(self):
        """Test different MCP resource URI formats."""
        # Graph URI
        link1 = ResourceLink(uri="graph://callers/MyClass.method", title="Callers")
        assert "graph://" in link1.uri

        # Memory URI
        link2 = ResourceLink(uri="memories://get/123", title="Memory")
        assert "memories://" in link2.uri

        # Index URI
        link3 = ResourceLink(uri="index://status/default", title="Status")
        assert "index://" in link3.uri

    def test_json_serialization(self):
        """Test ResourceLink serializes to JSON correctly."""
        link = ResourceLink(
            uri="cache://stats",
            title="Cache Statistics"
        )

        json_str = link.model_dump_json()
        data = json.loads(json_str)

        assert data["uri"] == "cache://stats"
        assert data["title"] == "Cache Statistics"


# ============================================================================
# CacheMetadata Tests
# ============================================================================


class TestCacheMetadata:
    """Test CacheMetadata model."""

    def test_cache_miss(self):
        """Test cache miss metadata."""
        meta = CacheMetadata()

        assert meta.cache_hit is False
        assert meta.cache_key is None
        assert meta.ttl_seconds is None

    def test_cache_hit(self):
        """Test cache hit metadata."""
        meta = CacheMetadata(
            cache_hit=True,
            cache_key="search:a1b2c3d4",
            ttl_seconds=300
        )

        assert meta.cache_hit is True
        assert meta.cache_key == "search:a1b2c3d4"
        assert meta.ttl_seconds == 300

    def test_json_serialization(self):
        """Test CacheMetadata serializes correctly."""
        meta = CacheMetadata(
            cache_hit=True,
            cache_key="graph:xyz123",
            ttl_seconds=120
        )

        json_str = meta.model_dump_json()
        data = json.loads(json_str)

        assert data["cache_hit"] is True
        assert data["cache_key"] == "graph:xyz123"
        assert data["ttl_seconds"] == 120


# ============================================================================
# CodeChunk Tests
# ============================================================================


class TestCodeChunk:
    """Test CodeChunk model."""

    def test_minimal_chunk(self):
        """Test creating chunk with required fields."""
        chunk_id = uuid4()

        chunk = CodeChunk(
            id=chunk_id,
            file_path="api/main.py",
            start_line=10,
            end_line=25,
            content="def hello(): pass",
            language="python",
            chunk_type="function"
        )

        assert chunk.id == chunk_id
        assert chunk.file_path == "api/main.py"
        assert chunk.start_line == 10
        assert chunk.end_line == 25
        assert chunk.qualified_name is None
        assert chunk.score is None

    def test_chunk_with_qualified_name(self):
        """Test chunk with qualified name."""
        chunk = CodeChunk(
            id=uuid4(),
            file_path="api/models.py",
            start_line=50,
            end_line=75,
            content="class User: pass",
            language="python",
            chunk_type="class",
            qualified_name="api.models.User"
        )

        assert chunk.qualified_name == "api.models.User"

    def test_chunk_with_score(self):
        """Test chunk with search relevance score."""
        chunk = CodeChunk(
            id=uuid4(),
            file_path="test.py",
            start_line=1,
            end_line=10,
            content="code",
            language="python",
            chunk_type="function",
            score=0.89
        )

        assert chunk.score == 0.89
        assert 0.0 <= chunk.score <= 1.0

    def test_score_validation(self):
        """Test score must be in [0.0, 1.0] range."""
        with pytest.raises(ValidationError):
            CodeChunk(
                id=uuid4(),
                file_path="test.py",
                start_line=1,
                end_line=10,
                content="code",
                language="python",
                chunk_type="function",
                score=1.5  # Invalid
            )

    def test_chunk_with_timestamp(self):
        """Test chunk with indexed_at timestamp."""
        now = datetime.utcnow()

        chunk = CodeChunk(
            id=uuid4(),
            file_path="test.py",
            start_line=1,
            end_line=10,
            content="code",
            language="python",
            chunk_type="function",
            indexed_at=now
        )

        assert chunk.indexed_at == now


# ============================================================================
# Memory Tests
# ============================================================================


class TestMemory:
    """Test Memory model."""

    def test_minimal_memory(self):
        """Test creating memory with required fields."""
        memory_id = uuid4()
        now = datetime.utcnow()

        memory = Memory(
            id=memory_id,
            name="test-memory",
            content="This is a test memory",
            memory_type="note",
            tags=[],
            created_at=now,
            updated_at=now,
            resource_links=[],
            metadata={}
        )

        assert memory.id == memory_id
        assert memory.name == "test-memory"
        assert memory.memory_type == "note"
        assert memory.author is None
        assert memory.project_id is None

    def test_memory_types(self):
        """Test different memory types."""
        now = datetime.utcnow()

        for mem_type in ["note", "decision", "bug", "feature"]:
            memory = Memory(
                id=uuid4(),
                name=f"test-{mem_type}",
                content="content",
                memory_type=mem_type,
                tags=[],
                created_at=now,
                updated_at=now,
                resource_links=[],
                metadata={}
            )
            assert memory.memory_type == mem_type

    def test_memory_with_tags(self):
        """Test memory with tags."""
        memory = Memory(
            id=uuid4(),
            name="tagged-memory",
            content="content",
            memory_type="note",
            tags=["auth", "security", "jwt"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            resource_links=[],
            metadata={}
        )

        assert len(memory.tags) == 3
        assert "auth" in memory.tags
        assert "security" in memory.tags

    def test_memory_with_author(self):
        """Test memory with author."""
        memory = Memory(
            id=uuid4(),
            name="test",
            content="content",
            memory_type="decision",
            tags=[],
            author="developer@example.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            resource_links=[],
            metadata={}
        )

        assert memory.author == "developer@example.com"

    def test_memory_with_resource_links(self):
        """Test memory with MCP resource links."""
        link = ResourceLink(
            uri="graph://nodes/abc123",
            title="Related code"
        )

        memory = Memory(
            id=uuid4(),
            name="test",
            content="content",
            memory_type="note",
            tags=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            resource_links=[link],
            metadata={}
        )

        assert len(memory.resource_links) == 1
        assert memory.resource_links[0].uri == "graph://nodes/abc123"

    def test_memory_with_project_id(self):
        """Test memory with project association."""
        project_id = uuid4()

        memory = Memory(
            id=uuid4(),
            name="test",
            content="content",
            memory_type="note",
            tags=[],
            project_id=project_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            resource_links=[],
            metadata={}
        )

        assert memory.project_id == project_id


# ============================================================================
# CodeGraphNode Tests
# ============================================================================


class TestCodeGraphNode:
    """Test CodeGraphNode model."""

    def test_minimal_node(self):
        """Test creating node with required fields."""
        node_id = uuid4()
        chunk_id = uuid4()

        node = CodeGraphNode(
            id=node_id,
            chunk_id=chunk_id,
            name="authenticate_user",
            chunk_type="function",
            file_path="api/auth.py",
            language="python",
            metadata={}
        )

        assert node.id == node_id
        assert node.chunk_id == chunk_id
        assert node.name == "authenticate_user"
        assert node.qualified_name is None

    def test_node_with_qualified_name(self):
        """Test node with qualified name."""
        node = CodeGraphNode(
            id=uuid4(),
            chunk_id=uuid4(),
            name="User",
            qualified_name="api.models.User",
            chunk_type="class",
            file_path="api/models.py",
            language="python",
            metadata={}
        )

        assert node.qualified_name == "api.models.User"

    def test_node_with_metadata(self):
        """Test node with additional metadata."""
        node = CodeGraphNode(
            id=uuid4(),
            chunk_id=uuid4(),
            name="process_data",
            chunk_type="function",
            file_path="api/utils.py",
            language="python",
            metadata={
                "complexity": 8,
                "parameters": ["data", "options"],
                "return_type": "Dict[str, Any]"
            }
        )

        assert node.metadata["complexity"] == 8
        assert len(node.metadata["parameters"]) == 2


# ============================================================================
# CodeGraphEdge Tests
# ============================================================================


class TestCodeGraphEdge:
    """Test CodeGraphEdge model."""

    def test_basic_edge(self):
        """Test creating edge with required fields."""
        source_id = uuid4()
        target_id = uuid4()

        edge = CodeGraphEdge(
            source_id=source_id,
            target_id=target_id,
            relation_type="calls"
        )

        assert edge.source_id == source_id
        assert edge.target_id == target_id
        assert edge.relation_type == "calls"
        assert edge.weight == 1.0
        assert edge.metadata == {}

    def test_edge_relation_types(self):
        """Test different relation types."""
        source = uuid4()
        target = uuid4()

        for rel_type in ["calls", "imports", "inherits", "uses", "defines", "references"]:
            edge = CodeGraphEdge(
                source_id=source,
                target_id=target,
                relation_type=rel_type
            )
            assert edge.relation_type == rel_type

    def test_edge_with_weight(self):
        """Test edge with custom weight."""
        edge = CodeGraphEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            relation_type="calls",
            weight=5.0
        )

        assert edge.weight == 5.0

    def test_edge_weight_validation(self):
        """Test weight must be >= 0."""
        with pytest.raises(ValidationError):
            CodeGraphEdge(
                source_id=uuid4(),
                target_id=uuid4(),
                relation_type="calls",
                weight=-1.0  # Invalid
            )

    def test_edge_with_metadata(self):
        """Test edge with metadata."""
        edge = CodeGraphEdge(
            source_id=uuid4(),
            target_id=uuid4(),
            relation_type="calls",
            metadata={
                "call_count": 15,
                "file": "api/main.py",
                "line": 42
            }
        )

        assert edge.metadata["call_count"] == 15
        assert edge.metadata["line"] == 42


# ============================================================================
# ProjectInfo Tests
# ============================================================================


class TestProjectInfo:
    """Test ProjectInfo model."""

    def test_basic_project(self):
        """Test creating project info."""
        project_id = uuid4()

        project = ProjectInfo(
            id=project_id,
            name="mnemolite",
            indexed_files=234,
            total_chunks=1567,
            languages=[],
            is_active=False
        )

        assert project.id == project_id
        assert project.name == "mnemolite"
        assert project.indexed_files == 234
        assert project.total_chunks == 1567
        assert project.last_indexed is None

    def test_project_with_languages(self):
        """Test project with multiple languages."""
        project = ProjectInfo(
            id=uuid4(),
            name="polyglot-project",
            indexed_files=100,
            total_chunks=500,
            languages=["python", "javascript", "go", "rust"],
            is_active=True
        )

        assert len(project.languages) == 4
        assert "python" in project.languages
        assert "rust" in project.languages

    def test_active_project(self):
        """Test marking project as active."""
        project = ProjectInfo(
            id=uuid4(),
            name="current-project",
            indexed_files=50,
            total_chunks=200,
            languages=["python"],
            is_active=True
        )

        assert project.is_active is True

    def test_project_with_timestamp(self):
        """Test project with last indexed timestamp."""
        last_indexed = datetime.utcnow()

        project = ProjectInfo(
            id=uuid4(),
            name="test-project",
            indexed_files=10,
            total_chunks=50,
            languages=["python"],
            last_indexed=last_indexed,
            is_active=False
        )

        assert project.last_indexed == last_indexed


# ============================================================================
# CacheStats Tests
# ============================================================================


class TestCacheStats:
    """Test CacheStats model."""

    def test_basic_stats(self):
        """Test creating cache statistics."""
        stats = CacheStats(
            total_keys=1234,
            memory_usage_mb=45.6,
            hit_rate=0.82,
            total_hits=5678,
            total_misses=1234
        )

        assert stats.total_keys == 1234
        assert stats.memory_usage_mb == 45.6
        assert stats.hit_rate == 0.82
        assert stats.total_hits == 5678
        assert stats.total_misses == 1234

    def test_hit_rate_validation(self):
        """Test hit_rate must be in [0.0, 1.0] range."""
        with pytest.raises(ValidationError):
            CacheStats(
                total_keys=100,
                memory_usage_mb=10.0,
                hit_rate=1.5,  # Invalid
                total_hits=100,
                total_misses=10
            )

    def test_high_hit_rate(self):
        """Test cache stats with high hit rate."""
        stats = CacheStats(
            total_keys=5000,
            memory_usage_mb=120.5,
            hit_rate=0.95,
            total_hits=9500,
            total_misses=500
        )

        assert stats.hit_rate == 0.95
        assert stats.total_hits > stats.total_misses

    def test_low_memory_usage(self):
        """Test cache stats with low memory usage."""
        stats = CacheStats(
            total_keys=50,
            memory_usage_mb=1.2,
            hit_rate=0.60,
            total_hits=100,
            total_misses=67
        )

        assert stats.memory_usage_mb < 10.0
        assert stats.total_keys == 50

    def test_json_serialization(self):
        """Test CacheStats serializes to JSON."""
        stats = CacheStats(
            total_keys=1000,
            memory_usage_mb=50.0,
            hit_rate=0.75,
            total_hits=3000,
            total_misses=1000
        )

        json_str = stats.model_dump_json()
        data = json.loads(json_str)

        assert data["total_keys"] == 1000
        assert data["hit_rate"] == 0.75
        assert data["total_hits"] == 3000
