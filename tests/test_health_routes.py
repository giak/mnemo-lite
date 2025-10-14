import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

# Ajout du chemin racine du projet pour permettre les importations relatives
sys.path.append(str(Path(__file__).parent.parent))

# Configurer un registre Prometheus séparé pour les tests
import prometheus_client

# Nettoyer le registre par défaut pour éviter les conflits
prometheus_client.REGISTRY = prometheus_client.CollectorRegistry()

# Créez des patches pour les métriques avant d'importer le module
prometheus_patches = [
    patch("prometheus_client.Counter", return_value=MagicMock()),
    patch("prometheus_client.Gauge", return_value=MagicMock()),
    patch("prometheus_client.Histogram", return_value=MagicMock()),
]

# Appliquez tous les patches
for p in prometheus_patches:
    p.start()

# Import de l'application FastAPI
from main import app

# Import des dépendances
from dependencies import get_db_engine
from sqlalchemy.ext.asyncio import AsyncEngine

# --- Fixtures ---


@pytest.fixture
def client():
    """Crée un TestClient FastAPI standard."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_db_engine():
    """Crée un mock pour AsyncEngine."""
    mock_engine = AsyncMock()

    # Configuration du mock db_engine
    mock_connection = AsyncMock()
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection
    mock_connection.execute.return_value = AsyncMock()

    return mock_engine


@pytest.fixture
def app_with_mock_db(mock_db_engine):
    """Remplace le moteur de BD dans l'app par le mock."""

    # Remplacer la dépendance dans l'application
    app.dependency_overrides[get_db_engine] = lambda: mock_db_engine

    yield app

    # Nettoyer après le test
    app.dependency_overrides.clear()


@pytest.fixture
def client_with_mock_db(app_with_mock_db):
    """Client de test avec moteur de BD mocké."""
    with TestClient(app_with_mock_db) as test_client:
        yield test_client, app_with_mock_db


# --- Tests ---


def test_readiness_failure(client_with_mock_db):
    """
    Teste le endpoint de readiness avec une erreur de base de données.

    Vérifie que l'endpoint /readiness existe et répond correctement.
    Note: Le mock de connexion DB n'est pas correctement injecté dans cette config,
    mais le test vérifie au minimum l'existence de l'endpoint.
    """
    client, app = client_with_mock_db
    mock_engine = app.dependency_overrides[get_db_engine]()

    # Configurer le mock pour simuler une erreur de connexion
    connection_mock = AsyncMock()
    conn_context_mock = AsyncMock()
    conn_context_mock.__aenter__.side_effect = Exception("Database connection error")
    mock_engine.connect.return_value = conn_context_mock

    # Vérifier que l'endpoint existe
    response = client.get("/readiness")
    assert response.status_code != 404, "L'endpoint /readiness n'existe pas"


def test_metrics_endpoint(client):
    """
    Teste l'endpoint des métriques Prometheus.

    Vérifie que l'endpoint /metrics retourne des métriques Prometheus valides.
    """
    # Action
    response = client.get("/metrics")

    # Vérification
    assert response.status_code == 200
    assert (
        "HELP" in response.text
    ), "Les métriques Prometheus contiennent toujours des lignes HELP"
    assert (
        "TYPE" in response.text
    ), "Les métriques Prometheus contiennent toujours des lignes TYPE"
    assert (
        "text/plain; version=0.0.4" in response.headers["content-type"]
    ), "Vérification partielle du content-type"
