# Diagrammes d'Architecture MnemoLite

Ce document présente divers diagrammes pour visualiser l'architecture, les interactions et les flux de données du système MnemoLite.

## Architecture Globale

```mermaid
graph TD
    Client[Client HTTP] --> |Requêtes HTTP| API[API FastAPI]
    API --> |Dépend de| DR[Dependency Resolver]
    
    DR --> |Injecte| ER[EventRepository]
    DR --> |Injecte| MR[MemoryRepository]
    DR --> |Injecte| ES[EmbeddingService]
    DR --> |Injecte| MS[MemorySearchService]
    DR --> |Injecte| EP[EventProcessor]
    DR --> |Injecte| NS[NotificationService]
    
    ER --> |Utilise| DB[(Base de données)]
    MR --> |Utilise| DB
    
    MS --> |Dépend de| ER
    MS --> |Dépend de| MR
    MS --> |Dépend de| ES
    
    EP --> |Dépend de| ER
    EP --> |Dépend de| ES
    EP --> |Dépend de| MR
    
    subgraph "Couche API"
        API
        DR
    end
    
    subgraph "Couche Services"
        ES
        MS
        EP
        NS
    end
    
    subgraph "Couche Données"
        ER
        MR
        DB
    end
```

## Architecture Ports & Adapters (Hexagonale)

```mermaid
graph TD
    subgraph "Adaptateurs Primaires (Entrée)"
        RESTRoutes[Routes REST]
    end
    
    subgraph "Domaine (Core)"
        Interfaces[Protocoles/Interfaces]
        MemorySearchService[MemorySearchService]
        EventProcessor[EventProcessor]
        NotificationService[Service de Notification]
    end
    
    subgraph "Adaptateurs Secondaires (Sortie)"
        EventRepo[EventRepository]
        MemoryRepo[MemoryRepository]
        EmbeddingImpl[Service d'Embedding]
    end
    
    RESTRoutes --> |Utilise| Interfaces
    Interfaces --> MemorySearchService
    Interfaces --> EventProcessor
    Interfaces --> NotificationService
    
    MemorySearchService --> |Dépend de| Interfaces
    EventProcessor --> |Dépend de| Interfaces
    NotificationService --> |Dépend de| Interfaces
    
    Interfaces --> EventRepo
    Interfaces --> MemoryRepo
    Interfaces --> EmbeddingImpl
    
    EventRepo --> |Stocke dans| PostgreSQL[(PostgreSQL)]
    MemoryRepo --> |Stocke dans| PostgreSQL
```

## Injection de Dépendances

```mermaid
flowchart TB
    API[Routes API] --> |Depends| GetMR[get_memory_repository]
    API --> |Depends| GetER[get_event_repository]
    API --> |Depends| GetMS[get_memory_search_service]
    API --> |Depends| GetEP[get_event_processor]
    API --> |Depends| GetNS[get_notification_service]
    API --> |Depends| GetES[get_embedding_service]
    
    GetMR --> |Depends| GetEngine[get_db_engine]
    GetER --> |Depends| GetEngine
    
    GetMS --> |Depends| GetMR
    GetMS --> |Depends| GetER
    GetMS --> |Depends| GetES
    
    GetEP --> |Depends| GetER
    GetEP --> |Depends| GetES
    GetEP --> |Depends| GetMR
    
    GetEngine --> |Obtient depuis| AppState[Application State]
    
    subgraph "FastAPI Dependency Injection"
        GetMR
        GetER
        GetMS
        GetEP
        GetNS
        GetES
        GetEngine
    end
```

## Flux de Traitement des Événements

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI Routes
    participant EP as EventProcessor
    participant ES as EmbeddingService
    participant ER as EventRepository
    participant DB as PostgreSQL
    
    Client->>API: POST /events
    API->>EP: process_event(event)
    alt Event Lacks Embedding
        EP->>ES: generate_embedding(event.content)
        ES-->>EP: embedding
        EP->>ER: update_metadata(event_id, {**metadata, "has_embedding": True})
        ER->>DB: UPDATE events SET metadata = ..., embedding = ...
        DB-->>ER: OK
        ER-->>EP: Updated EventModel (potentially)
    end
    EP-->>API: Enriched Metadata (or original)
    API-->>Client: 201 Created (original event response)
```

## Flux de Recherche de Mémoires

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI Routes
    participant MS as MemorySearchService
    participant ES as EmbeddingService
    participant ER as EventRepository
    participant DB as PostgreSQL
    
    Client->>API: GET /search/?vector_query=text...
    API->>MS: search_hybrid(query=text, ...)
    MS->>ES: generate_embedding(query)
    ES-->>MS: query_embedding
    MS->>ER: search_vector(vector=query_embedding, ...)
    ER->>DB: SELECT ... ORDER BY embedding <-> vector_query
    DB-->>ER: Event Records
    ER-->>MS: Tuple[List[EventModel], int]
    MS-->>API: SearchResponse{ data: List[EventModel], meta: ...}
    API-->>Client: 200 OK (EventModel list)
    
    Client->>API: GET /search/?filter_metadata=...
    API->>MS: search_hybrid(metadata_filter=..., ...)
    MS->>ER: search_vector(metadata=..., ...)
    ER->>DB: SELECT ... WHERE metadata @> filter
    DB-->>ER: Event Records
    ER-->>MS: Tuple[List[EventModel], int]
    MS-->>API: SearchResponse{ data: List[EventModel], meta: ...}
    API-->>Client: 200 OK (EventModel list)
```

## Relations Entre Modèles

```mermaid
classDiagram
    class EventModel {
        +UUID id
        +datetime timestamp
        +Dict content
        +Dict metadata
        +List[float] embedding
        +float similarity_score
    }
    
    class EventCreate {
        +Dict content
        +Dict metadata
        +List[float] embedding
        +datetime timestamp
    }
    
    class Memory {
        <<Derived>>
        +memory_type: str
        +event_type: str
        +role_id: int
        +expiration: datetime
        +id: UUID
        +timestamp: datetime
        +content: Dict
        +metadata: Dict
        +embedding: List[float]
        +similarity_score: float
    }
    
    EventCreate --|> EventModel : "Input for creation"
    EventModel ..|> Memory : "Can be represented as"
```

## Protocoles et Implémentations

```mermaid
classDiagram
    class EventRepositoryProtocol {
        <<interface>>
        +add(event: EventCreate) EventModel
        +get_by_id(event_id: UUID) EventModel
        +update_metadata(event_id: UUID, metadata: Dict) EventModel
        +delete(event_id: UUID) bool
        +filter_by_metadata(metadata_filter: Dict, limit: int, offset: int) List[EventModel]
        +search_vector(vector, metadata, ts_start, ts_end, limit, offset, distance_threshold) Tuple[List[EventModel], int]
    }
    
    class MemoryRepositoryProtocol {
        <<interface>>
        +add(memory: MemoryCreate) Memory
        +get_by_id(memory_id: UUID) Memory
        +update(memory_id: UUID, memory_update: MemoryUpdate) Memory
        +delete(memory_id: UUID) bool
        +list_memories(limit, skip, memory_type, event_type, role_id, session_id, metadata_filter, ts_start, ts_end, offset) tuple[List[Memory], int]
        +search_by_embedding(embedding, limit, skip, ts_start, ts_end) tuple[List[Memory], int]
    }
    
    class EmbeddingServiceProtocol {
        <<interface>>
        +generate_embedding(text: str) List[float]
        +compute_similarity(item1: Union[str, List[float]], item2: Union[str, List[float]]) float
    }
    
    class MemorySearchServiceProtocol {
        <<interface>>
        +search_by_content(query: str, limit: int) List[Memory]
        +search_by_metadata(metadata_filter: Dict, limit: int, offset: int, ts_start: datetime, ts_end: datetime) List[Memory]
        +search_by_similarity(query: str, limit: int, offset: int, ts_start: datetime, ts_end: datetime) List[Memory]
        +search_hybrid(query, metadata_filter, ts_start, ts_end, limit, offset, distance_threshold) Tuple[List[EventModel], int]
    }
    
    class EventProcessorProtocol {
        <<interface>>
        +process_event(event: EventModel) Dict[str, Any]
        +generate_memory_from_event(event: EventModel) Optional[Memory]
    }
    
    class NotificationServiceProtocol {
        <<interface>>
        +send_notification(user_id: str, message: str, metadata: Optional[Dict[str, Any]]) bool
        +broadcast_notification(message: str, user_ids: Optional[List[str]]) Dict[str, bool]
    }
    
    EventRepositoryProtocol <|.. EventRepository: implements
    MemoryRepositoryProtocol <|.. MemoryRepository: implements
    EmbeddingServiceProtocol <|.. SimpleEmbeddingService: implements
    MemorySearchServiceProtocol <|.. MemorySearchService: implements
    EventProcessorProtocol <|.. EventProcessor: implements
    NotificationServiceProtocol <|.. NotificationService: implements
```

## Schéma de la Base de Données

```mermaid
erDiagram
    EVENTS {
        uuid id PK
        timestamp timestamp PK
        jsonb content
        jsonb metadata
        vector embedding
    }
    
    NODES {
        uuid node_id PK
        text node_type
        text label
        jsonb properties
        timestamp created_at
    }
    
    EDGES {
        uuid edge_id PK
        uuid source_node_id FK
        uuid target_node_id FK
        text relation_type
        jsonb properties
        timestamp created_at
    }
    
    NODES ||--o{ EDGES : "source"
    NODES ||--o{ EDGES : "target"
``` 