#!/usr/bin/env python3
"""
Script pour standardiser les imports dans le projet MnemoLite.

Ce script parcourt tous les fichiers Python du projet et applique une convention
d'import cohérente en supprimant le préfixe 'api.' lorsqu'il est présent.

Usage:
    python scripts/standardize_imports.py [--dry-run] [--verbose]

Options:
    --dry-run   Montre les modifications sans les appliquer
    --verbose   Affiche des informations détaillées sur chaque fichier analysé
"""

import os
import re
import argparse
import logging
from pathlib import Path
from typing import List, Tuple, Dict

# Configuration du logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("import_standardizer")

# Patterns à rechercher et remplacer
IMPORT_PATTERNS = [
    # from api.X import Y -> from X import Y
    (r"from\s+api\.([a-zA-Z0-9_.]+)\s+import", r"from \1 import"),
    # import api.X -> import X
    (r"import\s+api\.([a-zA-Z0-9_.]+)", r"import \1"),
    # from api import X -> from X import X (cas spécial à traiter manuellement)
    # (r'from\s+api\s+import\s+([a-zA-Z0-9_.]+)', SPECIAL_HANDLING)
]

# Extensions de fichier à traiter
FILE_EXTENSIONS = [".py"]

# Répertoires à exclure
EXCLUDED_DIRS = [
    ".git",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
]


def find_python_files(base_dir: str = ".") -> List[Path]:
    """Trouve tous les fichiers Python dans le répertoire spécifié."""
    files = []
    base_path = Path(base_dir).resolve()

    for root, dirs, filenames in os.walk(base_path):
        # Filtrer les répertoires exclus
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

        for filename in filenames:
            if any(filename.endswith(ext) for ext in FILE_EXTENSIONS):
                file_path = Path(root) / filename
                files.append(file_path)

    return files


def process_file(
    file_path: Path, dry_run: bool = False, verbose: bool = False
) -> Tuple[int, Dict[str, int]]:
    """
    Traite un fichier pour standardiser les imports.

    Args:
        file_path: Chemin vers le fichier à traiter
        dry_run: Si True, n'applique pas les changements
        verbose: Si True, affiche des informations détaillées

    Returns:
        Tuple contenant le nombre total de changements et un dictionnaire de stats par pattern
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content
        total_changes = 0
        stats = {}

        for pattern, replacement in IMPORT_PATTERNS:
            # Compiler le pattern pour plus d'efficacité
            regex = re.compile(pattern)
            # Compter les occurrences
            occurrences = len(regex.findall(content))

            if occurrences > 0:
                # Effectuer le remplacement
                new_content = regex.sub(replacement, content)

                if verbose and new_content != content:
                    logger.info(f"Dans {file_path}:")
                    for match in regex.finditer(content):
                        original = match.group(0)
                        modified = regex.sub(replacement, original)
                        logger.info(f"  {original} -> {modified}")

                content = new_content
                total_changes += occurrences
                stats[pattern] = occurrences

        # Écrire les changements si nécessaire
        if not dry_run and content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Mise à jour de {file_path}: {total_changes} changements.")
        elif content != original_content:
            logger.info(
                f"[DRY RUN] {file_path}: {total_changes} changements seraient appliqués."
            )

        return total_changes, stats

    except Exception as e:
        logger.error(f"Erreur lors du traitement de {file_path}: {e}")
        return 0, {}


def main():
    """Point d'entrée principal du script."""
    parser = argparse.ArgumentParser(
        description="Standardise les imports dans le projet MnemoLite."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Montre les modifications sans les appliquer",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Affiche des informations détaillées"
    )
    args = parser.parse_args()

    base_dir = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )  # Dossier racine du projet

    logger.info(f"Recherche de fichiers Python dans {base_dir}...")
    files = find_python_files(base_dir)
    logger.info(f"Trouvé {len(files)} fichiers Python à analyser.")

    total_files_changed = 0
    total_changes = 0
    pattern_stats = {}

    for file_path in files:
        changes, stats = process_file(file_path, args.dry_run, args.verbose)

        if changes > 0:
            total_files_changed += 1
            total_changes += changes

            # Agréger les stats par pattern
            for pattern, count in stats.items():
                if pattern in pattern_stats:
                    pattern_stats[pattern] += count
                else:
                    pattern_stats[pattern] = count

    # Afficher le récapitulatif
    logger.info("\n===== Récapitulatif =====")
    logger.info(f"Fichiers traités: {len(files)}")
    logger.info(f"Fichiers modifiés: {total_files_changed}")
    logger.info(f"Total des changements: {total_changes}")

    if pattern_stats:
        logger.info("\nDétails par pattern:")
        for pattern, count in pattern_stats.items():
            logger.info(f"  {pattern}: {count} occurrences")

    if args.dry_run:
        logger.info("\nExécuté en mode dry-run, aucune modification n'a été appliquée.")
        logger.info(
            "Pour appliquer les modifications, exécutez sans l'option --dry-run."
        )


if __name__ == "__main__":
    main()
