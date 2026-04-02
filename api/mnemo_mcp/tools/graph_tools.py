"""
MCP Graph Tools (EPIC-31 Story 31.1).

Tools for code graph navigation and analysis.
"""
import structlog
from typing import Optional

from mcp.server.fastmcp import Context

from mnemo_mcp.base import BaseMCPComponent

logger = structlog.get_logger()


class GetGraphStatsTool(BaseMCPComponent):
    """Tool: get_graph_stats — Get code graph statistics."""

    def get_name(self) -> str:
        return "get_graph_stats"

    def get_description(self) -> str:
        return (
            "Get code graph statistics for a repository including "
            "node count, edge count, module count, and top hubs."
        )

    async def execute(
        self,
        repository: str = "default",
        ctx: Optional[Context] = None,
    ) -> dict:
        """Get graph stats."""
        engine = self._services.get("engine") if self._services else None
        if not engine:
            return {"success": False, "message": "Database engine not available"}

        try:
            from sqlalchemy import text
            async with engine.connect() as conn:
                # Node stats
                node_result = await conn.execute(text("""
                    SELECT COUNT(*) as total_nodes,
                           COUNT(DISTINCT module) as modules,
                           COUNT(DISTINCT language) as languages
                    FROM graph_nodes
                    WHERE repository = :repo
                """), {"repo": repository})
                node_row = node_result.fetchone()

                # Edge stats
                edge_result = await conn.execute(text("""
                    SELECT COUNT(*) as total_edges,
                           COUNT(DISTINCT type) as edge_types
                    FROM graph_edges
                    WHERE repository = :repo
                """), {"repo": repository})
                edge_row = edge_result.fetchone()

                # Top hubs (most connections)
                hub_result = await conn.execute(text("""
                    SELECT gn.name, gn.module, gn.language, COUNT(ge.id) as connections
                    FROM graph_nodes gn
                    LEFT JOIN graph_edges ge ON (ge.source_id = gn.id OR ge.target_id = gn.id)
                    WHERE gn.repository = :repo
                    GROUP BY gn.id, gn.name, gn.module, gn.language
                    ORDER BY connections DESC
                    LIMIT 10
                """), {"repo": repository})
                hubs = [{"name": r[0], "module": r[1], "language": r[2], "connections": r[3]}
                        for r in hub_result.fetchall()]

            return {
                "success": True,
                "repository": repository,
                "total_nodes": node_row[0] if node_row else 0,
                "modules": node_row[1] if node_row else 0,
                "languages": node_row[2] if node_row else 0,
                "total_edges": edge_row[0] if edge_row else 0,
                "edge_types": edge_row[1] if edge_row else 0,
                "top_hubs": hubs,
            }

        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to get graph stats: {e}"}


class TraverseGraphTool(BaseMCPComponent):
    """Tool: traverse_graph — Navigate the code graph from a node."""

    def get_name(self) -> str:
        return "traverse_graph"

    def get_description(self) -> str:
        return (
            "Traverse the code graph from a given node. "
            "Returns connected nodes (callers/callees/imports) up to a given depth."
        )

    async def execute(
        self,
        node_id: str,
        direction: str = "outgoing",
        depth: int = 1,
        repository: str = "default",
        ctx: Optional[Context] = None,
    ) -> dict:
        """Traverse graph from a node."""
        engine = self._services.get("engine") if self._services else None
        if not engine:
            return {"success": False, "message": "Database engine not available"}

        try:
            from sqlalchemy import text
            async with engine.connect() as conn:
                # Get starting node
                node_result = await conn.execute(text("""
                    SELECT id, name, module, language, file_path
                    FROM graph_nodes WHERE id = :node_id AND repository = :repo
                """), {"node_id": node_id, "repo": repository})
                node_row = node_result.fetchone()
                if not node_row:
                    return {"success": False, "message": f"Node {node_id} not found"}

                # Get connected nodes
                if direction == "outgoing":
                    join_clause = "ge.source_id = gn.id"
                elif direction == "incoming":
                    join_clause = "ge.target_id = gn.id"
                else:
                    join_clause = "(ge.source_id = gn.id OR ge.target_id = gn.id)"

                result = await conn.execute(text(f"""
                    SELECT DISTINCT gn.id, gn.name, gn.module, gn.language,
                           ge.type as edge_type, ge.source_id, ge.target_id
                    FROM graph_edges ge
                    JOIN graph_nodes gn ON {join_clause}
                    WHERE ge.repository = :repo
                      AND (ge.source_id = :node_id OR ge.target_id = :node_id)
                    ORDER BY gn.module, gn.name
                """), {"node_id": node_id, "repo": repository})

                connected = []
                for row in result.fetchall():
                    connected.append({
                        "id": row[0],
                        "name": row[1],
                        "module": row[2],
                        "language": row[3],
                        "edge_type": row[4],
                        "direction": "outgoing" if row[5] == node_id else "incoming",
                    })

            return {
                "success": True,
                "repository": repository,
                "source_node": {
                    "id": node_row[0], "name": node_row[1],
                    "module": node_row[2], "language": node_row[3],
                    "file_path": node_row[4],
                },
                "direction": direction,
                "depth": depth,
                "connected_nodes": connected,
                "total_connections": len(connected),
            }

        except Exception as e:
            logger.error(f"Failed to traverse graph: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to traverse graph: {e}"}


class FindPathTool(BaseMCPComponent):
    """Tool: find_path — Find path between two nodes in the code graph."""

    def get_name(self) -> str:
        return "find_path"

    def get_description(self) -> str:
        return (
            "Find a path between two nodes in the code graph. "
            "Returns the sequence of nodes and edges connecting them."
        )

    async def execute(
        self,
        source_id: str,
        target_id: str,
        repository: str = "default",
        max_depth: int = 5,
        ctx: Optional[Context] = None,
    ) -> dict:
        """Find path between two nodes using BFS."""
        engine = self._services.get("engine") if self._services else None
        if not engine:
            return {"success": False, "message": "Database engine not available"}

        try:
            from sqlalchemy import text
            from collections import deque

            async with engine.connect() as conn:
                # Verify nodes exist
                for nid, label in [(source_id, "source"), (target_id, "target")]:
                    r = await conn.execute(text("""
                        SELECT name, module FROM graph_nodes
                        WHERE id = :node_id AND repository = :repo
                    """), {"node_id": nid, "repo": repository})
                    if not r.fetchone():
                        return {"success": False, "message": f"{label} node {nid} not found"}

                # Load adjacency list
                edge_result = await conn.execute(text("""
                    SELECT source_id, target_id, type
                    FROM graph_edges
                    WHERE repository = :repo
                """), {"repo": repository})

                # Build adjacency (bidirectional)
                adj = {}
                edge_types = {}
                for row in edge_result.fetchall():
                    src, tgt, etype = row
                    adj.setdefault(src, []).append(tgt)
                    adj.setdefault(tgt, []).append(src)
                    edge_types[(src, tgt)] = etype
                    edge_types[(tgt, src)] = etype

            # BFS
            queue = deque([(source_id, [source_id])])
            visited = {source_id}

            while queue:
                current, path = queue.popleft()
                if len(path) > max_depth:
                    continue
                if current == target_id:
                    # Build path with edge info
                    nodes_path = []
                    edges_path = []
                    for i, nid in enumerate(path):
                        async with engine.connect() as conn:
                            r = await conn.execute(text("""
                                SELECT name, module, language FROM graph_nodes
                                WHERE id = :nid AND repository = :repo
                            """), {"nid": nid, "repo": repository})
                            nr = r.fetchone()
                            if nr:
                                nodes_path.append({"id": nid, "name": nr[0], "module": nr[1], "language": nr[2]})
                        if i > 0:
                            prev = path[i-1]
                            edges_path.append({
                                "from": prev, "to": nid,
                                "type": edge_types.get((prev, nid), "unknown"),
                            })
                    return {
                        "success": True,
                        "repository": repository,
                        "source": source_id,
                        "target": target_id,
                        "path_length": len(path),
                        "nodes": nodes_path,
                        "edges": edges_path,
                    }
                for neighbor in adj.get(current, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, path + [neighbor]))

            return {
                "success": True,
                "repository": repository,
                "source": source_id,
                "target": target_id,
                "path_found": False,
                "message": f"No path found within {max_depth} hops",
            }

        except Exception as e:
            logger.error(f"Failed to find path: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to find path: {e}"}


class GetModuleDataTool(BaseMCPComponent):
    """Tool: get_module_data — Get data for a specific module."""

    def get_name(self) -> str:
        return "get_module_data"

    def get_description(self) -> str:
        return (
            "Get detailed data for a module including all nodes, "
            "internal/external connections, and complexity metrics."
        )

    async def execute(
        self,
        module_path: str,
        repository: str = "default",
        ctx: Optional[Context] = None,
    ) -> dict:
        """Get module data."""
        engine = self._services.get("engine") if self._services else None
        if not engine:
            return {"success": False, "message": "Database engine not available"}

        try:
            from sqlalchemy import text
            async with engine.connect() as conn:
                # Get all nodes in module
                nodes_result = await conn.execute(text("""
                    SELECT id, name, language, file_path, node_type
                    FROM graph_nodes
                    WHERE repository = :repo AND module = :module
                    ORDER BY name
                """), {"repo": repository, "module": module_path})
                nodes = [{"id": r[0], "name": r[1], "language": r[2],
                          "file_path": r[3], "node_type": r[4]}
                         for r in nodes_result.fetchall()]

                if not nodes:
                    return {"success": False, "message": f"Module {module_path} not found"}

                node_ids = [n["id"] for n in nodes]

                # Internal edges
                internal_result = await conn.execute(text("""
                    SELECT ge.type, COUNT(*) as cnt
                    FROM graph_edges ge
                    WHERE ge.repository = :repo
                      AND ge.source_id = ANY(:nids)
                      AND ge.target_id = ANY(:nids)
                    GROUP BY ge.type
                """), {"repo": repository, "nids": node_ids})
                internal_edges = {r[0]: r[1] for r in internal_result.fetchall()}

                # External connections
                external_result = await conn.execute(text("""
                    SELECT ge.type,
                           COUNT(DISTINCT CASE WHEN ge.source_id = ANY(:nids) THEN ge.target_id ELSE ge.source_id END) as external_nodes
                    FROM graph_edges ge
                    WHERE ge.repository = :repo
                      AND (ge.source_id = ANY(:nids) OR ge.target_id = ANY(:nids))
                      AND NOT (ge.source_id = ANY(:nids) AND ge.target_id = ANY(:nids))
                    GROUP BY ge.type
                """), {"repo": repository, "nids": node_ids})
                external_edges = {r[0]: r[1] for r in external_result.fetchall()}

                return {
                    "success": True,
                    "repository": repository,
                    "module": module_path,
                    "total_nodes": len(nodes),
                    "nodes": nodes,
                    "internal_edges": internal_edges,
                    "external_connections": external_edges,
                    "total_internal": sum(internal_edges.values()),
                    "total_external": sum(external_edges.values()),
                }

        except Exception as e:
            logger.error(f"Failed to get module data: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to get module data: {e}"}


# Singleton instances
get_graph_stats_tool = GetGraphStatsTool()
traverse_graph_tool = TraverseGraphTool()
find_path_tool = FindPathTool()
get_module_data_tool = GetModuleDataTool()
