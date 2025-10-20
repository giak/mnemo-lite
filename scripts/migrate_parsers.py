#!/usr/bin/env python3
"""
Script de migration automatique des parsers vers architecture modulaire.

Extrait les classes de parser du fichier monolithique code_chunking_service.py
et génère les fichiers modulaires individuels.

Usage:
    python scripts/migrate_parsers.py
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple


# Configuration
SOURCE_FILE = Path("api/services/code_chunking_service.py")
TARGET_DIR = Path("api/services/code_chunking/parsers")
PARSERS_INIT = TARGET_DIR / "__init__.py"

# Parsers à migrer (nom de la classe → nom du fichier)
PARSERS_TO_MIGRATE = {
    "JavaScriptParser": "javascript_parser.py",
    "TypeScriptParser": "typescript_parser.py",
    "PHPParser": "php_parser.py",
    "VueParser": "vue_parser.py",
}


def extract_class_code(source_code: str, class_name: str) -> Tuple[str, int, int]:
    """
    Extrait le code d'une classe du fichier source.

    Returns:
        Tuple[class_code, start_line, end_line]
    """
    lines = source_code.split('\n')

    # Find class definition
    class_pattern = rf'^class {class_name}\('
    start_idx = None

    for i, line in enumerate(lines):
        if re.match(class_pattern, line):
            start_idx = i
            break

    if start_idx is None:
        raise ValueError(f"Class {class_name} not found")

    # Find end of class (next class or end of file)
    end_idx = len(lines)
    indent_level = len(lines[start_idx]) - len(lines[start_idx].lstrip())

    for i in range(start_idx + 1, len(lines)):
        line = lines[i]

        # Skip empty lines
        if not line.strip():
            continue

        # Check if we've reached the next top-level element
        current_indent = len(line) - len(line.lstrip())

        # If we find a line at the same or lower indentation (and it's not empty/comment)
        if current_indent <= indent_level and line.strip() and not line.strip().startswith('#'):
            end_idx = i
            break

    class_code = '\n'.join(lines[start_idx:end_idx])

    return class_code, start_idx + 1, end_idx


def generate_parser_file(
    class_name: str,
    class_code: str,
    language: str,
    description: str,
    requires_language_pack: bool = True
) -> str:
    """Génère le contenu complet d'un fichier parser."""

    # Extract imports needed
    imports = []
    if requires_language_pack:
        imports.append("from tree_sitter import Node, Tree")
        imports.append("from tree_sitter_language_pack import get_language")
    else:
        imports.append("from tree_sitter import Language, Node, Tree")
        imports.append("import tree_sitter_python as tspython")

    imports.append("from models.code_chunk_models import CodeUnit")
    imports.append("from ..base_parser import LanguageParser")

    header = f'''"""
{language} parser for AST-based code chunking.

{description}
"""

'''

    imports_section = '\n'.join(imports) + '\n\n'

    # Process class code to use helper methods
    processed_class = class_code

    return header + imports_section + processed_class + '\n'


def update_parsers_init(parser_classes: List[str]) -> str:
    """Met à jour le fichier parsers/__init__.py avec tous les parsers."""

    content = '''"""
Auto-discovery and registration of language parsers.

This module automatically imports and registers all available language parsers
with the ParserRegistry. Adding a new language is as simple as creating a new
parser file in this directory.
"""

import logging

from ..parser_registry import ParserRegistry

logger = logging.getLogger(__name__)


# =============================================================================
# PARSER AUTO-DISCOVERY
# =============================================================================

# Python Parser (always available)
try:
    from .python_parser import PythonParser
    ParserRegistry.register("python", PythonParser)
    logger.debug("Registered Python parser")
except ImportError as e:
    logger.warning(f"Failed to import Python parser: {e}")

# JavaScript/TypeScript Parsers (require tree-sitter-language-pack)
try:
    from .javascript_parser import JavaScriptParser
    from .typescript_parser import TypeScriptParser

    ParserRegistry.register("javascript", JavaScriptParser)
    ParserRegistry.register("typescript", TypeScriptParser)
    ParserRegistry.register("jsx", JavaScriptParser)  # JSX uses JavaScript parser
    ParserRegistry.register("tsx", TypeScriptParser)  # TSX uses TypeScript parser
    logger.debug("Registered JavaScript/TypeScript parsers")
except ImportError as e:
    logger.debug(f"JavaScript/TypeScript parsers not available: {e}")

# PHP Parser (require tree-sitter-language-pack)
try:
    from .php_parser import PHPParser
    ParserRegistry.register("php", PHPParser)
    logger.debug("Registered PHP parser")
except ImportError as e:
    logger.debug(f"PHP parser not available: {e}")

# Vue Parser (require tree-sitter-language-pack)
try:
    from .vue_parser import VueParser
    ParserRegistry.register("vue", VueParser)
    logger.debug("Registered Vue parser")
except ImportError as e:
    logger.debug(f"Vue parser not available: {e}")


# =============================================================================
# PUBLIC EXPORTS
# =============================================================================

__all__ = [
    "PythonParser",
    "JavaScriptParser",
    "TypeScriptParser",
    "PHPParser",
    "VueParser",
]
'''

    return content


def main():
    """Execute migration."""
    print("=" * 80)
    print("🚀 Migration automatique des parsers")
    print("=" * 80)

    # Read source file
    print(f"\n📖 Lecture du fichier source: {SOURCE_FILE}")
    with open(SOURCE_FILE, 'r') as f:
        source_code = f.read()

    print(f"✅ {len(source_code)} caractères lus")

    # Migrate each parser
    migrated = []

    for class_name, filename in PARSERS_TO_MIGRATE.items():
        print(f"\n🔄 Migration de {class_name}...")

        try:
            # Extract class code
            class_code, start, end = extract_class_code(source_code, class_name)
            print(f"   Extrait lignes {start}-{end} ({end - start} lignes)")

            # Determine language and description
            lang_map = {
                "JavaScriptParser": ("JavaScript/JSX", "Handles JavaScript and JSX parsing using tree-sitter."),
                "TypeScriptParser": ("TypeScript/TSX", "Handles TypeScript and TSX parsing, extending JavaScript parser."),
                "PHPParser": ("PHP", "Handles PHP parsing including traits, interfaces, and namespaces."),
                "VueParser": ("Vue.js", "Handles Vue.js Single File Components (SFC) parsing."),
            }

            language, description = lang_map.get(class_name, (class_name, "Parser"))

            # Generate file content
            file_content = generate_parser_file(
                class_name,
                class_code,
                language,
                description,
                requires_language_pack=True
            )

            # Write to file
            target_file = TARGET_DIR / filename
            with open(target_file, 'w') as f:
                f.write(file_content)

            print(f"   ✅ Créé {target_file} ({len(file_content)} caractères)")
            migrated.append(class_name)

        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            import traceback
            traceback.print_exc()

    # Update parsers/__init__.py
    if migrated:
        print(f"\n📝 Mise à jour de {PARSERS_INIT}...")
        init_content = update_parsers_init(migrated)

        with open(PARSERS_INIT, 'w') as f:
            f.write(init_content)

        print(f"   ✅ {PARSERS_INIT} mis à jour")

    # Summary
    print("\n" + "=" * 80)
    print("✅ MIGRATION TERMINÉE")
    print("=" * 80)
    print(f"📊 Parsers migrés: {len(migrated)}/{len(PARSERS_TO_MIGRATE)}")
    for parser in migrated:
        print(f"   ✅ {parser}")

    if len(migrated) < len(PARSERS_TO_MIGRATE):
        failed = set(PARSERS_TO_MIGRATE.keys()) - set(migrated)
        print(f"\n⚠️  Échecs: {len(failed)}")
        for parser in failed:
            print(f"   ❌ {parser}")

    print("\n🎯 Prochaine étape: Tester que tout fonctionne!")
    print("=" * 80)


if __name__ == "__main__":
    main()
