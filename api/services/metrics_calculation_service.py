"""
Service for calculating code quality metrics and graph analytics.
"""
import logging
from collections import defaultdict
from typing import Dict, List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text

logger = logging.getLogger(__name__)


class MetricsCalculationService:
    """
    Calculate code quality metrics and graph analytics.

    Responsibilities:
    - Coupling metrics (afferent, efferent, instability)
    - Graph centrality (PageRank, betweenness)
    - Edge weights (importance scoring)
    - Critical path detection
    """

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def calculate_coupling_for_node(
        self,
        node_id: UUID
    ) -> Dict[str, float]:
        """
        Calculate coupling metrics for a single node.

        Afferent coupling (Ca): Number of nodes that depend on this node
        Efferent coupling (Ce): Number of nodes this node depends on
        Instability (I): Ce / (Ca + Ce)

        Returns:
            {"afferent": int, "efferent": int, "instability": float}
        """
        # Count incoming edges (afferent)
        afferent_query = text("""
            SELECT COUNT(DISTINCT source_node_id)
            FROM edges
            WHERE target_node_id = :node_id
              AND relation_type = 'calls'
        """)

        # Count outgoing edges (efferent)
        efferent_query = text("""
            SELECT COUNT(DISTINCT target_node_id)
            FROM edges
            WHERE source_node_id = :node_id
              AND relation_type = 'calls'
        """)

        async with self.engine.connect() as conn:
            afferent_result = await conn.execute(afferent_query, {"node_id": str(node_id)})
            afferent = afferent_result.scalar() or 0

            efferent_result = await conn.execute(efferent_query, {"node_id": str(node_id)})
            efferent = efferent_result.scalar() or 0

        # Calculate instability
        total = afferent + efferent
        instability = efferent / total if total > 0 else 0.0

        return {
            "afferent": afferent,
            "efferent": efferent,
            "instability": instability
        }

    async def calculate_coupling_for_repository(
        self,
        repository: str
    ) -> Dict[UUID, Dict[str, float]]:
        """
        Calculate coupling metrics for all nodes in a repository.

        Returns:
            {node_id: {"afferent": int, "efferent": int, "instability": float}}
        """
        # Get all nodes for repository
        nodes_query = text("""
            SELECT node_id
            FROM nodes
            WHERE properties->>'repository' = :repository
        """)

        async with self.engine.connect() as conn:
            result = await conn.execute(nodes_query, {"repository": repository})
            node_ids = [row[0] if isinstance(row[0], UUID) else UUID(row[0]) for row in result.fetchall()]

        # Calculate coupling for each node
        coupling_metrics = {}
        for node_id in node_ids:
            coupling_metrics[node_id] = await self.calculate_coupling_for_node(node_id)

        logger.info(f"Calculated coupling for {len(coupling_metrics)} nodes in {repository}")
        return coupling_metrics

    async def calculate_pagerank(
        self,
        repository: str,
        damping: float = 0.85,
        max_iterations: int = 100,
        tolerance: float = 1e-6
    ) -> Dict[UUID, float]:
        """
        Calculate PageRank scores for all nodes in repository graph.

        PageRank measures node importance based on incoming edges.
        Higher score = more central/important in dependency graph.

        Args:
            repository: Repository name
            damping: Damping factor (0.85 = standard)
            max_iterations: Max iterations for convergence
            tolerance: Convergence threshold

        Returns:
            {node_id: pagerank_score}
        """
        # Get all nodes
        nodes_query = text("""
            SELECT node_id
            FROM nodes
            WHERE properties->>'repository' = :repository
        """)

        # Get all edges (calls relationships)
        edges_query = text("""
            SELECT e.source_node_id, e.target_node_id
            FROM edges e
            JOIN nodes n ON e.source_node_id = n.node_id
            WHERE n.properties->>'repository' = :repository
              AND e.relation_type = 'calls'
        """)

        async with self.engine.connect() as conn:
            nodes_result = await conn.execute(nodes_query, {"repository": repository})
            node_ids = [row[0] if isinstance(row[0], UUID) else UUID(row[0]) for row in nodes_result.fetchall()]

            edges_result = await conn.execute(edges_query, {"repository": repository})
            edges = [
                (row[0] if isinstance(row[0], UUID) else UUID(row[0]),
                 row[1] if isinstance(row[1], UUID) else UUID(row[1]))
                for row in edges_result.fetchall()
            ]

        if not node_ids:
            return {}

        # Build adjacency structure
        outlinks = defaultdict(list)
        for source, target in edges:
            outlinks[source].append(target)

        # Initialize PageRank scores (uniform distribution)
        num_nodes = len(node_ids)
        scores = {node_id: 1.0 / num_nodes for node_id in node_ids}

        # Iterative PageRank calculation
        for iteration in range(max_iterations):
            new_scores = {}

            for node in node_ids:
                # Base score (teleportation)
                rank = (1 - damping) / num_nodes

                # Sum contributions from incoming links
                for source in node_ids:
                    if node in outlinks[source]:
                        num_outlinks = len(outlinks[source])
                        rank += damping * (scores[source] / num_outlinks)

                new_scores[node] = rank

            # Check convergence
            diff = sum(abs(new_scores[n] - scores[n]) for n in node_ids)
            scores = new_scores

            if diff < tolerance:
                logger.info(f"PageRank converged after {iteration + 1} iterations")
                break

        # Normalize scores to sum to 1.0
        total = sum(scores.values())
        if total > 0:
            scores = {node: score / total for node, score in scores.items()}

        logger.info(f"Calculated PageRank for {len(scores)} nodes in {repository}")
        return scores

    async def calculate_edge_weights(
        self,
        repository: str,
        pagerank_scores: Dict[UUID, float]
    ) -> Dict[UUID, float]:
        """
        Calculate importance scores for edges based on PageRank propagation.

        Edge weight = (PageRank of source + PageRank of target) / 2
        This gives higher weight to edges between important nodes.

        Args:
            repository: Repository name
            pagerank_scores: Pre-calculated PageRank scores

        Returns:
            {edge_id: importance_score}
        """
        edges_query = text("""
            SELECT e.edge_id, e.source_node_id, e.target_node_id
            FROM edges e
            JOIN nodes n ON e.source_node_id = n.node_id
            WHERE n.properties->>'repository' = :repository
              AND e.relation_type = 'calls'
        """)

        async with self.engine.connect() as conn:
            result = await conn.execute(edges_query, {"repository": repository})
            edges = result.fetchall()

        edge_weights = {}
        for edge_id, source_id, target_id in edges:
            # Convert to UUID if needed
            edge_uuid = edge_id if isinstance(edge_id, UUID) else UUID(edge_id)
            source_uuid = source_id if isinstance(source_id, UUID) else UUID(source_id)
            target_uuid = target_id if isinstance(target_id, UUID) else UUID(target_id)

            source_score = pagerank_scores.get(source_uuid, 0.0)
            target_score = pagerank_scores.get(target_uuid, 0.0)

            # Average PageRank as edge importance
            importance = (source_score + target_score) / 2.0
            edge_weights[edge_uuid] = importance

        logger.info(f"Calculated weights for {len(edge_weights)} edges in {repository}")
        return edge_weights
