.PHONY: up down build restart logs ps clean prune health db-up db-shell db-backup db-restore api-shell api-test api-test-file api-test-one api-coverage api-debug worker-shell certs help

# Variables
COMPOSE_FILE := docker-compose.yml
PROD_COMPOSE_FILE := docker-compose.prod.yml
# Variables par défaut pour les commandes exec (simplifié)
POSTGRES_USER ?= mnemo
POSTGRES_DB ?= mnemolite
API_PORT ?= 8001
TEST_ENV ?= -e TEST_DATABASE_URL="postgresql+asyncpg://mnemo:5eCqZDyUV6MmcZMKin1GmFTlTkPbU50n@db:5432/mnemolite_test"

# Commandes de développement
up:
	docker compose -f $(COMPOSE_FILE) up -d

down:
	docker compose -f $(COMPOSE_FILE) down --remove-orphans

build:
	DOCKER_BUILDKIT=1 docker compose -f $(COMPOSE_FILE) build

restart:
	docker compose -f $(COMPOSE_FILE) restart

logs:
	docker compose -f $(COMPOSE_FILE) logs -f

ps:
	docker compose -f $(COMPOSE_FILE) ps

clean:
	docker compose -f $(COMPOSE_FILE) down -v --remove-orphans

prune:
	make clean
	docker system prune -af --volumes

# Commandes pour la production (Adapter si docker-compose.prod.yml existe)
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
	# Démarre uniquement le service 'db'
	docker compose -f $(COMPOSE_FILE) up -d db

db-shell:
	# Utilise les variables définies en haut du Makefile ou l'environnement
	docker compose -f $(COMPOSE_FILE) exec db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

db-backup:
	# Utilise les variables définies en haut du Makefile ou l'environnement
	docker compose -f $(COMPOSE_FILE) exec db pg_dump -U $(POSTGRES_USER) -d $(POSTGRES_DB) > backup-$(shell date +%Y%m%d%H%M%S).sql

db-restore:
	@echo "Usage: make db-restore file=<backup-file>"
	# Utilise les variables définies en haut du Makefile ou l'environnement
	@test -f $(file) && cat $(file) | docker compose -f $(COMPOSE_FILE) exec -T db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

# Commandes pour l'API
api-shell:
	docker compose -f $(COMPOSE_FILE) exec api /bin/bash

api-test:
	# Exécuter tous les tests avec verbosité
	docker compose -f $(COMPOSE_FILE) exec -w /app $(TEST_ENV) api pytest tests/ -xvs

api-test-file:
	@echo "Usage: make api-test-file file=<test_file_path>"
	@test -n "$(file)" || (echo "Error: 'file' parameter is required"; exit 1)
	docker compose -f $(COMPOSE_FILE) exec -w /app $(TEST_ENV) api pytest $(file) -vvs

api-test-one:
	@echo "Usage: make api-test-one test=<test_file_path>::<test_name>"
	@test -n "$(test)" || (echo "Error: 'test' parameter is required"; exit 1)
	docker compose -f $(COMPOSE_FILE) exec -w /app $(TEST_ENV) api pytest $(test) -vvs

api-coverage:
	docker compose -f $(COMPOSE_FILE) exec -w /app $(TEST_ENV) api pytest --cov=api tests/

api-debug:
	@echo "Usage: make api-debug file=<python_script_path>"
	@test -n "$(file)" || (echo "Error: 'file' parameter is required"; exit 1)
	docker compose -f $(COMPOSE_FILE) exec -it -e PYTHONUNBUFFERED=1 -e DEBUG=1 -w /app api python -m pdb $(file)

# Commandes pour les workers
worker-shell:
	docker compose -f $(COMPOSE_FILE) exec worker /bin/bash

worker-run:
	@echo "Usage: make worker-run task=<task_module>"
	@test -n "$(task)" || (echo "Error: 'task' parameter is required"; exit 1)
	docker compose -f $(COMPOSE_FILE) exec -w /app/workers -e PYTHONUNBUFFERED=1 worker python -m $(task)

# Vérification de l'état des services (Nouvelle cible)
health:
	@echo "API Health (Port $(API_PORT)):'"
	@curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:$(API_PORT)/health
	@echo "PostgreSQL Health:'"
	@docker compose -f $(COMPOSE_FILE) exec db pg_isready -U $(POSTGRES_USER) -d $(POSTGRES_DB) -q && echo "OK" || echo "FAIL"

# Création des certificats auto-signés (développement)
certs:
	mkdir -p certs
	openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout certs/key.pem -out certs/cert.pem -subj "/C=FR/ST=Paris/L=Paris/O=MnemoLite/CN=localhost"

# Benchmark
benchmark:
	docker compose -f $(COMPOSE_FILE) exec -w /app api python -m scripts.benchmarks.run_benchmark

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
	@echo "  make api-test        - Run all API tests with verbosity"
	@echo "  make api-test-file file=<path> - Run tests in specific file"
	@echo "  make api-test-one test=<path>::<name> - Run specific test"
	@echo "  make api-coverage    - Run tests with coverage report"
	@echo "  make api-debug file=<path> - Debug Python script with pdb"
	@echo ""
	@echo "Worker:"
	@echo "  make worker-shell    - Connect to worker container shell"
	@echo "  make worker-run task=<module> - Run specific worker task"
	@echo ""
	@echo "Utils:"
	@echo "  make certs           - Generate self-signed certificates"
	@echo "  make health          - Check API (at /health) and PostgreSQL health"
	@echo "  make benchmark       - Run performance benchmarks" 