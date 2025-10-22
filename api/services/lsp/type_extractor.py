"""
Type Metadata Extraction Service using LSP.

Story: EPIC-13 Story 13.2 - Type Metadata Extraction Service
Author: Claude Code
Date: 2025-10-22

Extracts type information from Pyright LSP server and merges with tree-sitter metadata.
"""

import re
import structlog
from typing import Optional, Dict, Any

from services.lsp.lsp_client import PyrightLSPClient
from services.lsp.lsp_errors import LSPError
from models.code_chunk_models import CodeChunk

logger = structlog.get_logger()


class TypeExtractorService:
    """
    Extract type information using LSP hover queries.

    Provides semantic type analysis to enhance structural metadata from tree-sitter.

    Workflow:
    1. Query LSP for hover info at symbol position
    2. Parse hover text to extract signature components
    3. Return structured type metadata

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

    def __init__(self, lsp_client: Optional[PyrightLSPClient] = None):
        """
        Initialize TypeExtractorService.

        Args:
            lsp_client: Pyright LSP client (optional - graceful degradation if None)
        """
        self.lsp = lsp_client
        self.logger = logger.bind(service="type_extractor")

    async def extract_type_metadata(
        self,
        file_path: str,
        source_code: str,
        chunk: CodeChunk
    ) -> Dict[str, Any]:
        """
        Extract type metadata for a code chunk using LSP hover.

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

        # Graceful degradation: No LSP client
        if not self.lsp:
            self.logger.debug("LSP client not available, skipping type extraction")
            return metadata

        # Graceful degradation: No start_line (cannot query LSP)
        if chunk.start_line is None:
            self.logger.debug(
                "Chunk has no start_line, skipping type extraction",
                chunk_name=chunk.name
            )
            return metadata

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
                "Type metadata extracted",
                chunk_name=chunk.name,
                return_type=metadata.get("return_type"),
                param_count=len(metadata.get("param_types", {}))
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
