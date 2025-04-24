# MnemoLite - Configuration Docker

## Vue d'ensemble

Ce document détaille la configuration Docker pour l'environnement de développement et de production de MnemoLite. Nous utilisons Docker Compose pour orchestrer les différents services nécessaires au fonctionnement de l'application.

## Configuration optimisée (Approche hybride)

Suite à une analyse stratégique des besoins de MnemoLite, cette configuration hybride a été optimisée pour combiner performance, sécurité et robustesse.

```yaml
version: '3.8'

x-logging: &default-logging
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"

services:
  db:
    image: postgres:17
    container_name: mnemo-postgres
    user: postgres:postgres
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          memory: 1G
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-mnemo}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-mnemopass}
      POSTGRES_DB: ${POSTGRES_DB:-mnemolite}
      POSTGRES_INITDB_ARGS: "--data-checksums"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d:ro
      - ./db/scripts:/scripts:ro
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s
    command: >
      postgres -c shared_preload_libraries=pg_cron,pg_partman_bgw,pgmq.pg_queue
               -c pg_partman_bgw.interval=3600
               -c pg_partman_bgw.role=mnemo
               -c pg_cron.use_background_workers=on
               -c shared_buffers=512MB
               -c work_mem=16MB
               -c effective_cache_size=1GB
               -c maintenance_work_mem=128MB
               -c max_parallel_workers_per_gather=4
    shm_size: 1gb
    networks:
      backend:
        aliases:
          - database
    logging: *default-logging

  chromadb:
    image: ghcr.io/chroma-core/chroma:latest
    container_name: mnemo-chroma
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
    volumes:
      - chroma_data:/chroma/chroma
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      - CHROMA_DB_IMPL=duckdb+parquet
      - CHROMA_PERSIST_DIRECTORY=/chroma/chroma
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      backend:
        aliases:
          - chromadb
    logging: *default-logging

  api:
    build:
      context: .
      dockerfile: api/Dockerfile
      args:
        - BUILDKIT_INLINE_CACHE=1
    container_name: mnemo-api
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
    volumes:
      - ./api/config:/app/config:ro
      - ./api/templates:/app/templates:ro
      - api_cache:/app/cache
    ports:
      - "127.0.0.1:8001:8000"
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER:-mnemo}:${POSTGRES_PASSWORD:-mnemopass}@db:5432/${POSTGRES_DB:-mnemolite}
      - CHROMA_URL=http://chromadb:8000
      - UVICORN_WORKERS=2
      - UVICORN_LOOP=uvloop
    depends_on:
      db:
        condition: service_healthy
      chromadb:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      backend:
      frontend:
    logging: *default-logging

  worker:
    build:
      context: .
      dockerfile: workers/Dockerfile
      args:
        - BUILDKIT_INLINE_CACHE=1
    container_name: mnemo-worker
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
    volumes:
      - ./workers/config:/app/config:ro
      - worker_data:/app/data
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER:-mnemo}:${POSTGRES_PASSWORD:-mnemopass}@db:5432/${POSTGRES_DB:-mnemolite}
      - CHROMA_URL=http://chromadb:8000
      - PYTHONUNBUFFERED=1
    depends_on:
      db:
        condition: service_healthy
      chromadb:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import os; os.system('ps aux | grep ingestion.py | grep -v grep || exit 1')"]
      interval: 30s
      retries: 3
    networks:
      backend:
    logging: *default-logging

networks:
  frontend:
  backend:
    internal: true

volumes:
  postgres_data:
  chroma_data:
  api_cache:
  worker_data:
```

### Explication des optimisations clés

#### 1. Gestion des ressources
Chaque service est configuré avec des limites de ressources précises adaptées à son rôle :
- **PostgreSQL**: 2 CPUs et 2GB mémoire avec 1GB de réservation minimale
- **ChromaDB**: 1 CPU et 1GB mémoire pour l'indexation vectorielle
- **API**: 1 CPU et 512MB mémoire, suffisant pour traiter plusieurs requêtes simultanées
- **Worker**: 1 CPU et 1GB mémoire pour les tâches d'ingestion

#### 2. Optimisation de PostgreSQL
```yaml
command: >
  postgres -c shared_buffers=512MB
           -c work_mem=16MB
           -c effective_cache_size=1GB
           -c maintenance_work_mem=128MB
           -c max_parallel_workers_per_gather=4
shm_size: 1gb
```
Ces paramètres sont spécifiquement ajustés pour les workloads d'une base de données vectorielle :
- `shared_buffers` : Mémoire dédiée au cache de données partagé
- `work_mem` : Mémoire allouée aux opérations de tri et de hash
- `effective_cache_size` : Estimation de la mémoire disponible pour le cache disque
- `maintenance_work_mem` : Mémoire pour les opérations de maintenance
- `max_parallel_workers_per_gather` : Utilisation du parallélisme pour accélérer les requêtes

#### 3. Sécurité et isolation réseau
```yaml
networks:
  frontend:
  backend:
    internal: true
```
- Réseau `backend` interne sans accès direct depuis l'extérieur
- Seule l'API est accessible via le réseau `frontend`
- Montage des volumes en lecture seule (`:ro`) pour les configurations et scripts

#### 4. Healthchecks et observabilité
Chaque service dispose de healthchecks adaptés à sa nature :
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
  interval: 5s
  timeout: 5s
  retries: 5
  start_period: 10s
```
Configuration de logs standardisée via l'anchor YAML :
```yaml
x-logging: &default-logging
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

#### 5. Optimisation des performances de l'API
```yaml
environment:
  - UVICORN_WORKERS=2
  - UVICORN_LOOP=uvloop
```
- Utilisation de plusieurs workers pour traiter les requêtes en parallèle
- Utilisation d'uvloop pour améliorer les performances asyncio

## Dockerfiles optimisés

### Pour l'API (api/Dockerfile)

```dockerfile
# Multi-stage build
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim AS runtime

# Optimisations Python
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Optimisation des couches
COPY ./api/models/ /app/models/
COPY ./api/routes/ /app/routes/
COPY ./api/main.py /app/

# Utilisation d'un utilisateur non-root
RUN useradd -m appuser && \
    mkdir -p /app/cache && \
    chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Pour les Workers (workers/Dockerfile)

```dockerfile
# Multi-stage build
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim AS runtime

# Optimisations Python
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Optimisation des couches
COPY ./workers/ingestion.py /app/
COPY ./workers/utils/ /app/utils/

# Utilisation d'un utilisateur non-root
RUN useradd -m appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app
USER appuser

CMD ["python", "ingestion.py"]
```

## Configuration .env

```
# PostgreSQL
POSTGRES_USER=mnemo
POSTGRES_PASSWORD=mnemopass
POSTGRES_DB=mnemolite

# API
API_PORT=8001
UVICORN_WORKERS=2

# Chroma
CHROMA_PORT=8000

# Resources
PG_CPU_LIMIT=2
PG_MEM_LIMIT=2G
CHROMA_CPU_LIMIT=1
CHROMA_MEM_LIMIT=1G
API_CPU_LIMIT=1
API_MEM_LIMIT=512M
WORKER_CPU_LIMIT=1
WORKER_MEM_LIMIT=1G
```

## Makefile amélioré

```makefile
.PHONY: up down build logs ps shell-db shell-api shell-worker restart clean prune status health setup production

# Variables from .env
include .env
export

up:
	docker-compose up -d

down:
	docker-compose down

build:
	DOCKER_BUILDKIT=1 docker-compose build

logs:
	docker-compose logs -f

ps:
	docker-compose ps

shell-db:
	docker-compose exec db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

shell-api:
	docker-compose exec api bash

shell-worker:
	docker-compose exec worker bash

restart:
	docker-compose restart

clean:
	docker-compose down --volumes --remove-orphans

prune:
	docker system prune -af

status:
	@echo "===== Services Status ====="
	@docker-compose ps
	@echo "\n===== Services Health ====="
	@docker-compose ps | grep Up | awk '{print $$1}' | xargs -I{} docker inspect --format='{{.Name}} - {{.State.Health.Status}}' {}

health:
	@curl -s http://localhost:$(API_PORT)/health | jq

setup: build up
	@echo "Waiting for services to start..."
	@sleep 10
	docker-compose exec db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB) -f /scripts/setup.sql
	@echo "Setup complete!"

production: 
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Avantages de l'approche hybride

1. **Performance optimisée**
   - Paramètres PostgreSQL spécifiquement ajustés pour les workloads vectoriels
   - Multi-stage builds réduisant la taille des images et les temps de démarrage
   - Utilisation d'uvloop et de workers multiples pour l'API FastAPI

2. **Sécurité renforcée**
   - Containers exécutés avec des utilisateurs non-root
   - Isolation réseau avec séparation frontend/backend
   - Montage de volumes en lecture seule pour les fichiers statiques
   - Exposition des ports uniquement sur localhost (127.0.0.1)

3. **Robustesse opérationnelle**
   - Healthchecks spécifiques pour chaque service
   - Redémarrages automatiques configurés
   - Limitations de ressources pour éviter la surcharge
   - Gestion optimisée des logs avec rotation automatique

4. **Maintenabilité améliorée**
   - Structure de configuration YAML claire avec réutilisation (anchors)
   - Variables d'environnement centralisées
   - Makefile avec commandes utilitaires
   - Documentation détaillée des paramètres et optimisations

5. **Efficacité des ressources**
   - Limites de mémoire et CPU pour chaque service
   - Réservation de mémoire pour garantir les performances minimales
   - Optimisation des caches PostgreSQL pour workloads spécifiques
   - Images Docker plus légères grâce aux builds multi-étapes

## Inconvénients potentiels

1. **Complexité accrue**
   - Configuration plus complexe à comprendre et maintenir
   - Nécessite une meilleure connaissance des options Docker et des services

2. **Risque de sous-allocation**
   - Les limites de ressources statiques peuvent être trop restrictives dans certains scénarios
   - Nécessite des tests de charge pour valider les configurations

3. **Dépendance aux health checks**
   - Le système dépend fortement des health checks correctement configurés
   - Un health check mal conçu peut causer des redémarrages inutiles

4. **Configuration spécifique au hardware**
   - Les paramètres d'optimisation PostgreSQL peuvent nécessiter des ajustements selon les spécifications matérielles

5. **Maintenance DevOps requise**
   - Les logs rotations et volumes nécessitent une surveillance périodique
   - La mise à jour des images et dépendances doit être gérée régulièrement

## Installation et démarrage

### Prérequis

- Docker Engine 24.0+ 
- Docker Compose 2.20+
- Make (pour utiliser le Makefile)
- Minimum 4GB RAM disponible
- 30GB espace disque recommandé

### Étapes d'installation

1. Cloner le dépôt
   ```bash
   git clone https://github.com/giak/mnemo-lite.git
   cd mnemo-lite
   ```

2. Créer le fichier .env (copier depuis .env.example)
   ```bash
   cp .env.example .env
   # Modifier les valeurs selon votre environnement
   ```

3. Créer la structure de dossiers
   ```bash
   mkdir -p api/{models,routes,config,templates} workers/{utils,config} db/{init,scripts}
   touch api/main.py workers/ingestion.py
   ```

4. Initialiser les Dockerfiles et scripts
   ```bash
   # Créer les Dockerfiles pour api et workers selon les modèles ci-dessus
   # Créer les scripts SQL d'initialisation
   ```

5. Démarrer l'environnement
   ```bash
   make setup
   ```

### Vérification de l'installation

Après le démarrage des services, vérifiez que tout fonctionne correctement :

1. Vérifier l'état des containers
   ```bash
   make status
   ```

2. Vérifier les logs
   ```bash
   make logs
   ```

3. Tester l'accès à l'API
   ```bash
   make health
   # ou
   curl http://localhost:8001/health
   ```

## Monitoring et dépannage

### Commandes utiles

```bash
# Voir les ressources consommées par les containers
docker stats $(docker ps --format={{.Names}})

# Redémarrer un service spécifique
docker-compose restart <service-name>

# Voir les logs d'un service spécifique
docker-compose logs -f <service-name>

# Exécuter une commande dans un container
docker-compose exec <service-name> <command>

# Inspecter la configuration d'un container
docker inspect <container-name>
```

### Problèmes courants

1. **PostgreSQL ne démarre pas**
   - Vérifier que les ports ne sont pas déjà utilisés
   - Vérifier les permissions des volumes
   - Vérifier si les ressources allouées sont suffisantes

2. **API ne peut pas se connecter à la base de données**
   - Vérifier les variables d'environnement dans le fichier .env
   - Vérifier que le service PostgreSQL est bien démarré et en bonne santé
   - Vérifier les logs pour les erreurs de connexion

3. **ChromaDB ne persiste pas les données**
   - Vérifier les volumes et leur configuration
   - S'assurer que le chemin de persistance est correctement configuré

4. **Performances dégradées**
   - Vérifier l'utilisation CPU/mémoire avec `docker stats`
   - Ajuster les limites de ressources si nécessaire
   - Vérifier les logs pour les warnings ou erreurs

---

**Version**: 1.1.0  
**Dernière mise à jour**: 2025-04-24  
**Auteur**: Giak 