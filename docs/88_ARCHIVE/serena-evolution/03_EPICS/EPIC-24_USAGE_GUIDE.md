# EPIC-24: Usage Guide - Auto-Save Conversations

**Guide pratique** pour utiliser, vérifier, et débugger le système d'auto-sauvegarde des conversations Claude Code.

---

## 🚀 Quick Start

### Prérequis
```bash
# 1. Docker containers running
docker compose ps
# api, db, redis doivent être "Up (healthy)"

# 2. MCP configured
cat .mcp.json | jq '.mcpServers.mnemolite'
# Doit afficher configuration serveur

# 3. Hooks enabled
cat .claude/settings.local.json | jq '.disableAllHooks'
# Doit afficher: false
```

### Vérification Rapide
```bash
# Compter conversations sauvegardées
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT COUNT(*) as total_conversations
FROM memories
WHERE memory_type = 'conversation' AND deleted_at IS NULL;"
```

**Attendu**: Un nombre croissant à chaque session

---

## 📋 Commandes Utiles

### 1. Lister Toutes les Conversations

```bash
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT
    ROW_NUMBER() OVER (ORDER BY created_at DESC) as num,
    LEFT(id::text, 8) as id,
    LEFT(title, 60) as title,
    created_at AT TIME ZONE 'Europe/Paris' as created,
    LENGTH(content) as chars
FROM memories
WHERE memory_type = 'conversation' AND deleted_at IS NULL
ORDER BY created_at DESC
LIMIT 10;"
```

**Output Exemple**:
```
 num | id       | title                         | created             | chars
-----+----------+-------------------------------+---------------------+-------
   1 | 5563e90c | Conv: Double check système... | 2025-10-28 15:08:54 | 186
   2 | beb657cb | Conv: Vérification hook...    | 2025-10-28 15:05:59 | 192
   3 | 63125eca | Conv: Test hook fonctionne?   | 2025-10-28 13:37:16 | 254
```

---

### 2. Lire une Conversation Complète

```bash
# Par ID
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT
    title,
    content,
    tags,
    author,
    created_at
FROM memories
WHERE id = '63125eca-b9b3-42dd-9635-c0dd951ade36';"
```

---

### 3. Rechercher par Tag

```bash
# Conversations d'une session spécifique
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT
    title,
    created_at AT TIME ZONE 'Europe/Paris' as created
FROM memories
WHERE memory_type = 'conversation'
  AND tags @> ARRAY['session:20251028_test']::text[]
  AND deleted_at IS NULL
ORDER BY created_at DESC;"
```

---

### 4. Rechercher par Date

```bash
# Conversations d'aujourd'hui
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT
    COUNT(*) as today_count,
    SUM(LENGTH(content)) as total_chars
FROM memories
WHERE memory_type = 'conversation'
  AND DATE(created_at) = CURRENT_DATE
  AND deleted_at IS NULL;"
```

---

### 5. Statistiques Générales

```bash
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embeddings,
    COUNT(*) FILTER (WHERE tags @> ARRAY['auto-saved']) as auto_saved,
    AVG(LENGTH(content))::int as avg_chars,
    MIN(created_at)::date as first_conv,
    MAX(created_at)::date as last_conv
FROM memories
WHERE memory_type = 'conversation' AND deleted_at IS NULL;"
```

---

## 🔍 Recherche Sémantique

### Recherche Python (dans container)

```bash
docker compose exec -T api python3 <<'EOF'
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from db.repositories.memory_repository import MemoryRepository
from services.embedding_service import MockEmbeddingService
from mnemo_mcp.models.memory_models import MemoryFilters, MemoryType

async def search():
    # Setup
    url = "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite"
    engine = create_async_engine(url, pool_size=2)
    repo = MemoryRepository(engine)
    emb_svc = MockEmbeddingService(model_name="mock", dimension=768)

    # Query
    query = "bugs corrigés database SQL"
    query_emb = await emb_svc.generate_embedding(query)

    # Search
    memories, total = await repo.search_by_vector(
        vector=query_emb,
        filters=MemoryFilters(memory_type=MemoryType.CONVERSATION),
        limit=5
    )

    # Results
    print(f"\nTrouvé {total} résultats pour: '{query}'\n")
    for i, mem in enumerate(memories, 1):
        print(f"{i}. {mem.title}")
        print(f"   Created: {mem.created_at}")
        print(f"   Tags: {mem.tags[:3]}")
        print()

    await engine.dispose()

asyncio.run(search())
EOF
```

---

### Recherche SQL Brute (Full-Text)

```bash
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT
    title,
    ts_rank(
        to_tsvector('french', title || ' ' || content),
        plainto_tsquery('french', 'hook sauvegarde')
    ) as rank
FROM memories
WHERE memory_type = 'conversation'
  AND to_tsvector('french', title || ' ' || content) @@ plainto_tsquery('french', 'hook sauvegarde')
  AND deleted_at IS NULL
ORDER BY rank DESC
LIMIT 5;"
```

---

## 🛠️ Troubleshooting

### Problème 1: Aucune Conversation Sauvegardée

**Symptômes**:
```bash
SELECT COUNT(*) FROM memories WHERE memory_type = 'conversation';
# Output: 0
```

**Diagnostics**:

```bash
# 1. Vérifier hook configuré
cat .claude/settings.local.json | jq '.hooks.Stop'
# Doit afficher configuration

# 2. Vérifier hooks activés
cat .claude/settings.local.json | jq '.disableAllHooks'
# Doit afficher: false

# 3. Vérifier fichiers hook montés
docker compose exec -T api ls -la /app/.claude/hooks/Stop/
# Doit lister: auto-save.sh, save-direct.py

# 4. Test manuel hook
docker compose exec -T api python3 /app/.claude/hooks/Stop/save-direct.py \
  "Test user" "Test assistant" "test_session" 2>&1 | tail -5
# Doit afficher: ✓ Saved: <uuid>
```

**Solutions Communes**:
- `disableAllHooks: true` → Changer à `false`
- Volume mount manquant → Ajouter `./.claude:/app/.claude:ro` dans docker-compose.yml
- Container pas recréé → `docker compose up -d api`

---

### Problème 2: Hook Échoue Silencieusement

**Symptômes**:
- Hook configuré ✅
- Fichiers montés ✅
- Mais aucune conversation sauvegardée ❌

**Diagnostics**:

```bash
# 1. Vérifier logs API
docker compose logs api --tail 50 | grep -i "memory\|error"

# 2. Tester script manuellement avec logs verbeux
docker compose exec -T api bash -x /app/.claude/hooks/Stop/save-direct.py \
  "Test" "Response" "session" 2>&1
```

**Erreurs Communes**:
```
# Error: ModuleNotFoundError
# Solution: pip install dans container
docker compose exec -T api pip install sqlalchemy asyncpg

# Error: ConnectionRefusedError
# Solution: Vérifier PostgreSQL up
docker compose ps db

# Error: Permission denied
# Solution: chmod +x scripts
chmod +x .claude/hooks/Stop/*.sh .claude/hooks/Stop/*.py
```

---

### Problème 3: Embeddings Manquants

**Symptômes**:
```sql
SELECT COUNT(*) FROM memories WHERE embedding IS NULL;
# Output: > 0
```

**Diagnostics**:

```bash
# Vérifier EmbeddingService
docker compose exec -T api python3 <<EOF
from services.embedding_service import MockEmbeddingService
emb = MockEmbeddingService(model_name="mock", dimension=768)
test = emb.generate_embedding("test")
print(f"Embedding dim: {len(test)}")
EOF
# Doit afficher: 768
```

**Solution**:
```bash
# Régénérer embeddings manquants
docker compose exec -T api python3 <<EOF
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from db.repositories.memory_repository import MemoryRepository
from services.embedding_service import MockEmbeddingService

async def fix():
    url = "postgresql+asyncpg://mnemo:mnemopass@db:5432/mnemolite"
    engine = create_async_engine(url)
    repo = MemoryRepository(engine)
    emb_svc = MockEmbeddingService(model_name="mock", dimension=768)

    # Get memories without embeddings
    from sqlalchemy import text
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT id, title, content
            FROM memories
            WHERE embedding IS NULL AND deleted_at IS NULL
        """))
        for row in result:
            emb = await emb_svc.generate_embedding(f"{row.title}\n{row.content}")
            await conn.execute(text("""
                UPDATE memories
                SET embedding = :emb::vector
                WHERE id = :id
            """), {"emb": f"[{','.join(map(str, emb))}]", "id": row.id})
            print(f"Fixed: {row.id}")

    await engine.dispose()

asyncio.run(fix())
EOF
```

---

### Problème 4: Performance Dégradée

**Symptômes**:
- Claude Code lent après chaque réponse
- Timeout hooks (>5s)

**Diagnostics**:

```bash
# Mesurer temps sauvegarde
time docker compose exec -T api python3 /app/.claude/hooks/Stop/save-direct.py \
  "Test" "Response" "session" 2>&1 | grep "Saved"

# Doit être < 100ms
```

**Solutions**:
```bash
# 1. Optimiser pool PostgreSQL
# docker-compose.yml
environment:
  DATABASE_URL: "...?pool_size=2&max_overflow=5"

# 2. Désactiver echo SQL
# save-direct.py
engine = create_async_engine(url, echo=False)  # Pas echo=True

# 3. Reduce embedding dimension (si vrai embeddings)
# Config: 768 → 384 dimensions
```

---

## 🔧 Configuration Avancée

### Custom Hook Behavior

Éditer `.claude/hooks/Stop/auto-save.sh`:

```bash
# Skip si message trop court
if [ ${#LAST_USER} -lt 10 ]; then
  echo '{"continue": true}' >&2
  exit 0
fi

# Custom tags
TAGS="auto-saved,session:$SESSION_ID,user:$USER,project:mnemolite"

# Custom memory type
MEMORY_TYPE="conversation"  # ou "note", "decision", etc.
```

---

### Disable Auto-Save Temporairement

```bash
# Méthode 1: Disable tous hooks
# .claude/settings.local.json
{
  "disableAllHooks": true
}

# Méthode 2: Disable hook Stop uniquement
{
  "hooks": {
    "Stop": []  # Empty array
  }
}

# Méthode 3: Matcher conditionnel
{
  "hooks": {
    "Stop": [{
      "matcher": "*.py",  # Seulement fichiers Python
      "hooks": [...]
    }]
  }
}
```

---

### Sauvegarder dans Projet Différent

Modifier `.claude/hooks/Stop/save-direct.py`:

```python
# Add project_id parameter
result = await tool.execute(
    ctx=ctx,
    title=title,
    content=content,
    memory_type="conversation",
    tags=tags,
    author="AutoSave",
    project_id="550e8400-e29b-41d4-a716-446655440000"  # ← Custom UUID
)
```

---

## 📊 Monitoring

### Daily Report Script

```bash
#!/bin/bash
# daily_report.sh

docker compose exec -T db psql -U mnemo -d mnemolite <<SQL
SELECT
  'Conversations Today' as metric,
  COUNT(*)::text as value
FROM memories
WHERE memory_type = 'conversation'
  AND DATE(created_at) = CURRENT_DATE
  AND deleted_at IS NULL

UNION ALL

SELECT
  'Total Characters',
  SUM(LENGTH(content))::text
FROM memories
WHERE memory_type = 'conversation'
  AND DATE(created_at) = CURRENT_DATE
  AND deleted_at IS NULL

UNION ALL

SELECT
  'With Embeddings',
  COUNT(*) FILTER (WHERE embedding IS NOT NULL)::text
FROM memories
WHERE memory_type = 'conversation'
  AND DATE(created_at) = CURRENT_DATE
  AND deleted_at IS NULL;
SQL
```

**Cron**:
```cron
0 23 * * * /path/to/daily_report.sh >> /var/log/mnemolite/daily_report.log
```

---

### Alertes

```bash
#!/bin/bash
# check_autosave.sh

RECENT=$(docker compose exec -T db psql -U mnemo -d mnemolite -t -c "
SELECT COUNT(*)
FROM memories
WHERE memory_type = 'conversation'
  AND created_at > NOW() - INTERVAL '1 hour'
  AND deleted_at IS NULL;")

if [ "$RECENT" -lt 1 ]; then
  echo "⚠️  ALERT: No conversations saved in last hour"
  # Send notification (email, Slack, etc.)
fi
```

---

## 🧪 Tests

### Test End-to-End

```bash
# 1. Ouvrir nouvelle session Claude Code
# 2. Taper: "Test auto-save: Est-ce que ça fonctionne?"
# 3. Attendre réponse Claude
# 4. Chercher conversation:

docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT
  title,
  created_at AT TIME ZONE 'Europe/Paris'
FROM memories
WHERE memory_type = 'conversation'
  AND created_at > NOW() - INTERVAL '5 minutes'
ORDER BY created_at DESC
LIMIT 1;"

# Doit afficher la conversation actuelle
```

---

## 📚 Exemples Use Cases

### 1. Retrouver une Solution Bug

```bash
# Recherche conversations mentionnant "bug fix" + "database"
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT
  title,
  LEFT(content, 200) as preview
FROM memories
WHERE memory_type = 'conversation'
  AND (content ILIKE '%bug%' OR content ILIKE '%fix%')
  AND content ILIKE '%database%'
  AND deleted_at IS NULL
ORDER BY created_at DESC
LIMIT 3;"
```

---

### 2. Tracer Décision Technique

```bash
# Chercher conversations avec tag "decision"
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT
  title,
  tags,
  created_at::date
FROM memories
WHERE memory_type = 'conversation'
  AND tags @> ARRAY['decision']::text[]
ORDER BY created_at DESC;"
```

---

### 3. Statistiques Productivité

```bash
# Conversations par jour (7 derniers jours)
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT
  DATE(created_at) as date,
  COUNT(*) as conversations,
  SUM(LENGTH(content)) as total_chars,
  AVG(LENGTH(content))::int as avg_chars
FROM memories
WHERE memory_type = 'conversation'
  AND created_at > NOW() - INTERVAL '7 days'
  AND deleted_at IS NULL
GROUP BY DATE(created_at)
ORDER BY date DESC;"
```

---

## 🔗 Références Rapides

### URLs Utiles
- Claude Code Hooks: https://docs.claude.com/en/docs/claude-code/hooks
- MCP Spec: https://modelcontextprotocol.io/
- pgvector: https://github.com/pgvector/pgvector

### Fichiers Clés
- Hook script: `.claude/hooks/Stop/auto-save.sh`
- Python wrapper: `.claude/hooks/Stop/save-direct.py`
- Configuration: `.claude/settings.local.json`
- Docker volumes: `docker-compose.yml:113`

### Commandes Essentielles
```bash
# Status système
docker compose ps

# Logs hooks
docker compose logs api --tail 100 | grep -i "memory\|hook"

# Test manuel
docker compose exec -T api python3 /app/.claude/hooks/Stop/save-direct.py \
  "Test" "Response" "session"

# Compter conversations
docker compose exec -T db psql -U mnemo -d mnemolite -c \
  "SELECT COUNT(*) FROM memories WHERE memory_type='conversation';"
```

---

## ❓ FAQ

**Q: Les conversations sont-elles sauvegardées en temps réel?**
R: Non, elles sont sauvegardées à la FIN de chaque réponse de Claude (hook Stop).

**Q: Puis-je désactiver l'auto-save temporairement?**
R: Oui, mettre `"disableAllHooks": true` dans `.claude/settings.local.json`.

**Q: Les embeddings sont-ils générés automatiquement?**
R: Oui, MockEmbeddingService génère des embeddings 768D pour chaque conversation.

**Q: Combien de temps les conversations sont-elles conservées?**
R: Indéfiniment, sauf si supprimées manuellement (soft delete avec `deleted_at`).

**Q: Puis-je chercher dans les conversations depuis Claude Code?**
R: Pas directement, mais UserPromptSubmit hook peut injecter contexte pertinent (à implémenter).

**Q: Performance impact sur Claude Code?**
R: Minimal, ~30-40ms par sauvegarde (timeout: 5000ms).

---

**Guide Version**: 1.0.0
**Last Updated**: 2025-10-28
**Maintainer**: MnemoLite Team
