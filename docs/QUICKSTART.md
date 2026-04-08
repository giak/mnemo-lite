# MnemoLite Quick Start

**Setup en 5 minutes.**

## Prérequis

- Docker & Docker Compose v2+
- 8 GB RAM minimum (16 GB recommandé)
- 3 GB disk space

## 1. Démarrer MnemoLite

```bash
cd <project-root>
docker compose --profile dev up -d

# Vérifier
docker compose ps
# Expected: api, db, redis, mcp all "Up (healthy)"
```

## 2. Configurer MCP

Créer `.mcp.json` dans votre projet:

```json
{
  "mcpServers": {
    "mnemolite": {
      "command": "bash",
      "args": ["<project-root>/scripts/mcp_server.sh"],
      "env": {
        "DOCKER_COMPOSE_PROJECT": "mnemolite"
      }
    }
  }
}
```

**Note:** Remplacer `<project-root>` par le chemin absolu vers MnemoLite (ex: `/home/user/MnemoLite`).

## 3. Vérifier

```bash
# Health check API
curl http://localhost:8001/health

# Health check MCP
curl http://localhost:8002/health
```

## 4. Premier Usage

### Indexer un projet

Dans Claude Code (ou autre client MCP):

```
Indexe /path/to/project avec repository='my-project'
```

### Rechercher du code

```
Cherche les fonctions d'authentification
```

### Sauvegarder une mémoire

```
Sauvegarde: le projet utilise FastAPI + PostgreSQL
Tags: tech-stack, architecture
```

## 5. Services Disponibles

| Service | URL |
|---------|-----|
| Web UI | http://localhost:3000 |
| API | http://localhost:8001 |
| API Docs | http://localhost:8001/docs |
| MCP | http://localhost:8002 |
| OpenObserve | http://localhost:5080 |

## Troubleshooting

**MCP not available?**
```bash
docker compose ps | grep mcp
# Si down: docker compose up -d mcp
```

**Connection refused?**
```bash
docker compose logs api --tail 20
```

**Need to rebuild?**
```bash
docker compose build && docker compose up -d
```