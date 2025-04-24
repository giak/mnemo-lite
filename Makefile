.PHONY: up down build restart logs ps clean prune

# Variables
COMPOSE_FILE := docker-compose.yml
PROD_COMPOSE_FILE := docker-compose.prod.yml

# Commandes de développement
up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

restart:
	docker compose restart

logs:
	docker compose logs -f

ps:
	docker compose ps

clean:
	docker compose down -v

prune:
	docker system prune -a --volumes

# Commandes pour la production
prod-up:
	docker compose -f $(COMPOSE_FILE) -f $(PROD_COMPOSE_FILE) up -d

prod-down:
	docker compose -f $(COMPOSE_FILE) -f $(PROD_COMPOSE_FILE) down

prod-build:
	docker compose -f $(COMPOSE_FILE) -f $(PROD_COMPOSE_FILE) build

prod-restart:
	docker compose -f $(COMPOSE_FILE) -f $(PROD_COMPOSE_FILE) restart

prod-logs:
	docker compose -f $(COMPOSE_FILE) -f $(PROD_COMPOSE_FILE) logs -f

prod-clean:
	docker compose -f $(COMPOSE_FILE) -f $(PROD_COMPOSE_FILE) down -v

# Commandes pour les bases de données
db-up:
	docker compose up -d db chromadb

db-shell:
	docker compose exec db psql -U $(shell grep POSTGRES_USER .env | cut -d '=' -f2) -d $(shell grep POSTGRES_DB .env | cut -d '=' -f2)

db-backup:
	docker compose exec db pg_dump -U $(shell grep POSTGRES_USER .env | cut -d '=' -f2) -d $(shell grep POSTGRES_DB .env | cut -d '=' -f2) > backup-$(shell date +%Y%m%d%H%M%S).sql

db-restore:
	@echo "Usage: make db-restore file=<backup-file>"
	@test -f $(file) && cat $(file) | docker compose exec -T db psql -U $(shell grep POSTGRES_USER .env | cut -d '=' -f2) -d $(shell grep POSTGRES_DB .env | cut -d '=' -f2)

# Commandes pour l'API
api-shell:
	docker compose exec api /bin/bash

api-test:
	docker compose exec api pytest

# Commandes pour les workers
worker-shell:
	docker compose exec worker /bin/bash

# Création des certificats auto-signés (développement)
certs:
	mkdir -p certs
	openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout certs/key.pem -out certs/cert.pem -subj "/C=FR/ST=Paris/L=Paris/O=MnemoLite/CN=localhost"

# Aide
help:
	@echo "Usage:"
	@echo "  make up              - Start services in development mode"
	@echo "  make down            - Stop services"
	@echo "  make build           - Build services"
	@echo "  make restart         - Restart services"
	@echo "  make logs            - View logs"
	@echo "  make ps              - List running containers"
	@echo "  make clean           - Remove containers and volumes"
	@echo "  make prune           - Remove all unused Docker resources"
	@echo ""
	@echo "Production:"
	@echo "  make prod-up         - Start services in production mode"
	@echo "  make prod-down       - Stop production services"
	@echo "  make prod-build      - Build production services"
	@echo "  make prod-logs       - View production logs"
	@echo "  make prod-clean      - Remove production containers and volumes"
	@echo ""
	@echo "Database:"
	@echo "  make db-up           - Start only database services"
	@echo "  make db-shell        - Connect to PostgreSQL shell"
	@echo "  make db-backup       - Create database backup"
	@echo "  make db-restore file=<file> - Restore database from backup"
	@echo ""
	@echo "API:"
	@echo "  make api-shell       - Connect to API container shell"
	@echo "  make api-test        - Run API tests"
	@echo ""
	@echo "Worker:"
	@echo "  make worker-shell    - Connect to worker container shell"
	@echo ""
	@echo "Utils:"
	@echo "  make certs           - Generate self-signed certificates" 