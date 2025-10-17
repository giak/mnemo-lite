# MnemoLite Scripts

Scripts utilitaires pour MnemoLite v2.0.0

## 📁 Structure

```
scripts/
├── performance/        # Performance & optimization (EPIC-08)
│   ├── apply_optimizations.sh       # Apply/rollback optimizations (4 modes)
│   ├── fix_embedding_performance.sh # Fix embedding model loading
│   └── verify_optimizations.py      # Verify optimizations work
│
├── testing/            # Test utilities (EPIC-08)
│   ├── test_application.sh          # Quick testing (quick/full/load)
│   ├── generate_test_data.py        # Generate test events (768D embeddings)
│   └── fake_event_poster.py         # Post fake events to API
│
├── database/           # Database utilities
│   └── init_test_db.sql             # Initialize test database
│
├── benchmarks/         # Performance benchmarking
│   └── (benchmark scripts)
│
└── archive/            # Historical scripts (Q1-Q2 2025)
    └── (old migration/audit scripts)
```

## 🚀 Scripts Actifs (v2.0.0)

### Performance (EPIC-08)

**apply_optimizations.sh** - Manage performance optimizations
```bash
# Test current performance
scripts/performance/apply_optimizations.sh test

# Apply optimizations
scripts/performance/apply_optimizations.sh apply

# Benchmark (100 req/s)
scripts/performance/apply_optimizations.sh benchmark

# Rollback (10-second recovery)
scripts/performance/apply_optimizations.sh rollback
```

**verify_optimizations.py** - Verify optimizations
```bash
python scripts/performance/verify_optimizations.py
```

### Testing (EPIC-08)

**test_application.sh** - Quick testing suite
```bash
# Quick test (health + events)
scripts/testing/test_application.sh quick

# Full test suite
scripts/testing/test_application.sh full

# Load testing
scripts/testing/test_application.sh load
```

**generate_test_data.py** - Generate test data
```bash
# Generate 100 test events (768D embeddings)
docker exec mnemo-api python scripts/testing/generate_test_data.py
```

**fake_event_poster.py** - Post fake events
```bash
# Post fake events to API
docker exec mnemo-api python scripts/testing/fake_event_poster.py
```

### Database

**init_test_db.sql** - Initialize test database
```bash
docker exec mnemo-postgres psql -U mnemo -d mnemolite_test -f /app/scripts/database/init_test_db.sql
```

## 📦 Scripts Archivés

Scripts historiques de la phase initiale (Q1-Q2 2025) conservés pour référence:

- `cleanup_phase1.sh` - Migration structure api/ (déjà complétée)
- `migrate_imports.sh` - Migration imports (déjà complétée)
- `standardize_imports.py` - Standardisation imports (déjà complétée)
- `audit_story3_*.py` - Audits EPIC-06 Story 3 (déjà complétés)
- `validate_story3_metadata.py` - Validation EPIC-06 (déjà complétée)

**Note**: Ces scripts ne sont plus nécessaires pour v2.0.0 mais sont conservés pour historique.

## 🔧 Maintenance

### Ajouter un nouveau script
1. Placer dans le dossier approprié (performance/testing/database)
2. Rendre exécutable: `chmod +x scripts/<category>/<script>.sh`
3. Documenter dans ce README

### Archiver un script obsolète
```bash
mv scripts/<category>/<script> scripts/archive/
```

---

**Last Updated**: 2025-10-17
**Version**: v2.0.0 (EPIC-08 Complete)
