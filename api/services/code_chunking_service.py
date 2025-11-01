"""
Code chunking service for EPIC-06 Phase 1 Story 1.

Implements AST-based semantic chunking using tree-sitter for multiple languages.
Inspired by cAST paper (2024) - split-then-merge algorithm for optimal chunk quality.

EPIC-12 Story 12.1: Added timeout protection to prevent infinite hangs.
"""

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any, Optional

from tree_sitter import Node, Tree
from tree_sitter_language_pack import get_language, get_parser

from api.models.code_chunk_models import ChunkType, CodeChunk, CodeUnit
from utils.timeout import with_timeout, TimeoutError
from config.timeouts import get_timeout

logger = logging.getLogger(__name__)


class LanguageParser(ABC):
    """
    Abstract base class for language-specific parsers.

    Each language implementation must define how to:
    - Parse source code to AST
    - Identify code units (functions, classes, methods)
    - Extract metadata from AST nodes
    """

    def __init__(self, language: str):
        self.language = language
        self.parser = get_parser(language)
        self.tree_sitter_language = get_language(language)

    @abstractmethod
    def get_function_nodes(self, tree: Tree) -> list[Node]:
        """Extract function definition nodes from AST."""
        pass

    @abstractmethod
    def get_class_nodes(self, tree: Tree) -> list[Node]:
        """Extract class definition nodes from AST."""
        pass

    @abstractmethod
    def get_method_nodes(self, node: Node) -> list[Node]:
        """Extract method nodes from a class node."""
        pass

    @abstractmethod
    def node_to_code_unit(self, node: Node, source_code: str) -> CodeUnit:
        """Convert AST node to CodeUnit model."""
        pass

    def parse(self, source_code: str) -> Tree:
        """Parse source code to AST tree."""
        return self.parser.parse(bytes(source_code, "utf8"))


class PythonParser(LanguageParser):
    """
    Python-specific AST parser using tree-sitter.

    Handles:
    - Function definitions (def)
    - Class definitions (class)
    - Method definitions (functions inside classes)
    - Async functions
    """

    def __init__(self):
        super().__init__("python")

    def get_function_nodes(self, tree: Tree) -> list[Node]:
        """Extract all function definition nodes (top-level and nested)."""
        import tree_sitter

        query = tree_sitter.Query(
            self.tree_sitter_language,
            "(function_definition) @function"
        )
        cursor = tree_sitter.QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        # Extract nodes from matches: [(pattern_idx, {'capture_name': [nodes]}), ...]
        nodes = []
        for _, captures_dict in matches:
            nodes.extend(captures_dict.get('function', []))
        return nodes

    def get_class_nodes(self, tree: Tree) -> list[Node]:
        """Extract all class definition nodes."""
        import tree_sitter

        query = tree_sitter.Query(
            self.tree_sitter_language,
            "(class_definition) @class"
        )
        cursor = tree_sitter.QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        # Extract nodes from matches
        nodes = []
        for _, captures_dict in matches:
            nodes.extend(captures_dict.get('class', []))
        return nodes

    def get_method_nodes(self, node: Node) -> list[Node]:
        """Extract method definitions from a class node."""
        methods = []
        for child in node.children:
            if child.type == "block":
                for subchild in child.children:
                    if subchild.type == "function_definition":
                        methods.append(subchild)
        return methods

    def node_to_code_unit(self, node: Node, source_code: str) -> CodeUnit:
        """
        Convert tree-sitter node to CodeUnit model.

        Extracts:
        - Node type (FunctionDef, ClassDef)
        - Name
        - Source code slice
        - Line numbers
        - Size
        """
        # Get name from identifier child
        name = None
        for child in node.children:
            if child.type == "identifier":
                name = source_code[child.start_byte:child.end_byte]
                break

        # Extract source code for this node
        node_source = source_code[node.start_byte:node.end_byte]

        return CodeUnit(
            node_type=node.type,
            name=name,
            source_code=node_source,
            start_line=node.start_point[0] + 1,  # tree-sitter is 0-indexed
            end_line=node.end_point[0] + 1,
            size=len(node_source),
            children=[]
        )


class TypeScriptParser(LanguageParser):
    """
    TypeScript/TSX AST parser using tree-sitter.

    Handles:
    - Function declarations (function)
    - Class declarations (class)
    - Method definitions (methods in classes)
    - Interface declarations (TypeScript)
    - Arrow functions (const x = () => {})
    - Async functions

    EPIC-15 Story 15.1: TypeScript support (8 pts)
    """

    def __init__(self):
        super().__init__("typescript")

    def get_function_nodes(self, tree: Tree) -> list[Node]:
        """Extract function declarations + arrow functions."""
        import tree_sitter

        query = tree_sitter.Query(
            self.tree_sitter_language,
            "(function_declaration) @function (lexical_declaration (variable_declarator value: (arrow_function) @arrow_function))"
        )
        cursor = tree_sitter.QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        nodes = []
        for _, captures_dict in matches:
            nodes.extend(captures_dict.get('function', []))
            nodes.extend(captures_dict.get('arrow_function', []))
        return nodes

    def get_class_nodes(self, tree: Tree) -> list[Node]:
        """Extract class declarations."""
        import tree_sitter

        query = tree_sitter.Query(
            self.tree_sitter_language,
            "(class_declaration) @class"
        )
        cursor = tree_sitter.QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        nodes = []
        for _, captures_dict in matches:
            nodes.extend(captures_dict.get('class', []))
        return nodes

    def get_interface_nodes(self, tree: Tree) -> list[Node]:
        """Extract interface declarations (TypeScript-specific)."""
        import tree_sitter

        query = tree_sitter.Query(
            self.tree_sitter_language,
            "(interface_declaration) @interface"
        )
        cursor = tree_sitter.QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        nodes = []
        for _, captures_dict in matches:
            nodes.extend(captures_dict.get('interface', []))
        return nodes

    def get_method_nodes(self, node: Node) -> list[Node]:
        """Extract method definitions from class body."""
        methods = []
        for child in node.children:
            if child.type == "class_body":
                for subchild in child.children:
                    if subchild.type == "method_definition":
                        methods.append(subchild)
        return methods

    def node_to_code_unit(self, node: Node, source_code: str) -> CodeUnit:
        """
        Convert TypeScript tree-sitter node to CodeUnit.

        Handles:
        - type_identifier (class names, interface names)
        - identifier (function/method names)
        - Async functions (async keyword)
        """
        # Get name from identifier/type_identifier
        name = None
        for child in node.children:
            if child.type in ["identifier", "type_identifier"]:
                name = source_code[child.start_byte:child.end_byte]
                break

        if not name:
            name = f"anonymous_{node.type}"

        # Extract source code for this node
        node_source = source_code[node.start_byte:node.end_byte]

        return CodeUnit(
            node_type=node.type,
            name=name,
            source_code=node_source,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            size=len(node_source),
            children=[]
        )


class JavaScriptParser(TypeScriptParser):
    """
    JavaScript/JSX parser (inherits from TypeScript).

    JavaScript is a subset of TypeScript syntax,
    so we can reuse the TypeScript parser.

    The only difference is the tree-sitter language name:
    - TypeScript uses "typescript" grammar (includes interfaces, types)
    - JavaScript uses "javascript" grammar (no type syntax)

    EPIC-15 Story 15.2: JavaScript support (3 pts)
    EPIC-26 Story 26.3: JavaScript doesn't support interfaces - override to return empty list
    """

    def __init__(self):
        # Call LanguageParser.__init__ directly to override language name
        LanguageParser.__init__(self, "javascript")
        # Do NOT call super().__init__() - would set language to "typescript"

    def get_interface_nodes(self, tree: Tree) -> list[Node]:
        """
        JavaScript doesn't support interfaces.

        EPIC-26 Story 26.3: Override TypeScript's get_interface_nodes to return empty list.
        """
        return []


class CodeChunkingService:
    """
    Service for semantic code chunking via AST parsing.

    Algorithm (cAST-inspired):
    1. Parse code → AST (via tree-sitter)
    2. Identify code units (functions, classes, methods)
    3. Split large units recursively if > max_chunk_size
    4. Merge small adjacent chunks if < min_chunk_size
    5. Fallback to fixed chunking if AST parsing fails

    Performance target: <100ms for 300 LOC
    Quality target: >80% chunks = complete functions/classes
    """

    def __init__(self, max_workers: int = 4, metadata_service: Optional['MetadataExtractorService'] = None):
        """
        Initialize CodeChunkingService.

        Args:
            max_workers: Number of thread pool workers for parsing
            metadata_service: Optional metadata extractor service (EPIC-26: TypeScript/JavaScript metadata extraction)
        """
        self._parsers: dict[str, LanguageParser] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._parse_cache: dict[str, Tree] = {}  # Cache parsed trees
        self._metadata_service = metadata_service  # EPIC-26: Metadata extraction integration

        # EPIC-29: Add file classifier for barrels, configs, and tests
        from api.services.file_classification_service import FileClassificationService
        self._classifier = FileClassificationService()

        # Initialize parsers (lazy loading)
        # EPIC-15: Multi-language support (Python, TypeScript, JavaScript)
        self._supported_languages = {
            "python": PythonParser,
            "javascript": JavaScriptParser,
            "typescript": TypeScriptParser,
            "tsx": TypeScriptParser,  # TSX uses TypeScript parser
        }

        logger.info(
            f"CodeChunkingService initialized with {len(self._supported_languages)} language parsers "
            f"(metadata_extraction={'enabled' if metadata_service else 'disabled'})"
        )

    def _get_parser(self, language: str) -> Optional[LanguageParser]:
        """Get parser for language (lazy loading)."""
        if language not in self._supported_languages:
            logger.warning(f"Language '{language}' not supported")
            return None

        if language not in self._parsers:
            parser_class = self._supported_languages[language]
            self._parsers[language] = parser_class()
            logger.info(f"Loaded parser for language: {language}")

        return self._parsers[language]

    async def chunk_code(
        self,
        source_code: str,
        language: str,
        file_path: str = "<unknown>",
        max_chunk_size: int = 2000,
        min_chunk_size: int = 100
    ) -> list[CodeChunk]:
        """
        Chunk source code semantically via AST.

        Args:
            source_code: Source code to chunk
            language: Programming language (python, javascript, etc.)
            file_path: Path to source file
            max_chunk_size: Maximum chunk size in characters
            min_chunk_size: Minimum chunk size (for merging)

        Returns:
            List of CodeChunk models

        Raises:
            ValueError: If source_code is empty
        """
        if not source_code.strip():
            raise ValueError("source_code cannot be empty")

        # EPIC-29: Classify file type (for TypeScript/JavaScript only)
        from api.services.file_classification_service import FileType
        file_type = None
        if language.lower() in ("typescript", "javascript", "tsx"):
            file_type = self._classifier.classify_by_filename(file_path)

            # Skip test files entirely
            if self._classifier.should_skip_file(file_path):
                logger.info(f"Skipping test file: {file_path}")
                return []

        # Try AST-based chunking
        parser = self._get_parser(language.lower())
        if parser is None:
            logger.warning(f"No parser for '{language}', falling back to fixed chunking")
            return await self._fallback_fixed_chunking(source_code, file_path, language, max_chunk_size)

        try:
            # Parse in thread pool (CPU-bound operation) with timeout protection
            # EPIC-12 Story 12.1: Prevent infinite hangs on pathological input
            loop = asyncio.get_event_loop()
            parse_coro = loop.run_in_executor(
                self._executor,
                parser.parse,
                source_code
            )

            tree = await with_timeout(
                parse_coro,
                timeout=get_timeout("tree_sitter_parse"),
                operation_name="tree_sitter_parse",
                context={"file_path": file_path, "language": language},
                raise_on_timeout=True
            )

            # EPIC-29: Handle config files (light extraction)
            if file_type == FileType.CONFIG:
                return await self._chunk_config_file(
                    source_code, file_path, language, tree
                )

            # EPIC-29: Check if barrel using heuristic
            if file_type == FileType.POTENTIAL_BARREL and self._metadata_service:
                # Extract metadata first to get re_exports
                from api.services.metadata_extractors.typescript_extractor import TypeScriptMetadataExtractor
                extractor = TypeScriptMetadataExtractor(language)
                metadata = await extractor.extract_metadata(
                    source_code=source_code,
                    node=tree.root_node,
                    tree=tree
                )

                # Check if barrel
                is_barrel = await self._classifier.is_barrel_heuristic(
                    source_code, metadata
                )

                if is_barrel:
                    return await self._chunk_barrel_file(
                        source_code, file_path, language, tree, metadata
                    )

            # Extract code units
            code_units = await self._extract_code_units(parser, tree, source_code)

            # Split large units, merge small units
            chunks = await self._split_and_merge(
                code_units,
                source_code,
                file_path,
                language,
                max_chunk_size,
                min_chunk_size
            )

            # EPIC-26 Story 26.3: Extract metadata for each chunk (TypeScript/JavaScript support)
            # EPIC-25 Story 25.5: Enable Python metadata extraction for graph relations
            if self._metadata_service and language.lower() in ("python", "typescript", "javascript", "tsx"):
                await self._extract_metadata_for_chunks(chunks, tree, source_code, language)

            logger.info(f"Chunked {file_path}: {len(chunks)} chunks via AST")
            return chunks

        except TimeoutError as e:
            # EPIC-12 Story 12.1: Handle timeout gracefully
            logger.error(
                f"Tree-sitter parsing timed out for {file_path} after {get_timeout('tree_sitter_parse')}s",
                extra={"file_path": file_path, "language": language, "error": str(e)}
            )
            logger.info(f"Falling back to fixed chunking for {file_path} after timeout")
            return await self._fallback_fixed_chunking(source_code, file_path, language, max_chunk_size)

        except Exception as e:
            logger.error(f"AST chunking failed for {file_path}: {e}", exc_info=True)
            logger.info(f"Falling back to fixed chunking for {file_path}")
            return await self._fallback_fixed_chunking(source_code, file_path, language, max_chunk_size)

    async def _extract_metadata_for_chunks(
        self,
        chunks: list[CodeChunk],
        tree: Tree,
        source_code: str,
        language: str
    ) -> None:
        """
        Extract metadata for each chunk using MetadataExtractorService.

        EPIC-26 Story 26.3: TypeScript/JavaScript metadata extraction integration.
        EPIC-25 Story 25.5: Python metadata extraction for graph relations.

        For TypeScript/JavaScript chunks:
        - Extracts imports (file-level, from tree)
        - Extracts calls (chunk-level, from node)

        For Python chunks:
        - Uses ast module instead of tree-sitter
        - Extracts calls, imports, docstrings, complexity

        Args:
            chunks: List of chunks to populate with metadata
            tree: Tree-sitter AST tree (or Python ast tree if language='python')
            source_code: Full source code
            language: Programming language

        Modifies chunks in-place by setting chunk.metadata.
        """
        if not chunks:
            return

        logger.debug(f"Extracting metadata for {len(chunks)} {language} chunks")

        # EPIC-25: For Python, parse with ast module instead of tree-sitter
        if language.lower() == "python":
            import ast as python_ast
            try:
                python_tree = python_ast.parse(source_code)
            except SyntaxError as e:
                logger.warning(f"Failed to parse Python source with ast: {e}")
                # Fallback: set empty metadata for all chunks
                for chunk in chunks:
                    chunk.metadata = {"imports": [], "calls": []}
                return
        else:
            python_tree = None

        for chunk in chunks:
            try:
                # EPIC-25: For Python, find the ast.FunctionDef/ClassDef node for this chunk
                if language.lower() == "python" and python_tree:
                    # Find the ast node corresponding to this chunk
                    # Simple approach: walk ast and match by name
                    import ast as python_ast
                    ast_node = None
                    for node in python_ast.walk(python_tree):
                        if isinstance(node, (python_ast.FunctionDef, python_ast.AsyncFunctionDef, python_ast.ClassDef)):
                            if node.name == chunk.name:
                                ast_node = node
                                break

                    if not ast_node:
                        logger.debug(f"Could not find ast node for chunk '{chunk.name}', using tree root")
                        ast_node = python_tree

                    # EPIC-28: Extract metadata using FULL file source (not chunk source!)
                    # This ensures byte offsets are correct for ast.get_source_segment()
                    metadata = await self._metadata_service.extract_metadata(
                        source_code=source_code,  # FULL file source
                        node=ast_node,
                        tree=python_tree,
                        language=language
                    )
                else:
                    # For TypeScript/JavaScript, use tree-sitter nodes
                    # Find the tree-sitter node corresponding to this chunk's line range
                    # For now, use the root node (will extract file-level imports + all calls)
                    # TODO: Optimize by finding exact node for chunk (performance improvement)
                    node = tree.root_node

                    # EPIC-28: Extract metadata using FULL file source (not chunk source!)
                    # This ensures tree-sitter byte offsets are correct
                    metadata = await self._metadata_service.extract_metadata(
                        source_code=source_code,  # FULL file source
                        node=node,
                        tree=tree,
                        language=language
                    )

                # Assign metadata to chunk
                chunk.metadata = metadata

                logger.debug(
                    f"Extracted metadata for chunk '{chunk.name}': "
                    f"{len(metadata.get('imports', []))} imports, "
                    f"{len(metadata.get('calls', []))} calls"
                )

            except Exception as e:
                # Graceful degradation: log error but continue with empty metadata
                logger.warning(
                    f"Failed to extract metadata for chunk '{chunk.name}': {e}",
                    exc_info=True
                )
                chunk.metadata = {"imports": [], "calls": []}

        logger.info(
            f"Metadata extraction complete for {len(chunks)} chunks "
            f"({language})"
        )

    async def _extract_code_units(
        self,
        parser: LanguageParser,
        tree: Tree,
        source_code: str
    ) -> list[CodeUnit]:
        """Extract code units from AST tree."""
        code_units = []

        # Get all functions (top-level)
        function_nodes = parser.get_function_nodes(tree)
        for node in function_nodes:
            unit = parser.node_to_code_unit(node, source_code)
            code_units.append(unit)

        # Get all classes
        class_nodes = parser.get_class_nodes(tree)
        for node in class_nodes:
            unit = parser.node_to_code_unit(node, source_code)
            # Extract methods from class
            method_nodes = parser.get_method_nodes(node)
            for method_node in method_nodes:
                method_unit = parser.node_to_code_unit(method_node, source_code)
                unit.children.append(method_unit)
            code_units.append(unit)

        # Get all interfaces (TypeScript-specific)
        # EPIC-15 Story 15.1: Support TypeScript interfaces
        if hasattr(parser, 'get_interface_nodes'):
            interface_nodes = parser.get_interface_nodes(tree)
            for node in interface_nodes:
                unit = parser.node_to_code_unit(node, source_code)
                code_units.append(unit)

        return code_units

    async def _split_and_merge(
        self,
        code_units: list[CodeUnit],
        source_code: str,
        file_path: str,
        language: str,
        max_chunk_size: int,
        min_chunk_size: int
    ) -> list[CodeChunk]:
        """
        Split large units and merge small adjacent units.

        Algorithm:
        1. For each unit:
           - If size <= max_chunk_size → create chunk
           - If size > max_chunk_size → split recursively
        2. Merge small adjacent chunks (< min_chunk_size)
        """
        chunks = []

        for unit in code_units:
            if unit.size <= max_chunk_size:
                # Unit fits in one chunk
                chunk = self._unit_to_chunk(unit, file_path, language)
                chunks.append(chunk)
            else:
                # Unit too large, try to split by children (e.g., methods in class)
                if unit.children:
                    # Split class into methods
                    for child in unit.children:
                        if child.size <= max_chunk_size:
                            chunk = self._unit_to_chunk(child, file_path, language)
                            chunks.append(chunk)
                        else:
                            # Method still too large, use fixed chunking on it
                            logger.warning(
                                f"Method '{child.name}' too large ({child.size} chars), "
                                f"using fixed chunking"
                            )
                            fixed_chunks = await self._fallback_fixed_chunking(
                                child.source_code,
                                file_path,
                                language,
                                max_chunk_size
                            )
                            chunks.extend(fixed_chunks)
                else:
                    # No children, use fixed chunking
                    logger.warning(
                        f"Function '{unit.name}' too large ({unit.size} chars), "
                        f"using fixed chunking"
                    )
                    fixed_chunks = await self._fallback_fixed_chunking(
                        unit.source_code,
                        file_path,
                        language,
                        max_chunk_size
                    )
                    chunks.extend(fixed_chunks)

        # TODO: Implement merge small chunks (Phase 1 optional)
        # For now, return chunks as-is

        return chunks

    def _unit_to_chunk(self, unit: CodeUnit, file_path: str, language: str) -> CodeChunk:
        """Convert CodeUnit to CodeChunk model."""
        # Determine chunk type from node type
        # EPIC-15: Added TypeScript/JavaScript node types
        chunk_type_map = {
            # Python
            "function_definition": ChunkType.FUNCTION,
            "class_definition": ChunkType.CLASS,
            "method_definition": ChunkType.METHOD,
            # TypeScript/JavaScript
            "function_declaration": ChunkType.FUNCTION,
            "arrow_function": ChunkType.FUNCTION,
            "class_declaration": ChunkType.CLASS,
            "interface_declaration": ChunkType.INTERFACE,
        }
        chunk_type = chunk_type_map.get(unit.node_type, ChunkType.FUNCTION)

        return CodeChunk(
            file_path=file_path,
            language=language,
            chunk_type=chunk_type,
            name=unit.name,
            source_code=unit.source_code,
            start_line=unit.start_line,
            end_line=unit.end_line,
            metadata={}
        )

    async def _fallback_fixed_chunking(
        self,
        source_code: str,
        file_path: str,
        language: str,
        chunk_size: int = 2000
    ) -> list[CodeChunk]:
        """
        Fallback fixed-size chunking when AST parsing fails.

        Strategy:
        - Split by lines with overlap (10%)
        - Try to preserve logical boundaries (don't split mid-line)
        """
        lines = source_code.split('\n')
        chunks = []

        # Calculate lines per chunk (approximate)
        avg_line_length = len(source_code) / len(lines) if lines else 80
        lines_per_chunk = max(1, int(chunk_size / avg_line_length))
        overlap_lines = max(1, int(lines_per_chunk * 0.1))  # 10% overlap

        i = 0
        chunk_num = 0
        while i < len(lines):
            # Take lines_per_chunk lines
            chunk_lines = lines[i:i + lines_per_chunk]
            chunk_source = '\n'.join(chunk_lines)

            # Don't create tiny chunks at the end
            if len(chunk_source.strip()) < 50 and chunks:
                # Merge with previous chunk
                prev_chunk = chunks[-1]
                prev_chunk.source_code += '\n' + chunk_source
                prev_chunk.end_line = i + len(chunk_lines)
                break

            chunk = CodeChunk(
                file_path=file_path,
                language=language,
                chunk_type=ChunkType.FALLBACK_FIXED,
                name=f"chunk_{chunk_num}",
                source_code=chunk_source,
                start_line=i + 1,
                end_line=i + len(chunk_lines),
                metadata={"fallback": True, "reason": "ast_parsing_failed"}
            )
            chunks.append(chunk)

            # Move forward with overlap
            i += lines_per_chunk - overlap_lines
            chunk_num += 1

        logger.info(f"Fixed chunking: created {len(chunks)} chunks for {file_path}")
        return chunks

    async def _chunk_barrel_file(
        self,
        source_code: str,
        file_path: str,
        language: str,
        tree: Tree,
        metadata: dict[str, Any]
    ) -> list[CodeChunk]:
        """
        Create single BARREL chunk for re-export aggregators.

        EPIC-29 Task 4: Barrels become Module nodes in graph.

        Args:
            source_code: Full file source
            file_path: Path to file
            language: Programming language
            tree: Parsed AST tree
            metadata: Pre-extracted metadata with re_exports

        Returns:
            List with single BARREL chunk
        """
        from pathlib import Path

        # Derive module name from path
        # packages/shared/src/index.ts -> "shared"
        # packages/core/src/cv/index.ts -> "cv"
        path_parts = Path(file_path).parts
        if "packages" in path_parts:
            pkg_index = path_parts.index("packages")
            if pkg_index + 1 < len(path_parts):
                module_name = path_parts[pkg_index + 1]
            else:
                module_name = "index"
        else:
            # For non-package files, use parent directory name
            module_name = Path(file_path).parent.name

        chunk = CodeChunk(
            file_path=file_path,
            language=language,
            chunk_type=ChunkType.BARREL,
            name=module_name,
            source_code=source_code,
            start_line=1,
            end_line=len(source_code.split('\n')),
            metadata=metadata
        )

        logger.info(
            f"Created BARREL chunk for {file_path}: "
            f"{len(metadata.get('re_exports', []))} re-exports"
        )

        return [chunk]

    async def _chunk_config_file(
        self,
        source_code: str,
        file_path: str,
        language: str,
        tree: Tree
    ) -> list[CodeChunk]:
        """
        Create single CONFIG_MODULE chunk with light extraction.

        EPIC-29 Task 4: Configs get imports only, no call extraction.

        Args:
            source_code: Full file source
            file_path: Path to file
            language: Programming language
            tree: Parsed AST tree

        Returns:
            List with single CONFIG_MODULE chunk
        """
        from pathlib import Path
        from api.services.metadata_extractors.typescript_extractor import TypeScriptMetadataExtractor

        # Light extraction: imports only
        extractor = TypeScriptMetadataExtractor(language)

        # Extract only imports
        imports = await extractor.extract_imports(tree.root_node, source_code)

        # Derive config name from filename
        config_name = Path(file_path).stem  # vite.config.ts -> vite.config

        chunk = CodeChunk(
            file_path=file_path,
            language=language,
            chunk_type=ChunkType.CONFIG_MODULE,
            name=config_name,
            source_code=source_code,
            start_line=1,
            end_line=len(source_code.split('\n')),
            metadata={
                "imports": imports,
                "calls": [],  # No call extraction for configs
                "re_exports": []
            }
        )

        logger.info(f"Created CONFIG_MODULE chunk for {file_path}")

        return [chunk]


# Singleton instance (will be injected via dependencies)
_chunking_service: Optional[CodeChunkingService] = None


def get_code_chunking_service() -> CodeChunkingService:
    """
    Get singleton instance of CodeChunkingService.

    EPIC-26 Story 26.3: Injects MetadataExtractorService for TypeScript/JavaScript metadata extraction.
    """
    global _chunking_service
    if _chunking_service is None:
        # EPIC-26: Import and inject MetadataExtractorService
        from services.metadata_extractor_service import get_metadata_extractor_service

        metadata_service = get_metadata_extractor_service()
        _chunking_service = CodeChunkingService(
            max_workers=4,
            metadata_service=metadata_service
        )
    return _chunking_service
