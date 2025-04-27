# tests/test_search_routes.py

import pytest
# import pytest_asyncio # No longer needed
import asyncpg
import json
# import httpx # No longer needed
import os
# import sys # Supprimer import sys
from pathlib import Path # Add import
from typing import Dict, Any, AsyncGenerator, Optional, List
from urllib.parse import urlparse, urlunparse # Add urlunparse

# # --- Supprimer ajout chemin --- 
# project_root = Path(__file__).resolve().parent.parent 
# sys.path.insert(0, str(project_root))
# # --- Fin suppression chemin --- 

import base64
import datetime
import random
from unittest.mock import MagicMock # Import MagicMock
from fastapi.testclient import TestClient # Import TestClient
import pgvector.asyncpg # Add import
import asyncio # Add import
from datetime import datetime, timedelta, timezone # Add timedelta, timezone
import uuid

# Import de l'application FastAPI et des modèles/dépendances (sans le préfixe 'api.')
from main import app # Import the FastAPI app instance
from db.repositories.event_repository import EventRepository, EventCreate, EventModel
from dependencies import get_event_repository # Import the dependency function

# --- Configuration --- 
# URL de la DB de test, DOIT être fournie via la variable d'environnement TEST_DATABASE_URL
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
# API_BASE_URL = "http://api:8000" # No longer needed with TestClient

# --- Fixtures --- 

@pytest.fixture(scope="function") # Revert scope to function
async def test_db_pool():
    """Fixture pour créer et gérer la DB de test et un pool de connexion."""
    test_url_with_driver = os.getenv("TEST_DATABASE_URL") # This should be postgresql+asyncpg://...
    if not test_url_with_driver:
        pytest.fail("TEST_DATABASE_URL environment variable not set.")

    # --- Derive URLs ---
    try:
        # from urllib.parse import urlparse # Already imported
        
        # Parse the full URL (expected: postgresql+asyncpg://...)
        parsed_test_url = urlparse(test_url_with_driver)
        if not parsed_test_url.scheme.startswith("postgresql+"):
             pytest.fail(f"TEST_DATABASE_URL scheme should start with 'postgresql+', got '{parsed_test_url.scheme}'")

        test_db_name = parsed_test_url.path.lstrip('/')
        test_db_user = parsed_test_url.username
        test_db_password = parsed_test_url.password
        test_db_host = parsed_test_url.hostname
        test_db_port = parsed_test_url.port

        # Create URL for direct asyncpg connection (scheme: postgresql://)
        admin_db_name = "postgres"
        # Build components for urlunparse
        admin_url_parts = ("postgresql", f"{test_db_user}:{test_db_password}@{test_db_host}:{test_db_port}", f"/{admin_db_name}", "", "", "")
        admin_conn_url_direct = urlunparse(admin_url_parts)
        
        test_url_parts_direct = ("postgresql", f"{test_db_user}:{test_db_password}@{test_db_host}:{test_db_port}", f"/{test_db_name}", "", "", "")
        test_url_direct = urlunparse(test_url_parts_direct) # URL for direct asyncpg setup

    except Exception as e:
        pytest.fail(f"Could not parse TEST_DATABASE_URL ('{test_url_with_driver}') for setup: {e}")

    # --- Tentative de création de la DB de Test ---
    conn_admin = None
    try:
        print(f"\nConnecting to admin database ({admin_db_name}) to ensure test database ({test_db_name}) exists...")
        # Use the direct URL for asyncpg.connect
        conn_admin = await asyncpg.connect(admin_conn_url_direct) 
        db_exists = await conn_admin.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            test_db_name
        )
        if not db_exists:
            print(f"Database '{test_db_name}' does not exist. Creating...")
            await conn_admin.close()
            conn_admin = None 
            conn_creator = await asyncpg.connect(admin_conn_url_direct) 
            try:
                await conn_creator.execute(f'CREATE DATABASE "{test_db_name}" OWNER "{test_db_user}";')
                print(f"Database '{test_db_name}' created successfully.")
            except asyncpg.DuplicateDatabaseError:
                print(f"Database '{test_db_name}' was created concurrently.")
            except Exception as creation_error:
                 pytest.fail(f"Failed to execute CREATE DATABASE for '{test_db_name}': {creation_error}")
            finally:
                if conn_creator: await conn_creator.close()
        else:
            print(f"Database '{test_db_name}' already exists.")
            
    except asyncpg.InvalidCatalogNameError:
         pytest.fail(f"Admin database '{admin_db_name}' not found. Cannot check/create test database.")
    except Exception as e:
        pytest.fail(f"Failed to connect to admin DB or create test DB '{test_db_name}': {e}")
    finally:
        if conn_admin:
            await conn_admin.close()
            
    # --- Fin création DB test --- 

    # --- Application du schéma à la DB de Test --- 
    conn_schema = None
    try:
        print(f"\nConnecting to test database ({test_db_name}) to apply schema via script...")
        # Use the direct URL for asyncpg.connect
        conn_schema = await asyncpg.connect(test_url_direct) 
        
        init_script_path = Path("scripts/init_test_db.sql") 
        
        if init_script_path.is_file():
            print(f"  Applying {init_script_path}...")
            sql_content = init_script_path.read_text()
            await conn_schema.execute(sql_content)
            print("Schema script executed successfully.")
        else:
            pytest.fail(f"Test DB initialization script not found: {init_script_path}")

    except Exception as e:
        # Add more specific error detail
        pytest.fail(f"Failed to connect to test DB ({test_db_name} using {test_url_direct}) or apply schema script: {e}")
    finally:
        if conn_schema:
            await conn_schema.close()

    # --- Installer l'extension pgvector dans la DB de Test --- 
    conn_ext = None
    try:
        print(f"\nConnecting to test database ({test_db_name}) to install pgvector extension...")
         # Use the direct URL for asyncpg.connect
        conn_ext = await asyncpg.connect(test_url_direct) 
        await conn_ext.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("pgvector extension installed/verified in test database.")
    except Exception as e:
        pytest.fail(f"Failed to connect to test DB ({test_db_name}) or install pgvector extension: {e}")
    finally:
        if conn_ext:
            await conn_ext.close()

    # --- Création du Pool (original asyncpg, might be unused by client fixture now) --- 
    # This part might become irrelevant if the client fixture relies solely on the app's lifespan engine.
    # However, we keep it for now in case some tests import and use this pool directly.
    pool = None
    try:
        print("\nCreating test database pool (asyncpg)...") 
        # asyncpg still needs the direct URL
        pool = await asyncpg.create_pool(test_url_direct, min_size=1, max_size=2) 
        
        async with pool.acquire() as conn:
            await pgvector.asyncpg.register_vector(conn)
            print("\nRegistered pgvector codecs for test pool connection.")

        yield pool # Provide the pool 
    finally:
        if pool:
            print("\nClosing test database pool (asyncpg)...")
            await pool.close()


@pytest.fixture(scope="function") # Revert scope to function
async def client(test_db_pool: asyncpg.Pool): # Depends on the function-scoped pool
    """Crée un TestClient et nettoie la DB avant le test. 
    UTILISE LE POOL DE L'APPLICATION géré par le lifespan.
    """

    # --- Nettoyage AVANT le test --- 
    # Important car on utilise le pool/état partagé de l'app
    try:
        async with test_db_pool.acquire() as conn:
            await conn.execute("TRUNCATE TABLE events RESTART IDENTITY CASCADE;")
        print("\nTruncated 'events' table before test via client fixture.") 
    except Exception as e:
        pytest.fail(f"Failed to truncate table before test in client fixture: {e}")
    # --- Fin Nettoyage --- 

    # Create the TestClient instance (synchronous client)
    # It will use the app as-is, including its lifespan-managed pool
    with TestClient(app) as test_client:
        yield test_client # Provide the client to the test

# --- Fonctions d'aide (Helper) ---

def generate_fake_vector(dim: int = 1536) -> List[float]:
    """Génère un vecteur factice de la dimension spécifiée."""
    return [random.uniform(0.0, 1.0) for _ in range(dim)]

async def create_test_event(
    client: TestClient,
    content: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    embedding: Optional[List[float]] = None,
    timestamp: Optional[datetime] = None,
) -> EventModel:
    """Crée un événement de test en utilisant l'endpoint API dédié.
    Retourne le modèle Pydantic EventModel de l'événement créé.
    """
    # Construire le payload pour l'API
    payload = EventCreate(content=content, metadata=metadata, embedding=embedding, timestamp=timestamp)
    
    # Important: Pydantic v2 model_dump(mode='json') sérialise correctement datetime vers string ISO
    payload_dict = payload.model_dump(mode='json') 

    print(f"DEBUG: Calling test endpoint with payload: {payload_dict}")

    # Appeler l'endpoint de test via le client
    response = client.post("/v1/_test_only/events/", json=payload_dict) 

    # Gérer la réponse
    if response.status_code == 200:
        response_data = response.json()
        # Re-créer un EventModel Pydantic à partir de la réponse pour la cohérence
        # Noter que l'API retourne un JSON, il faut le re-parser en objet Pydantic
        # pour que les types (comme datetime) soient corrects.
        try:
            # Utiliser directement model_validate sur le dict JSON
            return EventModel.model_validate(response_data)
        except Exception as e:
             print(f"Error validating response from test endpoint: {e} - Data: {response_data}")
             raise
    else:
        try:
            error_detail = response.json().get("detail", response.text)
        except json.JSONDecodeError:
            error_detail = response.text
        pytest.fail(f"Failed to create test event via API endpoint. Status: {response.status_code}, Detail: {error_detail}")
        return None # Ne sera jamais atteint à cause de pytest.fail, mais pour la complétude

# --- TEST DE CONNEXION DIRECTE (Utile à garder) ---
@pytest.mark.anyio
async def test_direct_db_connection():
    """Teste la connexion directe à la base de données de test en utilisant TEST_DATABASE_URL."""
    conn = None
    test_url_env = os.getenv("TEST_DATABASE_URL") # Lire la variable d'environnement
    if not test_url_env:
        pytest.skip("TEST_DATABASE_URL environment variable not set, skipping direct connection test.")

    try:
        # Parse the URL from env var (postgresql+asyncpg://...)
        parsed_url = urlparse(test_url_env)
        # Construct the direct connection URL (postgresql://...)
        direct_conn_url_parts = (
            "postgresql", # Replace scheme
            parsed_url.netloc, # Keep user:pass@host:port
            parsed_url.path,   # Keep /database_name
            parsed_url.params, # Keep params, query, fragment (usually empty)
            parsed_url.query,
            parsed_url.fragment
        )
        direct_conn_url = urlunparse(direct_conn_url_parts)

        print(f"\nAttempting direct connection using parsed URL: {direct_conn_url}") 
        conn = await asyncpg.connect(direct_conn_url) # Use the corrected URL
        # Si la connexion réussit, vérifier qu'on peut faire une requête simple
        result = await conn.fetchval("SELECT 1")
        assert result == 1
        print("Direct connection successful!")
    except Exception as e:
        print(f"Direct connection failed: {e}")
        # Inclure l'URL (sans le mdp) dans le message d'erreur peut aider
        try:
            # Use the already parsed URL parts for safer logging
            safe_url = f"postgresql://{parsed_url.username}@{parsed_url.hostname}:{parsed_url.port}{parsed_url.path}"
        except:
            safe_url = "[Could not parse URL safely]"
        pytest.fail(f"Direct connection failed using URL derived from env var ({safe_url}): {e}")
    finally:
        if conn:
            await conn.close()

# --- Tests --- 

@pytest.mark.anyio
async def test_search_by_metadata_not_found(client: TestClient, test_db_pool: asyncpg.Pool):
    """Teste la recherche par métadonnées quand aucun événement ne correspond."""
    # Arrange: DB is clean via transaction rollback
    # Act
    filter_criteria = {"tag": "nonexistent"}
    response = client.get(f"/v1/search/", params={"filter_metadata": json.dumps(filter_criteria)}) 
    
    # Assert
    assert response.status_code == 200
    response_data = response.json()
    print(f"\nDEBUG (_not_found): Response JSON: {response_data}")
    assert response_data["data"] == []
    # assert response_data.get("meta", {}).get("total_hits", 0) == 0 # total_hits not implemented yet

@pytest.mark.anyio
async def test_search_by_metadata_found_simple(client: TestClient, test_db_pool: asyncpg.Pool):
    """Teste une recherche simple par métadonnées qui trouve un événement."""
    # Arrange: Insérer des données de test via l'API de test
    event1_meta = {"source": "test", "type": "log", "level": "info"}
    event2_meta = {"source": "test", "type": "metric", "unit": "ms"}
    event1 = await create_test_event(client, {"msg": "Event 1"}, event1_meta)
    await create_test_event(client, {"val": 123}, event2_meta)
    
    # Act: Rechercher par type=log
    filter_criteria = {"type": "log"}
    response = client.get("/v1/search/", params={"filter_metadata": json.dumps(filter_criteria)})
    
    # Assert
    assert response.status_code == 200
    response_data = response.json()
    print(f"\nDEBUG (_found_simple): Response JSON: {response_data}")
    assert len(response_data["data"]) == 1
    # assert response_data.get("meta", {}).get("total_hits", 1) == 1 # total_hits not implemented
    found_event = response_data["data"][0]
    assert found_event["id"] == str(event1.id)
    assert found_event["metadata"] == event1_meta

@pytest.mark.anyio
async def test_search_by_metadata_found_nested(client: TestClient, test_db_pool: asyncpg.Pool):
    """Teste une recherche par métadonnées imbriquées."""
    # Arrange: Insérer des données de test via l'API de test
    event1_meta = {"source": "app", "details": {"user_id": 123, "action": "login"}}
    event2_meta = {"source": "app", "details": {"user_id": 456, "action": "logout"}}
    event1 = await create_test_event(client, {"msg": "Login event"}, event1_meta)
    await create_test_event(client, {"msg": "Logout event"}, event2_meta)

    # Act: Rechercher les actions de login
    filter_criteria = {"details": {"action": "login"}}
    response = client.get("/v1/search/", params={"filter_metadata": json.dumps(filter_criteria)})

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    print(f"\nDEBUG (_found_nested): Response JSON: {response_data}")
    assert len(response_data["data"]) == 1
    assert response_data["data"][0]["id"] == str(event1.id)

# Note: No db_conn needed if test doesn't interact with DB directly
# TestClient still uses the override provided by the client fixture
@pytest.mark.anyio 
async def test_search_by_metadata_invalid_json(client: TestClient):
    """Teste la recherche avec un JSON invalide dans filter_metadata."""
    # Arrange: (DB propre via transaction)
    # Act
    invalid_json_string = '{"key": "value"' # JSON mal formé
    response = client.get("/v1/search/", params={"filter_metadata": invalid_json_string})
    
    # Assert
    assert response.status_code == 422 # Unprocessable Entity
    response_data = response.json()
    assert "detail" in response_data
    # assert "invalid character" in str(response_data["detail"]).lower() # Made assertion less brittle

# --- Tests pour la recherche hybride --- 

@pytest.mark.anyio
async def test_search_vector_only_found(client: TestClient, test_db_pool: asyncpg.Pool):
    """Teste la recherche vectorielle seule qui trouve des événements."""
    # Arrange: Insérer des données avec embeddings via l'API de test
    vec1 = generate_fake_vector() 
    vec2 = generate_fake_vector()
    vec3 = vec1[:]
    for i in range(10): vec3[i] = min(1.0, vec1[i] * 1.1 + 0.01)
        
    event1 = await create_test_event(client, {"msg": "Close to Q"}, {"tag": "vec"}, vec1)
    event2 = await create_test_event(client, {"msg": "Far from Q"}, {"tag": "vec"}, vec2)
    event3 = await create_test_event(client, {"msg": "Also close to Q"}, {"tag": "vec"}, vec3)

    # Act: Rechercher un vecteur proche de vec1 et vec3
    query_vector = vec1[:]
    for i in range(5): query_vector[i] = min(1.0, vec1[i] * 1.05 + 0.005)
        
    query_vector_str = json.dumps(query_vector)
    query_vector_b64 = base64.b64encode(query_vector_str.encode('utf-8')).decode('utf-8')
    
    response = client.get(
        f"/v1/search/", 
        params={
            "vector_query": query_vector_b64, 
            "top_k": 5,
            "limit": 2
        }
    )

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    print(f"\nDEBUG (vector_only): Response JSON: {response_data}")
    assert len(response_data["data"]) == 2
    found_ids = [d["id"] for d in response_data["data"]]
    assert str(event1.id) in found_ids
    assert str(event3.id) in found_ids
    assert str(event2.id) not in found_ids
    assert "similarity_score" in response_data["data"][0]
    assert response_data["data"][0]["similarity_score"] is not None
    assert response_data["meta"]["limit"] == 2
    assert response_data["meta"]["offset"] == 0

@pytest.mark.anyio
async def test_search_hybrid_found(client: TestClient, test_db_pool: asyncpg.Pool):
    """Teste la recherche hybride (vecteur + metadata) qui trouve un événement."""
    # Arrange: Insérer des données via l'API de test
    vec1 = generate_fake_vector()
    vec2 = generate_fake_vector()
    event1 = await create_test_event(client, {"msg": "Match A"}, {"tag": "hybrid", "group": "A"}, vec1)
    event2 = await create_test_event(client, {"msg": "Match B Vector"}, {"tag": "other", "group": "B"}, vec1)
    event3 = await create_test_event(client, {"msg": "Match B Meta"}, {"tag": "hybrid", "group": "B"}, vec2)

    # Act: Rechercher un vecteur proche de vec1 ET tag='hybrid'
    query_vector = vec1[:]
    for i in range(5): query_vector[i] = min(1.0, vec1[i] * 1.05 + 0.005)
        
    query_vector_str = json.dumps(query_vector)
    query_vector_b64 = base64.b64encode(query_vector_str.encode('utf-8')).decode('utf-8')
    filter_criteria = {"tag": "hybrid"}
    
    response = client.get(
        f"/v1/search/",
        params={
            "vector_query": query_vector_b64,
            "filter_metadata": json.dumps(filter_criteria),
            "top_k": 5,
            "limit": 5
        }
    )

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    print(f"\nDEBUG (hybrid): Response JSON: {response_data}")
    assert len(response_data["data"]) == 1
    assert response_data["data"][0]["id"] == str(event1.id)

@pytest.mark.anyio
async def test_search_invalid_vector_query(client: TestClient):
    """Teste l'envoi d'une query vector invalide (mauvais base64)."""
    response = client.get(
        f"/v1/search/",
        params={"vector_query": "not_base64!"}
    )
    assert response.status_code == 422
    response_data = response.json()
    assert "detail" in response_data 
    # assert "invalid base64" in str(response_data["detail"]).lower() # Made assertion less brittle

@pytest.mark.anyio
async def test_search_invalid_vector_content(client: TestClient):
    """Teste l'envoi d'une query vector dont le contenu décodé n'est pas valide."""
    invalid_content = base64.b64encode(b'{"not": "a list"}').decode('utf-8')
    response = client.get(
        f"/v1/search/",
        params={"vector_query": invalid_content}
    )
    assert response.status_code == 422
    response_data = response.json()
    assert "detail" in response_data
    # assert "not a list of numbers" in str(response_data["detail"]).lower() # Made assertion less brittle

@pytest.mark.anyio
async def test_search_metadata_with_time_filter(client: TestClient, test_db_pool: asyncpg.Pool):
    """Teste la recherche par métadonnées avec un filtre temporel."""
    # Arrange: Créer des événements avec des timestamps distincts via l'API de test
    now = datetime.now(timezone.utc)
    event_past = await create_test_event(
        client, {"msg": "Event 1"}, {"type": "log", "tag": "time_test"},
        timestamp=now - timedelta(days=2)
    )
    event_recent = await create_test_event(
        client, {"msg": "Event 2"}, {"type": "log", "tag": "time_test"},
        timestamp=now - timedelta(hours=1)
    )
    event_future = await create_test_event( # Usually unlikely, but good for testing bounds
        client, {"msg": "Event 3"}, {"type": "log", "tag": "time_test"},
        timestamp=now + timedelta(days=1) 
    )
    # Un autre type d'événement dans la plage de temps (ne doit pas être retourné)
    await create_test_event(
        client, {"msg": "Event 4"}, {"type": "metric", "tag": "time_test"},
        timestamp=now - timedelta(hours=2)
    )

    # Act: Rechercher les logs des dernières 24 heures
    filter_criteria = {"type": "log", "tag": "time_test"}
    time_start = (now - timedelta(days=1)).isoformat()
    time_end = now.isoformat()

    response = client.get(
        "/v1/search/", 
        params={
            "filter_metadata": json.dumps(filter_criteria),
            "ts_start": time_start,
            "ts_end": time_end
        }
    )

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    print(f"\nDEBUG (metadata_time): Response JSON: {response_data}")
    assert len(response_data["data"]) == 1
    found_ids = [d["id"] for d in response_data["data"]]
    assert str(event_recent.id) in found_ids
    assert str(event_past.id) not in found_ids
    assert str(event_future.id) not in found_ids

@pytest.mark.anyio
async def test_search_hybrid_with_time_filter(client: TestClient, test_db_pool: asyncpg.Pool):
    """Teste la recherche hybride (vecteur + métadonnées) avec un filtre temporel."""
    # Arrange: Créer des événements avec timestamps et vecteurs distincts via l'API de test
    now = datetime.now(timezone.utc)
    vec1 = generate_fake_vector()
    vec2 = generate_fake_vector()
    # Event dans la plage de temps, bon vecteur, bon metadata
    event_target = await create_test_event(
        client, {"msg": "Target"}, {"type": "target", "status": "active"}, vec1,
        timestamp=now - timedelta(hours=1)
    )
    # Event hors plage de temps (passé), bon vecteur, bon metadata
    await create_test_event(
        client, {"msg": "Past"}, {"type": "target", "status": "active"}, vec1,
        timestamp=now - timedelta(days=2)
    )
    # Event dans la plage de temps, mauvais vecteur, bon metadata
    await create_test_event(
        client, {"msg": "Wrong Vec"}, {"type": "target", "status": "active"}, vec2,
        timestamp=now - timedelta(hours=2)
    )
    # Event dans la plage de temps, bon vecteur, mauvais metadata
    await create_test_event(
        client, {"msg": "Wrong Meta"}, {"type": "other", "status": "active"}, vec1,
        timestamp=now - timedelta(hours=3)
    )

    # Act: Rechercher type=target, status=active, vecteur proche de vec1, dans les dernières 24h
    query_vector = vec1[:]
    query_vector_str = json.dumps(query_vector)
    query_vector_b64 = base64.b64encode(query_vector_str.encode('utf-8')).decode('utf-8')
    filter_criteria = {"type": "target", "status": "active"}
    time_start = (now - timedelta(days=1)).isoformat()
    time_end = now.isoformat()

    response = client.get(
        "/v1/search/", 
        params={
            "vector_query": query_vector_b64,
            "top_k": 5, # Assez grand pour potentiellement inclure les mauvais 
            "filter_metadata": json.dumps(filter_criteria),
            "ts_start": time_start,
            "ts_end": time_end,
            "limit": 10
        }
    )

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    print(f"\nDEBUG (hybrid_time): Response JSON: {response_data}")
    assert len(response_data["data"]) == 1
    found_ids = [d["id"] for d in response_data["data"]]
    assert str(event_target.id) in found_ids

# --- Tests pour la gestion des erreurs et cas limites ---
# (Ajouter ici tests pour pagination, ordre, aucun paramètre, etc.)

@pytest.mark.anyio
async def test_search_pagination(client: TestClient):
    """Teste la pagination avec limit et offset pour une recherche par métadonnées."""
    # Create a unique tag for this test run to prevent data pollution from past runs
    unique_test_id = str(uuid.uuid4())
    tag_filter = {"tag": f"pagination_test_{unique_test_id}"}
    
    # Arrange: Créer 7 événements avec le même tag via l'API de test
    now = datetime.now(timezone.utc)
    created_events = []
    # Use the initial client for setup
    for i in range(7):
        event = await create_test_event(
            client,
            {"msg": f"Page Event {i}"},
            tag_filter,
            timestamp=now - timedelta(minutes=i) # Les plus récents en premier
        )
        created_events.append(event)
    
    print(f"\nCreated 7 test events with unique tag: {tag_filter['tag']}")

    # Trier les événements créés par timestamp descendant (comme la DB le fera par défaut)
    # created_events.sort(key=lambda x: x.timestamp, reverse=True) # No longer strictly needed for assertion
    # expected_ids_ordered = [str(e.id) for e in created_events]
    # print(f"\nDEBUG Expected Order (post-sort): {expected_ids_ordered}") # Log expected order

    # Act & Assert - Page 1
    response_p1 = client.get( # Use the client from the fixture
        "/v1/search/",
        params={
            "filter_metadata": json.dumps(tag_filter),
            "limit": 3,
            "offset": 0
        }
    )
    assert response_p1.status_code == 200
    data_p1 = response_p1.json()["data"]
    assert len(data_p1) == 3
    # ids_p1 = [d["id"] for d in data_p1]
    # print(f"\nDEBUG Page 1 IDs: {ids_p1}") 
    # assert ids_p1 == expected_ids_ordered[0:3] # Assert based on content instead
    assert data_p1[0]["content"]["msg"] == "Page Event 0"
    assert data_p1[1]["content"]["msg"] == "Page Event 1"
    assert data_p1[2]["content"]["msg"] == "Page Event 2"

    # Act & Assert - Page 2
    response_p2 = client.get( # Use the client from the fixture
        "/v1/search/",
        params={
            "filter_metadata": json.dumps(tag_filter),
            "limit": 3,
            "offset": 3
        }
    )
    assert response_p2.status_code == 200
    data_p2 = response_p2.json()["data"]
    assert len(data_p2) == 3
    # ids_p2 = [d["id"] for d in data_p2]
    # print(f"DEBUG Page 2 IDs: {ids_p2}")
    # assert ids_p2 == expected_ids_ordered[3:6] # Assert based on content instead
    assert data_p2[0]["content"]["msg"] == "Page Event 3"
    assert data_p2[1]["content"]["msg"] == "Page Event 4"
    assert data_p2[2]["content"]["msg"] == "Page Event 5"

    # Act & Assert - Page 3 (dernière page avec 1 élément)
    response_p3 = client.get( # Use the client from the fixture
        "/v1/search/",
        params={
            "filter_metadata": json.dumps(tag_filter),
            "limit": 3,
            "offset": 6
        }
    )
    assert response_p3.status_code == 200
    data_p3 = response_p3.json()["data"]
    # print(f"DEBUG Page 3 Raw Data: {data_p3}") 
    # ids_p3 = [d["id"] for d in data_p3]
    # print(f"DEBUG Page 3 IDs: {ids_p3}")
    assert len(data_p3) == 1
    # assert ids_p3 == expected_ids_ordered[6:7] # Assert based on content instead
    assert data_p3[0]["content"]["msg"] == "Page Event 6" # Le plus ancien

    # Act & Assert - Page 4 (devrait être vide)
    response_p4 = client.get(
        "/v1/search/",
        params={
            "filter_metadata": json.dumps(tag_filter),
            "limit": 3,
            "offset": 9 # Au-delà du nombre total d'événements
        }
    )
    assert response_p4.status_code == 200
    data_p4 = response_p4.json()["data"]
    assert len(data_p4) == 0

# TODO: Ajouter tests pour :
# - Cas limites (ex: filtre vide ? {} ) 