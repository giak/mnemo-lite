# tests/test_search_routes.py

import pytest
import pytest_asyncio
import asyncpg
import json
import httpx
import os
from typing import Dict, Any, AsyncGenerator

# Import de l'application FastAPI et des modèles
from api.db.repositories.event_repository import EventRepository, EventCreate, EventModel

# --- Configuration --- 
# URL de la DB de test, DOIT être fournie via la variable d'environnement TEST_DATABASE_URL
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
# URL de l'API à tester (interne au réseau Docker)
API_BASE_URL = "http://api:8000" # Cible le service 'api' sur son port interne 8000

# --- Fixtures --- 

@pytest_asyncio.fixture(scope="function")
async def test_db_pool():
    """Fixture pour créer et gérer le pool de connexion à la DB de test.
    Scope 'function' pour isolation.
    """
    test_url = os.getenv("TEST_DATABASE_URL")
    if not test_url:
        pytest.fail("TEST_DATABASE_URL environment variable not set. Cannot create test pool.")
    pool = None
    try:
        pool = await asyncpg.create_pool(test_url, min_size=1, max_size=2) # Pool dédié aux tests
        yield pool
    finally:
        if pool:
            await pool.close()

@pytest_asyncio.fixture(scope="function")
async def db_pool(test_db_pool):
    """Fixture pour obtenir le pool de test et nettoyer la table après chaque test."""
    yield test_db_pool # Fournir le pool aux tests
    
    # Nettoyage explicite après le test
    async with test_db_pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE events RESTART IDENTITY CASCADE;")

@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Crée un client HTTP async qui cible l'API en cours d'exécution via httpx."""
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=10.0) as async_client:
        # Vérifier si l'API est joignable avant de lancer les tests
        try:
            # Utiliser l'endpoint /v1/health (sans 'z')
            response = await async_client.get("/v1/health") 
            response.raise_for_status() # Lève une exception pour 4xx/5xx
        except (httpx.ConnectError, httpx.HTTPStatusError) as e:
            pytest.fail(f"Impossible de joindre l'API sur {API_BASE_URL}/v1/health. L'avez-vous démarrée avant ? Erreur: {e}")
        yield async_client

# --- Fonctions d'aide (Helper) ---

async def create_test_event(db_pool: asyncpg.Pool, content: Dict[str, Any], metadata: Dict[str, Any]) -> EventModel:
    """Insère un événement de test directement en utilisant le pool de test."""
    repo = EventRepository(pool=db_pool)
    event_data = EventCreate(content=content, metadata=metadata)
    created_event = await repo.add(event_data)
    return created_event

# --- TEST DE CONNEXION DIRECTE (Utile à garder) ---
@pytest.mark.asyncio
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

@pytest.mark.asyncio
async def test_search_by_metadata_not_found(client: httpx.AsyncClient, db_pool: asyncpg.Pool):
    """Teste la recherche par métadonnées quand aucun événement ne correspond."""
    # Arrange: DB est propre (grâce au nettoyage de la fixture db_pool)
    # Act
    filter_criteria = {"tag": "nonexistent"}
    # Utiliser await client.get pour httpx
    response = await client.get(f"/v1/search/", params={"filter_metadata": json.dumps(filter_criteria)}) 
    
    # Assert
    assert response.status_code == 200
    response_data = response.json()
    print(f"\nDEBUG (_not_found): Response JSON: {response_data}")
    assert response_data["data"] == []
    assert response_data.get("meta", {}).get("total_hits", 0) == 0

@pytest.mark.asyncio
async def test_search_by_metadata_found_simple(client: httpx.AsyncClient, db_pool: asyncpg.Pool):
    """Teste une recherche simple par métadonnées qui trouve un événement."""
    # Arrange: Insérer des données de test via le pool
    event1_meta = {"source": "test", "type": "log", "level": "info"}
    event2_meta = {"source": "test", "type": "metric", "unit": "ms"}
    event1 = await create_test_event(db_pool, {"msg": "Event 1"}, event1_meta)
    await create_test_event(db_pool, {"val": 123}, event2_meta)
    
    # Act: Rechercher par type=log
    filter_criteria = {"type": "log"}
    response = await client.get("/v1/search/", params={"filter_metadata": json.dumps(filter_criteria)})
    
    # Assert
    assert response.status_code == 200
    response_data = response.json()
    print(f"\nDEBUG (_found_simple): Response JSON: {response_data}")
    assert len(response_data["data"]) == 1
    assert response_data.get("meta", {}).get("total_hits", 1) == 1 
    found_event = response_data["data"][0]
    assert found_event["id"] == str(event1.id)
    assert found_event["metadata"] == event1_meta

@pytest.mark.asyncio
async def test_search_by_metadata_found_nested(client: httpx.AsyncClient, db_pool: asyncpg.Pool):
    """Teste une recherche par métadonnées imbriquées."""
    # Arrange: Insérer des données de test via le pool
    event1_meta = {"source": "app", "details": {"user_id": 123, "action": "login"}}
    event2_meta = {"source": "app", "details": {"user_id": 456, "action": "logout"}}
    event1 = await create_test_event(db_pool, {"msg": "Login event"}, event1_meta)
    await create_test_event(db_pool, {"msg": "Logout event"}, event2_meta)

    # Act: Rechercher les actions de login
    filter_criteria = {"details": {"action": "login"}}
    response = await client.get("/v1/search/", params={"filter_metadata": json.dumps(filter_criteria)})

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    print(f"\nDEBUG (_found_nested): Response JSON: {response_data}")
    assert len(response_data["data"]) == 1
    assert response_data["data"][0]["id"] == str(event1.id)

@pytest.mark.asyncio
async def test_search_by_metadata_invalid_json(client: httpx.AsyncClient, db_pool: asyncpg.Pool):
    """Teste la recherche avec un JSON invalide dans filter_metadata."""
    # Arrange: (DB propre)
    # Act
    invalid_json_string = '{"key": "value"' # JSON mal formé
    response = await client.get("/v1/search/", params={"filter_metadata": invalid_json_string})
    
    # Assert
    assert response.status_code == 422 # Unprocessable Entity
    response_data = response.json()
    assert "detail" in response_data
    assert response_data["detail"] == "Le paramètre 'filter_metadata' contient du JSON invalide."

# TODO: Ajouter tests pour :
# - Recherche sans filtre (retourne tout? pagination?)
# - Combinaison de filtre metadata et autres paramètres (ex: ts_start, ts_end si implémentés)
# - Cas limites (ex: filtre vide ? {} ) 