# MnemoLite Architecture

**Version:** v5.0.0-dev  
**API Docs:** [http://localhost:8001/docs](http://localhost:8001/docs) | **MCP:** Streamable HTTP :8002

---

## Table des Matières

1. [Vue d'Ensemble](#1-vue-densemble)
2. [Architecture Système](#2-architecture-système)
3. [Flux de Recherche](#3-flux-de-recherche)
4. [Pipeline d'Indexation](#4-pipeline-dindexation)
5. [Recherche Hybride](#5-recherche-hybride)
6. [Mémoire Sémantique](#6-mémoire-sémantique)
7. [Graphe de Code](#7-graphe-de-code)
8. [Cache Triple-Layer](#8-cache-triple-layer)
9. [Schéma Base de Données](#9-schéma-base-de-données)
10. [MCP - 33 Outils](#10-mcp---33-outils)
11. [Déploiement](#11-déploiement)

---

## 1. Vue d'Ensemble

MnemoLite est un système cognitif de mémoire et d'intelligence de code **100% local**, built on PostgreSQL 18. Il combine recherche vectorielle hybride, analyse de graphe, et intégration MCP pour fournir une mémoire persistante aux agents IA.

### Fonctionnalités Clés

| Capacité | Description | Impact |
|----------|-------------|--------|
| **Mémoire Sémantique** | Stockage avec embeddings + decay temporel | Connaissance persistante |
| **Intelligence de Code** | Indexation AST, graphe de dépendances | Compréhension codebase |
| **Recherche Hybride** | Lexical + Vectoriel + RRF + Reranking | Résultats précis |
| **Intégration MCP** | 33 outils pour LLM (Claude, KiloCode) | Interface LLM native |
| **Cache Triple-Layer** | L1 → L2 → L3 avec fallback | Performance |

### Stack Technique

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MnemoLite v5.0.0-dev                        │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │  Vue 3   │  │  FastAPI │  │  MCP 1.12│  │  PostgreSQL 18    │   │
│  │   SPA    │  │  AsyncPG │  │  (33 tools)│  │  pgvector 0.8.1  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Embeddings: nomic-embed-text (768D) + jina-code (768D)   │   │
│  │  Indexation: tree-sitter (15+ langs) + LSP (Pyright)       │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture Système

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#4CAF50', 'primaryTextColor': '#fff', 'primaryBorderColor': '#388E3C', 'lineColor': '#666', 'secondaryColor': '#2196F3', 'tertiaryColor': '#9C27B0'}}}%%
graph TB
    subgraph "🐳 Docker Compose" 
        subgraph "🌐 Interface"
            Web["<b>Vue 3 SPA</b><br/>:3000"]
        end
        
        subgraph "⚙️ Backend Services"
            API["<b>FastAPI REST</b><br/>:8001"]
            MCP["<b>MCP Server</b><br/>Streamable HTTP :8002"]
        end
        
        subgraph "💾 Data Layer"
            Redis["<b>Redis 7</b><br/>Cache L2"]
            PG["<b>PostgreSQL 18</b><br/>pgvector 0.8.1"]
        end
    end

    subgraph "🤖 LLM Clients"
        Claude["Claude Desktop"]
        Kilo["KiloCode / OpenCode"]
    end

    Claude -->|"MCP JSON-RPC"| MCP
    Kilo -->|"MCP JSON-RPC"| MCP
    Web -->|"HTTP REST"| API
    
    API <-->|"Cache L1/L2"| Redis
    API <-->|"Queries + Vectors"| PG
    MCP <-->|"Cache + Data"| Redis
    MCP <-->|"Queries + Vectors"| PG

    classDef service fill:#4CAF50,stroke:#388E3C,color:#fff
    classDef data fill:#2196F3,stroke:#1976D2,color:#fff
    classDef client fill:#9C27B0,stroke:#7B1FA2,color:#fff
    
    class API,MCP service
    class Redis,PG data
    class Claude,Kilo client
```

### Services

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| **Frontend** | 3000 | HTTP | Vue 3 SPA avec design SCADA |
| **API REST** | 8001 | HTTP/HTTPS | FastAPI backend |
| **MCP Server** | 8002 | Streamable HTTP | 33 outils pour LLM |
| **PostgreSQL** | 5432 | TCP | Données + Vecteurs 768D |
| **Redis** | 6379 | TCP | Cache L2 + Sessions |
| **OpenObserve** | 5080 | HTTP | Logs + Traces + Metrics |

---

## 3. Flux de Recherche

```mermaid
sequenceDiagram
    autonumber
    participant Client as 🤖 LLM Client
    participant MCP as MCP Server
    participant API as FastAPI
    participant L1 as L1 Cache<br/>(In-Memory)
    participant L2 as L2 Cache<br/>(Redis)
    participant PG as PostgreSQL

    Client->>MCP: search_memory(query, filters)
    MCP->>API: POST /api/v1/memories/search

    API->>L1: GET cache key
    L1-->>API: Cache Hit?

    alt L1 Miss
        API->>L2: GET cache key
        L2-->>API: Cache Hit?
        
        alt L2 Miss
            API->>PG: SQL + Vector Query
            Note over PG: RRF Fusion<br/>BM25 Reranking
            PG-->>API: Ranked Results
            
            API->>L2: SET cache (TTL: 5min)
        else L2 Hit
            L2-->>API: Cached Results
        end
    end

    API->>L1: SET cache (TTL: 1min)
    API-->>MCP: {results, scores, meta}
    MCP-->>Client: Structured Response
```

### Chemins de Cache

| Hit | Latence | Source |
|-----|---------|--------|
| L1 | ~1ms | In-memory dict |
| L2 | ~10ms | Redis |
| L3 | ~50ms | PostgreSQL |

---

## 4. Pipeline d'Indexation

Le pipeline transforme le code source en chunks sémantiques avec embeddings.

```mermaid
flowchart TB
    subgraph INPUT["📥 Code Source"]
        A["<b>File</b><br/>main.py, app.ts, etc."]
    end

    subgraph PROCESSING["⚙️ 7 Étapes du Pipeline"]
        B["1️⃣ Detection<br/><b>Language ID</b><br/>Python, JS, TS..."]
        C["2️⃣ Parsing<br/><b>AST Tree-sitter</b><br/>Abstract Syntax Tree"]
        D["3️⃣ Chunking<br/><b>Semantic Split</b><br/>functions, classes, methods"]
        E["4️⃣ Métadonnées<br/><b>LSP Analysis</b><br/>types, signatures, imports"]
        F["5️⃣ Embed TEXT<br/><b>nomic-embed-text</b><br/>768D vector"]
        G["6️⃣ Embed CODE<br/><b>jina-embeddings-v2</b><br/>768D vector"]
        H["7️⃣ Graphe<br/><b>Dependency Graph</b><br/>calls, imports"]
    end

    subgraph OUTPUT["📤 PostgreSQL Storage"]
        I["<b>code_chunks</b><br/>embeddings + metadata"]
        J["<b>graph_nodes</b><br/>functions, classes"]
        K["<b>graph_edges</b><br/>relationships"]
    end

    A --> B --> C --> D --> E --> F --> G --> H --> I
    H --> J
    H --> K

    style INPUT fill:#FF7043,stroke:#E64A19,color:#fff
    style PROCESSING fill:#42A5F5,stroke:#1976D2,color:#fff
    style OUTPUT fill:#66BB6A,stroke:#388E3C,color:#fff
```

### Langages Supportés

```
Python • JavaScript • TypeScript • JSX • TSX • Go • Rust • Java
C • C++ • C# • Ruby • PHP • Swift • Kotlin • Scala
HTML • CSS • SQL • Markdown • YAML • JSON • TOML
```

---

## 5. Recherche Hybride

```mermaid
flowchart TB
    subgraph QUERY["🔍 Query"]
        Q["<b>Natural Language</b><br/>'authenticate function in API'"]
    end

    subgraph PROCESS["⚙️ Hybrid Search Pipeline"]
        Q -->|"a)"| EMB["Embedding Generation<br/><b>nomic-embed-text-v1.5</b>"]
        Q -->|"b)"| TOK["Tokenisation<br/><b>pg_trgm</b>"]

        subgraph LEXICAL["📝 Lexical Search"]
            TOK --> TRGM["Trigram Matching<br/>similarity(title, content)"]
        end

        subgraph VECTOR["🔢 Vector Search"]
            EMB --> HNSW["<b>HNSW Index</b><br/>ef_search=100, m=16"]
        end

        subgraph FUSION["🔄 RRF Fusion"]
            TRGM --> RRF["<b>Reciprocal Rank Fusion</b><br/>k=60 (adaptive)"]
            HNSW --> RRF
        end

        RRF --> RERANK["<b>BM25 Reranking</b><br/>Top-30 candidates"]
    end

    subgraph OUTPUT["✨ Results"]
        RERANK --> OUT["<b>Top-K Ranked Results</b><br/>score + metadata"]
    end

    style QUERY fill:#FF7043,stroke:#E64A19,color:#fff
    style PROCESS fill:#42A5F5,stroke:#1976D2,color:#fff
    style OUTPUT fill:#66BB6A,stroke:#388E3C,color:#fff
    style LEXICAL fill:#AB47BC,stroke:#7B1FA2,color:#fff
    style VECTOR fill:#26A69A,stroke:#00897B,color:#fff
    style FUSION fill:#5C6BC0,stroke:#3949AB,color:#fff
```

### Scores de Fusion

```sql
final_score = 0.4 × trgm_similarity + 0.6 × (1 − cosine_distance)
```

| Paramètre | Valeur | Application |
|-----------|--------|-------------|
| `k` adaptatif | 20 | Queries code-heavy `(){}→::` |
| `k` adaptatif | 80 | Natural language (>5 words) |
| `k` défaut | 60 | Mix queries |
| Lexical weight | 0.4 | Précision pour code |
| Vector weight | 0.6 | Recall sémantique |

---

## 6. Mémoire Sémantique

### Types de Mémoires

| Type | Badge | Description | Duration | Decay |
|------|-------|-------------|----------|-------|
| `note` | 📝 | Observations générales | 30 jours | 0.005 |
| `decision` | ⚖️ | Décisions d'architecture | Permanent | 0.0 |
| `task` | ✅ | TODO items | Until done | 0.01 |
| `reference` | 🔗 | Liens documentation | 90 jours | 0.002 |
| `conversation` | 💬 | Contexte dialogue | 14 jours | 0.02 |
| `investigation` | 🔬 | Résultats debug | 45 jours | 0.005 |

### Cycle de Vie

```mermaid
stateDiagram-v2
    [*] --> Created: write_memory()

    Created --> Embedding: Generate
    note right of Embedding: ~100ms latency

    Embedding --> Active: Success
    Active --> Consumed: mark_consumed()

    Consumed --> Active: Refresh
    Consumed --> Decayed: decay_rate × time

    Decayed --> Consolidated: threshold (20)
    Consolidated --> Summary: LLM summary生成

    Summary --> [*]: Auto-archive
    Active --> [*]: Manual delete
```

### Décay Configuration

```mermaid
graph LR
    subgraph "Tag-based Decay Rules"
        CORE["sys:core<br/>rate=0.0<br/>permanent"] -->|"priority +0.5"| SCORE["Final Score"]
        PATTERN["sys:pattern<br/>rate=0.005<br/>140j half-life"] -->|"priority +0.2"| SCORE
        HISTORY["sys:history<br/>rate=0.05<br/>14j half-life"] -->|"priority -0.1"| SCORE
        DRIFT["sys:drift<br/>rate=0.02<br/>35j half-life"] -->|"priority +0.3"| SCORE
    end

    SCORE["final_score = rrf_score × exp(−decay_rate × age_days)"]

    style CORE fill:#4CAF50,color:#fff
    style SCORE fill:#2196F3,color:#fff
```

### Consolidation Workflow

```
When count(sys:history) > 20:
┌─────────────────────────────────────────────────────────────┐
│  1. Search oldest 10 memories (ORDER BY created_at ASC)    │
│  2. Generate LLM summary (~200 words)                      │
│  3. Create new memory (type=note, tags=[sys:history:summary])│
│  4. Soft-delete source memories (deleted_at = NOW())       │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Graphe de Code

```mermaid
graph TD
    subgraph "📁 Module: api/users/"
        A["<b>users.py</b><br/>Module"]
    end

    subgraph "🔧 Classes & Functions"
        B["<b>AuthService</b><br/>Class"]
        C["<b>UserRepository</b><br/>Class"]
        D["<b>authenticate()</b><br/>Method"]
        E["<b>validate_token()</b><br/>Function"]
        F["<b>create_user()</b><br/>Method"]
    end

    subgraph "📦 Dependencies"
        G["<b>jwt.decode</b><br/>Import"]
        H["<b>asyncpg</b><br/>Import"]
        I["<b>UserModel</b><br/>Import"]
    end

    A -->|"contains"| B
    A -->|"contains"| C
    B -->|"calls"| D
    B -->|"calls"| F
    D -->|"calls"| E
    D -->|"imports"| G
    F -->|"imports"| H
    C -->|"imports"| I

    classDef module fill:#336791,stroke:#1A237E,color:#fff
    classDef class fill:#4CAF50,stroke:#388E3C,color:#fff
    classDef func fill:#42A5F5,stroke:#1976D2,color:#fff
    classDef imp fill:#9E9E9E,stroke:#616161,color:#fff

    class A module
    class B,C class
    class D,E,F func
    class G,H,I imp
```

### Traversal Operations

```mermaid
flowchart LR
    subgraph "Traversal Types"
        subgraph "OUTGOING"
            O1["📤 callees"]
            O2["📤 imports"]
        end
        
        subgraph "INCOMING"
            I1["📥 callers"]
            I2["📥 references"]
        end
        
        subgraph "BOTH"
            B1["🔄 full neighborhood"]
        end
    end

    NODE["🔵 Starting Node"] --> OUTGOING
    NODE --> INCOMING
    NODE --> BOTH
```

### Path Finding (BFS)

```
find_path(source_id, target_id, max_depth=5)

Example: How does authenticate() reach asyncpg?

authenticate() → UserRepository.create_user() → asyncpg.connect()

Path length: 3 hops
```

---

## 8. Cache Triple-Layer

```mermaid
flowchart LR
    subgraph REQUEST["📥 Request"]
        Q["search_memory()<br/>search_code()"]
    end

    subgraph LAYERS["🏗️ Cache Layers"]
        L1["<b>L1</b><br/>In-Memory<br/>Dict<br/>~1ms"]
        L2["<b>L2</b><br/>Redis<br/>Distributed<br/>~10ms"]
        L3["<b>L3</b><br/>PostgreSQL<br/>Disk<br/>~50ms"]
    end

    subgraph RESPONSE["📤 Response"]
        R["Results"]
    end

    Q --> L1

    L1 -->|"HIT ✅"| R
    L1 -.->|"MISS ❌"| L2

    L2 -->|"HIT ✅"| R
    L2 -.->|"MISS ❌"| L3

    L3 -->|"HIT ✅"| R

    L3 -.->|"STORE"| L2 -.->|"STORE"| L1

    style L1 fill:#1976D2,stroke:#0D47A1,color:#fff
    style L2 fill:#7B1FA2,stroke:#4A148C,color:#fff
    style L3 fill:#388E3C,stroke:#1B5E20,color:#fff
    style R fill:#4CAF50,stroke:#388E3C,color:#fff
```

### Cache Keys

```
memory:{id}              → Full memory content
search:{query_hash}       → Search results (TTL: 5min)
graph:{repo}:stats       → Graph statistics (TTL: 1h)
index:{repo}:status      → Indexing status
config:decay:{tag}       → Decay rules
```

### Configuration Redis

```yaml
redis:
  maxmemory: 256mb
  maxmemory-policy: allkeys-lru
  ttl:
    search: 300        # 5 minutes
    graph: 3600        # 1 hour
    index: 86400       # 1 day
```

---

## 9. Schéma Base de Données

```mermaid
erDiagram
    PROJECT ||--o{ MEMORY : contains
    PROJECT ||--o{ CODE_CHUNK : indexes
    PROJECT ||--o{ GRAPH_NODE : contains
    PROJECT ||--o{ GRAPH_EDGE : relates

    MEMORY ||--o{ TAG : tagged_with
    MEMORY {
        uuid id PK
        string title "max 200"
        text content
        enum memory_type "note|decision|task|..."
        array tags
        vector embedding "halfvec(768)"
        string author
        uuid project_id FK
        bool consumed "agent processed"
        timestamptz created_at
        timestamptz updated_at
        timestamptz deleted_at "soft delete"
    }

    CODE_CHUNK {
        uuid id PK
        string repository
        text file_path
        enum chunk_type "function|class|method|..."
        string name
        text source_code
        vector embedding_text "halfvec(768)"
        vector embedding_code "halfvec(768)"
        string language
        jsonb metadata "LSP types, signatures"
        timestamptz created_at
    }

    GRAPH_NODE {
        uuid id PK
        string repository
        enum node_type "function|class|module|import"
        string name
        text file_path
        jsonb metadata
    }

    GRAPH_EDGE {
        uuid id PK
        uuid source_id FK
        uuid target_id FK
        enum edge_type "calls|imports|inherits"
    }

    TAG {
        uuid id PK
        string name
        string prefix "sys:|user:|trace:"
    }
```

### Indexes

| Table | Index | Type | Usage |
|-------|-------|------|-------|
| memories | embedding | HNSW | Vector search |
| memories | tags | GIN | Tag filtering |
| memories | created_at | B-tree | Time queries |
| code_chunks | embedding_text | HNSW | Text search |
| code_chunks | embedding_code | HNSW | Code search |
| code_chunks | repository | B-tree | Repo filter |

---

## 10. MCP - 33 Outils

```mermaid
graph TD
    subgraph "🎯 MCP Server (FastMCP 1.12.3)"
        
        subgraph "🧠 Memory (9)"
            WM["write_memory"]
            RM["read_memory"]
            UM["update_memory"]
            DM["delete_memory"]
            SM["search_memory"]
            SS["get_system_snapshot"]
            MC["mark_consumed"]
            CM["consolidate_memory"]
            CD["configure_decay"]
        end

        subgraph "📊 Indexing (7)"
            IP["index_project"]
            II["index_incremental"]
            IM["index_markdown_workspace"]
            RF["reindex_file"]
            GS["get_indexing_status"]
            GE["get_indexing_errors"]
            RI["retry_indexing"]
        end

        subgraph "🔍 Search (1)"
            SC["search_code"]
        end

        subgraph "📈 Analytics (4)"
            IS["get_indexing_stats"]
            MH["get_memory_health"]
            CS["get_cache_stats"]
            CC["clear_cache"]
        end

        subgraph "🔗 Graph (4)"
            GGS["get_graph_stats"]
            TG["traverse_graph"]
            FP["find_path"]
            GMD["get_module_data"]
        end

        subgraph "⚙️ Config (2)"
            SP["switch_project"]
            PNG["ping"]
        end
    end

    style WM fill:#4CAF50,stroke:#388E3C,color:#fff
    style IP fill:#42A5F5,stroke:#1976D2,color:#fff
    style SC fill:#FF9800,stroke:#F57C00,color:#fff
    style IS fill:#9C27B0,stroke:#7B1FA2,color:#fff
    style GGS fill:#00BCD4,stroke:#00838F,color:#fff
    style SP fill:#607D8B,stroke:#455A64,color:#fff
```

### Protocole MCP

```mermaid
sequenceDiagram
    participant Client as 🎮 MCP Client
    participant MCP as MnemoLite MCP

    Note over Client,MCP: Handshake (Obligatoire)
    Client->>MCP: initialize (protocolVersion, clientInfo)
    MCP-->>Client: serverInfo, capabilities
    Client->>MCP: notifications/initialized

    Note over Client,MCP: Session Active
    loop Chaque Requête
        Client->>MCP: tools/call {name, arguments}
        MCP->>MCP: Validate + Execute
        alt Read Operations
            MCP->>MCP: Query Database
        else Write Operations
            MCP->>MCP: Write + Invalidate Cache
        end
        MCP-->>Client: {content: [{text: result}]}
    end
```

### Configuration Client

**KiloCode / OpenCode:**
```json
{
  "mcpServers": {
    "mnemolite": {
      "url": "http://localhost:8002/mcp",
      "alwaysAllow": ["search_memory", "write_memory", "ping"]
    }
  }
}
```

---

## 11. Déploiement

### Docker Compose

```yaml
version: '3.8'

services:
  # ─────────────────────────────────────────────
  # Frontend Vue 3 SPA
  # ─────────────────────────────────────────────
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    profiles: ["dev", "prod"]
    depends_on: [api]

  # ─────────────────────────────────────────────
  # FastAPI REST API
  # ─────────────────────────────────────────────
  api:
    build: ./api
    ports: ["8001:8001"]
    environment:
      DATABASE_URL: postgresql://mnemo:mnemopass@postgres:5432/mnemolite
      REDIS_URL: redis://redis:6379/0
      EMBEDDING_MODE: real
    depends_on: [postgres, redis]
    profiles: ["dev", "prod"]

  # ─────────────────────────────────────────────
  # MCP Server (33 tools)
  # ─────────────────────────────────────────────
  mcp:
    build: ./api
    command: python -m api.mcp.server
    ports: ["8002:8002"]
    environment:
      DATABASE_URL: postgresql://mnemo:mnemopass@postgres:5432/mnemolite
      REDIS_URL: redis://redis:6379/0
    depends_on: [postgres, redis]
    profiles: ["dev", "prod"]

  # ─────────────────────────────────────────────
  # PostgreSQL 18 + Extensions
  # ─────────────────────────────────────────────
  postgres:
    image: postgres:18
    environment:
      POSTGRES_DB: mnemolite
      POSTGRES_USER: mnemo
      POSTGRES_PASSWORD: mnemopass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    command: >
      postgres
      -c shared_preload_libraries=vector,pg_trgm
      -c vector.ef_search=100
    profiles: ["dev", "prod"]

  # ─────────────────────────────────────────────
  # Redis 7 Cache
  # ─────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes:
      - redis_data:/data
    profiles: ["dev", "prod"]

  # ─────────────────────────────────────────────
  # OpenObserve (Observability)
  # ─────────────────────────────────────────────
  openobserve:
    image: openobserve/openobserve:latest
    ports: ["5080:5080"]
    environment:
      ZOOKEEPER_ENABLED: "true"
      ZOOKEEPER_PORT: "2181"
    profiles: ["dev"]

volumes:
  postgres_data:
  redis_data:
```

### Variables d'Environnement

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | postgresql://... | PostgreSQL connection |
| `REDIS_URL` | redis://localhost:6379 | Redis connection |
| `EMBEDDING_MODE` | real | real/mock |
| `EMBEDDING_MODEL` | nomic-ai/nomic-embed-text-v1.5 | TEXT embedding |
| `CODE_EMBEDDING_MODEL` | jinaai/jina-embeddings-v2-base-code | CODE embedding |
| `EMBEDDING_DIMENSION` | 768 | Vector dimension |
| `MCP_PORT` | 8002 | MCP server port |

---

## Performance

| Métrique | Valeur | Conditions |
|----------|--------|-----------|
| **Search (cached)** | <10ms | L1/L2 hit |
| **Search (uncached)** | ~100ms | Full pipeline |
| **Embedding generation** | ~5ms | Per query |
| **Indexation** | ~5s | Per file |
| **Graphe traversal (3 hops)** | ~0.15ms | Recursive CTE |
| **Cache hit rate** | 80%+ | L1 + L2 |
| **Mémoire (MCP)** | ~1.6GB | With models |

---

## License

MIT - Made with ❤️ for AI agents
