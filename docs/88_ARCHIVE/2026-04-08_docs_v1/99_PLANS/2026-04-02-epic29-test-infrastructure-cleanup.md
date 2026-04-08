# EPIC-29: Test Infrastructure & Dead Code Cleanup

**Status**: ✅ COMPLETE | **Created**: 2026-04-02 | **Completed**: 2026-04-02

---
on v afaire danbs l'ord
## Context

L'infrastructure de tests a des problèmes structurels qui empêchent la confiance CI/CD :
- 13 fichiers de tests API avec erreurs d'import (dépendances manquantes)
- 1 fichier de dead code (`cross_encoder_rerank_service.py`)
- 3 routes stubs vides jamais implémentées
- 1 composant scaffold inutile (`HelloWorld.vue`)
- Endpoint `/import` déprécié mais toujours dans le code

Ces dettes techniques bloquent l'automatisation et créent de la confusion.

---

## Stories

### Story 29.1: Fixer l'environnement de tests API
**Priority**: P0 | **Effort**: 2 pts | **Value**: High

Les tests API ne peuvent pas être collectés par pytest car les dépendances ne sont pas installées dans l'environnement de test.

**Actions** :
- Créer un `requirements-test.txt` ou section `[test]` dans pyproject.toml
- Inclure : `sqlalchemy[asyncio]`, `asyncpg`, `psycopg2`, `httpx`, `pytest-asyncio`
- Vérifier que `docker exec mnemo-api python -m pytest tests/` collecte tous les tests
- Documenter la commande pour lancer les tests

**Fichiers à modifier** :
- `api/requirements-test.txt` (nouveau)
- `api/Dockerfile` (ajouter `pip install -r requirements-test.txt`)
- `docs/tests/README.md` (documentation)

---

### Story 29.2: Supprimer le dead code
**Priority**: P1 | **Effort**: 0.5 pts | **Value**: Low

Fichiers et composants non utilisés qui polluent le codebase.

**À supprimer** :
- `api/services/cross_encoder_rerank_service.py` — remplacé par BM25
- `frontend/src/components/HelloWorld.vue` — scaffold Vite par défaut
- `api/tests/test_p0_critical_fixes.py` — fichier de test temporaire non tracké

**Fichiers à modifier** :
- Supprimer les 3 fichiers ci-dessus
- Vérifier qu'aucun import ne référence ces fichiers

---

### Story 29.3: Implémenter ou supprimer les 3 routes stubs
**Priority**: P1 | **Effort**: 1.5 pts | **Value**: Medium

Trois fichiers de routes existent mais sont vides :
- `api/routes/cache_admin_routes.py` — Administration du cache L1/L2
- `api/routes/code_indexing_routes.py` — Indexation de code via API REST
- `api/routes/search_routes.py` — Recherche unifiée (déjà couverte par `code_search_routes.py` et `memories_routes.py`)

**Décision** :
- `cache_admin_routes.py` → Implémenter 2 endpoints basiques (clear L1, clear L2)
- `code_indexing_routes.py` → Supprimer (déjà couvert par MCP `index_project`)
- `search_routes.py` → Supprimer (déjà couvert par les routes existantes)

**Fichiers à modifier** :
- `api/routes/cache_admin_routes.py` — implémenter
- `api/routes/code_indexing_routes.py` — supprimer
- `api/routes/search_routes.py` — supprimer
- `api/main.py` — retirer les imports des routes supprimées

---

### Story 29.4: Nettoyer l'endpoint déprécié `/import`
**Priority**: P2 | **Effort**: 0.5 pts | **Value**: Low

L'endpoint `POST /api/v1/conversations/import` est marqué DEPRECATED dans `conversations_routes.py:518`. Il faut le supprimer proprement.

**Actions** :
- Supprimer la route `/import` de `conversations_routes.py`
- Ajouter un log de dépréciation si quelqu'un l'appelle (avant suppression)
- Mettre à jour la doc API

**Fichiers à modifier** :
- `api/routes/conversations_routes.py`
- `api/docs/` (si doc existe)

---

### Story 29.5: Documenter les commandes de test
**Priority**: P2 | **Effort**: 0.5 pts | **Value**: Medium

Créer une documentation claire pour lancer les tests.

**Fichier à créer** :
- `docs/tests/README.md` — Guide complet :
  - Tests MCP : `docker exec mnemo-api python -m pytest tests/mnemo_mcp/ -v`
  - Tests API : `docker exec mnemo-api python -m pytest tests/ -v`
  - Tests frontend : `cd frontend && npx vitest run`
  - Tests avec coverage : `--cov=api --cov-report=html`

---

## Critères de complétion

- [ ] Tous les tests API se collectent sans erreur d'import
- [ ] `cross_encoder_rerank_service.py` supprimé
- [ ] `HelloWorld.vue` supprimé
- [ ] 2 stubs supprimés, 1 implémenté (cache_admin)
- [ ] Endpoint `/import` déprécié supprimé
- [ ] Documentation de test créée
- [ ] 358+ tests MCP toujours passing

---

## Ordre d'exécution

```
29.2 (dead code) → 29.3 (stubs) → 29.4 (deprecated) → 29.1 (test env) → 29.5 (docs)
```

Nettoyer d'abord, puis fixer l'infra, puis documenter.
