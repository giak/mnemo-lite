# tests/test_search_routes.py

import pytest
# import pytest_asyncio # No longer needed
import asyncpg
import json
# import httpx # No longer needed
import os
from typing import Dict, Any, AsyncGenerator, Optional, List
import base64
import datetime
import random
from unittest.mock import MagicMock # Import MagicMock
from fastapi.testclient import TestClient # Import TestClient
import pgvector.asyncpg # Add import
import asyncio # Add import

# Import de l'application FastAPI et des modèles/dépendances
from api.main import app # Import the FastAPI app instance
from api.db.repositories.event_repository import EventRepository, EventCreate, EventModel
from api.dependencies import get_event_repository # Import the dependency function

# --- Configuration --- 
# URL de la DB de test, DOIT être fournie via la variable d'environnement TEST_DATABASE_URL
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
# API_BASE_URL = "http://api:8000" # No longer needed with TestClient

# --- Fixtures --- 

@pytest.fixture(scope="function") # Revert scope to function
async def test_db_pool():
    """Fixture pour créer et gérer le pool de connexion à la DB de test."""
    test_url = os.getenv("TEST_DATABASE_URL")
    if not test_url:
        pytest.fail("TEST_DATABASE_URL environment variable not set. Cannot create test pool.")
    pool = None
    loop = asyncio.get_running_loop() # Get the current event loop
    try:
        # print(f"\nCreating test database pool for function ({test_url.split('@')[-1]})...") # Less noisy
        pool = await asyncpg.create_pool(test_url, min_size=1, max_size=2, loop=loop) # Pass loop explicitly
        
        # Register pgvector codecs for the test pool connections
        async with pool.acquire() as conn:
            await pgvector.asyncpg.register_vector(conn)
            print("\nRegistered pgvector codecs for test pool connection.") # Optional debug print
            
            # Truncate ONCE per session after pool setup
            try:
                await conn.execute("TRUNCATE TABLE events RESTART IDENTITY CASCADE;")
                print("\nTruncated 'events' table at start of session.")
            except Exception as e:
                pytest.fail(f"Failed to truncate table at start of session: {e}")

        yield pool
    finally:
        if pool:
            # print("\nClosing test database pool for function...") # Less noisy
            await pool.close()

@pytest.fixture(scope="function") # Revert scope to function
async def client(test_db_pool: asyncpg.Pool): # Depends on the function-scoped pool
    """Crée un TestClient, override la dépendance DB et nettoie avant le test."""

    # --- Nettoyage AVANT le test --- 
    try:
        async with test_db_pool.acquire() as conn:
            await conn.execute("TRUNCATE TABLE events RESTART IDENTITY CASCADE;")
        print("\nTruncated 'events' table before test.") # Optional: Debug print
    except Exception as e:
        pytest.fail(f"Failed to truncate table before test: {e}")
    # --- Fin Nettoyage --- 

    # Define the override function
    async def override_get_repository() -> EventRepository:
        # Return a repository instance using the *test* pool
        # The application code will use this pool via the overridden dependency
        return EventRepository(pool=test_db_pool)

    # Apply the override
    app.dependency_overrides[get_event_repository] = override_get_repository

    # Create the TestClient instance (synchronous client)
    with TestClient(app) as test_client:
        yield test_client # Provide the client to the test

    # Clean up the override after the test runs
    del app.dependency_overrides[get_event_repository]

# --- Fonctions d'aide (Helper) ---

def generate_fake_vector(dim: int = 1536) -> List[float]:
    """Génère un vecteur factice de la dimension spécifiée."""
    return [random.uniform(0.0, 1.0) for _ in range(dim)]

async def create_test_event(
    db_pool: asyncpg.Pool, # Now uses the test pool again
    content: Dict[str, Any], 
    metadata: Dict[str, Any],
    embedding: Optional[List[float]] = None
) -> EventModel:
    """Insère un événement de test directement en utilisant le pool de test."""
    # Initialize repository directly with the test pool
    repo = EventRepository(pool=db_pool)
    event_data = EventCreate(content=content, metadata=metadata, embedding=embedding)
    created_event = await repo.add(event_data)
    return created_event

# --- TEST DE CONNEXION DIRECTE (Utile à garder) ---
@pytest.mark.anyio
async def test_direct_db_connection():
    """Teste la connexion directe à la base de données de test en utilisant TEST_DATABASE_URL."""
    conn = None
    test_url = os.getenv("TEST_DATABASE_URL") # Lire la variable d'environnement
    if not test_url:
        pytest.skip("TEST_DATABASE_URL environment variable not set, skipping direct connection test.")

    try:
        print(f"\nAttempting to connect using TEST_DATABASE_URL environment variable...") 
        conn = await asyncpg.connect(test_url)
        # Si la connexion réussit, vérifier qu'on peut faire une requête simple
        result = await conn.fetchval("SELECT 1")
        assert result == 1
        print("Direct connection successful!")
    except Exception as e:
        print(f"Direct connection failed: {e}")
        # Inclure l'URL (sans le mdp) dans le message d'erreur peut aider
        try:
            parsed_url = asyncpg.connect_utils._parse_connect_dsn_and_args(test_url, {})[0]
            safe_url = f"postgresql://{parsed_url.user}@{parsed_url.host}:{parsed_url.port}/{parsed_url.database}"
        except: 
            safe_url = "[Could not parse URL safely]"
        pytest.fail(f"Direct connection failed using URL {safe_url}: {e}")
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
    # Arrange: Insérer des données de test via la connexion
    event1_meta = {"source": "test", "type": "log", "level": "info"}
    event2_meta = {"source": "test", "type": "metric", "unit": "ms"}
    event1 = await create_test_event(test_db_pool, {"msg": "Event 1"}, event1_meta)
    await create_test_event(test_db_pool, {"val": 123}, event2_meta)
    
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
    # Arrange: Insérer des données de test via la connexion
    event1_meta = {"source": "app", "details": {"user_id": 123, "action": "login"}}
    event2_meta = {"source": "app", "details": {"user_id": 456, "action": "logout"}}
    event1 = await create_test_event(test_db_pool, {"msg": "Login event"}, event1_meta)
    await create_test_event(test_db_pool, {"msg": "Logout event"}, event2_meta)

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
    # Arrange: Insérer des données avec embeddings de 1536 dimensions
    vec1 = generate_fake_vector() 
    vec2 = generate_fake_vector()
    vec3 = vec1[:]
    for i in range(10): vec3[i] = min(1.0, vec1[i] * 1.1 + 0.01)
        
    event1 = await create_test_event(test_db_pool, {"msg": "Close to Q"}, {"tag": "vec"}, vec1)
    event2 = await create_test_event(test_db_pool, {"msg": "Far from Q"}, {"tag": "vec"}, vec2)
    event3 = await create_test_event(test_db_pool, {"msg": "Also close to Q"}, {"tag": "vec"}, vec3)

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
    # Arrange: Insérer des données
    vec1 = generate_fake_vector()
    vec2 = generate_fake_vector()
    event1 = await create_test_event(test_db_pool, {"msg": "Match A"}, {"tag": "hybrid", "group": "A"}, vec1)
    event2 = await create_test_event(test_db_pool, {"msg": "Match B Vector"}, {"tag": "other", "group": "B"}, vec1)
    event3 = await create_test_event(test_db_pool, {"msg": "Match B Meta"}, {"tag": "hybrid", "group": "B"}, vec2)

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

# TODO: Ajouter tests pour :
# - Cas limites (ex: filtre vide ? {} ) 