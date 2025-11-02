"""
Repository for computed_metrics table operations.
"""
import logging
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text
from models.metadata_models import ComputedMetrics

logger = logging.getLogger(__name__)


class ComputedMetricsRepository:
    """Repository for computed code quality metrics."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def create(
        self,
        node_id: UUID,
        chunk_id: UUID,
        repository: str,
        cyclomatic_complexity: int = 0,
        cognitive_complexity: int = 0,
        lines_of_code: int = 0,
        afferent_coupling: int = 0,
        efferent_coupling: int = 0,
        version: int = 1,
        connection=None
    ) -> ComputedMetrics:
        """Create computed metrics entry."""
        query = text("""
            INSERT INTO computed_metrics
            (node_id, chunk_id, repository, cyclomatic_complexity, cognitive_complexity,
             lines_of_code, afferent_coupling, efferent_coupling, version)
            VALUES (:node_id, :chunk_id, :repository, :cc, :cognitive, :loc, :ac, :ec, :version)
            RETURNING metric_id, node_id, chunk_id, repository, cyclomatic_complexity,
                      cognitive_complexity, lines_of_code, afferent_coupling, efferent_coupling,
                      pagerank_score, betweenness_centrality, version, computed_at
        """)

        params = {
            "node_id": str(node_id),
            "chunk_id": str(chunk_id),
            "repository": repository,
            "cc": cyclomatic_complexity,
            "cognitive": cognitive_complexity,
            "loc": lines_of_code,
            "ac": afferent_coupling,
            "ec": efferent_coupling,
            "version": version
        }

        if connection:
            result = await connection.execute(query, params)
            row = result.fetchone()
        else:
            async with self.engine.begin() as conn:
                result = await conn.execute(query, params)
                row = result.fetchone()

        return ComputedMetrics(
            metric_id=row[0],
            node_id=row[1],
            chunk_id=row[2],
            repository=row[3],
            cyclomatic_complexity=row[4],
            cognitive_complexity=row[5],
            lines_of_code=row[6],
            afferent_coupling=row[7],
            efferent_coupling=row[8],
            pagerank_score=row[9],
            betweenness_centrality=row[10],
            version=row[11],
            computed_at=row[12]
        )

    async def update_coupling(
        self,
        node_id: UUID,
        afferent_coupling: int,
        efferent_coupling: int,
        version: int = 1
    ) -> ComputedMetrics:
        """Update coupling metrics after graph construction."""
        query = text("""
            UPDATE computed_metrics
            SET afferent_coupling = :ac,
                efferent_coupling = :ec,
                computed_at = NOW()
            WHERE node_id = :node_id AND version = :version
            RETURNING metric_id, node_id, chunk_id, repository, cyclomatic_complexity,
                      cognitive_complexity, lines_of_code, afferent_coupling, efferent_coupling,
                      pagerank_score, betweenness_centrality, version, computed_at
        """)

        async with self.engine.begin() as conn:
            result = await conn.execute(query, {
                "node_id": str(node_id),
                "ac": afferent_coupling,
                "ec": efferent_coupling,
                "version": version
            })
            row = result.fetchone()

        return ComputedMetrics(
            metric_id=row[0],
            node_id=row[1],
            chunk_id=row[2],
            repository=row[3],
            cyclomatic_complexity=row[4],
            cognitive_complexity=row[5],
            lines_of_code=row[6],
            afferent_coupling=row[7],
            efferent_coupling=row[8],
            pagerank_score=row[9],
            betweenness_centrality=row[10],
            version=row[11],
            computed_at=row[12]
        )

    async def get_by_repository(self, repository: str, version: int = 1) -> List[ComputedMetrics]:
        """Get all metrics for a repository."""
        query = text("""
            SELECT metric_id, node_id, chunk_id, repository, cyclomatic_complexity,
                   cognitive_complexity, lines_of_code, afferent_coupling, efferent_coupling,
                   pagerank_score, betweenness_centrality, version, computed_at
            FROM computed_metrics
            WHERE repository = :repository AND version = :version
        """)

        async with self.engine.connect() as conn:
            result = await conn.execute(query, {"repository": repository, "version": version})
            rows = result.fetchall()

        return [
            ComputedMetrics(
                metric_id=row[0],
                node_id=row[1],
                chunk_id=row[2],
                repository=row[3],
                cyclomatic_complexity=row[4],
                cognitive_complexity=row[5],
                lines_of_code=row[6],
                afferent_coupling=row[7],
                efferent_coupling=row[8],
                pagerank_score=row[9],
                betweenness_centrality=row[10],
                version=row[11],
                computed_at=row[12]
            )
            for row in rows
        ]
