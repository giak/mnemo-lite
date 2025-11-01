"""
Metadata extractors package for multi-language support.

EPIC-26 Story 26.1: TypeScript/JavaScript metadata extraction.
"""

from .base import MetadataExtractor
from .typescript_extractor import TypeScriptMetadataExtractor

__all__ = [
    "MetadataExtractor",
    "TypeScriptMetadataExtractor",
]
