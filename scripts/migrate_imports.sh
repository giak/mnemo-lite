#!/bin/bash
# scripts/migrate_imports.sh
# Migre automatiquement les imports des anciennes structures vers api/*

set -e  # Exit on error

echo "🔄 Migration des imports vers structure api/*"
echo ""

# Backup first
echo "📦 Creating backup..."
timestamp=$(date +%Y%m%d_%H%M%S)
backup_dir=".backup_imports_$timestamp"
mkdir -p "$backup_dir"

# Backup files that will be modified
find . -name "*.py" -type f \
    -not -path "./.venv/*" \
    -not -path "./__pycache__/*" \
    -not -path "./.archive/*" \
    -not -path "./$backup_dir/*" \
    -exec cp --parents {} "$backup_dir/" \; 2>/dev/null || true

echo "✅ Backup created in $backup_dir"
echo ""

# Migration patterns
echo "🔧 Applying migration patterns..."

# Pattern 1: from db.repositories → from api.db.repositories
echo "  - db.repositories → api.db.repositories"
find . -name "*.py" -type f \
    -not -path "./.venv/*" \
    -not -path "./__pycache__/*" \
    -not -path "./.archive/*" \
    -not -path "./$backup_dir/*" \
    -exec sed -i 's/from db\.repositories/from api.db.repositories/g' {} \;

# Pattern 2: from services. → from api.services.
# ATTENTION: Ne pas toucher "from api.services." qui est déjà correct
echo "  - services. → api.services."
find . -name "*.py" -type f \
    -not -path "./.venv/*" \
    -not -path "./__pycache__/*" \
    -not -path "./.archive/*" \
    -not -path "./$backup_dir/*" \
    -not -path "./api/services/*" \
    -exec sed -i 's/^from services\./from api.services./g' {} \;

# Pattern 3: from interfaces. → from api.interfaces.
echo "  - interfaces. → api.interfaces."
find . -name "*.py" -type f \
    -not -path "./.venv/*" \
    -not -path "./__pycache__/*" \
    -not -path "./.archive/*" \
    -not -path "./$backup_dir/*" \
    -not -path "./api/interfaces/*" \
    -exec sed -i 's/^from interfaces\./from api.interfaces./g' {} \;

echo "✅ Migrations applied"
echo ""

# Validate Python syntax
echo "🔍 Validating Python syntax..."
python_files=$(find . -name "*.py" -type f \
    -not -path "./.venv/*" \
    -not -path "./__pycache__/*" \
    -not -path "./.archive/*" \
    -not -path "./$backup_dir/*")

syntax_errors=0
for file in $python_files; do
    if ! python3 -m py_compile "$file" 2>/dev/null; then
        echo "❌ Syntax error in: $file"
        syntax_errors=$((syntax_errors + 1))
    fi
done

if [ $syntax_errors -gt 0 ]; then
    echo ""
    echo "❌ $syntax_errors files with syntax errors!"
    echo "Rollback: cp -r $backup_dir/* ."
    exit 1
fi

echo "✅ All Python files have valid syntax"
echo ""

# Show summary
echo "📊 Migration Summary:"
echo ""
echo "Files modified:"
git diff --name-only | wc -l

echo ""
echo "✅ Migration complete!"
echo ""
echo "Next steps:"
echo "  1. Review changes: git diff"
echo "  2. Run tests: make api-test"
echo "  3. If OK, commit: git add -A && git commit"
echo "  4. If problems, rollback: cp -r $backup_dir/* . && git checkout ."
