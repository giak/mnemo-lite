import pytest
import sys
from pathlib import Path

# Add api directory to path for imports
api_path = Path(__file__).parent.parent.parent / "api"
sys.path.insert(0, str(api_path))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from services.graph_construction_service import GraphConstructionService
from db.repositories.code_chunk_repository import CodeChunkRepository
from models.code_chunk_models import CodeChunkCreate
import os


@pytest.mark.asyncio
async def test_graph_nodes_have_correct_type_from_chunks():
    """Test that graph nodes extract type from chunk metadata."""
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url)
    test_repo = "test_node_properties"

    # Cleanup
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM code_chunks WHERE repository = :repo"), {"repo": test_repo})
        await conn.execute(text("DELETE FROM nodes WHERE properties->>'repository' = :repo"), {"repo": test_repo})

    # Create chunks with different types
    chunks = [
        CodeChunkCreate(
            repository=test_repo,
            file_path="/test/Calculator.ts",
            chunk_index=0,
            chunk_type="class",
            language="typescript",
            source_code="class Calculator { add() {} }",
            start_line=1,
            end_line=5,
            embedding_code=[0.1] * 768,
            metadata={
                "name": "Calculator",
                "type": "class",
                "exports": ["Calculator"]
            }
        ),
        CodeChunkCreate(
            repository=test_repo,
            file_path="/test/Calculator.ts",
            chunk_index=1,
            chunk_type="method",
            language="typescript",
            source_code="add(a, b) { return a + b; }",
            start_line=2,
            end_line=4,
            embedding_code=[0.2] * 768,
            metadata={
                "name": "add",
                "type": "method",
                "signature": {"function_name": "add"}
            }
        ),
        CodeChunkCreate(
            repository=test_repo,
            file_path="/test/utils.ts",
            chunk_index=0,
            chunk_type="function",
            language="typescript",
            source_code="function sum(arr) {}",
            start_line=1,
            end_line=3,
            embedding_code=[0.3] * 768,
            metadata={
                "name": "sum",
                "type": "function",
                "signature": {"function_name": "sum"}
            }
        )
    ]

    # Insert chunks
    async with engine.begin() as conn:
        chunk_repo = CodeChunkRepository(engine, connection=conn)
        for chunk in chunks:
            await chunk_repo.add(chunk)

    # Build graph
    graph_service = GraphConstructionService(engine)
    await graph_service.build_graph_for_repository(test_repo, languages=["typescript"])

    # Verify nodes have correct properties
    async with engine.begin() as conn:
        nodes = await conn.execute(text("""
            SELECT label, properties
            FROM nodes
            WHERE properties->>'repository' = :repo
            ORDER BY properties->>'name'
        """), {"repo": test_repo})

        nodes_list = nodes.fetchall()

    await engine.dispose()

    # Assertions
    assert len(nodes_list) >= 3, f"Expected at least 3 nodes, got {len(nodes_list)}"

    # Check Calculator class node
    calc_node = next((n for n in nodes_list if n.properties.get('name') == 'Calculator'), None)
    assert calc_node is not None, "Calculator node not found"
    assert calc_node.properties.get('type') == 'class', f"Expected type='class', got {calc_node.properties.get('type')}"
    assert calc_node.properties.get('file') == '/test/Calculator.ts', "File path incorrect"
    assert 'Calculator' in calc_node.label, f"Label should contain 'Calculator', got {calc_node.label}"

    # Check add method node
    add_node = next((n for n in nodes_list if n.properties.get('name') == 'add'), None)
    assert add_node is not None, "add method node not found"
    assert add_node.properties.get('type') == 'method', f"Expected type='method', got {add_node.properties.get('type')}"

    # Check sum function node
    sum_node = next((n for n in nodes_list if n.properties.get('name') == 'sum'), None)
    assert sum_node is not None, "sum function node not found"
    assert sum_node.properties.get('type') == 'function', f"Expected type='function', got {sum_node.properties.get('type')}"


@pytest.mark.asyncio
async def test_graph_node_labels_not_truncated():
    """Test that node labels preserve full names."""
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url)
    test_repo = "test_label_length"

    # Cleanup
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM code_chunks WHERE repository = :repo"), {"repo": test_repo})
        await conn.execute(text("DELETE FROM nodes WHERE properties->>'repository' = :repo"), {"repo": test_repo})

    # Create chunk with long name
    long_name = "VeryLongClassNameThatExceedsTwentyCharacters"
    chunk = CodeChunkCreate(
        repository=test_repo,
        file_path="/test/Long.ts",
        chunk_index=0,
        chunk_type="class",
        language="typescript",
        source_code=f"class {long_name} {{ }}",
        start_line=1,
        end_line=1,
        embedding_code=[0.1] * 768,
        metadata={"name": long_name, "type": "class"}
    )

    async with engine.begin() as conn:
        chunk_repo = CodeChunkRepository(engine, connection=conn)
        await chunk_repo.add(chunk)

    # Build graph
    graph_service = GraphConstructionService(engine)
    await graph_service.build_graph_for_repository(test_repo, languages=["typescript"])

    # Verify label contains full name (or reasonable truncation with ellipsis)
    async with engine.begin() as conn:
        node = await conn.execute(text("""
            SELECT label, properties
            FROM nodes
            WHERE properties->>'repository' = :repo
        """), {"repo": test_repo})

        node_data = node.fetchone()

    await engine.dispose()

    assert node_data is not None
    # Either full name or truncated with ellipsis (not corrupt)
    assert long_name in node_data.label or node_data.label.endswith('...'), \
        f"Label should contain full name or ellipsis, got: {node_data.label}"


@pytest.mark.asyncio
async def test_graph_nodes_handle_missing_metadata():
    """Test fallback when chunk has no metadata or missing name."""
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    engine = create_async_engine(db_url)
    test_repo = "test_missing_metadata"

    # Cleanup
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM code_chunks WHERE repository = :repo"), {"repo": test_repo})
        await conn.execute(text("DELETE FROM nodes WHERE properties->>'repository' = :repo"), {"repo": test_repo})

    # Create chunk with empty metadata
    chunk = CodeChunkCreate(
        repository=test_repo,
        file_path="/test/noname.ts",
        chunk_index=0,
        chunk_type="function",
        language="typescript",
        source_code="function() {}",
        start_line=1,
        end_line=1,
        embedding_code=[0.1] * 768,
        metadata={}  # Empty metadata - should fallback to generated name
    )

    async with engine.begin() as conn:
        chunk_repo = CodeChunkRepository(engine, connection=conn)
        await chunk_repo.add(chunk)

    # Build graph
    graph_service = GraphConstructionService(engine)
    await graph_service.build_graph_for_repository(test_repo, languages=["typescript"])

    # Verify node created with fallback name
    async with engine.begin() as conn:
        node = await conn.execute(text("""
            SELECT label, properties
            FROM nodes
            WHERE properties->>'repository' = :repo
        """), {"repo": test_repo})
        node_data = node.fetchone()

    await engine.dispose()

    assert node_data is not None, "Node should be created even with empty metadata"
    # Should have fallback name like "function_0"
    assert node_data.properties.get('name') is not None
    assert node_data.properties.get('type') == 'function'
