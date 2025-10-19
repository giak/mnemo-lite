"""
Code chunking service for EPIC-06 Phase 1 Story 1 & 3.

DEPRECATED: This file is a backward compatibility wrapper.
New code should import from services.code_chunking module instead.

For new code, use:
    from services.code_chunking import CodeChunkingService, get_code_chunking_service
"""

# Import from new modular structure and re-export
from services.code_chunking.base_parser import LanguageParser
from services.code_chunking.parser_registry import ParserRegistry
from services.code_chunking.parsers import (
    PythonParser,
    JavaScriptParser,
    TypeScriptParser,
    PHPParser,
    VueParser,
    RustParser,
    DockerfileParser,
    SQLParser,
    HTMLParser,
    CSSParser,
    SCSSParser,
)
from services.code_chunking.parsers.javascript_parser import LANGUAGE_PACK_AVAILABLE
from services.code_chunking.service import (
    CodeChunkingService,
    get_code_chunking_service,
)

# Re-export for backward compatibility
__all__ = [
    # Parser classes
    "LanguageParser",
    "PythonParser",
    "JavaScriptParser",
    "TypeScriptParser",
    "PHPParser",
    "VueParser",
    "RustParser",
    "DockerfileParser",
    "SQLParser",
    "HTMLParser",
    "CSSParser",
    "SCSSParser",

    # Registry
    "ParserRegistry",

    # Service
    "CodeChunkingService",
    "get_code_chunking_service",

    # Constants
    "LANGUAGE_PACK_AVAILABLE",
]
