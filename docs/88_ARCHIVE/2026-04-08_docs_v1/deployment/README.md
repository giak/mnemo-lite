# MnemoLite Deployment Guide

## Overview

MnemoLite is a cognitive memory system with:
- **API**: FastAPI backend (Python)
- **MCP**: Model Context Protocol server
- **Frontend**: Vue 3 SPA (Vite dev / Nginx prod)
- **Database**: PostgreSQL 18 with pgvector
- **Cache**: Redis 7
- **Observability**: OpenObserve

## Prerequisites

- Docker 24+ and Docker Compose v2
- 16GB+ RAM (24GB recommended for embeddings)
- 50GB+ disk space
- Linux (Ubuntu 22.04+, Debian 12+) or macOS

## Quick Start

### Development

```bash
# Clone repository
git clone https://github.com/your-org/mnemolite.git
cd mnemolite

# Start dev environment
docker compose --profile dev up -d

# Wait for services to be healthy
docker compose ps

# Access services
# Frontend:  http://localhost:3000
# API:       http://localhost:8001
# MCP:       http://localhost:8002
# OpenObserve: http://localhost:5080
```

### Production

```bash
# Set environment variables
export VITE_API_URL=https://api.mnemolite.example.com
export POSTGRES_PASSWORD=<strong-password>

# Start production environment
docker compose --profile prod up -d

# Run database migrations
docker compose exec api alembic upgrade head

# Verify health
curl http://localhost/health
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `mnemo` | Database user |
| `POSTGRES_PASSWORD` | `mnemopass` | Database password |
| `POSTGRES_DB` | `mnemolite` | Database name |
| `API_PORT` | `8001` | API port |
| `EMBEDDING_MODE` | `real` | `real` or `mock` |
| `EMBEDDING_MODEL` | `nomic-ai/nomic-embed-text-v1.5` | Text embedding model |
| `VITE_API_URL` | `http://localhost:8001` | Frontend API URL |

### Frontend Environment

```bash
# Development
cp frontend/.env frontend/.env.local
# Edit VITE_API_URL if needed

# Production
# Set VITE_API_URL in docker-compose.yml or .env file
```

## Verification

### Health Checks

```bash
# API health
curl http://localhost:8001/health

# MCP health
curl -X POST http://localhost:8002/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-06-18"},"id":1}'

# Database
docker compose exec db pg_isready -U mnemo

# Redis
docker compose exec redis redis-cli ping
```

### Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f frontend
docker compose logs -f mcp

# OpenObserve (structured logs)
# http://localhost:5080
# Login: admin@mnemolite.local / Complexpass#123
```

## Updates

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker compose --profile dev up -d --build

# Run migrations
docker compose exec api alembic upgrade head

# Verify
docker compose ps
curl http://localhost:8001/health
```

## Backup

### Database

```bash
# Backup
docker compose exec db pg_dump -U mnemo mnemolite > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T db psql -U mnemo mnemolite < backup_20260402.sql
```

### Redis

```bash
# Backup
docker compose exec redis redis-cli BGSAVE
docker cp mnemo-redis:/data/dump.rdb ./redis-backup.rdb

# Restore
docker cp ./redis-backup.rdb mnemo-redis:/data/dump.rdb
docker compose restart redis
```

## Troubleshooting

### API won't start

```bash
# Check logs
docker compose logs api

# Common issues:
# - Database not ready: wait for db healthcheck
# - Port conflict: change API_PORT in .env
# - Memory: ensure 16GB+ available
```

### Frontend 404 errors

```bash
# Dev: check Vite proxy
docker compose logs frontend

# Prod: check Nginx config
docker compose exec frontend-prod cat /etc/nginx/conf.d/default.conf
```

### MCP timeout

```bash
# Increase timeout in kilo.jsonc
# "timeout": 30000

# Check MCP logs
docker compose logs mcp
```
