#!/bin/bash
# Phase 1 - Nettoyage Structure: Suppression duplications et migration imports

set -e

echo "🧹 Phase 1 - Nettoyage Structure MnemoLite"
echo "=========================================="
echo ""

# Créer backup
timestamp=$(date +%Y%m%d_%H%M%S)
backup_dir=".phase1_backup_$timestamp"
echo "📦 Création backup dans $backup_dir..."
mkdir -p "$backup_dir"

# Backup structures à supprimer
for dir in db/repositories services interfaces routes dependencies.py; do
    if [ -e "$dir" ]; then
        cp -r "$dir" "$backup_dir/" 2>/dev/null || true
    fi
done

echo "✅ Backup créé"
echo ""

# Étape 1: Mettre à jour les imports dans /api/*
echo "🔧 Étape 1: Mise à jour imports dans /api/*..."

# Dans /api/, remplacer imports relatifs par imports absolus depuis api.*
find api/ -name "*.py" -type f -exec sed -i \
    -e 's|^from db\.repositories|from api.db.repositories|g' \
    -e 's|^from services\.|from api.services.|g' \
    -e 's|^from interfaces\.|from api.interfaces.|g' \
    {} \;

echo "   ✅ Imports dans /api/ mis à jour"

# Étape 2: Mettre à jour les imports dans les autres fichiers
echo "🔧 Étape 2: Mise à jour imports dans tests/ et scripts/..."

# Tests et scripts
for dir in tests/ scripts/; do
    if [ -d "$dir" ]; then
        find "$dir" -name "*.py" -type f -exec sed -i \
            -e 's|^from db\.repositories|from api.db.repositories|g' \
            -e 's|^from services\.|from api.services.|g' \
            -e 's|^from interfaces\.|from api.interfaces.|g' \
            {} \;
    fi
done

echo "   ✅ Imports dans tests/ et scripts/ mis à jour"

# Étape 3: Mettre à jour dependencies.py à la racine
echo "🔧 Étape 3: Mise à jour dependencies.py à la racine..."
if [ -f "dependencies.py" ]; then
    sed -i \
        -e 's|^from db\.repositories|from api.db.repositories|g' \
        -e 's|^from services\.|from api.services.|g' \
        -e 's|^from interfaces\.|from api.interfaces.|g' \
        dependencies.py
    echo "   ✅ dependencies.py mis à jour"
fi

# Étape 4: Mettre à jour main.py dans api/
echo "🔧 Étape 4: Mise à jour api/main.py..."
if [ -f "api/main.py" ]; then
    sed -i \
        -e 's|^from db\.repositories|from api.db.repositories|g' \
        -e 's|^from services\.|from api.services.|g' \
        -e 's|^from routes import|from api.routes import|g' \
        api/main.py
    echo "   ✅ api/main.py mis à jour"
fi

# Étape 5: Vérifier syntaxe Python
echo ""
echo "🔍 Validation syntaxe Python..."
syntax_errors=0
for file in $(find api/ tests/ scripts/ -name "*.py" -type f 2>/dev/null); do
    if ! python3 -m py_compile "$file" 2>/dev/null; then
        echo "   ❌ Erreur syntaxe: $file"
        syntax_errors=$((syntax_errors + 1))
    fi
done

if [ $syntax_errors -gt 0 ]; then
    echo ""
    echo "❌ $syntax_errors fichiers avec erreurs de syntaxe!"
    echo "Rollback: cp -r $backup_dir/* ."
    exit 1
fi

echo "   ✅ Tous les fichiers ont une syntaxe valide"

# Étape 6: Archiver les anciennes structures
echo ""
echo "📁 Étape 6: Archivage des structures obsolètes..."
mkdir -p .archive/phase1_$timestamp

for dir in db/ services/ interfaces/ routes/; do
    if [ -d "$dir" ]; then
        echo "   Archivage: $dir → .archive/phase1_$timestamp/"
        mv "$dir" ".archive/phase1_$timestamp/"
    fi
done

# Supprimer dependencies.py à la racine (on utilise api/dependencies.py)
if [ -f "dependencies.py" ]; then
    echo "   Archivage: dependencies.py → .archive/phase1_$timestamp/"
    mv "dependencies.py" ".archive/phase1_$timestamp/"
fi

echo "   ✅ Structures obsolètes archivées"

# Étape 7: Validation finale
echo ""
echo "✅ Phase 1 - Nettoyage Structure TERMINÉ"
echo ""
echo "📊 Résumé:"
echo "   - Structures archivées dans .archive/phase1_$timestamp/"
echo "   - Backup dans $backup_dir/"
echo "   - Tous les imports utilisent maintenant api.*"
echo ""
echo "🧪 Prochaines étapes:"
echo "   1. Vérifier: git status"
echo "   2. Tester: make api-test"
echo "   3. Si OK: git add -A && git commit"
echo "   4. Si problème: cp -r $backup_dir/* . && git checkout ."
echo ""
