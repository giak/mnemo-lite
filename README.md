# MnemoLite

MnemoLite est une plateforme de mémoire vectorielle pour applications d'intelligence artificielle. Elle permet de stocker, rechercher et récupérer des informations en utilisant des embeddings vectoriels.

## Architecture

Le système est composé de plusieurs services :

- **API** : Service FastAPI pour l'interface REST
- **Worker** : Traitement asynchrone des tâches d'ingestion
- **PostgreSQL** : Base de données principale avec extension pgvector, pg_cron, pg_partman et pgmq
- **ChromaDB** : Base de données vectorielle pour la recherche sémantique optimisée

L'architecture suit un modèle CQRS (Command Query Responsibility Segregation) avec une partie Command pour l'ingestion des données et une partie Query pour leur interrogation.

## Prérequis

- Docker et Docker Compose v2
- Python 3.12+ (pour le développement local)
- 4 Go de RAM minimum

## Installation

1. Cloner le dépôt :
   ```bash
   git clone https://github.com/yourusername/mnemolite.git
   cd mnemolite
   ```

2. Créer un fichier .env à partir de l'exemple :
   ```bash
   cp .env.example .env
   ```

3. Modifier les valeurs dans le fichier .env selon vos besoins.

4. Lancer les services en mode développement :
   ```bash
   docker compose up -d
   ```

## Utilisation en production

Pour un déploiement en production, utilisez :

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Cela activera les configurations optimisées pour la production, notamment :
- Traefik en tant que reverse proxy avec HTTPS
- Répliques pour l'API et les workers
- Configuration optimisée pour PostgreSQL
- Services de monitoring (Prometheus/Grafana)

## Documentation API

La documentation de l'API est accessible à l'adresse suivante après démarrage des services :

```
http://localhost:8000/docs
```

## Développement local

Pour le développement local sans Docker :

1. Installer les dépendances :
   ```bash
   pip install -r api/requirements.txt
   ```

2. Lancer uniquement les services de base de données :
   ```bash
   docker compose up -d db chromadb
   ```

3. Lancer l'API en mode développement :
   ```bash
   cd api
   uvicorn main:app --reload
   ```

## Structure du projet

```
mnemolite/
├── api/                # Service API FastAPI
│   ├── models/         # Modèles de données
│   ├── routes/         # Routes API
│   ├── config/         # Configuration
│   └── templates/      # Templates Jinja2
├── workers/            # Services de traitement asynchrone
│   └── utils/          # Utilitaires partagés
├── db/                 # Scripts de base de données
│   ├── init/           # Scripts d'initialisation
│   └── scripts/        # Scripts utilitaires
├── prometheus/         # Configuration Prometheus 
├── certs/              # Certificats TLS (non inclus)
└── docs/               # Documentation
```

## Licence

MIT
