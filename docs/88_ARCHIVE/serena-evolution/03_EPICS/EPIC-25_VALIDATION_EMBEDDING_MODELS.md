# Validation - Distinction Modèles Embeddings (EPIC-25)

**Date**: 2025-11-01
**Objectif**: Vérifier que la distinction TEXT vs CODE est claire dans toute la documentation EPIC-25
**Status**: ✅ VALIDÉ

---

## ✅ Configuration Vérifiée (.env.example)

### TEXT Model (Conversations)
```bash
EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5
```
- **Dimensions**: 768
- **Usage**: Conversations, docstrings, comments, texte général
- **Stats**: ~7,972 conversations auto-indexées
- **Performance**: ~10ms search avg
- **License**: Apache 2.0
- **MTEB Score**: ~65

### CODE Model (Code Chunks)
```bash
CODE_EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-code
```
- **Dimensions**: 768
- **Usage**: Source code, functions, classes (code chunks)
- **Stats**: ~125,000 code chunks indexés
- **Performance**: ~12ms search avg
- **License**: Apache 2.0
- **Spécialisation**: Code similarity and search

### Shared Config
```bash
EMBEDDING_DIMENSION=768
```
- Les 2 modèles utilisent la même dimension (768)
- HNSW index avec paramètres partagés (m=16, ef_construction=200)

---

## ✅ Documentation EPIC-25 - Checklist

### EPIC-25_README.md

**Ligne 30** - Problème Actuel:
```markdown
- ❌ **2 modèles embeddings** (TEXT: nomic-text-v1.5 | CODE: jina-code-v2)
  → pas de visibilité séparée
```
✅ Distinction claire dès l'introduction

**Ligne 116** - Story 25.4:
```markdown
| 25.4 | Embeddings Overview Cards | 3 pts | 🔴 PENDING |
```
✅ Story dédiée pour afficher les 2 modèles séparément

**Ligne 123** - Deliverables Phase 2:
```markdown
- ✅ 2 embedding cards (conversations + code stats)
```
✅ Clarification des 2 types de cards

**Ligne 422** - Acceptance Criteria:
```markdown
- [ ] 2 types embeddings visibles (conversations + code)
```
✅ Critère d'acceptance explicite

---

### EPIC-25_UI_UX_REFONTE_ULTRATHINK.md

**Section "Embeddings (2 modèles distincts)"** (lignes 55-73):
```markdown
### Embeddings (2 modèles distincts)

1. **EMBEDDING_MODEL** = `nomic-ai/nomic-embed-text-v1.5` (768 dims)
   - **Usage**: Conversations, docstrings, comments, texte général
   - **Stats**: ~7,972 conversations auto-indexées

2. **CODE_EMBEDDING_MODEL** = `jinaai/jina-embeddings-v2-base-code` (768 dims)
   - **Usage**: Source code, functions, classes
   - **Stats**: ~125,000 code chunks indexés
```
✅ Section dédiée avec distinction claire

**Wireframe Dashboard** (lignes 127-135):
```
│ 🔍 Embeddings Overview (2 Modèles Distincts)            │
│ ┌────────────────────────┬────────────────────────────┐ │
│ │ 💬 TEXT (Conversations)│ 💻 CODE (Code Chunks)      │ │
│ │ 7,972 embeddings       │ 125,000 embeddings         │ │
│ │ nomic-text-v1.5        │ jina-code-v2               │ │
```
✅ Design visuel séparant les 2 modèles

**Story 25.4** (lignes 176-193):
```markdown
#### Story 25.4: Embeddings Overview Cards (3 pts)

**2 cards séparées**:

**Card 1: TEXT Embeddings (Conversations)**:
- Model: nomic-ai/nomic-embed-text-v1.5
- Total: 7,972 embeddings
- Dimension: 768
- Type: Conversations, docstrings

**Card 2: CODE Embeddings (Code Chunks)**:
- Model: jinaai/jina-embeddings-v2-base-code
- Total: 125,000 embeddings
- Dimension: 768
- Type: Functions, classes, source code
```
✅ Spécification détaillée des 2 cards

**Settings Page** (lignes 580-599):
```markdown
#### D. Embedding Settings (2 Modèles)

**TEXT Model (Conversations)**:
- Model: nomic-ai/nomic-embed-text-v1.5
- Dimension: 768
- Usage: Conversations, docstrings, comments

**CODE Model (Code Chunks)**:
- Model: jinaai/jina-embeddings-v2-base-code
- Dimension: 768
- Usage: Source code, functions, classes

**HNSW Parameters** (shared):
- m: 16
- ef_construction: 200
- ef_search: 100
```
✅ Configuration séparée dans Settings

---

## 🎯 Points de Visibilité Garantis

### Dashboard (Story 25.4)
**2 cards distincts**:
- 💬 **TEXT Card**: Conversations, docstrings, comments
- 💻 **CODE Card**: Source code, functions, classes

**Métriques par card**:
- Model name
- Total embeddings count
- Dimension
- Index type (HNSW)
- Avg query time
- Dernière indexation

### Recherche Unifiée (Story 25.9-25.11)
**Faceted filters** permettent de:
- Filtrer par type: Conversations | Code | Functions
- Voir source de l'embedding (TEXT model vs CODE model)
- Comparer résultats des 2 modèles

### Settings (Story 25.21)
**Section Embeddings**:
- Configuration TEXT model (read-only)
- Configuration CODE model (read-only)
- HNSW params (tunable, shared)

---

## 📊 Comparaison Modèles

| Aspect | TEXT (nomic-text-v1.5) | CODE (jina-code-v2) |
|--------|------------------------|---------------------|
| **Usage** | Conversations, docstrings | Code chunks, functions |
| **Count** | ~7,972 embeddings | ~125,000 embeddings |
| **Dimension** | 768 | 768 |
| **Avg Query Time** | ~10ms | ~12ms |
| **Specialization** | General text, MTEB ~65 | Code similarity |
| **Index** | HNSW (m=16, ef=200) | HNSW (m=16, ef=200) |
| **License** | Apache 2.0 | Apache 2.0 |
| **Local** | ✅ 100% local | ✅ 100% local |

---

## ✅ Backend Endpoints à Créer

### Story 25.2 - Dashboard Backend API

**GET `/api/v1/dashboard/embeddings/text`**:
```json
{
  "model": "nomic-ai/nomic-embed-text-v1.5",
  "total_embeddings": 7972,
  "dimension": 768,
  "index_type": "hnsw",
  "avg_query_time_ms": 10.3,
  "last_indexed": "2025-11-01T12:34:56Z",
  "usage": "conversations, docstrings, comments"
}
```

**GET `/api/v1/dashboard/embeddings/code`**:
```json
{
  "model": "jinaai/jina-embeddings-v2-base-code",
  "total_embeddings": 125000,
  "dimension": 768,
  "index_type": "hnsw",
  "avg_query_time_ms": 12.1,
  "last_indexed": "2025-11-01T12:34:56Z",
  "usage": "source code, functions, classes"
}
```

---

## ✅ Tables PostgreSQL

### Conversations (TEXT embeddings)
```sql
SELECT
  'conversations' as table_name,
  COUNT(*) as total_embeddings,
  pg_size_pretty(pg_total_relation_size('conversations')) as table_size
FROM conversations;
```

### Code Chunks (CODE embeddings)
```sql
SELECT
  'code_chunks' as table_name,
  COUNT(*) as total_embeddings,
  pg_size_pretty(pg_total_relation_size('code_chunks')) as table_size
FROM code_chunks;
```

### HNSW Indexes
```sql
-- TEXT embeddings index
SELECT * FROM pg_indexes WHERE indexname = 'conversations_embedding_hnsw_idx';

-- CODE embeddings index
SELECT * FROM pg_indexes WHERE indexname = 'code_chunks_embedding_hnsw_idx';
```

---

## 🎨 UI Mockup - Dashboard Cards

```
┌─────────────────────────────────────────────────────────────────┐
│                    📊 Embeddings Overview                       │
├─────────────────────────────────┬───────────────────────────────┤
│ 💬 TEXT Embeddings              │ 💻 CODE Embeddings            │
│ (Conversations)                 │ (Code Chunks)                 │
│                                 │                               │
│ Model: nomic-text-v1.5          │ Model: jina-code-v2           │
│ Total: 7,972                    │ Total: 125,000                │
│ Dimension: 768                  │ Dimension: 768                │
│ Index: HNSW (m=16)              │ Index: HNSW (m=16)            │
│ Avg Query: 10ms                 │ Avg Query: 12ms               │
│ Last Indexed: 1 hour ago        │ Last Indexed: 2 hours ago     │
│                                 │                               │
│ [View Details]                  │ [View Details]                │
└─────────────────────────────────┴───────────────────────────────┘
```

---

## ✅ Conclusion

**Distinction TEXT vs CODE**:
- ✅ Documentée dans EPIC-25_README.md (4 mentions)
- ✅ Documentée dans EPIC-25_UI_UX_REFONTE_ULTRATHINK.md (5 sections)
- ✅ Vérifiée dans .env.example (configuration réelle)
- ✅ Spécifiée dans Story 25.4 (Embeddings Overview Cards)
- ✅ Intégrée dans wireframes et mockups
- ✅ Endpoint API design séparé
- ✅ Critères d'acceptance EPIC

**Aucune confusion possible**: Les 2 modèles sont clairement séparés dans toute la documentation.

---

**Status**: ✅ VALIDATION COMPLÈTE
**Next Step**: User review + Tech stack decision (React vs HTMX)
**Dernière mise à jour**: 2025-11-01
