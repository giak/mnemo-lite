import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
import asyncpg
import builtins # Import nécessaire pour mocker/spy print
import datetime
import json

# Import de la classe à tester (adapter le chemin si nécessaire)
# Assumons que le PYTHONPATH est configuré pour que 'api' soit accessible
from api.db.repositories.event_repository import EventRepository, EventModel, EventCreate
# from api.db.repositories import event_repository # Plus nécessaire si on ne spy pas le module

@pytest.mark.anyio # Nécessaire pour les tests async avec pytest-asyncio
async def test_event_repository_instantiation():
    """Teste si EventRepository peut être instancié avec un pool mocké."""
    # Crée un mock asynchrone pour simuler le pool de connexions asyncpg
    mock_pool = AsyncMock(spec=asyncpg.Pool)
    
    # Instancie le repository avec le mock
    repository = EventRepository(pool=mock_pool)
    
    # Vérifie que l'instance a bien été créée et que le pool est assigné
    assert isinstance(repository, EventRepository)
    assert repository.pool is mock_pool

@pytest.mark.anyio
async def test_add_event_success(mocker):
    """Teste l'ajout réussi d'un événement."""
    # 1. Préparation (Arrange)
    mock_pool = AsyncMock(spec=asyncpg.Pool)
    mock_connection = AsyncMock(spec=asyncpg.Connection)
    # Simule l'entrée dans le contexte `async with pool.acquire()`
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    
    # Données d'événement à créer
    event_content = {"text": "Test event content"}
    event_metadata = {"tag": "test", "source": "pytest"}
    event_embedding = [0.1, 0.2, 0.3]
    event_to_create = EventCreate(
        content=event_content,
        metadata=event_metadata,
        embedding=event_embedding
    )
    
    # Données simulées retournées par fetchrow
    fake_db_id = uuid.uuid4()
    fake_db_timestamp = datetime.datetime.now(datetime.timezone.utc)
    # Simule la sortie pgvector comme une chaîne (cas courant)
    fake_db_embedding_str = json.dumps(event_embedding) 
    
    # Données simulées retournées par fetchrow (maintenant un Dict)
    fake_db_return = {
        'id': fake_db_id,
        'timestamp': fake_db_timestamp,
        'content': event_content,
        'metadata': event_metadata,
        'embedding': fake_db_embedding_str # Simule la sortie str de pgvector
    }
    
    # Configurer fetchrow pour retourner le dictionnaire
    mock_connection.fetchrow.return_value = fake_db_return
    
    repository = EventRepository(pool=mock_pool)
    
    # 2. Action (Act)
    created_event = await repository.add(event_data=event_to_create)
    
    # 3. Vérification (Assert)
    # Vérifie que fetchrow a été appelé avec les bons arguments
    mock_connection.fetchrow.assert_awaited_once()
    call_args = mock_connection.fetchrow.call_args[0]
    assert call_args[0].strip().startswith("INSERT INTO events")
    assert call_args[1] == json.dumps(event_content)
    assert call_args[2] == json.dumps(event_metadata)
    assert call_args[3] == json.dumps(event_embedding) # Revert: Expect JSON string again
    
    # Vérifie que le résultat est du bon type et contient les bonnes données
    assert isinstance(created_event, EventModel)
    assert created_event.id == fake_db_id
    assert created_event.timestamp == fake_db_timestamp
    assert created_event.content == event_content
    assert created_event.metadata == event_metadata
    assert created_event.embedding == event_embedding

@pytest.mark.anyio
async def test_get_event_by_id_success(mocker):
    """Teste la récupération réussie d'un événement par ID."""
    # 1. Préparation (Arrange)
    mock_pool = AsyncMock(spec=asyncpg.Pool)
    mock_connection = AsyncMock(spec=asyncpg.Connection)
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    
    test_event_id = uuid.uuid4()
    expected_content = {"data": "sample"}
    expected_metadata = {"source": "test"}
    expected_embedding = [0.5, 0.6]
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    # Simuler l'enregistrement retourné par la base de données
    fake_db_record = {
        'id': test_event_id,
        'timestamp': expected_timestamp,
        'content': expected_content, # Simule déjà parsé par asyncpg
        'metadata': expected_metadata,
        'embedding': json.dumps(expected_embedding) # Simule str retourné par DB
    }
    
    mock_connection.fetchrow.return_value = fake_db_record
    
    repository = EventRepository(pool=mock_pool)
    
    # 2. Action (Act)
    found_event = await repository.get_by_id(event_id=test_event_id)
    
    # 3. Vérification (Assert)
    mock_connection.fetchrow.assert_awaited_once_with(
        mocker.ANY, # La requête SQL
        test_event_id
    )
    # Vérifier la requête SQL plus précisément si nécessaire
    query_arg = mock_connection.fetchrow.call_args[0][0]
    assert "SELECT id, timestamp, content, metadata, embedding" in query_arg
    assert "FROM events WHERE id = $1" in query_arg
    
    assert isinstance(found_event, EventModel)
    assert found_event.id == test_event_id
    assert found_event.timestamp == expected_timestamp
    assert found_event.content == expected_content
    assert found_event.metadata == expected_metadata
    assert found_event.embedding == expected_embedding

@pytest.mark.anyio
async def test_get_event_by_id_not_found(mocker):
    """Teste le cas où l'événement n'est pas trouvé par ID."""
    # 1. Préparation (Arrange)
    mock_pool = AsyncMock(spec=asyncpg.Pool)
    mock_connection = AsyncMock(spec=asyncpg.Connection)
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    
    test_event_id = uuid.uuid4()
    
    # Configurer fetchrow pour retourner None
    mock_connection.fetchrow.return_value = None
    
    repository = EventRepository(pool=mock_pool)
    
    # 2. Action (Act)
    found_event = await repository.get_by_id(event_id=test_event_id)
    
    # 3. Vérification (Assert)
    mock_connection.fetchrow.assert_awaited_once_with(
        mocker.ANY, # La requête SQL
        test_event_id
    )
    assert found_event is None

# --- Tests pour filter_by_metadata --- 

@pytest.mark.anyio
async def test_filter_by_metadata_found(mocker):
    """Teste le filtrage par métadonnées quand des événements correspondent."""
    # 1. Préparation (Arrange)
    mock_pool = AsyncMock(spec=asyncpg.Pool)
    mock_connection = AsyncMock(spec=asyncpg.Connection)
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    
    criteria = {"source": "test", "type": "filter"}
    expected_id1 = uuid.uuid4()
    expected_id2 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    # Simuler les enregistrements retournés par fetch (liste de dicts)
    fake_db_records = [
        {
            'id': expected_id1,
            'timestamp': expected_timestamp,
            'content': {"msg": "Event 1"},
            'metadata': {"source": "test", "type": "filter", "extra": "val1"},
            'embedding': json.dumps([0.1])
        },
        {
            'id': expected_id2,
            'timestamp': expected_timestamp - datetime.timedelta(minutes=1),
            'content': {"msg": "Event 2"},
            'metadata': {"source": "test", "type": "filter", "other": "val2"},
            'embedding': None
        }
    ]
    
    mock_connection.fetch.return_value = fake_db_records
    
    repository = EventRepository(pool=mock_pool)
    
    # 2. Action (Act)
    found_events = await repository.filter_by_metadata(metadata_criteria=criteria)
    
    # 3. Vérification (Assert)
    mock_connection.fetch.assert_awaited_once_with(
        mocker.ANY, # La requête SQL
        json.dumps(criteria)
    )
    # Vérifier la requête SQL plus précisément
    query_arg = mock_connection.fetch.call_args[0][0]
    assert "SELECT id, timestamp, content, metadata, embedding" in query_arg
    assert "FROM events" in query_arg
    assert "WHERE metadata @> $1::jsonb" in query_arg
    
    assert isinstance(found_events, list)
    assert len(found_events) == 2
    assert all(isinstance(event, EventModel) for event in found_events)
    assert found_events[0].id == expected_id1
    assert found_events[1].id == expected_id2
    assert found_events[0].metadata["source"] == "test"
    assert found_events[1].metadata["type"] == "filter"

@pytest.mark.anyio
async def test_filter_by_metadata_not_found(mocker):
    """Teste le filtrage par métadonnées quand aucun événement ne correspond."""
    # 1. Préparation (Arrange)
    mock_pool = AsyncMock(spec=asyncpg.Pool)
    mock_connection = AsyncMock(spec=asyncpg.Connection)
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    
    criteria = {"source": "nonexistent"}
    
    # Configurer fetch pour retourner une liste vide
    mock_connection.fetch.return_value = []
    
    repository = EventRepository(pool=mock_pool)
    
    # 2. Action (Act)
    found_events = await repository.filter_by_metadata(metadata_criteria=criteria)
    
    # 3. Vérification (Assert)
    mock_connection.fetch.assert_awaited_once_with(
        mocker.ANY, # La requête SQL
        json.dumps(criteria)
    )
    assert isinstance(found_events, list)
    assert len(found_events) == 0

# --- Tests pour search_vector --- 

@pytest.mark.anyio
async def test_search_vector_metadata_only(mocker):
    """Teste search_vector avec seulement un filtre metadata (vector=None)."""
    # 1. Préparation (Arrange)
    mock_pool = AsyncMock(spec=asyncpg.Pool)
    mock_connection = AsyncMock(spec=asyncpg.Connection)
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    
    criteria = {"source": "search_test"}
    expected_id1 = uuid.uuid4()
    expected_id2 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    # Simuler les enregistrements retournés par fetch (liste de dicts)
    # Le score de similarité est ajouté avec une valeur par défaut (0.0)
    fake_db_records = [
        {
            'id': expected_id1,
            'timestamp': expected_timestamp,
            'content': {"msg": "Event 1 - Search"},
            'metadata': {"source": "search_test", "type": "metadata_only"},
            'embedding': None,
            'similarity_score': 0.0 
        },
        {
            'id': expected_id2,
            'timestamp': expected_timestamp - datetime.timedelta(minutes=1),
            'content': {"msg": "Event 2 - Search"},
            'metadata': {"source": "search_test", "other": "val"},
            'embedding': None,
            'similarity_score': 0.0
        }
    ]
    
    mock_connection.fetch.return_value = fake_db_records
    
    repository = EventRepository(pool=mock_pool)
    test_limit = 10
    test_offset = 0
    
    # 2. Action (Act)
    found_events = await repository.search_vector(
        vector=None, # Pas de vecteur
        metadata=criteria,
        limit=test_limit,
        offset=test_offset
    )
    
    # 3. Vérification (Assert)
    mock_connection.fetch.assert_awaited_once()
    call_args = mock_connection.fetch.call_args[0]
    query_sql = call_args[0] # La requête SQL
    query_params = call_args[1:] # Les paramètres
    
    # Vérifier que la requête ne contient PAS de recherche vectorielle
    assert "embedding <= >" not in query_sql 
    assert "ORDER BY embedding <= >" not in query_sql
    # Vérifier que le filtre metadata est présent
    assert "WHERE 1=1 AND metadata @> $1::jsonb" in query_sql
    # Vérifier que le tri par défaut (timestamp DESC) est appliqué
    assert "ORDER BY timestamp DESC" in query_sql
    # Vérifier que LIMIT et OFFSET sont corrects
    assert "LIMIT $2" in query_sql
    assert "OFFSET $3" in query_sql
    
    # Vérifier les paramètres passés
    assert query_params[0] == json.dumps(criteria) # $1
    assert query_params[1] == test_limit # $2
    assert query_params[2] == test_offset # $3
    
    # Vérifier les résultats
    assert isinstance(found_events, list)
    assert len(found_events) == 2
    assert all(isinstance(event, EventModel) for event in found_events)
    assert found_events[0].id == expected_id1
    assert found_events[1].id == expected_id2
    assert found_events[0].metadata["source"] == "search_test"
    assert found_events[0].similarity_score == 0.0 # Vérifier le score par défaut

@pytest.mark.anyio
async def test_search_vector_vector_only(mocker):
    """Teste search_vector avec seulement un vecteur (metadata=None)."""
    # 1. Préparation (Arrange)
    mock_pool = AsyncMock(spec=asyncpg.Pool)
    mock_connection = AsyncMock(spec=asyncpg.Connection)
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    
    query_vector = [0.1, 0.9, 0.2] # Vecteur de requête
    expected_id1 = uuid.uuid4()
    expected_id2 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    # Simuler les enregistrements retournés par fetch (résultat de la requête complète)
    # Ces scores sont juste des exemples
    fake_db_records = [
        {
            'id': expected_id1,
            'timestamp': expected_timestamp,
            'content': {"msg": "Event 1 - Vector Match"},
            'metadata': {"source": "vector_search"},
            'embedding': json.dumps([0.11, 0.89, 0.19]), # Embedding proche
            'similarity_score': 0.05 # Score faible = proche pour <=>
        },
        {
            'id': expected_id2,
            'timestamp': expected_timestamp - datetime.timedelta(minutes=5),
            'content': {"msg": "Event 2 - Vector Match"},
            'metadata': {"source": "vector_search"},
            'embedding': json.dumps([0.2, 0.8, 0.3]), # Moins proche
            'similarity_score': 0.15
        }
    ]
    
    mock_connection.fetch.return_value = fake_db_records
    
    repository = EventRepository(pool=mock_pool)
    test_top_k = 5  # K demandé
    test_limit = 10 # Limite finale
    test_offset = 0
    overfetch_factor = 5 # Correspond à celui dans le code
    expected_knn_limit = test_top_k * overfetch_factor # Limite pour la sous-requête KNN
    
    # 2. Action (Act)
    found_events = await repository.search_vector(
        vector=query_vector,
        top_k=test_top_k,
        metadata=None,
        limit=test_limit,
        offset=test_offset
    )
    
    # 3. Vérification (Assert)
    mock_connection.fetch.assert_awaited_once()
    call_args = mock_connection.fetch.call_args[0]
    query_sql = call_args[0] # La requête SQL
    query_params = call_args[1:] # Les paramètres
    
    # Vérifier que la requête contient la recherche vectorielle
    assert "embedding <=> $1" in query_sql
    assert "ORDER BY embedding <=> $1" in query_sql
    assert f"LIMIT $2" in query_sql # Limite KNN dans la sous-requête
    # Vérifier qu'il n'y a pas de filtre metadata ajouté
    assert "metadata @>" not in query_sql
    assert "WHERE 1=1" in query_sql # Seul filtre
    # Vérifier que le tri par défaut HORS sous-requête n'est PAS appliqué
    assert "ORDER BY timestamp DESC" not in query_sql
    # Vérifier que LIMIT et OFFSET finaux sont corrects
    assert f"LIMIT $3" in query_sql # Correction: LIMIT final est $3
    assert f"OFFSET $4" in query_sql # L'OFFSET final est $4

    # Vérifier les paramètres passés
    assert query_params[0] == str(query_vector).replace(" ", "") # $1: Vecteur (Correct format '[...]')
    assert query_params[1] == expected_knn_limit      # $2: Limite KNN
    assert query_params[2] == test_limit             # $3: Limite finale
    assert query_params[3] == test_offset            # $4: Offset final
    
    # Vérifier les résultats
    assert isinstance(found_events, list)
    assert len(found_events) == 2 # Nombre d'enregistrements mockés
    assert all(isinstance(event, EventModel) for event in found_events)
    assert found_events[0].id == expected_id1
    assert found_events[1].id == expected_id2
    # Vérifier que les scores de similarité sont présents et corrects
    assert found_events[0].similarity_score == 0.05 
    assert found_events[1].similarity_score == 0.15

@pytest.mark.anyio
async def test_search_vector_hybrid(mocker):
    """Teste search_vector avec un vecteur ET un filtre metadata."""
    # 1. Préparation (Arrange)
    mock_pool = AsyncMock(spec=asyncpg.Pool)
    mock_connection = AsyncMock(spec=asyncpg.Connection)
    mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
    
    query_vector = [0.5, 0.5] 
    criteria = {"tag": "hybrid"}
    expected_id1 = uuid.uuid4()
    expected_timestamp = datetime.datetime.now(datetime.timezone.utc)
    
    # Simuler un enregistrement retourné qui correspond aux deux critères
    # Supposons que la sous-requête KNN a retourné plus d'éléments,
    # mais seul celui-ci correspond aussi au filtre metadata.
    fake_db_records = [
        {
            'id': expected_id1,
            'timestamp': expected_timestamp,
            'content': {"msg": "Hybrid Match"},
            'metadata': {"tag": "hybrid", "source": "test"}, # Correspond au critère
            'embedding': json.dumps([0.51, 0.49]), # Proche du vecteur
            'similarity_score': 0.02 
        }
        # D'autres enregistrements pourraient avoir été trouvés par KNN
        # mais sont filtrés par la clause WHERE metadata @> ...
    ]
    
    mock_connection.fetch.return_value = fake_db_records
    
    repository = EventRepository(pool=mock_pool)
    test_top_k = 3
    test_limit = 5
    test_offset = 0
    overfetch_factor = 5
    expected_knn_limit = test_top_k * overfetch_factor
    
    # 2. Action (Act)
    found_events = await repository.search_vector(
        vector=query_vector,
        top_k=test_top_k,
        metadata=criteria,
        limit=test_limit,
        offset=test_offset
    )
    
    # 3. Vérification (Assert)
    mock_connection.fetch.assert_awaited_once()
    call_args = mock_connection.fetch.call_args[0]
    query_sql = call_args[0]
    query_params = call_args[1:]
    
    # Vérifier la structure de la requête hybride
    assert "embedding <=> $1" in query_sql
    assert "ORDER BY embedding <=> $1" in query_sql
    assert f"LIMIT $2" in query_sql # Limite KNN
    assert "FROM events" in query_sql # Partie KNN
    assert ") AS vector_results" in query_sql # Fermeture sous-requête
    assert "WHERE 1=1 AND metadata @> $3::jsonb" in query_sql # Filtre metadata externe
    assert "ORDER BY timestamp DESC" not in query_sql # Pas de tri externe par défaut
    assert f"LIMIT $4" in query_sql # Limite finale
    assert f"OFFSET $5" in query_sql # Offset final
    
    # Vérifier les paramètres passés dans l'ordre
    assert query_params[0] == str(query_vector).replace(" ", "") # $1: Vecteur (Correct format '[...]')
    assert query_params[1] == expected_knn_limit      # $2: Limite KNN
    assert query_params[2] == json.dumps(criteria)    # $3: Filtre metadata
    assert query_params[3] == test_limit             # $4: Limite finale
    assert query_params[4] == test_offset            # $5: Offset final

    # Vérifier les résultats
    assert isinstance(found_events, list)
    assert len(found_events) == 1 # Seul l'enregistrement mocké correspond
    assert isinstance(found_events[0], EventModel)
    assert found_events[0].id == expected_id1
    assert found_events[0].metadata["tag"] == "hybrid"
    assert found_events[0].similarity_score == 0.02

# Ajouter ici d'autres tests pour update_metadata, delete quand implémentés 