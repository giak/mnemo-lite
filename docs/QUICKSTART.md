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

MnemoLite expose 34 outils MCP via Streamable HTTP sur le port 8002.

### Méthode moderne (recommandée) — Connexion directe HTTP

```json
{
  "mcpServers": {
    "mnemolite": {
      "type": "remote",
      "url": "http://localhost:8002/mcp"
    }
  }
}
```

> ⚠️ Le format exact (`type: "http"` ou `transport: "streamable-http"`) dépend du client. Voir [`MCP_SETUP.md`](../MCP_SETUP.md) pour les configurations détaillées.

### Méthode legacy — Script bash

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

# Health check MCP : pas de /health HTTP sur 8002 (404 attendu) —
# le serveur MCP se teste via l'handshake (initialize) ou le ping MCP.
curl -s -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}'
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

## 5. Configuration Sécurité

Les secrets (API keys, tokens, mots de passe) sont automatiquement rédactés lors de `write_memory` et `update_memory`.

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_PRIVACY_ENABLED` | `true` | Activer/désactiver la rédaction automatique |

Pour désactiver :
```bash
# Dans docker-compose.yml ou .env
MCP_PRIVACY_ENABLED=false
```

Secrets détectés : AWS, OpenAI, Anthropic, GitHub, GitLab, Slack, JWT, Bearer, Connection Strings, `<private>` tags.

Remplacement : `[REDACTED: TYPE]` (ex: `[REDACTED: OPENAI_KEY]`)

## 6. Services Disponibles

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