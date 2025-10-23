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
            """
            (function_definition) @function
            """
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
            """
            (class_definition) @class
            """
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

    def __init__(self, max_workers: int = 4):
        self._parsers: dict[str, LanguageParser] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._parse_cache: dict[str, Tree] = {}  # Cache parsed trees

        # Initialize parsers (lazy loading)
        self._supported_languages = {
            "python": PythonParser,
            # "javascript": JavaScriptParser,  # TODO: Phase 1.5
            # "typescript": TypeScriptParser,  # TODO: Phase 1.5
        }

        logger.info(f"CodeChunkingService initialized with {len(self._supported_languages)} language parsers")

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
        chunk_type_map = {
            "function_definition": ChunkType.FUNCTION,
            "class_definition": ChunkType.CLASS,
            "method_definition": ChunkType.METHOD,
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


# Singleton instance (will be injected via dependencies)
_chunking_service: Optional[CodeChunkingService] = None


def get_code_chunking_service() -> CodeChunkingService:
    """Get singleton instance of CodeChunkingService."""
    global _chunking_service
    if _chunking_service is None:
        _chunking_service = CodeChunkingService(max_workers=4)
    return _chunking_service
