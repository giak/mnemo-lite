# EPIC-28: Frontend Hardening & Completeness

**Status**: ✅ COMPLETE | **Created**: 2026-04-01 | **Completed**: 2026-04-02

---

## Context

Le front-end MnemoLite est fonctionnel mais présente des incohérences et des lacunes :
- 13 fichiers avec URL API hardcodée (`localhost:8001`)
- Page Logs.vue vide (placeholder)
- Projects.vue avec style non harmonisé (emojis vs SCADA)
- 16 tests MCP pré-existants en échec
- Cross-encoder reranking désactivé (bug accelerate)
- Migration sys:trace non appliquée en DB
- Frontend non inclus dans Docker Compose

---

## Stories

### Story 28.1: Centraliser l'URL API (Vite env vars)
**Priority**: P0 | **Effort**: 3 pts | **Value**: High

Remplacer les 13+ références hardcodées `localhost:8001` par des variables d'environnement Vite.

**Fichiers à modifier** (13 fichiers) :
- `frontend/src/composables/useProjects.ts`
- `frontend/src/composables/useDashboard.ts`
- `frontend/src/composables/useBrain.ts`
- `frontend/src/composables/useMemories.ts`
- `frontend/src/composables/useExpanse.ts`
- `frontend/src/composables/useExpanseMemory.ts`
- `frontend/src/composables/useMemorySearch.ts`
- `frontend/src/composables/useCodeSearch.ts`
- `frontend/src/composables/useCodeGraph.ts`
- `frontend/src/pages/ExpanseMemory.vue`
- `frontend/src/components/ConversationDetailModal.vue`
- `frontend/src/components/ExpanseTagModal.vue`
- `frontend/src/components/AutoSaveStatus.vue`

**Fichiers à créer** :
- `frontend/src/config/api.ts` — Configuration centralisée
- `frontend/.env` — Valeurs par défaut
- `frontend/.env.development` — Overrides dev

**Implémentation** :
```typescript
// frontend/src/config/api.ts
const VITE_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001'
export const API_BASE = `${VITE_API_URL}/api/v1`
```

---

### Story 28.2: Harmoniser Projects.vue au style SCADA
**Priority**: P1 | **Effort**: 2 pts | **Value**: Medium

Remplacer l'UI basée sur les emojis par le design system SCADA utilisé partout ailleurs.

**Fichiers à modifier** :
- `frontend/src/pages/Projects.vue`

**Changements** :
- `📦 Projects` → `<span class="scada-led scada-led-cyan"></span>` + `PROJECTS`
- `🎯` → LED SCADA pour projet actif
- `🔄 REFRESH` / `⏳ LOADING...` → `scada-btn scada-btn-primary`
- `⚠️ DELETE` → panneau danger SCADA
- Wrap header en layout SCADA flex (comme Dashboard.vue)
- Utiliser `scada-panel`, `scada-label`, `scada-data` partout

---

### Story 28.3: Implémenter Logs.vue
**Priority**: P2 | **Effort**: 3 pts | **Value**: Medium | **Depends on**: 28.1

Remplacer le placeholder par un viewer de logs fonctionnel.

**Option A — Iframe OpenObserve** (simple, 1 pt) :
- Intégrer OpenObserve (`localhost:5080`) dans un iframe
- Lien pour ouvrir dans un nouvel onglet
- Wrapper style SCADA

**Option B — API-backed** (complet, 3 pts) :
- Endpoint backend `/api/v1/logs` (OpenObserve API ou fichiers)
- Viewer paginé avec filtres (level, source, time range)
- Auto-refresh style SCADA

**Fichiers à modifier** :
- `frontend/src/pages/Logs.vue`

**Fichiers à créer** (Option B) :
- `api/routes/logs.py`
- `frontend/src/composables/useLogs.ts`

---

### Story 28.4: Ajouter Frontend à Docker Compose
**Priority**: P2 | **Effort**: 2 pts | **Value**: Medium | **Depends on**: 28.1

Ajouter le service frontend au docker-compose.yml pour un démarrage unique.

**Fichiers à modifier** :
- `docker-compose.yml` — Ajouter service `frontend`
- `docker/Dockerfile.frontend` — Améliorer pour production

**Config proposée** :
```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: ../docker/Dockerfile.frontend
  container_name: mnemo-frontend
  ports:
    - "127.0.0.1:3000:3000"
  environment:
    VITE_API_URL: http://api:8000
  volumes:
    - ./frontend:/app
    - /app/node_modules
  depends_on:
    - api
```

---

### Story 28.5: Fixer 16 tests MCP restants
**Priority**: P1 | **Effort**: 3 pts | **Value**: High

Corriger les échecs pré-existants pour atteindre 358/358 tests passants.

**Répartition** :
| Fichier | Échecs | Cause racine | Effort |
|---------|--------|-------------|--------|
| `test_indexing_tools.py` | 2 | Élicitation skip silencieusement | 0.5 |
| `test_memory_models.py` | 1 | Enum count mismatch | 0.5 |
| `test_memory_resources.py` | 3 | Mock mismatch | 1 |
| `test_search_tool.py` | 3 | Service injection | 1 |
| `test_graph_models.py` | 2 | Pré-existant | 0.5 |
| `test_memory_repository.py` | 2 | Mock incomplet | 0.5 |
| `test_memory_tools.py` | 2 | Assertion mismatch | 0.5 |
| `test_config_resources.py` | 1 | Languages no engine | 0.5 |

---

### Story 28.6: Fixer le Cross-Encoder Reranking
**Priority**: P3 | **Effort**: 4 pts | **Value**: Medium

Le reranking est désactivé par défaut (bug accelerate 1.13 + transformers 4.51 = recursion infinie).

**Options** (investiguer d'abord) :
1. **Upgrade accelerate** → `accelerate>=1.14.0` si disponible
2. **Pincer versions compatibles** → Downgrade combo connu
3. **BM25 reranking** → Pur Python, pas de dépendance ML
4. **Autre modèle** → `cross-encoder/ms-marco-MiniLM-L-6-v2`

**Fichiers à modifier** :
- `api/services/cross_encoder_rerank_service.py`
- `api/services/hybrid_memory_search_service.py`
- `api/requirements.txt`

---

### Story 28.7: Appliquer migration sys:trace en DB
**Priority**: P1 | **Effort**: 0.5 pts | **Value**: High

La migration existe mais n'a pas été run. Le tag est dans le code mais pas en DB.

**Actions** :
1. Identifier le fichier de migration
2. Run : `docker compose exec api alembic upgrade head`
3. Vérifier : `SELECT * FROM memory_decay_config WHERE tag_pattern = 'sys:trace';`

---

### Story 28.8: Définir le prochain EPIC
**Priority**: P2 | **Effort**: 1 pt | **Value**: Stratégique

Revoir la roadmap et définir le prochain EPIC.

**Fichiers à consulter** :
- `docs/agile/README.md`
- `docs/features/*.md`
- `docs/plans/*.md`
- `docs/01_DECISIONS/*.md`

---

## Ordre d'exécution suggéré

```
Phase 1 (Quick Wins, ~3h)
  28.7 → sys:trace DB (5min)
  28.5 → Fix 16 tests MCP (2h)
  28.2 → Projects.vue SCADA (1h)

Phase 2 (Foundation, ~5h)
  28.1 → API URL config (2h)
  28.3 → Logs.vue (3h)

Phase 3 (DevEx, ~2h)
  28.4 → Docker Compose frontend (2h)

Phase 4 (Qualité, ~5h)
  28.6 → Cross-encoder (4h)
  28.8 → Prochain EPIC (1h)
```

**Total estimé** : ~15h de travail effectif

---

## Critères de complétion

- [ ] 358/358 tests MCP passants
- [ ] 0 URL API hardcodée dans le frontend
- [ ] Projects.vue style SCADA cohérent
- [ ] Logs.vue fonctionnelle
- [ ] `docker compose up` démarre tout (y compris front)
- [ ] Cross-encoder reranking fonctionnel
- [ ] sys:trace présent en DB
- [ ] Prochain EPIC défini
