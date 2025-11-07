"""
Metadata extractors package for multi-language support.

EPIC-26 Story 26.1: TypeScript/JavaScript metadata extraction.
EPIC-29 Story 29.4: Python metadata extraction.
"""

from .base import MetadataExtractor
from .typescript_extractor import TypeScriptMetadataExtractor
from .python_extractor import PythonMetadataExtractor

__all__ = [
    "MetadataExtractor",
    "TypeScriptMetadataExtractor",
    "PythonMetadataExtractor",
]
