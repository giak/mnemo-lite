"""
GraphConstructionService for EPIC-06 Phase 2 Story 4.

Constructs code dependency graphs from code chunks metadata.
"""

import logging
import time
import uuid
from collections import defaultdict
from typing import Dict, List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncEngine

from db.repositories.node_repository import NodeRepository
from db.repositories.edge_repository import EdgeRepository
from db.repositories.code_chunk_repository import CodeChunkRepository
from models.code_chunk_models import CodeChunkModel
from models.graph_models import GraphStats, NodeModel, EdgeModel

logger = logging.getLogger(__name__)


# Python built-ins (functions, types, exceptions) - Skip these in graph
PYTHON_BUILTINS: Set[str] = {
    # Functions
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
    "callable", "chr", "classmethod", "compile", "complex", "delattr",
    "dict", "dir", "divmod", "enumerate", "eval", "exec", "filter",
    "float", "format", "frozenset", "getattr", "globals", "hasattr",
    "hash", "help", "hex", "id", "input", "int", "isinstance",
    "issubclass", "iter", "len", "list", "locals", "map", "max",
    "memoryview", "min", "next", "object", "oct", "open", "ord",
    "pow", "print", "property", "range", "repr", "reversed", "round",
    "set", "setattr", "slice", "sorted", "staticmethod", "str", "sum",
    "super", "tuple", "type", "vars", "zip", "__import__",
    # Common exceptions
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "AttributeError", "ImportError", "RuntimeError", "NotImplementedError",
    "StopIteration", "AssertionError", "SystemExit", "KeyboardInterrupt",
    # Common types
    "None", "True", "False", "Ellipsis", "NotImplemented",
}


def is_builtin(name: str) -> bool:
    """Check if name is a Python built-in."""
    return name in PYTHON_BUILTINS


class GraphConstructionService:
    """
    Construct dependency graphs from code chunks metadata.

    Responsibilities:
    - Extract call graph from chunks
    - Extract import graph from chunks
    - Resolve function/class targets
    - Create nodes and edges
    - Store in PostgreSQL
    """

    def __init__(self, engine: AsyncEngine):
        """Initialize service with database engine."""
        self.engine = engine
        self.node_repo = NodeRepository(engine)
        self.edge_repo = EdgeRepository(engine)
        self.chunk_repo = CodeChunkRepository(engine)
        self.logger = logging.getLogger(__name__)
        self.logger.info("GraphConstructionService initialized.")

    async def build_graph_for_repository(
        self,
        repository: str,
        language: str = "python"
    ) -> GraphStats:
        """
        Build complete graph for a repository.

        Steps:
        1. Get all chunks for repository
        2. Create nodes for all functions/classes
        3. Resolve calls and imports
        4. Create edges
        5. Return statistics

        Args:
            repository: Repository name (e.g., "MnemoLite")
            language: Programming language (default: "python")

        Returns:
            GraphStats with construction metrics
        """
        start_time = time.time()
        self.logger.info(f"Building graph for repository '{repository}', language '{language}'")

        # Step 1: Get all chunks for repository
        chunks = await self._get_chunks_for_repository(repository, language)
        self.logger.info(f"Found {len(chunks)} chunks for repository '{repository}'")

        if not chunks:
            self.logger.warning(f"No chunks found for repository '{repository}'. Returning empty stats.")
            return GraphStats(
                repository=repository,
                total_nodes=0,
                total_edges=0,
                nodes_by_type={},
                edges_by_type={},
                construction_time_seconds=time.time() - start_time,
                resolution_accuracy=None
            )

        # Step 2: Create nodes for all functions/classes
        chunk_to_node = await self._create_nodes_from_chunks(chunks)
        self.logger.info(f"Created {len(chunk_to_node)} nodes")

        # Step 3 & 4: Create call and import edges
        call_edges = await self._create_all_call_edges(chunks, chunk_to_node)
        import_edges = await self._create_all_import_edges(chunks, chunk_to_node)

        total_edges = len(call_edges) + len(import_edges)
        self.logger.info(f"Created {len(call_edges)} call edges and {len(import_edges)} import edges")

        # Step 5: Compute statistics
        construction_time = time.time() - start_time

        # Count nodes by type
        nodes_by_type = defaultdict(int)
        for node in chunk_to_node.values():
            nodes_by_type[node.node_type] += 1

        # Count edges by type
        edges_by_type = {
            "calls": len(call_edges),
            "imports": len(import_edges),
        }

        # Compute resolution accuracy (calls resolved / total calls)
        total_calls = sum(
            len(chunk.metadata.get("calls", []))
            for chunk in chunks
            if chunk.metadata
        )
        resolution_accuracy = (len(call_edges) / total_calls * 100) if total_calls > 0 else 100.0

        stats = GraphStats(
            repository=repository,
            total_nodes=len(chunk_to_node),
            total_edges=total_edges,
            nodes_by_type=dict(nodes_by_type),
            edges_by_type=edges_by_type,
            construction_time_seconds=construction_time,
            resolution_accuracy=resolution_accuracy
        )

        self.logger.info(f"Graph construction complete: {stats.total_nodes} nodes, {stats.total_edges} edges, "
                        f"{stats.resolution_accuracy:.1f}% resolution accuracy, "
                        f"{stats.construction_time_seconds:.2f}s")

        return stats

    async def _get_chunks_for_repository(
        self,
        repository: str,
        language: str
    ) -> List[CodeChunkModel]:
        """
        Get all code chunks for repository.

        For now, uses a simple query. In future, could add caching.
        """
        # Build query to get all chunks for repository
        query_str = f"""
            SELECT * FROM code_chunks
            WHERE repository = '{repository}' AND language = '{language}'
        """

        # For simplicity, use chunk_repo's engine directly
        # In production, would add a dedicated method to chunk_repo
        async with self.engine.connect() as connection:
            from sqlalchemy.sql import text
            result = await connection.execute(text(query_str))
            rows = result.mappings().all()

        return [CodeChunkModel.from_db_record(row) for row in rows]

    async def _create_nodes_from_chunks(
        self,
        chunks: List[CodeChunkModel]
    ) -> Dict[uuid.UUID, NodeModel]:
        """
        Create node for each function/class chunk.

        Args:
            chunks: List of code chunks

        Returns:
            Mapping {chunk_id: node}
        """
        chunk_to_node: Dict[uuid.UUID, NodeModel] = {}

        for chunk in chunks:
            # Only create nodes for functions, methods, classes
            # Skip nodes for imports, file-level code, etc.
            if chunk.chunk_type not in ["function", "method", "class"]:
                continue

            # Determine node type
            node_type = chunk.chunk_type

            # Use chunk name as label (fallback to "anonymous")
            label = chunk.name if chunk.name else "anonymous"

            # Build node properties from chunk metadata
            properties = {
                "chunk_id": str(chunk.id),
                "file_path": chunk.file_path,
                "language": chunk.language,
                "repository": chunk.repository,  # CRITICAL: Store repository for filtering
                "signature": chunk.metadata.get("signature", ""),
                "complexity": chunk.metadata.get("complexity", {}),
                "is_builtin": False,
                "is_stdlib": False,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
            }

            # Create node
            try:
                node = await self.node_repo.create_code_node(
                    node_type=node_type,
                    label=label,
                    chunk_id=chunk.id,
                    file_path=chunk.file_path,
                    metadata=properties
                )
                chunk_to_node[chunk.id] = node
                self.logger.debug(f"Created node {node.node_id} for chunk {chunk.id} ({label})")
            except Exception as e:
                self.logger.error(f"Failed to create node for chunk {chunk.id}: {e}")
                # Continue with other chunks

        return chunk_to_node

    async def _create_all_call_edges(
        self,
        chunks: List[CodeChunkModel],
        chunk_to_node: Dict[uuid.UUID, NodeModel]
    ) -> List[EdgeModel]:
        """
        Create call edges for all chunks.

        For each chunk with metadata['calls'], resolve target and create edge.
        """
        all_edges: List[EdgeModel] = []

        for chunk in chunks:
            if chunk.id not in chunk_to_node:
                # No node for this chunk (e.g., import statement)
                continue

            node = chunk_to_node[chunk.id]

            # Get calls from metadata
            calls = chunk.metadata.get("calls", []) if chunk.metadata else []

            if not calls:
                continue

            # Create edges for each call
            edges = await self._create_call_edges(chunk, node, chunk_to_node, chunks)
            all_edges.extend(edges)

        return all_edges

    async def _create_call_edges(
        self,
        chunk: CodeChunkModel,
        node: NodeModel,
        chunk_to_node: Dict[uuid.UUID, NodeModel],
        all_chunks: List[CodeChunkModel]
    ) -> List[EdgeModel]:
        """
        Create call edges for a chunk.

        For each call in chunk.metadata['calls']:
        1. Resolve target chunk
        2. Get target node_id
        3. Create edge (source_node=node, target_node=target, relationship='calls')
        """
        edges: List[EdgeModel] = []
        calls = chunk.metadata.get("calls", []) if chunk.metadata else []

        for call_name in calls:
            # Skip built-ins
            if is_builtin(call_name):
                self.logger.debug(f"Skipping built-in call '{call_name}' from chunk {chunk.id}")
                continue

            # Resolve call target
            target_chunk_id = await self._resolve_call_target(call_name, chunk, all_chunks)

            if not target_chunk_id:
                self.logger.debug(f"Could not resolve call '{call_name}' from chunk {chunk.id}")
                continue

            # Get target node
            target_node = chunk_to_node.get(target_chunk_id)
            if not target_node:
                self.logger.debug(f"No node found for target chunk {target_chunk_id}")
                continue

            # Create edge
            try:
                edge = await self.edge_repo.create_dependency_edge(
                    source_node=node.node_id,
                    target_node=target_node.node_id,
                    relationship="calls",
                    metadata={
                        "call_name": call_name,
                        "source_file": chunk.file_path,
                        "target_file": target_node.properties.get("file_path", ""),
                    }
                )
                edges.append(edge)
                self.logger.debug(f"Created call edge: {node.label} -> {target_node.label}")
            except Exception as e:
                self.logger.error(f"Failed to create call edge: {e}")

        return edges

    async def _create_all_import_edges(
        self,
        chunks: List[CodeChunkModel],
        chunk_to_node: Dict[uuid.UUID, NodeModel]
    ) -> List[EdgeModel]:
        """
        Create import edges for all chunks.

        For each chunk with metadata['imports'], create edge to imported module.
        """
        all_edges: List[EdgeModel] = []

        for chunk in chunks:
            if chunk.id not in chunk_to_node:
                continue

            node = chunk_to_node[chunk.id]

            # Get imports from metadata
            imports = chunk.metadata.get("imports", []) if chunk.metadata else []

            if not imports:
                continue

            # Create edges for each import
            edges = await self._create_import_edges(chunk, node, chunk_to_node, chunks)
            all_edges.extend(edges)

        return all_edges

    async def _create_import_edges(
        self,
        chunk: CodeChunkModel,
        node: NodeModel,
        chunk_to_node: Dict[uuid.UUID, NodeModel],
        all_chunks: List[CodeChunkModel]
    ) -> List[EdgeModel]:
        """
        Create import edges for a chunk.

        Note: For MVP, we create "imports" edges between functions in the same repository.
        External imports (stdlib, packages) are skipped for Phase 1.
        """
        edges: List[EdgeModel] = []
        imports = chunk.metadata.get("imports", []) if chunk.metadata else []

        # TODO: Implement import resolution
        # For now, skip import edges (Phase 1 MVP focuses on call graph)
        # Can be added in Phase 2 if needed

        return edges

    async def _resolve_call_target(
        self,
        call_name: str,
        current_chunk: CodeChunkModel,
        all_chunks: List[CodeChunkModel]
    ) -> Optional[uuid.UUID]:
        """
        Resolve call target to chunk_id.

        Strategy:
        1. Check if built-in → return None (skip)
        2. Check local file → return chunk_id
        3. Check imports → resolve import → return chunk_id
        4. Not found → return None (log warning)

        Args:
            call_name: Name of function being called
            current_chunk: Chunk making the call
            all_chunks: All chunks in repository (for resolution)

        Returns:
            chunk_id of target, or None if not found
        """
        # 1. Skip built-ins
        if is_builtin(call_name):
            return None

        # 2. Check local file (same file_path)
        for chunk in all_chunks:
            if chunk.file_path == current_chunk.file_path and chunk.name == call_name:
                return chunk.id

        # 3. Check imports (simplified for MVP)
        # Extract imported names from metadata
        imports = current_chunk.metadata.get("imports", []) if current_chunk.metadata else []

        for imp in imports:
            # Simple heuristic: if import ends with call_name, it's a match
            # E.g., "from utils import calculate_total" → call_name = "calculate_total"
            if imp.endswith(call_name) or imp.endswith(f".{call_name}"):
                # Search for chunk with this name
                for chunk in all_chunks:
                    if chunk.name == call_name:
                        return chunk.id

        # 4. Not found
        return None
