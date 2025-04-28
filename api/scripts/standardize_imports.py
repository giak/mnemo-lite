#!/usr/bin/env python3
"""
Script pour standardiser les imports dans le projet MnemoLite.

Ce script parcourt tous les fichiers Python du projet et standardise les imports
pour résoudre les problèmes d'incohérence entre l'environnement local et Docker.

Problème principal: Les chemins d'importation dans le code diffèrent entre 
l'environnement local et l'environnement Docker, ce qui cause des problèmes
dans les tests et l'exécution du code.

Usage:
    python standardize_imports.py [--dry-run]
"""

import os
import re
import argparse
from pathlib import Path
import sys

# Patterns d'import à standardiser
IMPORT_PATTERNS = [
    # Import direct avec préfixe api
    (r'from api\.([\w\.]+) import', r'from \1 import'),
    # Import direct avec préfixe api sans from
    (r'import api\.([\w\.]+)', r'import \1'),
    # Imports relatifs
    (r'from \.\.([\w\.]+) import', r'from \1 import'),
    (r'from \.([\w\.]+) import', r'from \1 import'),
]

# Extensions de fichiers à traiter
FILE_EXTENSIONS = ['.py']

# Répertoires à exclure
EXCLUDED_DIRS = [
    '.git',
    '__pycache__',
    'venv',
    'env',
    '.pytest_cache',
    '.coverage',
    'htmlcov',
]

def should_process_file(file_path):
    """
    Vérifie si le fichier doit être traité.
    
    Args:
        file_path: Chemin du fichier à vérifier
        
    Returns:
        True si le fichier doit être traité, False sinon
    """
    # Vérifie l'extension
    if not any(file_path.endswith(ext) for ext in FILE_EXTENSIONS):
        return False
    
    # Vérifie si dans un répertoire exclu
    if any(excl in str(file_path) for excl in EXCLUDED_DIRS):
        return False
    
    return True

def standardize_file_imports(file_path, dry_run=False):
    """
    Standardise les imports dans un fichier.
    
    Args:
        file_path: Chemin du fichier
        dry_run: Si True, n'écrit pas les modifications
        
    Returns:
        Nombre de modifications effectuées
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    modifications = 0
    
    for pattern, replacement in IMPORT_PATTERNS:
        # Utilise regex avec re.MULTILINE pour correspondre à chaque ligne
        new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)
        if count > 0:
            content = new_content
            modifications += count
    
    if modifications > 0:
        print(f"{file_path}: {modifications} modifications")
        
        if not dry_run:
            with open(file_path, 'w') as f:
                f.write(content)
    
    return modifications

def process_directory(directory, dry_run=False):
    """
    Traite récursivement un répertoire pour standardiser les imports.
    
    Args:
        directory: Répertoire à traiter
        dry_run: Si True, n'écrit pas les modifications
        
    Returns:
        (Nombre de fichiers traités, Nombre total de modifications)
    """
    total_files = 0
    total_modifications = 0
    
    for root, dirs, files in os.walk(directory):
        # Filtrer les répertoires exclus
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        
        for file in files:
            file_path = os.path.join(root, file)
            
            if should_process_file(file_path):
                modifications = standardize_file_imports(file_path, dry_run)
                if modifications > 0:
                    total_files += 1
                    total_modifications += modifications
    
    return total_files, total_modifications

def main():
    parser = argparse.ArgumentParser(description="Standardise les imports dans le projet MnemoLite")
    parser.add_argument('--dry-run', action='store_true', help="Exécute sans effectuer de modifications")
    parser.add_argument('--dir', default='api', help="Répertoire à traiter (par défaut: api)")
    
    args = parser.parse_args()
    
    print(f"Standardisation des imports dans {args.dir}...")
    if args.dry_run:
        print("Mode simulation - aucune modification ne sera écrite")
    
    directory = Path(args.dir)
    if not directory.exists() or not directory.is_dir():
        print(f"Erreur: {args.dir} n'est pas un répertoire valide")
        return 1
    
    files_modified, total_mods = process_directory(directory, args.dry_run)
    
    print(f"\nRésumé:")
    print(f"  - {files_modified} fichiers modifiés")
    print(f"  - {total_mods} modifications d'imports effectuées")
    
    if args.dry_run:
        print("Aucune modification écrite (mode simulation)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
