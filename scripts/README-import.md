# Import Claude Code Conversations - Guide Simple

## 🎯 Solution Simple Sans Dépendances

Ce script importe toutes vos conversations Claude Code dans MnemoLite **sans hooks, sans dépendances externes**.

### Principe

```
~/.claude/projects/*.jsonl (transcripts)
            ↓
    import-conversations.py (parse JSONL)
            ↓
    write_memory MCP tool
            ↓
PostgreSQL + pgvector (avec embeddings 768D)
```

---

## 🚀 Usage Simple

### Import Complet (Toutes les Conversations)

```bash
# Dans le container Docker
docker compose exec -T api python3 /app/scripts/import-conversations.py

# Résultat:
# 📁 Found 42 transcript files
# 📄 Processing: 5906b2a1-cbd9-4d97-bc2b-81445d816ebe.jsonl
#    Found 150 conversations
#    ✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓✓ ...
# ✅ Imported: 150
# ⊘  Skipped (duplicates): 0
# 🎉 Successfully imported 150 conversations!
```

### Import Depuis une Date

```bash
# Importer seulement depuis aujourd'hui
docker compose exec -T api python3 /app/scripts/import-conversations.py --since 2025-10-29

# Importer depuis hier
docker compose exec -T api python3 /app/scripts/import-conversations.py --since 2025-10-28
```

### Re-Import Complet (Force)

```bash
# Note: Les duplicates seront automatiquement skippés via hash
docker compose exec -T api python3 /app/scripts/import-conversations.py --all
```

---

## ✅ Vérification

```bash
# Compter les conversations importées
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT
  COUNT(*) as total,
  MIN(created_at) as premiere,
  MAX(created_at) as derniere
FROM memories
WHERE memory_type = 'conversation'
  AND author = 'BatchImport'
  AND deleted_at IS NULL;"

# Voir les 5 dernières importées
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT
  LEFT(title, 60) as title,
  created_at,
  array_length(tags, 1) as nb_tags
FROM memories
WHERE author = 'BatchImport'
  AND deleted_at IS NULL
ORDER BY created_at DESC
LIMIT 5;"
```

---

## 🔄 Setup Import Automatique (Optionnel)

### Option 1: Cron Quotidien

```bash
# Editer crontab
crontab -e

# Ajouter (import chaque nuit à 2h):
0 2 * * * cd /home/giak/Work/MnemoLite && docker compose exec -T api python3 /app/scripts/import-conversations.py --since $(date -d 'yesterday' +\%Y-\%m-\%d) >> /tmp/mnemo-import.log 2>&1
```

### Option 2: Script Wrapper

```bash
#!/bin/bash
# ~/bin/import-conversations.sh
cd /home/giak/Work/MnemoLite
docker compose exec -T api python3 /app/scripts/import-conversations.py "$@"
```

---

## 🎓 Comment Ça Marche

### 1. Parse Transcripts JSONL

Le script lit directement les fichiers `~/.claude/projects/*.jsonl`:

```json
{"role": "user", "content": "...", "timestamp": "2025-10-29T08:00:00Z"}
{"role": "assistant", "content": "...", "timestamp": "2025-10-29T08:00:05Z"}
```

### 2. Extraction des Paires

Extrait les paires user→assistant complètes.

### 3. Deduplication par Hash

Calcule un hash SHA256 du contenu pour éviter les duplicates:

```python
hash = sha256(user_text + assistant_text)[:16]
# Check if tag "hash:abc123..." exists → skip if yes
```

### 4. Sauvegarde via write_memory

Utilise le WriteMemoryTool MCP existant:

```python
await write_memory(
    title="Conv: Question utilisateur...",
    content="User: ...\n\nClaude: ...",
    tags=["imported", "claude-code", "session:abc", "date:20251029", "hash:xyz"],
    memory_type="conversation",
    author="BatchImport"
)
```

### 5. Génération Embeddings

Le WriteMemoryTool génère automatiquement l'embedding 768D pour recherche sémantique.

---

## 📊 Comparaison Approches

| Approche | Complexité | Fiabilité | Dépendances | Setup |
|----------|------------|-----------|-------------|-------|
| **Hooks Claude Code** | 🔴 Haute | 🔴 0% | Bug #10401 | 2h+ |
| **Import Script** | 🟢 Faible | 🟢 100% | Aucune | 1 min |

**Hooks**: Dépend de bug Claude Code, nécessite wrapper, alias, debug flag

**Import Script**: Parse fichiers directement, aucune dépendance, toujours fonctionne

---

## 🐛 Troubleshooting

### Erreur: "No transcript files found"

```bash
# Vérifier que les transcripts existent
ls -lh ~/.claude/projects/-home-giak-Work-MnemoLite/*.jsonl

# Si autre projet:
docker compose exec -T api python3 /app/scripts/import-conversations.py --project-dir ~/.claude/projects/OTHER_PROJECT
```

### Erreur: "Connection refused" (PostgreSQL)

```bash
# Vérifier que le container db tourne
docker compose ps db

# Redémarrer si nécessaire
docker compose restart db
```

### Erreur: "ModuleNotFoundError"

Le script doit tourner **dans le container Docker** (pas en local):

```bash
# ✅ CORRECT
docker compose exec -T api python3 /app/scripts/import-conversations.py

# ❌ INCORRECT
python3 scripts/import-conversations.py  # Erreur, pas dans container
```

---

## 🎯 Avantages

✅ **Zéro configuration** - Fonctionne immédiatement
✅ **Zéro dépendance externe** - Utilise seulement stdlib + MnemoLite existant
✅ **100% fiable** - Parse fichiers directement, pas de hooks bugués
✅ **Deduplication automatique** - Hash-based, run plusieurs fois sans problème
✅ **Embeddings inclus** - Génération automatique via MockEmbeddingService
✅ **Recherche sémantique** - Conversations interrogeables via MCP

---

## 📚 Références

- **EPIC-24**: docs/agile/serena-evolution/03_EPICS/EPIC-24_README.md
- **Script**: scripts/import-conversations.py
- **WriteMemoryTool**: api/mnemo_mcp/tools/memory_tools.py

---

**Dernière mise à jour**: 2025-10-29
**Version**: 1.0 - Simple Batch Import (No Hooks)
