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
        MemoryService[Services de Mémoire]
        EventService[Services d'Événements]
        NotificationService[Service de Notification]
    end
    
    subgraph "Adaptateurs Secondaires (Sortie)"
        EventRepo[EventRepository]
        MemoryRepo[MemoryRepository]
        EmbeddingImpl[Service d'Embedding]
    end
    
    RESTRoutes --> |Utilise| Interfaces
    Interfaces --> MemoryService
    Interfaces --> EventService
    Interfaces --> NotificationService
    
    MemoryService --> |Dépend de| Interfaces
    EventService --> |Dépend de| Interfaces
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
    EP->>ES: generate_embedding(event.content)
    ES-->>EP: embedding
    EP->>ER: update_metadata(event_id, enriched_metadata)
    ER->>DB: UPDATE events SET metadata = ...
    DB-->>ER: OK
    ER-->>EP: Updated Event
    EP-->>API: Enriched Metadata
    API-->>Client: 201 Created
```

## Flux de Recherche de Mémoires

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI Routes
    participant MS as MemorySearchService
    participant ES as EmbeddingService
    participant ER as EventRepository
    participant MR as MemoryRepository
    participant DB as PostgreSQL
    
    Client->>API: GET /search/similarity
    API->>MS: search_by_similarity(query, limit)
    MS->>ES: generate_embedding(query)
    ES-->>MS: query_embedding
    MS->>ER: search_by_embedding(query_embedding, limit)
    ER->>DB: SELECT ... ORDER BY embedding <-> vector_query
    DB-->>ER: Events
    ER-->>MS: Similar Events
    MS-->>API: Memory Results
    API-->>Client: 200 OK (Memories)
    
    Client->>API: GET /search/metadata
    API->>MS: search_by_metadata(metadata_filter, limit)
    MS->>MR: list_memories(metadata_filter, limit)
    MR->>DB: SELECT ... WHERE metadata @> filter
    DB-->>MR: Matching Records
    MR-->>MS: Matching Memories
    MS-->>API: Memory Results
    API-->>Client: 200 OK (Memories)
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
        +str id
        +datetime timestamp
        +str memory_type
        +str event_type
        +int role_id
        +Dict content
        +Dict metadata
        +datetime expiration
    }
    
    class MemoryCreate {
        +str memory_type
        +str event_type
        +int role_id
        +Dict content
        +Dict metadata
        +datetime expiration
    }
    
    class MemoryUpdate {
        +str memory_type
        +str event_type
        +int role_id
        +Dict content
        +Dict metadata
        +datetime expiration
    }
    
    EventCreate --|> EventModel: creates
    MemoryCreate --|> Memory: creates
    MemoryUpdate --|> Memory: updates
    EventModel --|> Memory: can generate
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
        +search_by_embedding(embedding: List[float], limit: int) List[EventModel]
        +filter_by_metadata(metadata_filter: Dict, limit: int, offset: int) List[EventModel]
    }
    
    class MemoryRepositoryProtocol {
        <<interface>>
        +add(memory: MemoryCreate) Memory
        +get_by_id(memory_id: UUID) Memory
        +update(memory_id: UUID, memory_update: MemoryUpdate) Memory
        +delete(memory_id: UUID) bool
        +list_memories(limit: int, offset: int, metadata_filter: Dict) List[Memory]
    }
    
    class EmbeddingServiceProtocol {
        <<interface>>
        +generate_embedding(text: str) List[float]
        +compute_similarity(embedding1: List[float], embedding2: List[float]) float
    }
    
    class MemorySearchServiceProtocol {
        <<interface>>
        +search_by_content(query: str, limit: int) List[Memory]
        +search_by_metadata(metadata_filter: Dict, limit: int) List[Memory]
        +search_by_similarity(query: str, limit: int) List[Memory]
    }
    
    class EventProcessor {
        +event_repository: EventRepositoryProtocol
        +embedding_service: EmbeddingServiceProtocol
        +process_event(event: EventModel) Dict
        +generate_memory_from_event(event: EventModel) Memory
    }
    
    class NotificationService {
        +smtp_host: str
        +smtp_port: int
        +smtp_user: str
        +smtp_password: str
        +send_notification(user_id: str, message: str, metadata: Dict) bool
        +broadcast_notification(message: str, user_ids: List[str]) Dict[str, bool]
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
        timestamp timestamp
        jsonb content
        jsonb metadata
        vector embedding
    }
    
    NODES {
        uuid id PK
        text label
        jsonb properties
    }
    
    EDGES {
        uuid id PK
        uuid source_id FK
        uuid target_id FK
        text label
        jsonb properties
    }
    
    NODES ||--o{ EDGES : "source"
    NODES ||--o{ EDGES : "target"
``` 