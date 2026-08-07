# MCP Setup — Guide LLM pour utiliser MnemoLite

> **But de ce document** : Permettre à n'importe quel agent LLM (Claude, Codebuff, Cursor, etc.) de configurer, connecter et utiliser MnemoLite — que ce soit via le protocole MCP, l'API REST, ou le CLI `mnemo`.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AGENT LLM (vous)                        │
│  Claude / Codebuff / Cursor / Autre                        │
└─────┬──────────────────────────────┬───────────────────────┘
      │ MCP (port 8002)              │ REST (port 8001)
      ▼                               ▼
┌──────────────┐            ┌──────────────────┐
│  MCP Server  │            │   FastAPI REST   │
│  (29 tools)  │            │  (tous endpoints)│
└──────┬───────┘            └────────┬─────────┘
       │                            │
       └──────────┬─────────────────┘
                  ▼
        ┌──────────────────┐
        │   PostgreSQL 18  │
        │  + pgvector HNSW │
        │  + pg_trgm       │
        └──────────────────┘
```

Deux façons d'interagir avec Mnemolite :

| Mode | Port | Protocole | Usage |
|------|------|-----------|-------|
| **MCP** | 8002 | SSE (Server-Sent Events) | Agents LLM compatibles MCP (Codebuff, Claude Desktop) |
| **REST API** | 8001 | HTTP/JSON | Accès direct via curl, Python, scripts |
| **CLI** | — | Ligne de commande | `mnemo search/write/health/status` |

---

## 1. Connexion MCP (port 8002) — Recommandé pour agents LLM

### Configuration Codebuff

Dans `.codebuff/config.json` :
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

### Configuration Claude Desktop

Dans `~/.config/Claude/claude_desktop_config.json` :
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

### Protocole MCP (bas niveau)

Le MCP utilise SSE (Server-Sent Events) pour le transport.
Les deux headers `Accept` sont obligatoires :
```
Accept: application/json, text/event-stream
Content-Type: application/json
```

**Exemple : lister les outils disponibles**
```bash
curl -s -X POST http://localhost:8002/mcp \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

**Exemple : appeler search_memory**
```bash
curl -s -X POST http://localhost:8002/mcp \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_memory","arguments":{"query":"bureaucratie dette"}}}'
```

### Vérifier la connexion
```bash
# Depuis le host
curl -s http://localhost:8001/health
# → {"status":"healthy","database":true,"services":{"postgres":"UP","redis":"UP"}}

# MCP ping
curl -s -X POST http://localhost:8002/mcp \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}'
```

---

## 2. Outils MCP Disponibles (29 tools)

### 🔧 Test

| Tool | Description | Paramètres |
|------|-------------|------------|
| `ping` | Test de connectivité | Aucun |

### 🔍 Recherche

| Tool | Description | Paramètres |
|------|-------------|------------|
| `search_memory` | Recherche textuelle hybride (vectoriel + lexical) | `query` (str), `memory_type` (opt), `tags` (opt, comma-separated), `limit` (1-100, def:20), `offset` (def:0) |
| `search_code` | Recherche de code (lexical + vectoriel + RRF) | `query` (str), `filters` (opt), `limit`, `offset`, `enable_lexical`, `enable_vector`, `lexical_weight`, `vector_weight` |
| `search_by_entity` | Recherche par entité nommée | `entity_name` (str), `limit` |

### 📝 CRUD Mémoires

| Tool | Description | Paramètres clés |
|------|-------------|-----------------|
| `write_memory` | Créer une mémoire | `title` (str), `content` (str), `memory_type` (note/investigation/article/quintessence/...), `tags`, `author`, `project_id` |
| `read_memory` | Lire une mémoire par ID | `memory_id` (str, UUID) |
| `update_memory` | Mettre à jour (partiel) | `memory_id`, `title`?, `content`?, `tags`? |
| `delete_memory` | Supprimer (soft par défaut) | `memory_id`, `hard` (bool, default:false) |

### 🧠 Mémoires avancées

| Tool | Description |
|------|-------------|
| `consolidate_memory` | Résumer plusieurs mémoires en une seule + soft-delete des sources |
| `mark_consumed` | Marquer comme traité (idempotent) |
| `rate_memory` | Noter une mémoire (influence le decay) |
| `export_memories` | Exporter en JSON (project scoping) |
| `configure_decay` | Configurer les règles de decay par tag |
| `get_system_snapshot` | État holistique du système (core memories, patterns, health) |

### 🔗 Graphe de connaissances

| Tool | Description |
|------|-------------|
| `get_graph_stats` | Statistiques du graphe de code |
| `traverse_graph` | Parcours du graphe |
| `find_path` | Plus court chemin entre deux nœuds |
| `get_module_data` | Données d'un module |
| `get_related_memories` | Mémoires liées |
| `get_memory_graph` | Graphe d'une mémoire |

### 📦 Indexation

| Tool | Description |
|------|-------------|
| `index_project` | Indexer un projet complet (code) |
| `reindex_file` | Réindexer un fichier |
| `index_incremental` | Indexation incrémentale |
| `index_markdown_workspace` | Indexer un workspace Markdown |
| `get_indexing_status` | État de l'indexation |
| `get_indexing_errors` | Erreurs d'indexation |
| `retry_indexing` | Réessayer les échecs |

### 📊 Analytics

| Tool | Description |
|------|-------------|
| `get_memory_health` | Santé du système de mémoire |
| `get_cache_stats` | Statistiques du cache |
| `clear_cache` | Vider le cache |
| `get_indexing_stats` | Statistiques d'indexation |
| `switch_project` | Changer de projet actif |

### 💡 Prompts MCP

| Prompt | Description |
|--------|-------------|
| `analyze_codebase` | Analyser l'architecture et les patterns du code |

### Signatures détaillées (inputSchema)

> **Note** : Les signatures ci-dessous décrivent les 8 outils les plus utilisés et sont stables. Pour la liste canonique complète avec inputSchema exact, appeler `tools/list` sur le MCP Server (port 8002).
> Les 21 autres outils (graphe, indexation, analytics) sont également accessibles via `tools/list`.

#### 🔍 `search_memory`

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `query` | `string` | ✅ | Texte de recherche (phrase, mots-clés, question) |
| `limit` | `number` | ❌ (défaut: 10) | Nombre max de résultats |
| `tags` | `string[]` | ❌ | Filtrer par tags exacts |
| `memory_type` | `string` | ❌ | Filtrer par type (`investigation`, `article`, `note`, `quintessence`) |

**Exemple MCP :**
```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_memory","arguments":{"query":"boycott arme economique","limit":5,"memory_type":"investigation"}}}
```

#### 📖 `read_memory`

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `memory_id` | `string` (UUID) | ✅ | Identifiant unique de la mémoire |

**Exemple MCP :**
```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"read_memory","arguments":{"memory_id":"<UUID>"}}}
```

#### ✏️ `write_memory`

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `title` | `string` | ✅ | Titre explicite (max 255 chars) |
| `content` | `string` | ✅ | Contenu complet du texte |
| `memory_type` | `string` | ❌ (défaut: `note`) | Type : `investigation`, `article`, `note`, `quintessence` |
| `tags` | `string[]` | ❌ | Tags pour filtrage |
| `source_url` | `string` | ❌ | URL source facultative |

**Exemple MCP :**
```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"write_memory","arguments":{"title":"Analyse dette publique","content":"Contenu complet...","memory_type":"investigation","tags":["dette","économie"]}}}
```

#### 🔄 `update_memory`

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `memory_id` | `string` (UUID) | ✅ | Identifiant de la mémoire à modifier |
| `title` | `string` | ❌ | Nouveau titre |
| `content` | `string` | ❌ | Nouveau contenu |
| `tags` | `string[]` | ❌ | Nouveaux tags |

#### 🗑️ `delete_memory`

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `memory_id` | `string` (UUID) | ✅ | Identifiant de la mémoire à supprimer |

#### 🧠 `get_system_snapshot`

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| *(aucun)* | — | — | Retourne l'état complet du système |

**Exemple MCP :**
```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_system_snapshot","arguments":{}}}
```

#### 💻 `search_code`

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `query` | `string` | ✅ | Requête de recherche sémantique de code |
| `project` | `string` | ❌ | Filtrer par projet |
| `limit` | `number` | ❌ (défaut: 10) | Nombre max de résultats |

#### `write_code_memory`

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `file_path` | `string` | ✅ | Chemin du fichier source |
| `content` | `string` | ✅ | Contenu du code |
| `language` | `string` | ❌ | Langage (auto-détecté si omis) |
| `project` | `string` | ❌ | Projet associé |

---

## 3. API REST (port 8001) — Accès direct

Documentation Swagger interactive : `http://localhost:8001/docs`

### Endpoints principaux

#### Mémoires

| Méthode | Route | Description |
|---------|-------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/memories/stats` | Statistiques |
| `GET` | `/api/v1/memories/recent` | Mémoires récentes |
| `POST` | `/api/v1/memories` | Créer une mémoire |
| `GET` | `/api/v1/memories/{id}` | Lire une mémoire |
| `PUT` | `/api/v1/memories/{id}` | Mettre à jour |
| `DELETE` | `/api/v1/memories/{id}` | Supprimer |
| `GET` | `/api/v1/memories/search?query=...` | Rechercher (GET) |
| `POST` | `/api/v1/memories/search` | Rechercher (POST, avec body) |
| `GET` | `/api/v1/memories/export` | Exporter |
| `GET` | `/api/v1/memories/embeddings/health` | Santé des embeddings |

#### Recherche code

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/v1/code/search/hybrid` | Recherche code hybride |

### Exemples curl

```bash
# Écrire une mémoire
curl -s -X POST http://localhost:8001/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Titre de la mémoire",
    "content": "Contenu complet...",
    "memory_type": "investigation",
    "tags": ["truth-engine", "sujet"]
  }'

# Lire une mémoire (remplacer UUID)
curl -s http://localhost:8001/api/v1/memories/<UUID>

# Rechercher
curl -s "http://localhost:8001/api/v1/memories/search?query=boycott+economique&limit=5"

# Health check
curl -s http://localhost:8001/health | python3 -m json.tool
```

---

## 4. CLI `mnemo` — Usage rapide

Le CLI `mnemo` est disponible à `/home/giak/.local/bin/mnemo`.

```bash
# Vérifier l'état
mnemo health
mnemo status          # → 37 000+ mémoires, DB OK, Redis OK

# Rechercher
mnemo search "bureaucratie dette" --limit 5

# Écrire
mnemo write --title "Titre" --content "Contenu..." --tags "tag1,tag2" --type investigation

# Aide
mnemo --help
mnemo search --help
mnemo write --help
```

---

## 5. Cas d'usage typiques

### A. Sauvegarder un fichier d'enquête

```bash
# Via CLI (fichiers < 10KB recommandé)
mnemo write --title "Titre de l'enquête" \
  --content "$(cat /chemin/vers/fichier.md | head -c 10000)" \
  --tags "truth-engine,sujet" \
  --type investigation

# Via API (tous fichiers, même >50KB — recommandé)
curl -s -X POST http://localhost:8001/api/v1/memories \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"Titre\",
    \"content\": $(python3 -c "import json; print(json.dumps(open('/chemin/fichier.md').read()))"),
    \"memory_type\": \"investigation\",
    \"tags\": [\"truth-engine\"]
  }"
```

### B. Rechercher des informations

```bash
# Mot-clé simple
mnemo search "boycott"

# Phrase spécifique
mnemo search "arme economique asymetrique"

# Requête transversale complexe (multi-sujets)
mnemo search "Quels sont les points communs entre le boycott economique et la saturation administrative?"
```

### C. Cycle complet (write → read → search → delete)

```python
import requests

API = "http://localhost:8001/api/v1/memories"

# Create
resp = requests.post(API, json={
    "title": "Test mémoire",
    "content": "Contenu de test...",
    "memory_type": "note",
    "tags": ["test"]
})
mem_id = resp.json()["id"]

# Read
resp = requests.get(f"{API}/{mem_id}")
print(resp.json()["title"])

# Search
test = requests.get(f"{API}/search", params={"query": "Test mémoire", "limit": 5})

# Delete
requests.delete(f"{API}/{mem_id}")
```

### D. Sauvegarde en masse de fichiers

```python
import requests, pathlib

API = "http://localhost:8001/api/v1/memories"

for path in pathlib.Path(".").rglob("*.md"):
    content = path.read_text(encoding="utf-8")
    requests.post(API, json={
        "title": path.stem,
        "content": content,
        "memory_type": "investigation",
        "tags": ["truth-engine", "investigation"],
    }, timeout=300)  # Timeout long pour les gros fichiers
```

---

## 6. Dépannage

### Le MCP ne répond pas

```bash
# Vérifier que le conteneur tourne
docker compose ps
# → mcp doit être "Up (healthy)"

# Vérifier les logs
docker compose logs mcp --tail 20

# Redémarrer
docker compose restart mcp
```

### L'API ne répond pas

```bash
# Vérifier le health check
curl http://localhost:8001/health

# Vérifier les logs
docker compose logs api --tail 30

# Redémarrer
docker compose restart api
```

### Recherche retourne 500

Les causes possibles :
- **Routage GET vs POST** : Corrigé (GET /search défini avant GET /{memory_id})
- **Dimensions vectorielles incompatibles** (code search uniquement) : 768 vs 1024

  ⚠️ **`search_code` (outil MCP) peut échouer** à cause de ce décalage (certains chunks ont été embeddés avec un modèle différent).
  - **Contournement** : Utiliser `search_memory` (MCP) ou `POST /api/v1/memories/search` (REST) — la recherche texte fonctionne parfaitement.
  - **Correction** : Réindexer le code via l'API (`POST /v1/code/reindex`) ou redémarrer l'indexation depuis l'UI.

- **Timeout embedding** : Les fichiers >20KB peuvent prendre >30s. Utiliser `timeout=300` dans les appels API

### La commande `mnemo memories` échoue avec AttributeError

⚠️ **Bug connu** : `mnemo memories` peut échouer avec une `AttributeError`.
- **Cause** : Régression dans la sérialisation des métadonnées lors de l'affichage.
- **Contournement** : Utiliser `mnemo search` ou `curl http://localhost:8001/api/v1/memories/search?query=<terme>` à la place.
- **Correction** : En cours — l'API REST fonctionne parfaitement en attendant.

### Le CLI `mnemo` est introuvable

```bash
export PATH=$PATH:/home/giak/.local/bin
echo 'export PATH=$PATH:/home/giak/.local/bin' >> ~/.bashrc
```

---

### Variables d'environnement

> En local standard, **aucune configuration nécessaire** — Docker Compose expose automatiquement les ports 8001 et 8002.

Pour des déploiements personnalisés (hôte distant, ports modifiés) :

| Variable | Défaut | Quand la définir ? |
|----------|--------|-------------------|
| `MCP_URL` | `http://localhost:8002/mcp` | Si le MCP Server est sur un autre hôte/port |
| `API_URL` | `http://localhost:8001` | Si l'API REST est sur un autre hôte/port |
| `MNEMO_BIN_DIR` | `$HOME/.local/bin` | Si `mnemo` CLI n'est pas dans le PATH |

> **Règle** : En local standard, **rien à configurer**. Lance `docker compose up -d` et les deux ports (8001, 8002) sont exposés automatiquement.

---

## 7. Référence rapide

```
# Services Docker
mnemo-api      → port 8001 (REST API + Swagger docs)
mnemo-mcp      → port 8002 (MCP SSE)
mnemo-postgres → port 5432 (base de données + pgvector)
mnemo-redis    → port 6379 (cache)
mnemo-worker   → worker asynchrone

# CLI
mnemo health       → État du serveur
mnemo status       → Statistiques (nb mémoires, uptime)
mnemo search       → Recherche textuelle
mnemo write        → Créer une mémoire

# API
GET  /health              → Health check
GET  /api/v1/memories/search?query=  → Rechercher
POST /api/v1/memories     → Créer
GET  /api/v1/memories/{id} → Lire
DELETE /api/v1/memories/{id} → Supprimer

# MCP Tools (29)
search_memory, search_code, write_memory, read_memory,
update_memory, delete_memory, consolidate_memory,
mark_consumed, rate_memory, export_memories,
get_system_snapshot, configure_decay,
get_graph_stats, traverse_graph, find_path,
get_related_memories, get_memory_graph,
index_project, reindex_file, index_incremental,
index_markdown_workspace, get_indexing_status,
get_indexing_errors, retry_indexing, clear_cache,
get_indexing_stats, get_memory_health,
get_cache_stats, switch_project, ping
```

## 8. Registre des conventions de tags (EPIC-60)

Registre central des conventions de tags, appliqué au write (validation **douce**, jamais bloquante : un écart produit un `tag_warnings` dans la réponse, pas une erreur).

### Règle générale

- Les tags sont en **minuscules**, sauf le namespace `status` dont la casse canonique est **MAJUSCULE** : `status:CONFIRME`.
- Un tag avec `:` doit utiliser un namespace réservé (ci-dessous). Un namespace inconnu (`foo:bar`) déclenche un warning et le tag est conservé tel quel.
- Un tag sans `:` est un tag libre (aucune contrainte).

### Namespaces réservés

| Namespace | Casse / vocabulaire | Exemples |
|---|---|---|
| `status:*` | Valeur MAJUSCULE, vocabulaire contraint : `CONFIRME`, `DOUTE`, `REFUTE`, `VERIFIE` | `status:CONFIRME` |
| `fact:*` | **Obsolète** : `fact:verifie` est remplacé automatiquement par `status:CONFIRME` (warning informatif) | `fact:verifie` → `status:CONFIRME` |
| `project:*` | Valeur libre (nom de projet) | `project:truth-engine` |
| `sys:*` | Valeur libre (tags système : history, core, anchor, pattern, drift...) | `sys:history`, `sys:core` |
| `session:*` | Valeur libre (auto-import) | `session:<uuid>` |
| `date:*` | Valeur libre (auto-import, format YYYYMMDD) | `date:20251030` |
| `source:*` | Valeur libre (auto-import) | `source-s3` (tag libre), `source:chatgpt` |

Namespaces **réservés mais non standardisés** (à venir, non observés en base) : `kind:*`, `memory:*`. Leur utilisation déclenche un warning « namespace inconnu » tant qu'ils ne sont pas standardisés.

### Tags documentés (hors namespace)

- `kernel` (et variantes `kernel-v2`, `kernel-apex`...) : mémoire issue du pipeline KERNEL. Une mémoire taguée `kernel*` **sans** tag `status:*` déclenche un warning (statut forensique manquant).
- Tags techniques d'import : `claude-code`, `auto-imported`, `auto-saved`, `investigation`, `truth-engine`, `livre-cst`, `polarite-*`, `discriminant-*`.

### Normalisation appliquée au write

- `status:confirme` → `status:CONFIRME` (casse normalisée, warning au tool MCP).
- `fact:verifie` → `status:CONFIRME` (obsolète ; remplacé par le modèle `MemoryCreate`/`MemoryUpdate`, donc sur tous les points d'écriture ; warning au tool MCP).
- Trim + déduplication des tags (modèle `MemoryCreate`/`MemoryUpdate`).
- Warning non bloquant (`tag_warnings` dans la réponse) : namespace inconnu, statut inconnu, mémoire `kernel*` sans `status:*`, casse normalisée.

---

*Guide manuel — Dernière mise à jour : 2026-08-07 (ajout section 8 : registre des tags EPIC-60)*
