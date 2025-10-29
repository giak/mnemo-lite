"""
Centralized Language Configuration for MnemoLite.

Defines all supported programming languages with their file extensions,
Tree-sitter grammars, and embedding models.

This configuration is used by:
- CodeIndexingService: File extension detection
- MCP SupportedLanguagesResource: Language listing for clients
- ProjectScanner: File filtering

NOTE: When adding a new language, update this file only (single source of truth).
"""

from dataclasses import dataclass
from typing import List, Dict


@dataclass
class LanguageConfig:
    """Configuration for a supported programming language."""

    name: str
    """Display name (e.g., 'Python')"""

    extensions: List[str]
    """File extensions (e.g., ['.py', '.pyi'])"""

    tree_sitter_grammar: str
    """Tree-sitter grammar name (e.g., 'tree-sitter-python')"""

    embedding_model: str = "nomic-embed-text-v1.5"
    """Embedding model used for this language (default: nomic-embed-text-v1.5)"""


# ============================================================================
# Supported Languages Configuration
# ============================================================================

SUPPORTED_LANGUAGES: List[LanguageConfig] = [
    LanguageConfig(
        name="Python",
        extensions=[".py", ".pyi"],
        tree_sitter_grammar="tree-sitter-python",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="JavaScript",
        extensions=[".js", ".jsx", ".mjs", ".cjs"],
        tree_sitter_grammar="tree-sitter-javascript",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="TypeScript",
        extensions=[".ts", ".tsx", ".d.ts"],
        tree_sitter_grammar="tree-sitter-typescript",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Go",
        extensions=[".go"],
        tree_sitter_grammar="tree-sitter-go",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Rust",
        extensions=[".rs"],
        tree_sitter_grammar="tree-sitter-rust",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Java",
        extensions=[".java"],
        tree_sitter_grammar="tree-sitter-java",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="C#",
        extensions=[".cs", ".csx"],
        tree_sitter_grammar="tree-sitter-c-sharp",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Ruby",
        extensions=[".rb", ".rake", ".gemspec"],
        tree_sitter_grammar="tree-sitter-ruby",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="PHP",
        extensions=[".php", ".php5", ".phtml"],
        tree_sitter_grammar="tree-sitter-php",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="C",
        extensions=[".c", ".h"],
        tree_sitter_grammar="tree-sitter-c",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="C++",
        extensions=[".cpp", ".hpp", ".cc", ".hh", ".cxx", ".hxx"],
        tree_sitter_grammar="tree-sitter-cpp",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Swift",
        extensions=[".swift"],
        tree_sitter_grammar="tree-sitter-swift",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Kotlin",
        extensions=[".kt", ".kts"],
        tree_sitter_grammar="tree-sitter-kotlin",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Scala",
        extensions=[".scala", ".sc"],
        tree_sitter_grammar="tree-sitter-scala",
        embedding_model="nomic-embed-text-v1.5"
    ),
    LanguageConfig(
        name="Bash",
        extensions=[".sh", ".bash", ".zsh"],
        tree_sitter_grammar="tree-sitter-bash",
        embedding_model="nomic-embed-text-v1.5"
    ),
]

# ============================================================================
# Convenience Mappings
# ============================================================================

# Extension to language name mapping (for quick lookup)
EXTENSION_TO_LANGUAGE: Dict[str, str] = {
    ext: lang.name
    for lang in SUPPORTED_LANGUAGES
    for ext in lang.extensions
}

# Language name to config mapping (for quick lookup)
LANGUAGE_NAME_TO_CONFIG: Dict[str, LanguageConfig] = {
    lang.name: lang
    for lang in SUPPORTED_LANGUAGES
}
