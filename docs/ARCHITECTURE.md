# Architecture MnemoLite

> **Statut :** DECISION | **Mis à jour :** 2026-04-03

## 1. Topologie du système

MnemoLite est un **système à double visage** : il sert à la fois d'API REST pour une interface web et de serveur MCP (Model Context Protocol) pour les agents IA. Les deux partagent la même couche de données mais tournent dans des processus séparés avec des cycles de vie indépendants.

```mermaid
graph TB
    subgraph "Clients externes"
        Browser[Navigateur Web]
        Claude[Client MCP / IA]
    end

    subgraph "Frontend"
        FE[Frontend Vue 3 Vite dev :3000 Nginx prod :80]
    end

    subgraph "Backend"
        API[API REST FastAPI :8001]
        MCP[Serveur MCP FastMCP :8002]
    end

    subgraph "Données"
        PG[(PostgreSQL 18 pgvector 0.8 pg_trgm)]
        Redis[(Redis 7 Cache L2)]
    end

    subgraph "Arrière-plan"
        Worker[Worker conversation]
    end

    subgraph "Observabilité"
        OObserve[OpenObserve :5080]
    end

    subgraph "Hôte (non-Docker)"
        LMStudio[LM Studio :1234]
    end

    Browser --> FE
    FE --> API
    Claude --> MCP
    API --> PG
    API --> Redis
    MCP --> PG
    MCP --> Redis
    Worker --> Redis
    Worker --> API
    API -.-> OObserve
    MCP -.-> OObserve
    API -.->|http host.docker.internal:1234| LMStudio
    MCP -.->|http host.docker.internal:1234| LMStudio

    style PG fill:#336791,color:#fff
    style Redis fill:#DC382D,color:#fff
    style LMStudio fill:#FF6B35,color:#fff
```

**Pourquoi deux processus séparés ?** L'API REST parle HTTP aux navigateurs (CORS, sessions). Le serveur MCP parle JSON-RPC en stdio ou Streamable HTTP — un protocole fondamentalement différent. Les exécuter séparément signifie que le serveur MCP peut être utilisé par Claude Desktop sans avoir besoin de l'API REST, et inversement. Ils ne partagent **aucun code à l'exécution** — chacun initialise ses propres pools de connexion, services et caches.

**Isolation réseau :** Deux réseaux Docker isolent le trafic. `backend` connecte API, MCP, Worker, PostgreSQL et Redis. `frontend` connecte Frontend, API, MCP et OpenObserve. PostgreSQL et Redis ne sont **jamais** exposés au réseau frontend.

## 2. Le pattern Lifespan — Comment les services s'initialisent

L'API et le serveur MCP utilisent le **pattern lifespan asynchrone** — pas de singletons au niveau module, pas d'initialisation paresseuse à la première requête. Chaque service est soit entièrement prêt avant la première requête, soit le démarrage échoue rapidement (services critiques) ou se dégrade gracieusement (services optionnels).

```mermaid
sequenceDiagram
    participant U as Uvicorn
    participant L as Lifespan
    participant P as PostgreSQL 18
    participant R as Redis
    participant E as Modèles d'embedding
    participant S as Services

    U->>L: async with lifespan(app)
    L->>P: create_async_engine pool=20
    P-->>L: connexion OK
    L->>R: RedisCache.connect()
    R-->>L: PONG
    L->>E: preload_models()
    E-->>L: TEXT + CODE chargés (~660 MB)
    L->>S: alert_monitoring_task créé
    L-->>U: prêt (yield)

    Note over U,S: Requêtes servies ici

    U->>L: signal d'arrêt
    L->>E: suppression modèles
    L->>R: déconnexion
    L->>P: engine.dispose()
    L->>S: tâche annulée
    L-->>U: nettoyage terminé
```

**Décision critique :** `app.state` est le localisateur de services. Chaque service initialisé pendant le lifespan est stocké sur `app.state` et récupéré par les fonctions `Depends()` de FastAPI. Le serveur MCP fait la même chose avec un dictionnaire `services` injecté via `inject_services()`.

**Modes de défaillance au démarrage :**

| Service | Comportement en cas d'échec | Raison |
|---------|---------------------------|--------|
| PostgreSQL | Engine = `None`, requêtes → 503 | Impossible de fonctionner sans DB |
| Redis | Warning loggé, `redis_cache = None` | Optionnel — le cache se rabat sur la DB |
| Modèles d'embedding | Prod : `RuntimeError`. Dev : warning | Correction prod vs vélocité dev |
| Serveurs LSP | Warning loggé, `None` | Optionnel — l'indexation fonctionne sans |
| Service d'alertes | Warning, tâche non démarrée | L'observabilité n'est pas critique |
| LM Studio | Skip silencieux, fallback recherche brute | L'extraction est optionnelle, la recherche fonctionne sans |

## 3. Le pipeline de recherche hybride

C'est la partie la plus significative architecturalement. Le pipeline de recherche n'est **pas** une simple requête — c'est une orchestration multi-étapes avec exécution parallèle, cache et chemins de repli.

### 3.1 Recherche de code

```mermaid
flowchart TD
    Q[Requête] --> CC{Cache L2 HIT?}
    CC -->|HIT| RC[Réponse en cache]
    CC -->|MISS| PE[Exécution parallèle]

    subgraph "Recherche parallèle"
        L[Recherche lexicale pg_trgm]
        V[Recherche vectorielle HNSW]
    end

    PE --> L
    PE --> V
    L --> F[Fusion RRF k=60]
    V --> F
    F --> R{Rerank BM25?}
    R -->|Oui| B[BM25 top-30]
    R -->|Non| Res
    B --> Res[Résultat final]
    Res --> CP[Cache L2 TTL=120s]
    CP --> Resp[Réponse]
    RC --> Resp

    style L fill:#4CAF50,color:#fff
    style V fill:#2196F3,color:#fff
    style F fill:#FF9800,color:#fff
    style B fill:#9C27B0,color:#fff
```

**Exécution parallèle :** Les recherches lexicale et vectorielle démarrent simultanément via `asyncio.gather()`. Aucune n'attend l'autre.

**Pourquoi RRF plutôt que la normalisation des scores ?** Les scores lexicaux (similarité trigramme 0.0–1.0) et vectoriels (distance cosinus 0.0–2.0) vivent sur des **échelles incomparables**. Les normaliser nécessiterait de connaître la distribution des scores de tout le corpus. RRF contourne le problème : il ne regarde que la **position dans le classement**, pas les scores absolus. La formule `1 / (k + rang)` avec `k=60` est le standard industriel.

**Le compromis BM25 :** Après la fusion RRF, les 30 meilleurs candidats sont rerankés avec BM25 — une implémentation pure Python sans dépendances ML. Choisi plutôt qu'un cross-encoder car :
- Le cross-encoder nécessiterait ~500 MB de modèle supplémentaire
- Le cold start serait de 10-15 secondes
- BM25 est ~100× plus rapide pour 20 documents
- La différence de qualité est marginale pour la recherche de code

### 3.2 Recherche de mémoires

Même architecture RRF, mais avec des sources de données différentes :

```mermaid
flowchart LR
    subgraph "Lexical mémoires"
        I[ILIKE titre + source]
        T[pg_trgm similarité GIN]
    end
    subgraph "Vectoriel mémoires"
        H[HNSW halfvec index]
    end
    subgraph "Entités et tags (EPIC-28)"
        E[JSONB containment @>]
        G[Tag overlap ANY]
    end
    I --> MF[Fusion RRF 4 sources]
    T --> MF
    H --> MF
    E --> MF
    G --> MF
    MF --> MD[Decay temporel]
    MD --> MR[Rerank BM25 optionnel]
    MR --> ResM[Résultat mémoire]
```

**Différence clé :** La recherche mémoire applique un **decay temporel** après le reranking. Le `MemoryDecayService` applique un decay exponentiel basé sur `created_at` — les anciennes mémoires obtiennent progressivement des scores plus bas. Configurable par tag via `configure_decay()`, permettant aux mémoires `sys:core` d'être permanentes (decay=0.0) tandis que `sys:history` decay avec une demi-vie de ~14 jours.

**Recherche intentionnelle (EPIC-28) :** Avant la recherche, un LLM local (LM Studio) décompose la requête en **HL keywords** (concepts abstraits) et **LL keywords** (entités concrètes). Les HL keywords orientent la recherche vectorielle, les LL keywords alimentent deux recherches supplémentaires — containment JSONB sur les entités et overlap sur les tags (manuels + auto-générés). La fusion RRF passe de 2 à 4 sources avec des poids normalisés dynamiquement. Si le LLM n'est pas disponible, le système se rabat silencieusement sur la recherche brute (comportement antérieur).

## 4. Architecture du cache à trois couches

Le cache n'est pas une couche unique — c'est une **cascade** avec promotion automatique :

```mermaid
flowchart TD
    Req[Requête] --> L1{L1 Mémoire LRU 100 MB}
    L1 -->|HIT <0,01ms| R1[Retour immédiat]
    L1 -->|MISS| L2{L2 Redis 2 GB TTL=300s}
    L2 -->|HIT 1-5ms| Pr[Promotion vers L1]
    Pr --> R2[Retour]
    L2 -->|MISS| L3[PostgreSQL 100-200ms]
    L3 --> WT[Write-through L1 + L2]
    WT --> R3[Retour]

    style L1 fill:#4CAF50,color:#fff
    style L2 fill:#FF9800,color:#fff
    style L3 fill:#2196F3,color:#fff
```

**Stratégie de clé de cache :** `chunks:{chemin_fichier}:{md5(code_source)}`. Le hash MD5 du code source est inclus pour que **tout changement de code invalide le cache automatiquement** — pas d'invalidation manuelle nécessaire pour les changements de contenu.

**Taux de hit combiné :** `L1 + (1 - L1) × L2`. Si L1 a 70 % de hit rate et L2 a 80 % sur les 30 % restants, le taux effectif est `70 % + (30 % × 80 %) = 94 %`.

## 5. Architecture duale d'embedding — Pourquoi deux modèles

Le système utilise **deux modèles d'embedding simultanément**, chacun optimisé pour un domaine différent :

| Modèle | Domaine | Paramètres | Dimensions | RAM |
|--------|---------|-----------|------------|-----|
| nomic-ai/nomic-embed-text-v1.5 | Texte (docs, conversations) | 137M | 768 | ~260 MB |
| jinaai/jina-embeddings-v2-base-code | Code (fonctions, classes) | 161M | 768 | ~400 MB |

**Pourquoi pas un seul modèle ?** Les modèles texte généraux performent mal sur le code car ils ne comprennent pas la sémantique des langages de programmation. Les modèles code ne comprennent pas bien les requêtes en langage naturel. En maintenant les deux, le système peut :
- Rechercher du code avec des embeddings code (capture la structure sémantique)
- Rechercher du code avec des embeddings texte (capture les docstrings, commentaires)
- Fusionner les deux résultats via RRF pour une couverture complète

**L'optimisation halfvec :** Les embeddings sont stockés en `vector(768)` (float32, 3 KB par embedding) mais **recherchés** via des colonnes `halfvec(768)` (float16, 1,5 KB). Un trigger PostgreSQL (`sync_halfvec_embeddings`) convertit automatiquement float32 → halfvec à l'INSERT/UPDATE. Cela donne :
- 50 % de réduction de stockage par ligne
- 50 % de réduction de taille d'index HNSW
- 99,2 % de rappel conservé
- 2× d'amélioration du QPS des requêtes

**Circuit breakers indépendants :** Chaque modèle a son propre circuit breaker (seuil=5 échecs, récupération=60s). Si le modèle CODE échoue, le modèle TEXT continue de fonctionner.

**Mode mock :** Quand `EMBEDDING_MODE=mock`, le service génère des vecteurs aléatoires déterministes à partir du hash du texte. Cela permet de tester sans télécharger 660 MB de modèles.

## 6. Inversion de dépendance — La couche Protocol

Le système utilise des classes `Protocol` Python pour définir des interfaces, puis des implémentations concrètes sont injectées via `Depends()` de FastAPI :

```mermaid
flowchart TD
    subgraph "Interfaces (protocoles)"
        EP[EventRepositoryProtocol]
        ESP[EmbeddingServiceProtocol]
        MSSP[MemorySearchServiceProtocol]
    end

    subgraph "Implémentations concrètes"
        ER[EventRepository]
        DES[DualEmbeddingService]
        DEA[DualEmbeddingServiceAdapter]
        MSS[MemorySearchService]
    end

    subgraph "Routes"
        RT[Route Handlers]
    end

    EP -.-> ER
    ESP -.-> DES
    ESP -.-> DEA
    MSSP -.-> MSS

    RT -->|Depends| EP
    RT -->|Depends| ESP
    RT -->|Depends| MSSP

    DEA -.->|enveloppe| DES

    style EP fill:#9C27B0,color:#fff
    style ESP fill:#9C27B0,color:#fff
    style DEA fill:#FF9800,color:#fff
```

**Le pattern Adapter pour DualEmbeddingService :** Le `DualEmbeddingService` a une API différente (`generate_embedding(text, domain)` retournant `Dict[str, List[float]]`) que le `EmbeddingServiceProtocol` legacy (`generate_embedding(text)` retournant `List[float]`). Le `DualEmbeddingServiceAdapter` enveloppe le service dual et traduit les appels — le code existant fonctionne sans changement.

**Le serveur MCP n'utilise pas `Depends()` de FastAPI :** Il construit un dictionnaire `services` pendant le lifespan et l'injecte dans chaque outil/ressource via `tool.inject_services(services)`. C'est parce que les outils FastMCP ne participent pas au système d'injection de dépendances de FastAPI.

## 7. Schéma de base de données

```mermaid
erDiagram
    events {
        UUID id PK
        TEXT title
        TEXT body
        JSONB metadata
        TIMESTAMPTZ created_at
        vector(768) embedding
        TEXT embedding_model
    }

    memories {
        UUID id PK
        TEXT title
        TEXT content
        TEXT memory_type
        TEXT[] tags
        TEXT author
        UUID project_id
        vector(768) embedding
        halfvec(768) embedding_half
        TEXT embedding_source
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
        TIMESTAMPTZ deleted_at
        TIMESTAMPTZ consumed_at
        UUID[] related_chunks
        JSONB resource_links
        JSONB entities
        JSONB concepts
        TEXT[] auto_tags
    }

    code_chunks {
        UUID id PK
        TEXT file_path
        TEXT language
        TEXT chunk_type
        TEXT name
        TEXT name_path
        TEXT source_code
        INT start_line
        INT end_line
        vector(768) embedding_text
        vector(768) embedding_code
        halfvec(768) embedding_text_half
        halfvec(768) embedding_code_half
        JSONB metadata
        TEXT repository
        TEXT return_type
        UUID node_id
        TIMESTAMPTZ indexed_at
    }

    graph_nodes {
        UUID id PK
        UUID chunk_id FK
        TEXT qualified_name
        TEXT node_type
        TEXT language
        JSONB lsp_data
    }

    graph_edges {
        UUID id PK
        UUID source_id FK
        UUID target_id FK
        TEXT relationship_type
    }

    alerts {
        UUID id PK
        TEXT alert_type
        TEXT severity
        TEXT message
        JSONB metadata
        TIMESTAMPTZ created_at
    }

    alert_rules {
        UUID id PK
        TEXT name
        TEXT alert_type
        FLOAT threshold
        TEXT severity
        INT cooldown_seconds
        BOOLEAN enabled
        JSONB metadata
    }

    metrics {
        UUID id PK
        TEXT metric_type
        FLOAT value
        JSONB metadata
        TIMESTAMPTZ recorded_at
    }

    events ||--o{ memories : "génère"
    code_chunks ||--o{ graph_nodes : "lié à"
    graph_nodes ||--o{ graph_edges : "source"
    graph_nodes ||--o{ graph_edges : "cible"
```

**Décisions clés du schéma :**

- **Table `events`** est le store original — c'était la première table. Les mémoires ont été dérivées plus tard via l'`EventProcessor`. Le `MemoryRepository` utilise SQLAlchemy Core (pas d'ORM) pour le contrôle SQL brut, surtout pour les opérations pgvector.

- **Table `memories`** a à la fois `embedding` (float32 vector) et `embedding_half` (float16 halfvec). Le trigger les garde synchronisés. Le champ `embedding_source` est un résumé textuel focalisé utilisé pour calculer les embeddings — séparé du `content` complet — permettant une meilleure qualité d'embedding. Trois colonnes supplémentaires enrichissent les mémoires avec des métadonnées structurées : `entities` (JSONB, entités nommées), `concepts` (JSONB, concepts abstraits), et `auto_tags` (TEXT[], tags auto-générés). Les colonnes JSONB ont des index GIN `jsonb_path_ops` pour des requêtes de containment efficaces (`@>`).

- **Table `code_chunks`** a **quatre** colonnes d'embedding : `embedding_text`, `embedding_code` (float32, pour l'écriture) et `embedding_text_half`, `embedding_code_half` (float16, pour la lecture/recherche). Les colonnes `repository` et `return_type` sont **générées automatiquement** depuis les métadonnées JSONB — cela transforme une extraction JSONB O(n) en recherche B-tree O(log n).

- **Tables `graph_nodes` et `graph_edges`** forment le graphe de dépendance de code. Les nœuds sont extraits par tree-sitter (parsing) et les serveurs LSP (informations de type). Les arêtes représentent les relations `calls`, `imports`, `inherits`. Le graphe est parcouru via BFS pour la recherche de chemin et DFS pour la découverte d'appelants/appelés.

## 8. Le serveur MCP — Un second point d'entrée

Le serveur MCP n'est **pas** un wrapper autour de l'API REST. C'est un processus complètement séparé avec son propre :
- Pool de connexions DB (asyncpg, pas SQLAlchemy)
- Client Redis
- Instances de services
- Gestion du cycle de vie

```mermaid
flowchart TD
    subgraph "Processus Serveur MCP"
        FMCP[FastMCP Server]
        LSP[server_lifespan]
        TO[Outils 30]
        RE[Ressources 12]
        PR[Prompts]

        subgraph "Dictionnaire de services"
            SDB[db: pool asyncpg]
            SR[redis: client aioredis]
            SE[embedding_service]
            SCI[code_indexing_service]
            SCC[chunk_cache: CascadeCache]
            SMR[memory_repository]
            SMS[hybrid_memory_search]
            SG[graph_traversal_service]
            SM[metrics_collector]
            SLM[lm_studio_client]
            SEE[entity_extraction_service]
            SQU[query_understanding_service]
        end

        LSP --> SDB
        LSP --> SR
        LSP --> SE
        LSP --> SCI
        LSP --> SCC
        LSP --> SMR
        LSP --> SMS
        LSP --> SG
        LSP --> SM
        LSP --> SLM
        LSP --> SEE
        LSP --> SQU

        SDB --> TO
        SR --> TO
        SE --> TO
        SCI --> TO
        SCC --> TO
        SMR --> TO
        SMS --> TO
        SG --> TO
        SM --> TO

        TO --> FMCP
        RE --> FMCP
        PR --> FMCP
    end

    Claude[Client IA / MCP] -->|stdio ou HTTP| FMCP
```

**Pourquoi asyncpg directement plutôt que SQLAlchemy ?** Le serveur MCP utilise asyncpg brut car il n'a pas besoin des fonctionnalités ORM de SQLAlchemy — il a juste besoin d'un pool de connexions et d'exécution SQL brute. Cela réduit l'empreinte mémoire (important pour la limite de 8 GB du container) et évite le surcoût d'initialisation de SQLAlchemy.

## 9. Communication Frontend vers API

```mermaid
flowchart LR
    Br[Navigateur :3000] -->|GET /api/v1/*| Vi[Vite Dev Server]
    Br -->|GET /mcp| Vi
    Vi -->|proxy /api → :8001| AP[FastAPI :8001]
    Vi -->|proxy /v1 → :8001| AP
    Vi -->|proxy /health → :8001| AP
    Vi -->|proxy /mcp → :8002| MC[FastMCP :8002]

    style Vi fill:#646BFF,color:#fff
    style AP fill:#009688,color:#fff
    style MC fill:#9C27B0,color:#fff
```

**Stratégie de proxy :** En développement, le serveur Vite proxy toutes les requêtes API pour éviter les problèmes CORS. Le code frontend utilise des **chemins relatifs** (`/api/v1/...`) — le proxy Vite les réécrit vers `http://localhost:8001/api/v1/...`. En production, le container Nginx sert les fichiers statiques construits et proxy les requêtes API directement.

**Deux profils frontend :** `docker compose --profile dev` lance le serveur Vite avec HMR. `docker compose --profile prod` lance un container Nginx pré-construit. Ils sont mutuellement exclusifs.

## 10. Modes de défaillance et dégradation gracieuse

Le système est conçu pour **se dégrader gracieusement** à chaque couche :

```mermaid
flowchart TD
    subgraph "Scénarios de panne"
        F1[PostgreSQL HS]
        F2[Redis HS]
        F3[Modèle embedding OOM]
        F4[LSP crash]
        F5[BM25 erreur]
        F6[Timeout vectoriel]
        F7[LM Studio indisponible]
    end

    subgraph "Chemins de dégradation"
        D1[Toutes requêtes → 503]
        D2[Cache miss → DB directe]
        D3[Circuit breaker ouvert → mode mock]
        D4[Extraction type ignorée]
        D5[Ordre RRF utilisé]
        D6[Repli lexical seul]
        D7[Recherche brute (sans HL/LL)]
    end

    F1 --> D1
    F2 --> D2
    F3 --> D3
    F4 --> D4
    F5 --> D5
    F6 --> D6
    F7 --> D7
```

**Le chemin de dégradation le plus important :** Si la recherche vectorielle est activée mais aucun embedding n'est disponible (modèle non chargé, circuit breaker ouvert, mode mock), le système **se rabat silencieusement sur la recherche lexicale seule** avec un warning dans les logs. L'utilisateur obtient des résultats — juste pas les sémantiques. C'est mieux que de retourner une erreur.

**L'échec Redis est invisible :** Si Redis est HS au démarrage, le warning est loggé et `app.state.redis_cache = None`. Tous les checks de cache deviennent des no-ops — le système interroge PostgreSQL directement. Aucune erreur n'est lancée à l'utilisateur.

## 11. Caractéristiques de scaling

| Couche | Actuel | Limite de scaling | Goulot d'étranglement |
|--------|--------|-------------------|----------------------|
| API (uvicorn) | 1 worker, 2 CPU, 24 GB RAM | Horizontal (workers multiples) | CPU pour génération d'embeddings |
| Serveur MCP | 1 instance, 1 CPU, 8 GB RAM | Horizontal (stateless) | Taille du pool de connexions (10) |
| PostgreSQL 18 | 1 CPU, 2 GB RAM, pool=20 | Read replicas, pool de connexions | Scan d'index HNSW sur gros datasets |
| Redis | 1 instance | Redis Cluster | Mémoire (config 2 GB) |
| Modèles d'embedding | CPU-only, chargés à la demande | Accélération GPU | RAM (660 MB par instance) |
| Serveurs LSP | 2 processus (Python + TS) | Isolation par workspace | Mémoire processus (~200 MB chacun) |

**Le goulot d'étranglement de la génération d'embeddings :** Générer un seul embedding prend 50-200 ms sur CPU. Pour un projet de 1000 fichiers avec 50 000 chunks, l'indexation complète prend des heures. Le système mitige cela avec :
- Encodage par batch (10-50× plus rapide que les appels individuels)
- Indexation incrémentale (seulement les fichiers modifiés)
- Redis Streams pour l'indexation en arrière-plan (EPIC-27)
- `torch.no_grad()` pour empêcher l'accumulation de mémoire

**Scaling de l'index HNSW :** L'index HNSW sur les colonnes halfvec avec `m=16, ef_construction=128` gère ~100k chunks efficacement. Au-delà, `ef_search` doit être augmenté (actuellement 100) pour un meilleur rappel, ce qui augmente la latence linéairement.

## 12. Résumé des compromis

| Décision | Sacrifié | Gagné |
|----------|----------|-------|
| SQLAlchemy Core plutôt qu'ORM | Ergonomie développeur, sécurité des types | Contrôle SQL brut pour pgvector, requêtes plus rapides |
| Localisateur `app.state` plutôt que container DI | Testabilité, explicitation | Simplicité, pas de dépendance supplémentaire |
| Deux processus séparés (API + MCP) | Efficacité des ressources | Cycles de vie indépendants, isolation des protocoles |
| RRF plutôt que normalisation des scores | Optimalité théorique | Pas besoin de distribution des scores du corpus |
| BM25 plutôt que cross-encoder | Qualité de reranking | Zéro dépendance ML, démarrage instant, 100× plus rapide |
| halfvec pour la recherche, vector pour l'écriture | CPU à la conversion | 50 % de stockage, 2× de QPS |
| Hash MD5 dans les clés de cache | Surcoût de calcul | Invalidation automatique basée sur le contenu |
| Chargement paresseux des modèles | Cold start à la première requête | Démarrage plus rapide, modèles chargés si nécessaire |
| Mode mock d'embedding | Réalisme des tests | Pas de téléchargement de modèles pour CI/CD |
| Triggers PostgreSQL pour sync halfvec | Calcul côté DB | Zéro changement de code app pour halfvec |
| Colonnes générées depuis JSONB | Surcoût de stockage (données redondantes) | Recherches O(log n) au lieu de O(n) |
| Circuit breakers indépendants par modèle | Gestion d'état légèrement plus complexe | Les échecs ne se propagent pas entre domaines |
| LLM local (LM Studio) pour l'extraction | Dépendance externe, latence 1-2s | Entités/concepts structurés, recherche intentionnelle |
| Extraction async non-bloquante | Délai entre création et extraction | Zéro impact sur la latence de création de mémoire |
| RRF 4 sources au lieu de 2 | Complexité accrue du pipeline | Meilleur rappel via entités et tags auto-générés |
