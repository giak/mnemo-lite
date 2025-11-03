"""
GraphConstructionService for EPIC-06 Phase 2 Story 4.

Constructs code dependency graphs from code chunks metadata.

EPIC-12 Story 12.1: Added timeout protection for graph construction.
"""

import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncEngine

from db.repositories.node_repository import NodeRepository
from db.repositories.edge_repository import EdgeRepository
from db.repositories.code_chunk_repository import CodeChunkRepository
from models.code_chunk_models import CodeChunkModel
from models.graph_models import GraphStats, NodeModel, EdgeModel
from utils.timeout import with_timeout, TimeoutError
from config.timeouts import get_timeout

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
        languages: Optional[List[str]] = None
    ) -> GraphStats:
        """
        Build complete graph for a repository (multi-language support).

        Steps:
        1. Get all chunks for repository (across all languages)
        2. Create nodes for all functions/classes
        3. Resolve calls and imports
        4. Create edges
        5. Return statistics

        Args:
            repository: Repository name (e.g., "MnemoLite")
            languages: List of languages to include (default: auto-detect all)

        Returns:
            GraphStats with construction metrics

        EPIC-15 Story 15.3: Multi-language graph construction
        """
        start_time = time.time()

        # Auto-detect languages if not specified
        if languages is None:
            languages = await self._detect_languages_in_repository(repository)

        self.logger.info(f"Building graph for repository '{repository}', languages: {languages}")

        # Step 1: Get all chunks for ALL languages
        all_chunks = []
        for language in languages:
            chunks = await self._get_chunks_for_repository(repository, language)
            all_chunks.extend(chunks)

        self.logger.info(f"Found {len(all_chunks)} chunks for repository '{repository}' across {len(languages)} languages")
        chunks = all_chunks  # Use aggregated chunks for rest of processing

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

        # EPIC-12 Story 12.2: Wrap graph construction in transaction
        # If node creation or edge creation fails, entire graph is rolled back (atomic operation)
        try:
            async with self.engine.begin() as conn:
                self.logger.info(
                    f"EPIC-12: Starting graph construction transaction for repository '{repository}'"
                )

                # Step 2: Create nodes for all functions/classes with timeout protection
                # EPIC-12 Story 12.1: Prevent infinite hangs on large repositories
                try:
                    chunk_to_node = await with_timeout(
                        self._create_nodes_from_chunks(chunks, connection=conn),
                        timeout=get_timeout("graph_construction"),
                        operation_name="graph_node_creation",
                        context={"repository": repository, "chunk_count": len(chunks)},
                        raise_on_timeout=True
                    )
                    self.logger.info(f"Created {len(chunk_to_node)} nodes")

                except TimeoutError as e:
                    self.logger.error(
                        f"Node creation timed out for repository '{repository}' after {get_timeout('graph_construction')}s",
                        extra={"repository": repository, "chunk_count": len(chunks), "error": str(e)}
                    )
                    raise

                # Step 3 & 4: Create call and import edges with timeout protection
                # EPIC-12 Story 12.1: Prevent infinite hangs on complex graphs
                try:
                    call_edges = await with_timeout(
                        self._create_all_call_edges(chunks, chunk_to_node, connection=conn),
                        timeout=get_timeout("graph_construction"),
                        operation_name="graph_call_edge_creation",
                        context={"repository": repository, "node_count": len(chunk_to_node)},
                        raise_on_timeout=True
                    )
                    import_edges = await with_timeout(
                        self._create_all_import_edges(chunks, chunk_to_node, connection=conn),
                        timeout=get_timeout("graph_construction"),
                        operation_name="graph_import_edge_creation",
                        context={"repository": repository, "node_count": len(chunk_to_node)},
                        raise_on_timeout=True
                    )

                    # EPIC-29 Task 5: Create re-export edges for barrel chunks
                    reexport_edge_dicts = []
                    barrel_chunks = [c for c in chunks if c.chunk_type == "barrel"]
                    for barrel in barrel_chunks:
                        edges = await self._create_reexport_edges(barrel, chunks)
                        reexport_edge_dicts.extend(edges)

                    # Save re-export edges to database
                    reexport_edges = []
                    for edge_dict in reexport_edge_dicts:
                        # Get source and target nodes
                        source_node = chunk_to_node.get(edge_dict["source_chunk_id"])
                        target_node = chunk_to_node.get(edge_dict["target_chunk_id"])

                        if source_node and target_node:
                            edge = await self.edge_repo.create_dependency_edge(
                                source_node=source_node.node_id,
                                target_node=target_node.node_id,
                                relationship=edge_dict["edge_type"],
                                metadata=edge_dict["properties"],
                                connection=conn,
                            )
                            reexport_edges.append(edge)

                    # Generate structural hierarchy (contains) edges
                    self.logger.info("Generating structural hierarchy (contains edges)...")
                    nodes_list = list(chunk_to_node.values())
                    contains_edge_models = await self._generate_contains_edges(nodes_list)

                    # Persist contains edges to database
                    contains_edges = []
                    for edge_model in contains_edge_models:
                        try:
                            edge = await self.edge_repo.create_dependency_edge(
                                source_node=edge_model.source_node_id,
                                target_node=edge_model.target_node_id,
                                relationship=edge_model.relation_type,
                                metadata=edge_model.properties,
                                connection=conn,
                            )
                            contains_edges.append(edge)
                        except Exception as e:
                            self.logger.warning(f"Failed to create contains edge: {e}")
                            continue

                    self.logger.info(f"Created {len(contains_edges)} contains edges")

                except TimeoutError as e:
                    self.logger.error(
                        f"Edge creation timed out for repository '{repository}' after {get_timeout('graph_construction')}s",
                        extra={"repository": repository, "node_count": len(chunk_to_node), "error": str(e)}
                    )
                    raise

                # Transaction auto-commits on successful context exit
                self.logger.info(
                    f"✅ EPIC-12: Graph construction transaction committed - "
                    f"{len(chunk_to_node)} nodes and {len(call_edges) + len(import_edges) + len(reexport_edges) + len(contains_edges)} edges stored atomically"
                )

        except Exception as e:
            # Transaction auto-rolled back on exception
            self.logger.error(
                f"EPIC-12: Graph construction transaction rolled back: {e}",
                exc_info=True
            )
            raise

        total_edges = len(call_edges) + len(import_edges) + len(reexport_edges) + len(contains_edges)
        self.logger.info(
            f"Created {len(call_edges)} call edges, {len(import_edges)} import edges, "
            f"{len(reexport_edges)} re-export edges, and {len(contains_edges)} contains edges"
        )

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
            "re_exports": len(reexport_edges),
            "contains": len(contains_edges),
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

        # Calculate metrics (NEW - Task 5.2)
        await self.calculate_and_store_metrics(repository, chunk_to_node)

        return stats

    async def calculate_and_store_metrics(
        self,
        repository: str,
        chunk_to_node: Dict[uuid.UUID, NodeModel]
    ) -> None:
        """
        Calculate and store graph metrics after construction.

        Steps:
        1. Calculate coupling metrics for all nodes
        2. Calculate PageRank scores
        3. Update computed_metrics table with coupling and PageRank
        4. Calculate and store edge weights

        Args:
            repository: Repository name
            chunk_to_node: Mapping from chunk IDs to node models
        """
        from services.metrics_calculation_service import MetricsCalculationService
        from db.repositories.computed_metrics_repository import ComputedMetricsRepository
        from db.repositories.edge_weights_repository import EdgeWeightsRepository

        self.logger.info(f"Calculating metrics for repository '{repository}'...")

        metrics_service = MetricsCalculationService(self.engine)
        metrics_repo = ComputedMetricsRepository(self.engine)
        weights_repo = EdgeWeightsRepository(self.engine)

        try:
            # 1. Calculate coupling for all nodes
            self.logger.info("Calculating coupling metrics...")
            coupling_metrics = await metrics_service.calculate_coupling_for_repository(repository)

            # 2. Calculate PageRank
            self.logger.info("Calculating PageRank scores...")
            pagerank_scores = await metrics_service.calculate_pagerank(repository)

            # 3. Update computed_metrics with coupling and PageRank
            self.logger.info("Updating computed_metrics table...")
            for chunk_id, node in chunk_to_node.items():
                # DEFENSIVE: Ensure coupling is a dict with required keys
                coupling = coupling_metrics.get(node.node_id)
                if coupling is None or not isinstance(coupling, dict):
                    coupling = {"afferent": 0, "efferent": 0}

                # DEFENSIVE: Ensure coupling has required keys
                if "afferent" not in coupling or "efferent" not in coupling:
                    coupling = {"afferent": coupling.get("afferent", 0), "efferent": coupling.get("efferent", 0)}

                pagerank = pagerank_scores.get(node.node_id, 0.0)

                try:
                    await metrics_repo.update_coupling(
                        node_id=node.node_id,
                        afferent_coupling=coupling["afferent"],
                        efferent_coupling=coupling["efferent"],
                        version=1
                    )

                    # Update PageRank score
                    await metrics_repo.update_pagerank(
                        node_id=node.node_id,
                        pagerank_score=pagerank,
                        version=1
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to update metrics for node {node.node_id}: {e}")
                    continue

            # 4. Calculate and store edge weights
            self.logger.info("Calculating edge weights...")
            edge_weights = await metrics_service.calculate_edge_weights(repository, pagerank_scores)

            for edge_id, importance in edge_weights.items():
                try:
                    await weights_repo.create_or_update(
                        edge_id=edge_id,
                        importance_score=importance,
                        version=1
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to store edge weight for edge {edge_id}: {e}")
                    continue

            self.logger.info(
                f"✅ Metrics calculated: {len(coupling_metrics)} nodes, "
                f"{len(edge_weights)} edges weighted"
            )

        except Exception as e:
            self.logger.error(f"Failed to calculate metrics for repository '{repository}': {e}", exc_info=True)
            # Don't raise - metrics are supplementary, graph construction still succeeded
            self.logger.warning("Continuing without metrics - graph construction completed successfully")

    async def _detect_languages_in_repository(
        self,
        repository: str
    ) -> List[str]:
        """
        Detect which languages exist in a repository.

        Returns:
            List of unique language names found in chunks

        EPIC-15 Story 15.3: Auto-detect languages for multi-language repos
        """
        query_str = """
            SELECT DISTINCT language
            FROM code_chunks
            WHERE repository = :repository
            ORDER BY language
        """

        async with self.engine.connect() as connection:
            from sqlalchemy.sql import text
            result = await connection.execute(
                text(query_str),
                {"repository": repository}
            )
            rows = result.fetchall()

        languages = [row[0] for row in rows if row[0]]

        if not languages:
            self.logger.warning(f"No languages found for repository '{repository}'")
            return []

        self.logger.info(f"Detected languages for repository '{repository}': {languages}")
        return languages

    async def _get_chunks_for_repository(
        self,
        repository: str,
        language: str
    ) -> List[CodeChunkModel]:
        """
        Get all code chunks for repository and specific language.

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

    async def _create_node_from_chunk(self, chunk: CodeChunkModel) -> dict:
        """
        Create node dictionary from code chunk.

        EPIC-29 Task 5: Extracts node creation logic for testability and barrel support.
        Extracts type, name, and file path from chunk metadata.

        Args:
            chunk: Code chunk to convert to node

        Returns:
            Dictionary with 'label', 'node_type', and 'properties' keys
        """
        # Extract metadata
        metadata = chunk.metadata or {}
        chunk_type = chunk.chunk_type  # class, method, function, interface

        # Get name from metadata (priority order)
        # Use safer signature access to handle None values
        signature = metadata.get('signature')
        function_name = signature.get('function_name') if isinstance(signature, dict) else None
        name = metadata.get('name') or function_name or chunk.name or f"{chunk_type}_{str(chunk.id)[:8]}"

        # Get type (use chunk_type or metadata.type)
        node_type_from_metadata = metadata.get('type') or chunk_type

        # Determine node type based on chunk_type (for backwards compatibility with graph structure)
        if chunk.chunk_type == "barrel":
            node_type = "Module"  # Barrels are Module nodes
        elif chunk.chunk_type == "config_module":
            node_type = "Config"
        elif chunk.chunk_type in ("class", "interface"):
            node_type = "Class"
        elif chunk.chunk_type in ("function", "method", "arrow_function", "async_function"):
            node_type = "Function"
        else:
            node_type = chunk.chunk_type  # Use chunk type as-is for others

        # Create label (use full name, truncate only if absolutely necessary)
        label = name
        if len(label) > 100:  # Reasonable limit
            label = label[:97] + "..."

        # Build properties
        properties = {
            # Semantic type: class/function/method/interface (from chunk metadata)
            "type": node_type_from_metadata,
            # Graph node category: Class/Function/Module (for graph queries and visualization)
            "node_type": node_type,
            "name": name,
            "file": chunk.file_path,  # Use 'file' instead of 'file_path' for consistency
            "file_path": chunk.file_path,
            "language": chunk.language,
            "repository": chunk.repository,
            "is_builtin": False,
            "is_stdlib": False,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "chunk_id": str(chunk.id),
        }

        # Add complexity if available
        if 'complexity' in metadata:
            complexity = metadata['complexity']
            if isinstance(complexity, dict):
                properties['cyclomatic_complexity'] = complexity.get('cyclomatic', 0)
                properties['lines_of_code'] = complexity.get('lines_of_code', 0)

        # EPIC-29: Add barrel-specific properties
        if chunk.chunk_type == "barrel":
            properties["is_barrel"] = True
            properties["re_exports"] = chunk.metadata.get("re_exports", [])
        else:
            properties["is_barrel"] = False

        # Add function/method metadata
        if node_type == "Function":
            properties["signature"] = chunk.metadata.get("signature", "")
            if "complexity" not in properties:
                properties["complexity"] = chunk.metadata.get("complexity", {})

        return {
            "label": label,
            "node_type": node_type,
            "properties": properties
        }

    async def _create_nodes_from_chunks(
        self,
        chunks: List[CodeChunkModel],
        connection=None,
    ) -> Dict[uuid.UUID, NodeModel]:
        """
        Create node for each function/class chunk.

        Args:
            chunks: List of code chunks
            connection: Optional external connection for transaction support (EPIC-12 Story 12.2)

        Returns:
            Mapping {chunk_id: node}
        """
        chunk_to_node: Dict[uuid.UUID, NodeModel] = {}

        for chunk in chunks:
            # EPIC-29: Include barrels and config modules
            # Skip only imports and file-level code
            if chunk.chunk_type not in ["function", "method", "class", "barrel", "config_module",
                                       "interface", "arrow_function", "async_function"]:
                continue

            # EPIC-30: Filter anonymous functions to reduce graph noise
            # Filters 413/581 nodes (71%) in CVGenerator: anonymous_arrow_function, anonymous_method_definition
            if chunk.name and chunk.name.startswith("anonymous"):
                self.logger.debug(f"Skipping anonymous function: {chunk.name} in {chunk.file_path}:{chunk.start_line}")
                continue

            # Create node dict using helper
            node_dict = await self._create_node_from_chunk(chunk)

            # Create node in database (EPIC-12 Story 12.2: Pass connection for transaction support)
            try:
                node = await self.node_repo.create_code_node(
                    node_type=node_dict["node_type"],
                    label=node_dict["label"],
                    chunk_id=chunk.id,
                    file_path=chunk.file_path,
                    metadata=node_dict["properties"],
                    connection=connection,
                )
                chunk_to_node[chunk.id] = node
                self.logger.debug(f"Created node {node.node_id} for chunk {chunk.id} ({node_dict['label']})")
            except Exception as e:
                self.logger.error(f"Failed to create node for chunk {chunk.id}: {e}")
                # Continue with other chunks

        return chunk_to_node

    async def _create_all_call_edges(
        self,
        chunks: List[CodeChunkModel],
        chunk_to_node: Dict[uuid.UUID, NodeModel],
        connection=None,
    ) -> List[EdgeModel]:
        """
        Create call edges for all chunks.

        For each chunk with metadata['calls'], resolve target and create edge.

        Args:
            chunks: List of code chunks
            chunk_to_node: Mapping of chunk IDs to nodes
            connection: Optional external connection for transaction support (EPIC-12 Story 12.2)
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

            # Create edges for each call (EPIC-12 Story 12.2: Pass connection)
            edges = await self._create_call_edges(chunk, node, chunk_to_node, chunks, connection=connection)
            all_edges.extend(edges)

        return all_edges

    async def _create_call_edges(
        self,
        chunk: CodeChunkModel,
        node: NodeModel,
        chunk_to_node: Dict[uuid.UUID, NodeModel],
        all_chunks: List[CodeChunkModel],
        connection=None,
    ) -> List[EdgeModel]:
        """
        Create call edges for a chunk.

        For each call in chunk.metadata['calls']:
        1. Resolve target chunk
        2. Get target node_id
        3. Create edge (source_node=node, target_node=target, relationship='calls')

        Args:
            chunk: Source chunk
            node: Source node
            chunk_to_node: Mapping of chunk IDs to nodes
            all_chunks: All chunks for resolution
            connection: Optional external connection for transaction support (EPIC-12 Story 12.2)
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

            # Create edge (EPIC-12 Story 12.2: Pass connection for transaction support)
            try:
                edge = await self.edge_repo.create_dependency_edge(
                    source_node=node.node_id,
                    target_node=target_node.node_id,
                    relationship="calls",
                    metadata={
                        "call_name": call_name,
                        "source_file": chunk.file_path,
                        "target_file": target_node.properties.get("file_path", ""),
                    },
                    connection=connection,
                )
                edges.append(edge)
                self.logger.debug(f"Created call edge: {node.label} -> {target_node.label}")
            except Exception as e:
                self.logger.error(f"Failed to create call edge: {e}")

        return edges

    async def _create_all_import_edges(
        self,
        chunks: List[CodeChunkModel],
        chunk_to_node: Dict[uuid.UUID, NodeModel],
        connection=None,
    ) -> List[EdgeModel]:
        """
        Create import edges for all chunks.

        For each chunk with metadata['imports'], create edge to imported module.

        Args:
            chunks: List of code chunks
            chunk_to_node: Mapping of chunk IDs to nodes
            connection: Optional external connection for transaction support (EPIC-12 Story 12.2)
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

            # Create edges for each import (EPIC-12 Story 12.2: Pass connection)
            edges = await self._create_import_edges(chunk, node, chunk_to_node, chunks, connection=connection)
            all_edges.extend(edges)

        return all_edges

    async def _create_import_edges(
        self,
        chunk: CodeChunkModel,
        node: NodeModel,
        chunk_to_node: Dict[uuid.UUID, NodeModel],
        all_chunks: List[CodeChunkModel],
        connection=None,
    ) -> List[EdgeModel]:
        """
        Create import edges for a chunk.

        Note: For MVP, we create "imports" edges between functions in the same repository.
        External imports (stdlib, packages) are skipped for Phase 1.

        Args:
            chunk: Source chunk
            node: Source node
            chunk_to_node: Mapping of chunk IDs to nodes
            all_chunks: All chunks for resolution
            connection: Optional external connection for transaction support (EPIC-12 Story 12.2)
        """
        edges: List[EdgeModel] = []
        imports = chunk.metadata.get("imports", []) if chunk.metadata else []

        for import_spec in imports:
            # Parse import spec (format: "package.symbol" or "symbol")
            # Examples: "@cv-generator/shared.ValidationLayerType", "vue.ref", "../service.BaseService"

            # Skip external package imports (not in our repository)
            if self._is_external_import(import_spec):
                self.logger.debug(f"Skipping external import '{import_spec}' from chunk {chunk.id}")
                continue

            # Extract symbol from import spec
            symbol = self._extract_symbol_from_import(import_spec)
            if not symbol:
                self.logger.debug(f"Could not extract symbol from import '{import_spec}'")
                continue

            # Resolve import target
            target_chunk_id = await self._resolve_import_target(symbol, import_spec, chunk, all_chunks)

            if not target_chunk_id:
                self.logger.debug(f"Could not resolve import '{import_spec}' (symbol: {symbol}) from chunk {chunk.id}")
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
                    relationship="imports",
                    metadata={
                        "import_spec": import_spec,
                        "symbol": symbol,
                        "source_file": chunk.file_path,
                        "target_file": target_node.properties.get("file_path", ""),
                    },
                    connection=connection,
                )
                edges.append(edge)
                self.logger.debug(f"Created import edge: {node.label} -> {target_node.label} ({symbol})")
            except Exception as e:
                self.logger.error(f"Failed to create import edge: {e}")

        return edges

    def _is_external_import(self, import_spec: str) -> bool:
        """
        Check if import is external (not in our repository).

        External imports include:
        - Standard library (no dots, e.g., "os", "sys")
        - Third-party packages (e.g., "vue.ref", "pinia.defineStore", "uuid.v4")
        - NOT internal packages (e.g., "@cv-generator/shared.ValidationLayerType")

        Args:
            import_spec: Import specification (e.g., "vue.ref", "@cv-generator/shared.Error")

        Returns:
            True if external, False if internal
        """
        # Internal imports start with repository-specific prefixes or relative paths
        internal_prefixes = ["@cv-generator/", "../", "./", "/tmp/code_test/"]

        for prefix in internal_prefixes:
            if import_spec.startswith(prefix):
                return False

        # External packages: vue, pinia, uuid, etc.
        external_packages = [
            "vue.", "pinia.", "uuid.", "axios.", "lodash.", "moment.",
            "react.", "angular.", "@vue/", "@angular/", "@react/"
        ]

        for pkg in external_packages:
            if import_spec.startswith(pkg):
                return True

        # If it's a relative path pattern, it's internal
        if "/" in import_spec:
            return False

        # Default: treat as external if it has a dot (package.symbol pattern)
        # but no recognized internal prefix
        return "." in import_spec

    def _extract_symbol_from_import(self, import_spec: str) -> Optional[str]:
        """
        Extract symbol name from import specification.

        Examples:
            "@cv-generator/shared.ValidationLayerType" → "ValidationLayerType"
            "vue.ref" → "ref"
            "../service.BaseService" → "BaseService"
            "./validation.service.BaseValidationService" → "BaseValidationService"

        Args:
            import_spec: Import specification

        Returns:
            Symbol name or None
        """
        if not import_spec:
            return None

        # Split by dot and take the last part
        parts = import_spec.split(".")
        if len(parts) >= 2:
            symbol = parts[-1]
            # Clean up any trailing characters
            return symbol.strip()

        return None

    async def _resolve_import_target(
        self,
        symbol: str,
        import_spec: str,
        current_chunk: CodeChunkModel,
        all_chunks: List[CodeChunkModel]
    ) -> Optional[uuid.UUID]:
        """
        Resolve import target to chunk_id.

        Strategy (priority order):
        1. name_path exact match → highest accuracy
        2. name exact match + file proximity
        3. name match anywhere

        Args:
            symbol: Symbol being imported (e.g., "ValidationLayerType")
            import_spec: Full import spec (e.g., "@cv-generator/shared.ValidationLayerType")
            current_chunk: Chunk making the import
            all_chunks: All chunks in repository

        Returns:
            chunk_id of target, or None if not found
        """
        # Strategy 1: name_path exact match
        # Examples: "shared.types.ValidationLayerType" matches symbol "ValidationLayerType"
        name_path_candidates = []
        for chunk in all_chunks:
            if chunk.name_path:
                # Match if name_path ends with symbol
                if chunk.name_path == symbol or chunk.name_path.endswith(f".{symbol}"):
                    name_path_candidates.append(chunk)

        if len(name_path_candidates) == 1:
            self.logger.debug(
                f"Resolved import '{symbol}' via name_path: {name_path_candidates[0].name_path}"
            )
            return name_path_candidates[0].id

        # If multiple matches, prefer same package (based on file path)
        if len(name_path_candidates) > 1:
            # Extract package hint from import_spec
            # E.g., "@cv-generator/shared.ValidationLayerType" → "shared"
            package_hint = self._extract_package_hint(import_spec)

            if package_hint:
                package_candidates = [
                    c for c in name_path_candidates
                    if package_hint in c.file_path
                ]
                if len(package_candidates) == 1:
                    self.logger.debug(
                        f"Resolved import '{symbol}' via package hint '{package_hint}': "
                        f"{package_candidates[0].name_path}"
                    )
                    return package_candidates[0].id
                if package_candidates:
                    # Return first match
                    return package_candidates[0].id

            # Otherwise, return first candidate
            return name_path_candidates[0].id

        # Strategy 2: name exact match
        name_candidates = []
        for chunk in all_chunks:
            if chunk.name == symbol:
                name_candidates.append(chunk)

        if len(name_candidates) == 1:
            self.logger.debug(f"Resolved import '{symbol}' via name match")
            return name_candidates[0].id

        # If multiple matches, prefer file proximity
        if len(name_candidates) > 1:
            # Prefer same directory
            current_dir = "/".join(current_chunk.file_path.split("/")[:-1])
            same_dir_candidates = [
                c for c in name_candidates
                if c.file_path.startswith(current_dir)
            ]
            if same_dir_candidates:
                return same_dir_candidates[0].id

            # Otherwise, return first
            return name_candidates[0].id

        # Not found
        return None

    def _extract_package_hint(self, import_spec: str) -> Optional[str]:
        """
        Extract package hint from import specification.

        Examples:
            "@cv-generator/shared.ValidationLayerType" → "shared"
            "@cv-generator/core.User" → "core"
            "../../../shared/i18n/domain-i18n.port.DomainI18nPort" → "shared"

        Args:
            import_spec: Import specification

        Returns:
            Package hint or None
        """
        # Handle @cv-generator/ packages
        if "@cv-generator/" in import_spec:
            # Extract package name after @cv-generator/
            parts = import_spec.split("@cv-generator/")
            if len(parts) > 1:
                package_part = parts[1].split(".")[0]  # "shared", "core", etc.
                return package_part

        # Handle relative paths with directory hints
        if "/" in import_spec:
            # Extract directory name before last /
            parts = import_spec.split("/")
            for part in reversed(parts):
                if part and part not in ["..", ".", "src", "dist"]:
                    return part.split(".")[0]

        return None

    async def _create_reexport_edges(
        self,
        barrel_chunk: CodeChunkModel,
        all_chunks: List[CodeChunkModel]
    ) -> List[dict]:
        """
        Create re-export edges from barrel to original symbols.

        EPIC-29 Task 5: Barrels create 're_exports' edges to symbols.

        Pattern:
            Barrel (Module) --[re_exports]--> Original Symbol (Function/Class)

        Args:
            barrel_chunk: Barrel chunk with re_exports metadata
            all_chunks: All chunks in repository (to find targets)

        Returns:
            List of edge dicts with keys: edge_type, properties, source_chunk_id, target_chunk_id
        """
        from pathlib import Path

        edges = []
        re_exports = barrel_chunk.metadata.get("re_exports", []) if barrel_chunk.metadata else []

        for reexport in re_exports:
            symbol = reexport["symbol"]
            source_path = reexport["source"]

            # Skip wildcard exports (handle separately in future)
            if symbol == "*":
                continue

            # Find target chunk by symbol name and file path
            # source_path is relative: './utils/result.utils'
            # Need to resolve to absolute path
            barrel_dir = Path(barrel_chunk.file_path).parent
            target_path_base = (barrel_dir / source_path).resolve()

            # Find chunk with matching name in target file
            target_chunk = None
            for chunk in all_chunks:
                chunk_path = Path(chunk.file_path).resolve()
                # Match file (with or without .ts/.js extension)
                chunk_path_str = str(chunk_path)
                target_path_str = str(target_path_base)

                # Try exact match or with common extensions
                matches = (
                    chunk_path_str.startswith(target_path_str) or
                    chunk_path_str.startswith(target_path_str + ".ts") or
                    chunk_path_str.startswith(target_path_str + ".js") or
                    chunk_path_str.startswith(target_path_str + ".tsx")
                )

                if matches and chunk.name == symbol:
                    target_chunk = chunk
                    break

            if target_chunk:
                edge = {
                    "source_chunk_id": barrel_chunk.id,
                    "target_chunk_id": target_chunk.id,
                    "edge_type": "re_exports",
                    "properties": {
                        "symbol": symbol,
                        "source_file": reexport["source"],
                        "is_type": reexport.get("is_type", False)
                    }
                }
                edges.append(edge)
                self.logger.debug(f"Created re-export edge: {barrel_chunk.name} -> {symbol}")
            else:
                self.logger.debug(
                    f"Could not find target for re-export: {symbol} "
                    f"from {source_path} (barrel: {barrel_chunk.file_path})"
                )

        return edges

    async def _generate_contains_edges(
        self,
        nodes: List[NodeModel]
    ) -> List[EdgeModel]:
        """
        Generate 'contains' edges to represent structural hierarchy.

        Hierarchy levels:
        - Package contains Module
        - Module contains File
        - File contains Class/Function

        Args:
            nodes: All nodes in the graph

        Returns:
            List of EdgeModel with relation_type="contains"
        """
        edges: List[EdgeModel] = []

        # Group nodes by type for efficient lookup
        nodes_by_type: Dict[str, List[NodeModel]] = {}
        for node in nodes:
            if node.node_type not in nodes_by_type:
                nodes_by_type[node.node_type] = []
            nodes_by_type[node.node_type].append(node)

        # Create Package → Module edges
        packages = nodes_by_type.get("Package", [])
        modules = nodes_by_type.get("Module", [])

        for module in modules:
            parent_package = module.properties.get("parent_package") if module.properties else None
            if parent_package:
                # Find matching package by label
                package = next((p for p in packages if p.label == parent_package), None)
                if package:
                    # Create EdgeModel directly (without DB persistence)
                    edge = EdgeModel(
                        edge_id=uuid.uuid4(),
                        source_node_id=package.node_id,
                        target_node_id=module.node_id,
                        relation_type="contains",
                        properties={"hierarchy_level": "package_to_module"},
                        created_at=datetime.now(timezone.utc)
                    )
                    edges.append(edge)

        # Create Module → File edges
        files = nodes_by_type.get("File", [])

        for file_node in files:
            parent_module = file_node.properties.get("parent_module") if file_node.properties else None
            if parent_module:
                module = next((m for m in modules if m.label == parent_module), None)
                if module:
                    edge = EdgeModel(
                        edge_id=uuid.uuid4(),
                        source_node_id=module.node_id,
                        target_node_id=file_node.node_id,
                        relation_type="contains",
                        properties={"hierarchy_level": "module_to_file"},
                        created_at=datetime.now(timezone.utc)
                    )
                    edges.append(edge)

        # Create File → Class/Function edges
        classes = nodes_by_type.get("Class", [])
        functions = nodes_by_type.get("Function", [])
        methods = nodes_by_type.get("Method", [])

        for entity in classes + functions + methods:
            parent_file = entity.properties.get("file_path") if entity.properties else None
            if parent_file:
                # Find file node by file_path
                file_node = next((f for f in files if f.properties.get("file_path") == parent_file), None)
                if file_node:
                    edge = EdgeModel(
                        edge_id=uuid.uuid4(),
                        source_node_id=file_node.node_id,
                        target_node_id=entity.node_id,
                        relation_type="contains",
                        properties={"hierarchy_level": "file_to_entity"},
                        created_at=datetime.now(timezone.utc)
                    )
                    edges.append(edge)

        return edges

    async def _resolve_call_target(
        self,
        call_name: str,
        current_chunk: CodeChunkModel,
        all_chunks: List[CodeChunkModel]
    ) -> Optional[uuid.UUID]:
        """
        Resolve call target to chunk_id with LSP-enhanced resolution.

        EPIC-13 Story 13.5: Enhanced call resolution using name_path (EPIC-11).

        Strategy (priority order):
        1. Skip built-ins → return None
        2. name_path exact match (EPIC-11) → highest accuracy
        3. Local file match (same file_path) → medium accuracy
        4. Import-based match → fallback

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

        # EPIC-13 Story 13.5: Strategy 2 - name_path exact match (highest priority)
        # Use hierarchical qualified names from EPIC-11 for precise resolution
        # Examples: "models.user.User.validate", "api.services.user_service.get_user"
        name_path_candidates = []
        for chunk in all_chunks:
            if chunk.name_path:
                # Match if name_path ends with ".call_name" or equals "call_name"
                if chunk.name_path == call_name or chunk.name_path.endswith(f".{call_name}"):
                    name_path_candidates.append(chunk)

        # If exactly one match, use it (high confidence)
        if len(name_path_candidates) == 1:
            self.logger.debug(
                f"EPIC-13: Resolved call '{call_name}' via name_path: {name_path_candidates[0].name_path}"
            )
            return name_path_candidates[0].id

        # If multiple matches, try to disambiguate using file proximity
        if len(name_path_candidates) > 1:
            # Prefer targets in the same file
            same_file_candidates = [
                c for c in name_path_candidates if c.file_path == current_chunk.file_path
            ]
            if len(same_file_candidates) == 1:
                self.logger.debug(
                    f"EPIC-13: Disambiguated call '{call_name}' using file proximity: "
                    f"{same_file_candidates[0].name_path}"
                )
                return same_file_candidates[0].id

            # Otherwise, return first candidate (alphabetically by name_path for determinism)
            sorted_candidates = sorted(name_path_candidates, key=lambda c: c.name_path or "")
            self.logger.debug(
                f"EPIC-13: Multiple name_path matches for '{call_name}', "
                f"using first: {sorted_candidates[0].name_path}"
            )
            return sorted_candidates[0].id

        # 3. Check local file (same file_path) - fallback to tree-sitter heuristic
        for chunk in all_chunks:
            if chunk.file_path == current_chunk.file_path and chunk.name == call_name:
                self.logger.debug(f"Resolved call '{call_name}' via local file match")
                return chunk.id

        # 4. Check imports (simplified for MVP) - final fallback
        # Extract imported names from metadata
        imports = current_chunk.metadata.get("imports", []) if current_chunk.metadata else []

        for imp in imports:
            # Simple heuristic: if import ends with call_name, it's a match
            # E.g., "from utils import calculate_total" → call_name = "calculate_total"
            if imp.endswith(call_name) or imp.endswith(f".{call_name}"):
                # Search for chunk with this name
                for chunk in all_chunks:
                    if chunk.name == call_name:
                        self.logger.debug(f"Resolved call '{call_name}' via imports")
                        return chunk.id

        # 5. Not found
        return None
