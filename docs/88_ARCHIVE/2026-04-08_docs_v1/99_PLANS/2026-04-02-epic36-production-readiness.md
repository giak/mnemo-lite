# EPIC-36: Production Readiness

**Status**: DRAFT | **Created**: 2026-04-02 | **Effort**: ~6 points | **Stories**: 5

---

## Context

Après 8 EPICs de développement fonctionnel, le projet doit être préparé
pour la production. Plusieurs éléments manquent pour un déploiement fiable.

### État actuel

| Area | Status | Notes |
|------|--------|-------|
| Docker Compose | ⚠️ Frontend manquant | Backend OK, frontend non inclus |
| Environment vars | ❌ Hardcodé | `localhost:8001` dans 13 fichiers frontend |
| CI/CD | ❌ Aucun | Pas de pipeline automatisé |
| Health checks | ✅ | `/health` fonctionnel |
| Logging | ✅ | Struct logging OK |
| Monitoring | ✅ | OpenObserve configuré |
| Documentation | ⚠️ Partielle | API docs auto, pas de guide deploy |

---

## Stories

### Story 36.1: Frontend dans Docker Compose
**Priority**: P0 | **Effort**: 1 pt | **Value**: High

**Problème** : Le frontend n'est pas dans docker-compose.yml.
`docker/Dockerfile.frontend` existe mais n'est pas référencé.

**Solution** : Ajouter le service frontend au compose avec Vite dev server
pour le dev, et build Nginx pour la prod.

**Implémentation** :
```yaml
# docker-compose.yml
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
  networks:
    - frontend
```

**Fichiers** :
- `docker-compose.yml` — Ajouter service frontend
- `docker/Dockerfile.frontend` — Vérifier qu'il fonctionne

---

### Story 36.2: Environment variables pour l'API URL
**Priority**: P0 | **Effort**: 1 pt | **Value**: High

**Problème** : `localhost:8001` est hardcodé dans le frontend.
En production, l'API sera sur un autre host.

**Solution** : Utiliser Vite env vars avec `.env` files.

**Implémentation** :
```bash
# frontend/.env (default)
VITE_API_URL=http://localhost:8001

# frontend/.env.production
VITE_API_URL=https://api.mnemolite.example.com
```

```typescript
// frontend/src/config/api.ts
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001'
export const API = `${API_URL}/api/v1`
```

**Fichiers** :
- `frontend/.env` — Créer avec valeurs par défaut
- `frontend/.env.production` — Template pour prod
- `frontend/src/config/api.ts` — Déjà fait, vérifier

---

### Story 36.3: Docker Compose production profile
**Priority**: P1 | **Effort**: 1.5 pts | **Value**: High

**Problème** : Un seul docker-compose.yml pour dev et prod.

**Solution** : Utiliser des profiles Docker Compose.

**Implémentation** :
```yaml
# docker-compose.yml
services:
  api:
    profiles: ["dev", "prod"]
    # ...
  
  frontend:
    profiles: ["dev"]
    # Dev: Vite dev server with HMR
  
  frontend-prod:
    profiles: ["prod"]
    build:
      context: ./frontend
      dockerfile: docker/Dockerfile.frontend.prod  # Nginx build
    # Prod: Static Nginx serving built frontend
```

**Usage** :
```bash
docker compose --profile dev up -d      # Dev avec HMR
docker compose --profile prod up -d     # Prod avec Nginx
```

**Fichiers** :
- `docker-compose.yml` — Ajouter profiles
- `docker/Dockerfile.frontend.prod` — Nginx production build

---

### Story 36.4: Guide de déploiement
**Priority**: P2 | **Effort**: 1 pt | **Value**: Medium

**Problème** : Pas de documentation pour déployer en production.

**Solution** : Créer un guide complet.

**Contenu** :
- Prérequis (Docker, Docker Compose, ressources)
- Configuration (env vars, secrets)
- Déploiement (docker compose up)
- Vérification (health checks, logs)
- Mise à jour (pull, rebuild, migrate)
- Backup (DB, Redis)

**Fichiers** :
- `docs/deployment/README.md` — Guide principal
- `docs/deployment/docker-compose.prod.yml` — Exemple prod
- `docs/deployment/.env.example` — Template env vars

---

### Story 36.5: CI/CD pipeline basique
**Priority**: P2 | **Effort**: 1.5 pts | **Value**: Medium

**Problème** : Pas de pipeline CI pour valider les changements.

**Solution** : GitHub Actions workflow basique.

**Implémentation** :
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run MCP tests
        run: docker compose exec api python -m pytest tests/mnemo_mcp/ -v
      - name: Type check frontend
        run: cd frontend && npx vue-tsc --noEmit
      - name: Build frontend
        run: cd frontend && npm run build
```

**Fichiers** :
- `.github/workflows/ci.yml` — Pipeline CI

---

## Ordre d'exécution

```
Phase 1 (Critical, ~2h)
  36.1 → Frontend dans Docker Compose
  36.2 → Environment variables

Phase 2 (Production, ~2.5h)
  36.3 → Docker Compose production profile
  36.4 → Guide de déploiement

Phase 3 (Automation, ~1.5h)
  36.5 → CI/CD pipeline basique
```

---

## Critères de complétion

- [ ] `docker compose up` démarre tout (frontend + backend)
- [ ] Frontend utilise VITE_API_URL, pas de hardcodage
- [ ] Profile prod disponible avec Nginx
- [ ] Guide de déploiement complet
- [ ] CI pipeline valide tests + build
- [ ] Health checks fonctionnels en prod
- [ ] Backup DB automatisé (optionnel)

---

## Métriques de succès

| Métrique | Avant | Après |
|----------|-------|-------|
| Services Docker | 6 | 7 (+frontend) |
| URLs hardcodées | 13 | 0 |
| Profiles Compose | 0 | 2 (dev, prod) |
| Docs déploiement | 0 pages | 1 guide complet |
| CI pipeline | ❌ | ✅ |
