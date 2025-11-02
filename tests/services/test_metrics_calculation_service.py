import pytest
import uuid
from services.metrics_calculation_service import MetricsCalculationService
from sqlalchemy.sql import text


@pytest.mark.asyncio
async def test_calculate_coupling_metrics(clean_db):
    """Test afferent/efferent coupling calculation."""
    service = MetricsCalculationService(clean_db)

    # Mock graph structure:
    # NodeA -> NodeB
    # NodeA -> NodeC
    # NodeD -> NodeA
    #
    # For NodeA:
    # - Efferent coupling = 2 (depends on B, C)
    # - Afferent coupling = 1 (D depends on it)

    node_a_id = uuid.uuid4()
    node_b_id = uuid.uuid4()
    node_c_id = uuid.uuid4()
    node_d_id = uuid.uuid4()

    # Create nodes
    async with clean_db.begin() as conn:
        await conn.execute(text("""
            INSERT INTO nodes (node_id, node_type, label, properties)
            VALUES
                (:node_a, 'function', 'NodeA', '{"repository": "test_repo"}'::jsonb),
                (:node_b, 'function', 'NodeB', '{"repository": "test_repo"}'::jsonb),
                (:node_c, 'function', 'NodeC', '{"repository": "test_repo"}'::jsonb),
                (:node_d, 'function', 'NodeD', '{"repository": "test_repo"}'::jsonb)
        """), {
            "node_a": str(node_a_id),
            "node_b": str(node_b_id),
            "node_c": str(node_c_id),
            "node_d": str(node_d_id)
        })

        # Create edges: A->B, A->C, D->A
        await conn.execute(text("""
            INSERT INTO edges (edge_id, source_node_id, target_node_id, relation_type, properties)
            VALUES
                (:edge1, :node_a, :node_b, 'calls', '{}'::jsonb),
                (:edge2, :node_a, :node_c, 'calls', '{}'::jsonb),
                (:edge3, :node_d, :node_a, 'calls', '{}'::jsonb)
        """), {
            "edge1": str(uuid.uuid4()),
            "edge2": str(uuid.uuid4()),
            "edge3": str(uuid.uuid4()),
            "node_a": str(node_a_id),
            "node_b": str(node_b_id),
            "node_c": str(node_c_id),
            "node_d": str(node_d_id)
        })

    # Calculate coupling
    coupling = await service.calculate_coupling_for_node(node_a_id)

    assert coupling["afferent"] == 1
    assert coupling["efferent"] == 2
    assert coupling["instability"] == pytest.approx(0.667, rel=0.01)  # 2/(1+2)


@pytest.mark.asyncio
async def test_calculate_pagerank(clean_db):
    """Test PageRank calculation for graph."""
    service = MetricsCalculationService(clean_db)

    # Create simple graph: A -> B -> C, A -> C (triangle)
    repository = "test_repo_pagerank"
    node_a_id = uuid.uuid4()
    node_b_id = uuid.uuid4()
    node_c_id = uuid.uuid4()

    async with clean_db.begin() as conn:
        await conn.execute(text("""
            INSERT INTO nodes (node_id, node_type, label, properties)
            VALUES
                (:node_a, 'function', 'NodeA', '{"repository": "test_repo_pagerank"}'::jsonb),
                (:node_b, 'function', 'NodeB', '{"repository": "test_repo_pagerank"}'::jsonb),
                (:node_c, 'function', 'NodeC', '{"repository": "test_repo_pagerank"}'::jsonb)
        """), {
            "node_a": str(node_a_id),
            "node_b": str(node_b_id),
            "node_c": str(node_c_id)
        })

        # Create edges: A->B, B->C, A->C
        await conn.execute(text("""
            INSERT INTO edges (edge_id, source_node_id, target_node_id, relation_type, properties)
            VALUES
                (:edge1, :node_a, :node_b, 'calls', '{}'::jsonb),
                (:edge2, :node_b, :node_c, 'calls', '{}'::jsonb),
                (:edge3, :node_a, :node_c, 'calls', '{}'::jsonb)
        """), {
            "edge1": str(uuid.uuid4()),
            "edge2": str(uuid.uuid4()),
            "edge3": str(uuid.uuid4()),
            "node_a": str(node_a_id),
            "node_b": str(node_b_id),
            "node_c": str(node_c_id)
        })

    pagerank_scores = await service.calculate_pagerank(repository)

    # Check scores sum to 1.0
    assert sum(pagerank_scores.values()) == pytest.approx(1.0, rel=0.01)

    # Check all nodes have scores
    assert len(pagerank_scores) == 3
    assert node_a_id in pagerank_scores
    assert node_b_id in pagerank_scores
    assert node_c_id in pagerank_scores

    # C should have highest score (receives most incoming links)
    assert pagerank_scores[node_c_id] > pagerank_scores[node_a_id]


@pytest.mark.asyncio
async def test_calculate_edge_weights(clean_db):
    """Test edge weight calculation based on PageRank."""
    service = MetricsCalculationService(clean_db)

    repository = "test_repo_weights"
    node_a_id = uuid.uuid4()
    node_b_id = uuid.uuid4()
    edge_id = uuid.uuid4()

    async with clean_db.begin() as conn:
        await conn.execute(text("""
            INSERT INTO nodes (node_id, node_type, label, properties)
            VALUES
                (:node_a, 'function', 'NodeA', '{"repository": "test_repo_weights"}'::jsonb),
                (:node_b, 'function', 'NodeB', '{"repository": "test_repo_weights"}'::jsonb)
        """), {
            "node_a": str(node_a_id),
            "node_b": str(node_b_id)
        })

        await conn.execute(text("""
            INSERT INTO edges (edge_id, source_node_id, target_node_id, relation_type, properties)
            VALUES (:edge_id, :node_a, :node_b, 'calls', '{}'::jsonb)
        """), {
            "edge_id": str(edge_id),
            "node_a": str(node_a_id),
            "node_b": str(node_b_id)
        })

    # Calculate PageRank first
    pagerank_scores = await service.calculate_pagerank(repository)

    # Calculate edge weights
    edge_weights = await service.calculate_edge_weights(repository, pagerank_scores)

    assert edge_id in edge_weights
    assert 0.0 <= edge_weights[edge_id] <= 1.0


@pytest.mark.asyncio
async def test_calculate_coupling_for_repository(clean_db):
    """Test batch coupling calculation for entire repository."""
    service = MetricsCalculationService(clean_db)

    repository = "test_repo_batch"
    node_a_id = uuid.uuid4()
    node_b_id = uuid.uuid4()

    async with clean_db.begin() as conn:
        await conn.execute(text("""
            INSERT INTO nodes (node_id, node_type, label, properties)
            VALUES
                (:node_a, 'function', 'NodeA', '{"repository": "test_repo_batch"}'::jsonb),
                (:node_b, 'function', 'NodeB', '{"repository": "test_repo_batch"}'::jsonb)
        """), {
            "node_a": str(node_a_id),
            "node_b": str(node_b_id)
        })

        await conn.execute(text("""
            INSERT INTO edges (edge_id, source_node_id, target_node_id, relation_type, properties)
            VALUES (:edge_id, :node_a, :node_b, 'calls', '{}'::jsonb)
        """), {
            "edge_id": str(uuid.uuid4()),
            "node_a": str(node_a_id),
            "node_b": str(node_b_id)
        })

    # Calculate coupling for all nodes
    coupling_metrics = await service.calculate_coupling_for_repository(repository)

    assert len(coupling_metrics) == 2
    assert node_a_id in coupling_metrics
    assert node_b_id in coupling_metrics

    # NodeA has 1 outgoing edge
    assert coupling_metrics[node_a_id]["efferent"] == 1
    assert coupling_metrics[node_a_id]["afferent"] == 0

    # NodeB has 1 incoming edge
    assert coupling_metrics[node_b_id]["efferent"] == 0
    assert coupling_metrics[node_b_id]["afferent"] == 1
