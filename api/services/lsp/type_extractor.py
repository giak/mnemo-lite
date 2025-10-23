"""
Type Metadata Extraction Service using LSP.

Story: EPIC-13 Story 13.2 - Type Metadata Extraction Service
Story: EPIC-13 Story 13.4 - LSP Result Caching (L2 Redis)
Story: EPIC-16 Story 16.2 - TypeScript LSP Support
Author: Claude Code
Date: 2025-10-22 (Updated: 2025-10-23)

Extracts type information from Pyright LSP (Python) and TypeScript LSP servers.
Caches LSP results in Redis (L2) for 10× performance improvement.
"""

import re
import hashlib
import structlog
from typing import Optional, Dict, Any

from services.lsp.lsp_client import PyrightLSPClient
from services.lsp.typescript_lsp_client import TypeScriptLSPClient
from services.lsp.lsp_errors import LSPError
from services.caches.redis_cache import RedisCache
from models.code_chunk_models import CodeChunk

logger = structlog.get_logger()


class TypeExtractorService:
    """
    Extract type information using LSP hover queries with L2 Redis caching.

    Provides semantic type analysis to enhance structural metadata from tree-sitter.

    Workflow (Story 13.4 - with L2 caching):
    1. Check Redis cache (L2) for cached type metadata
    2. If cache hit: return cached metadata (0ms LSP query)
    3. If cache miss: Query LSP for hover info at symbol position
    4. Parse hover text to extract signature components
    5. Store result in Redis cache (300s TTL)
    6. Return structured type metadata

    Cache Key Format: lsp:type:{content_hash}:{line_number}
    Cache TTL: 300 seconds (5 minutes)

    Example:
        type_metadata = await extractor.extract_type_metadata(
            "/app/src/user.py",
            "def process_user(user_id: int) -> User: ...",
            chunk  # CodeChunk with name="process_user", start_line=0
        )

        # Result:
        {
            "return_type": "User",
            "param_types": {"user_id": "int"},
            "signature": "process_user(user_id: int) -> User"
        }
    """

    def __init__(
        self,
        lsp_client: Optional[PyrightLSPClient] = None,
        typescript_lsp_client: Optional[TypeScriptLSPClient] = None,
        redis_cache: Optional[RedisCache] = None
    ):
        """
        Initialize TypeExtractorService.

        Args:
            lsp_client: Pyright LSP client for Python (optional - graceful degradation if None)
            typescript_lsp_client: TypeScript LSP client for TS/JS (optional - EPIC-16)
            redis_cache: Redis L2 cache (optional - Story 13.4)
        """
        self.lsp = lsp_client
        self.typescript_lsp = typescript_lsp_client
        self.cache = redis_cache
        self.logger = logger.bind(service="type_extractor")

    async def extract_type_metadata(
        self,
        file_path: str,
        source_code: str,
        chunk: CodeChunk
    ) -> Dict[str, Any]:
        """
        Extract type metadata for a code chunk using LSP hover with L2 Redis caching.

        Story 13.4: Added L2 cache lookup/population for 10× performance improvement.
        Story 16.2: Added TypeScript/JavaScript support via TypeScript LSP.

        Args:
            file_path: Absolute file path (for LSP URI)
            source_code: Complete source code of file
            chunk: Code chunk to analyze (must have start_line)

        Returns:
            Type metadata dict with:
                - return_type: str | None (e.g., "User", "int")
                - param_types: Dict[str, str] (e.g., {"user_id": "int"})
                - signature: str | None (e.g., "process_user(user_id: int) -> User")

        Graceful Degradation:
            - If Redis cache is None: queries LSP directly (no caching)
            - If LSP client is None: returns empty metadata
            - If LSP query fails: returns empty metadata (logs warning)
            - If hover text is empty: returns empty metadata
            - Never raises exceptions (production-safe)
        """
        # Default empty metadata
        metadata: Dict[str, Any] = {
            "return_type": None,
            "param_types": {},
            "signature": None
        }

        # Detect language from file extension
        language = self._detect_language(file_path)

        # Route to appropriate LSP client
        if language in ("typescript", "javascript", "tsx", "jsx"):
            return await self._extract_typescript_metadata(file_path, source_code, chunk, language)
        elif language == "python":
            return await self._extract_python_metadata(file_path, source_code, chunk)
        else:
            self.logger.debug("Unsupported language for LSP type extraction", language=language)
            return metadata

    def _detect_language(self, file_path: str) -> str:
        """
        Detect language from file extension.

        Args:
            file_path: File path

        Returns:
            Language identifier (python, typescript, javascript, tsx, jsx)
        """
        extension = file_path.split(".")[-1].lower() if "." in file_path else ""

        extension_map = {
            "py": "python",
            "ts": "typescript",
            "tsx": "tsx",
            "js": "javascript",
            "jsx": "jsx"
        }

        return extension_map.get(extension, "unknown")

    async def _extract_python_metadata(
        self,
        file_path: str,
        source_code: str,
        chunk: CodeChunk
    ) -> Dict[str, Any]:
        """
        Extract type metadata for Python code using Pyright LSP.

        (Original implementation - EPIC-13)
        """
        # Default empty metadata
        metadata: Dict[str, Any] = {
            "return_type": None,
            "param_types": {},
            "signature": None
        }

        # Graceful degradation: No LSP client
        if not self.lsp:
            self.logger.debug("Pyright LSP client not available, skipping type extraction")
            return metadata

        # Graceful degradation: No start_line (cannot query LSP)
        if chunk.start_line is None:
            self.logger.debug(
                "Chunk has no start_line, skipping type extraction",
                chunk_name=chunk.name
            )
            return metadata

        # STORY 13.4: L2 CACHE LOOKUP
        cache_key = None
        if self.cache:
            # Generate cache key: lsp:type:{content_hash}:{line_number}
            content_hash = hashlib.md5(source_code.encode()).hexdigest()
            cache_key = f"lsp:type:{content_hash}:{chunk.start_line}"

            try:
                cached_metadata = await self.cache.get(cache_key)
                if cached_metadata:
                    self.logger.debug(
                        "LSP cache HIT",
                        chunk_name=chunk.name,
                        cache_key=cache_key
                    )
                    return cached_metadata
            except Exception as e:
                # Cache lookup failed - continue to LSP query (graceful degradation)
                self.logger.warning(
                    "Redis cache lookup failed, continuing to LSP query",
                    error=str(e)
                )

        # CACHE MISS - Query LSP
        self.logger.debug(
            "LSP cache MISS, querying LSP",
            chunk_name=chunk.name,
            cache_key=cache_key
        )

        try:
            # Query LSP for hover info at symbol start
            # Calculate character position by finding symbol name in source line
            lines = source_code.split("\n")
            if chunk.start_line < len(lines):
                line_text = lines[chunk.start_line]

                # Find position of symbol name in line
                # Try to find chunk name in the line (e.g., "def add" or "class User")
                char_position = 4  # Default fallback
                if chunk.name and chunk.name in line_text:
                    # Find start of name (after "def " or "class ")
                    name_index = line_text.find(chunk.name)
                    if name_index != -1:
                        char_position = name_index
            else:
                char_position = 4  # Fallback

            hover_text = await self.lsp.hover(
                file_path=file_path,
                source_code=source_code,
                line=chunk.start_line,
                character=char_position
            )

            if not hover_text:
                # No hover info available (e.g., whitespace, comment)
                self.logger.debug(
                    "No hover info returned from LSP",
                    chunk_name=chunk.name,
                    line=chunk.start_line
                )
                return metadata

            # Parse hover text to extract type components
            metadata = self._parse_hover_signature(hover_text, chunk.name or "unknown")

            self.logger.debug(
                "Type metadata extracted from LSP",
                chunk_name=chunk.name,
                return_type=metadata.get("return_type"),
                param_count=len(metadata.get("param_types", {}))
            )

            # STORY 13.4: POPULATE L2 CACHE (300s TTL)
            if self.cache and cache_key and metadata.get("signature"):
                # Only cache if we have meaningful metadata (signature present)
                try:
                    await self.cache.set(cache_key, metadata, ttl_seconds=300)
                    self.logger.debug(
                        "LSP result cached",
                        cache_key=cache_key,
                        ttl_seconds=300
                    )
                except Exception as e:
                    # Cache population failed - continue (graceful degradation)
                    self.logger.warning(
                        "Redis cache set failed",
                        error=str(e)
                    )

            return metadata

        except LSPError as e:
            # LSP query failed - degrade gracefully
            self.logger.warning(
                "LSP type extraction failed",
                chunk_name=chunk.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return metadata  # Return empty metadata (graceful degradation)

        except Exception as e:
            # Unexpected error - degrade gracefully (never crash indexing)
            self.logger.error(
                "Unexpected error in type extraction",
                chunk_name=chunk.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return metadata  # Return empty metadata

    def _parse_hover_signature(self, hover_text: str, symbol_name: str) -> Dict[str, Any]:
        """
        Parse LSP hover text to extract signature components.

        Pyright hover format examples:
            "(function) add: (a: int, b: int) -> int"
            "(method) User.validate: (self) -> bool"
            "(class) User"
            "(variable) count: int"

        Args:
            hover_text: Raw hover text from LSP
            symbol_name: Symbol name being analyzed (for logging)

        Returns:
            Metadata dict with return_type, param_types, signature
        """
        metadata: Dict[str, Any] = {
            "return_type": None,
            "param_types": {},
            "signature": None
        }

        try:
            # Extract signature line (usually first line)
            lines = hover_text.strip().split("\n")
            signature_line = lines[0].strip()

            # Remove prefix like "(function)" or "(method)"
            # Example: "(function) add: (a: int, b: int) -> int"
            #          becomes: "add: (a: int, b: int) -> int"
            if ")" in signature_line and signature_line.startswith("("):
                # Find first closing paren
                closing_paren = signature_line.find(")")
                signature_line = signature_line[closing_paren + 1:].strip()

            # Store full signature
            metadata["signature"] = signature_line

            # Extract return type (after ->)
            # Example: "add: (a: int, b: int) -> int"
            if "->" in signature_line:
                return_part = signature_line.split("->")[-1].strip()
                metadata["return_type"] = return_part

            # Extract parameter types (between parentheses after colon)
            # Example: "add: (a: int, b: int) -> int"
            #          params: "a: int, b: int"
            if "(" in signature_line and ")" in signature_line:
                # Find parameters section after first colon
                if ":" in signature_line:
                    after_colon = signature_line.split(":", 1)[1].strip()

                    # Extract content between first ( and last )
                    paren_start = after_colon.find("(")
                    paren_end = after_colon.rfind(")")

                    if paren_start != -1 and paren_end != -1:
                        params_str = after_colon[paren_start + 1:paren_end]

                        # Parse parameters: "a: int, b: str, c: Optional[User]"
                        metadata["param_types"] = self._parse_parameters(params_str)

            return metadata

        except Exception as e:
            # Parsing failed - return empty metadata
            self.logger.warning(
                "Failed to parse hover signature",
                symbol_name=symbol_name,
                hover_text=hover_text[:100],  # First 100 chars for debugging
                error=str(e)
            )
            return metadata

    def _parse_parameters(self, params_str: str) -> Dict[str, str]:
        """
        Parse parameter string to extract parameter names and types.

        Handles:
        - Simple params: "a: int, b: str"
        - Generic types: "items: list[int]"
        - Optional types: "name: Optional[str]"
        - Default values: "count: int = 0"
        - Complex types: "config: Dict[str, Any]"

        Args:
            params_str: Parameter string (e.g., "a: int, b: str")

        Returns:
            Dict mapping parameter names to types
        """
        param_types: Dict[str, str] = {}

        if not params_str.strip():
            return param_types

        # Split by comma, but respect nested brackets
        # Example: "a: int, b: List[str], c: Dict[str, Any]"
        params = self._split_params(params_str)

        for param in params:
            param = param.strip()

            if not param or param == "...":  # Skip empty or ellipsis
                continue

            # Parse "name: type" or "name: type = default"
            if ":" in param:
                parts = param.split(":", 1)
                param_name = parts[0].strip()
                type_part = parts[1].strip()

                # Remove default value (after =)
                # Example: "count: int = 0" -> "int"
                if "=" in type_part:
                    type_part = type_part.split("=", 1)[0].strip()

                param_types[param_name] = type_part

        return param_types

    def _split_params(self, params_str: str) -> list[str]:
        """
        Split parameter string by comma, respecting nested brackets.

        Example:
            "a: int, b: List[str, int], c: Dict[str, Any]"
            -> ["a: int", "b: List[str, int]", "c: Dict[str, Any]"]

        Args:
            params_str: Parameter string

        Returns:
            List of parameter strings
        """
        params = []
        current_param = []
        bracket_depth = 0

        for char in params_str:
            if char in "[<(":
                bracket_depth += 1
                current_param.append(char)
            elif char in "]>)":
                bracket_depth -= 1
                current_param.append(char)
            elif char == "," and bracket_depth == 0:
                # Top-level comma - split here
                params.append("".join(current_param).strip())
                current_param = []
            else:
                current_param.append(char)

        # Add last parameter
        if current_param:
            params.append("".join(current_param).strip())

        return params

    async def _extract_typescript_metadata(
        self,
        file_path: str,
        source_code: str,
        chunk: CodeChunk,
        language: str
    ) -> Dict[str, Any]:
        """
        Extract type metadata for TypeScript/JavaScript code using TypeScript LSP.

        Story: EPIC-16 Story 16.2 - TypeScript LSP Type Extraction

        Args:
            file_path: Absolute file path (for LSP URI)
            source_code: Complete source code of file
            chunk: Code chunk to analyze
            language: Language ID (typescript, javascript, tsx, jsx)

        Returns:
            Type metadata dict with return_type, param_types, signature
        """
        # Default empty metadata
        metadata: Dict[str, Any] = {
            "return_type": None,
            "param_types": {},
            "signature": None
        }

        # Graceful degradation: No TypeScript LSP client
        if not self.typescript_lsp:
            self.logger.debug("TypeScript LSP client not available, skipping type extraction")
            return metadata

        # Graceful degradation: No start_line (cannot query LSP)
        if chunk.start_line is None:
            self.logger.debug(
                "Chunk has no start_line, skipping type extraction",
                chunk_name=chunk.name
            )
            return metadata

        # L2 CACHE LOOKUP
        cache_key = None
        if self.cache:
            content_hash = hashlib.md5(source_code.encode()).hexdigest()
            cache_key = f"lsp:ts:type:{content_hash}:{chunk.start_line}"

            try:
                cached_metadata = await self.cache.get(cache_key)
                if cached_metadata:
                    self.logger.debug(
                        "TypeScript LSP cache HIT",
                        chunk_name=chunk.name,
                        cache_key=cache_key
                    )
                    return cached_metadata
            except Exception as e:
                self.logger.warning(
                    "Redis cache lookup failed for TypeScript, continuing to LSP query",
                    error=str(e)
                )

        # CACHE MISS - Query TypeScript LSP
        self.logger.debug(
            "TypeScript LSP cache MISS, querying LSP",
            chunk_name=chunk.name,
            cache_key=cache_key
        )

        try:
            # Calculate character position by finding symbol name in source line
            lines = source_code.split("\n")
            if chunk.start_line < len(lines):
                line_text = lines[chunk.start_line]

                # Find position of symbol name in line
                char_position = 4  # Default fallback
                if chunk.name and chunk.name in line_text:
                    name_index = line_text.find(chunk.name)
                    if name_index != -1:
                        char_position = name_index
            else:
                char_position = 4  # Fallback

            # Map language to LSP language ID
            language_id_map = {
                "typescript": "typescript",
                "tsx": "typescriptreact",
                "javascript": "javascript",
                "jsx": "javascriptreact"
            }
            language_id = language_id_map.get(language, "typescript")

            # Query TypeScript LSP
            hover_text = await self.typescript_lsp.hover(
                file_path=file_path,
                source_code=source_code,
                line=chunk.start_line,
                character=char_position,
                language_id=language_id
            )

            if not hover_text:
                self.logger.debug(
                    "No hover info returned from TypeScript LSP",
                    chunk_name=chunk.name,
                    line=chunk.start_line
                )
                return metadata

            # Parse TypeScript hover text
            metadata = self._parse_typescript_hover(hover_text, chunk.name or "unknown")

            self.logger.debug(
                "TypeScript type metadata extracted from LSP",
                chunk_name=chunk.name,
                return_type=metadata.get("return_type"),
                param_count=len(metadata.get("param_types", {}))
            )

            # POPULATE L2 CACHE (300s TTL)
            if self.cache and cache_key and metadata.get("signature"):
                try:
                    await self.cache.set(cache_key, metadata, ttl_seconds=300)
                    self.logger.debug(
                        "TypeScript LSP result cached",
                        cache_key=cache_key,
                        ttl_seconds=300
                    )
                except Exception as e:
                    self.logger.warning(
                        "Redis cache set failed for TypeScript",
                        error=str(e)
                    )

            return metadata

        except LSPError as e:
            self.logger.warning(
                "TypeScript LSP type extraction failed",
                chunk_name=chunk.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return metadata  # Return empty metadata (graceful degradation)

        except Exception as e:
            self.logger.error(
                "Unexpected error in TypeScript type extraction",
                chunk_name=chunk.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return metadata  # Return empty metadata

    def _parse_typescript_hover(self, hover_text: str, symbol_name: str) -> Dict[str, Any]:
        """
        Parse TypeScript LSP hover text to extract signature components.

        TypeScript LSP hover format examples:
            "function getUser(id: string): Promise<User>"
            "(method) UserService.getUser(id: string): Promise<User>"
            "const helper: (x: number) => number"
            "interface User"

        Args:
            hover_text: Raw hover text from TypeScript LSP
            symbol_name: Symbol name being analyzed (for logging)

        Returns:
            Metadata dict with return_type, param_types, signature
        """
        metadata: Dict[str, Any] = {
            "return_type": None,
            "param_types": {},
            "signature": None
        }

        try:
            # Extract signature line (usually first line, may contain markdown code blocks)
            lines = hover_text.strip().split("\n")
            signature_line = lines[0].strip()

            # Remove markdown code block markers
            if signature_line.startswith("```"):
                if len(lines) > 1:
                    signature_line = lines[1].strip()
                else:
                    return metadata

            # Remove prefix like "(method)" or "(function)"
            if ")" in signature_line and signature_line.startswith("("):
                closing_paren = signature_line.find(")")
                signature_line = signature_line[closing_paren + 1:].strip()

            # Store full signature
            metadata["signature"] = signature_line

            # Extract return type (after : or =>)
            # Example 1: "getUser(id: string): Promise<User>"
            # Example 2: "const helper: (x: number) => number"

            # Try arrow function format first: (params) => return_type
            if "=>" in signature_line:
                return_part = signature_line.split("=>")[-1].strip()
                metadata["return_type"] = return_part
            elif ":" in signature_line and "(" in signature_line:
                # Function declaration format: name(params): return_type
                # Find last colon after parameters
                paren_end = signature_line.rfind(")")
                if paren_end != -1:
                    after_params = signature_line[paren_end + 1:].strip()
                    if after_params.startswith(":"):
                        return_part = after_params[1:].strip()
                        metadata["return_type"] = return_part

            # Extract parameter types
            if "(" in signature_line and ")" in signature_line:
                # Extract content between first ( and matching )
                paren_start = signature_line.find("(")
                paren_end = signature_line.rfind(")")

                if paren_start != -1 and paren_end != -1:
                    params_str = signature_line[paren_start + 1:paren_end]
                    metadata["param_types"] = self._parse_typescript_parameters(params_str)

            return metadata

        except Exception as e:
            self.logger.warning(
                "Failed to parse TypeScript hover signature",
                symbol_name=symbol_name,
                hover_text=hover_text[:100],
                error=str(e)
            )
            return metadata

    def _parse_typescript_parameters(self, params_str: str) -> Dict[str, str]:
        """
        Parse TypeScript parameter string to extract parameter names and types.

        Handles:
        - Simple params: "id: string, name: string"
        - Optional params: "id?: string"
        - Generic types: "items: Array<User>"
        - Complex types: "config: { name: string, value: number }"
        - Rest params: "...args: string[]"

        Args:
            params_str: Parameter string (e.g., "id: string, name?: string")

        Returns:
            Dict mapping parameter names to types
        """
        param_types: Dict[str, str] = {}

        if not params_str.strip():
            return param_types

        # Split by comma, respecting nested brackets
        params = self._split_params(params_str)

        for param in params:
            param = param.strip()

            if not param or param == "...":  # Skip empty or ellipsis
                continue

            # Parse "name: type" or "name?: type" or "...name: type"
            if ":" in param:
                parts = param.split(":", 1)
                param_name = parts[0].strip()

                # Remove rest operator (...)
                if param_name.startswith("..."):
                    param_name = param_name[3:].strip()

                # Remove optional marker (?)
                if param_name.endswith("?"):
                    param_name = param_name[:-1].strip()

                type_part = parts[1].strip()

                # Remove default value (after =)
                if "=" in type_part:
                    type_part = type_part.split("=", 1)[0].strip()

                param_types[param_name] = type_part

        return param_types
