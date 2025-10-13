"""
Tests pour le mécanisme de fallback automatique et les warnings de threshold.

Ce fichier teste les fonctionnalités suivantes:
1. Fallback automatique quand threshold trop strict retourne 0 résultats
2. Pas de fallback si metadata ou time filters présents
3. Désactivation du fallback avec enable_fallback=False
4. Warnings pour thresholds inhabituels (< 0.6 ou > 2.0)
5. Validation pour thresholds invalides (< 0.0)
"""

import pytest
import uuid
import datetime
import json
import logging
from unittest.mock import AsyncMock, MagicMock
from datetime import timezone

# Imports du code à tester
from db.repositories.event_repository import (
    EventRepository,
    EventModel,
    EventQueryBuilder,
    RepositoryError,
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection
from sqlalchemy.engine import Result
from sqlalchemy.sql.expression import text


# === Fixtures ===

@pytest.fixture
def mock_engine():
    """Fixture pour créer un moteur mocké."""
    return AsyncMock(spec=AsyncEngine)


@pytest.fixture
def mock_connection():
    """Fixture pour créer une connexion mockée."""
    return AsyncMock(spec=AsyncConnection)


@pytest.fixture
def mock_builder():
    """Fixture pour créer un query builder mocké."""
    return MagicMock(spec=EventQueryBuilder)


@pytest.fixture
def sample_event_dict():
    """Fixture pour un événement de test."""
    return {
        "id": uuid.uuid4(),
        "timestamp": datetime.datetime.now(timezone.utc),
        "content": json.dumps({"msg": "Test event"}),
        "metadata": json.dumps({"source": "test"}),
        "embedding": "[0.1, 0.2, 0.3]",
        "similarity_score": 0.5,
    }


# === Test 1: Fallback automatique ===

@pytest.mark.anyio
async def test_fallback_on_strict_threshold_returns_results(
    mock_engine, mock_connection, mock_builder, sample_event_dict
):
    """
    Test que le fallback fonctionne quand threshold strict retourne 0 résultats.

    Scénario:
    1. Première requête avec threshold=0.3 → 0 résultats
    2. Fallback automatique sans threshold → 1 résultat
    """
    # Setup mock engine et connection
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection

    # Mock pour la première requête (avec threshold strict) → 0 résultats
    mock_result_empty = AsyncMock(spec=Result)
    mock_mappings_empty = MagicMock()
    mock_mappings_empty.all.return_value = []
    mock_result_empty.mappings.return_value = mock_mappings_empty

    # Mock pour la deuxième requête (fallback sans threshold) → 1 résultat
    mock_result_fallback = AsyncMock(spec=Result)
    mock_mappings_fallback = MagicMock()
    mock_mappings_fallback.all.return_value = [sample_event_dict]
    mock_result_fallback.mappings.return_value = mock_mappings_fallback

    # Configure execute pour retourner d'abord vide, puis le résultat
    mock_connection.execute.side_effect = [mock_result_empty, mock_result_fallback]

    # Configure le builder pour retourner des requêtes mockées
    query_vector = [0.1] * 768
    mock_query_strict = text("SELECT ... WHERE dist <= 0.3")
    mock_params_strict = {"vec_query": str(query_vector), "dist_threshold": 0.3, "lim": 10, "off": 0}

    mock_query_fallback = text("SELECT ... ORDER BY dist")
    mock_params_fallback = {"vec_query": str(query_vector), "lim": 10, "off": 0}

    mock_builder.build_search_vector_query.side_effect = [
        (mock_query_strict, mock_params_strict),
        (mock_query_fallback, mock_params_fallback),
    ]

    # Créer repository et injecter le builder mocké
    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder

    # Action: recherche vectorielle avec threshold strict et fallback activé
    events, total_hits = await repository.search_vector(
        vector=query_vector,
        distance_threshold=0.3,
        limit=10,
        offset=0,
        enable_fallback=True  # Fallback activé
    )

    # Vérifications
    assert len(events) == 1, "Le fallback devrait retourner 1 résultat"
    assert events[0].id == sample_event_dict["id"]
    assert mock_builder.build_search_vector_query.call_count == 2, "Builder appelé 2 fois (strict + fallback)"
    assert mock_connection.execute.call_count == 2, "Execute appelé 2 fois"


# === Test 2: Pas de fallback si metadata filter ===

@pytest.mark.anyio
async def test_no_fallback_with_metadata_filter(
    mock_engine, mock_connection, mock_builder
):
    """
    Test que le fallback ne se déclenche PAS si metadata filter présent.

    Scénario:
    Recherche vectorielle + metadata filter avec threshold strict → 0 résultats
    → Pas de fallback car metadata filter restreint le scope
    """
    # Setup
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection

    mock_result_empty = AsyncMock(spec=Result)
    mock_mappings_empty = MagicMock()
    mock_mappings_empty.all.return_value = []
    mock_result_empty.mappings.return_value = mock_mappings_empty

    mock_connection.execute.return_value = mock_result_empty

    query_vector = [0.1] * 768
    metadata = {"project": "test"}
    mock_query = text("SELECT ... WHERE metadata @> ...")
    mock_params = {"vec_query": str(query_vector), "md_filter": json.dumps(metadata), "dist_threshold": 0.3}
    mock_builder.build_search_vector_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder

    # Action: recherche avec metadata filter
    events, total_hits = await repository.search_vector(
        vector=query_vector,
        metadata=metadata,  # Metadata filter présent
        distance_threshold=0.3,
        enable_fallback=True
    )

    # Vérifications
    assert len(events) == 0, "Devrait retourner 0 résultats (pas de fallback)"
    assert mock_builder.build_search_vector_query.call_count == 1, "Builder appelé 1 seule fois"
    assert mock_connection.execute.call_count == 1, "Execute appelé 1 seule fois"


# === Test 3: Pas de fallback si time filter ===

@pytest.mark.anyio
async def test_no_fallback_with_time_filter(
    mock_engine, mock_connection, mock_builder
):
    """
    Test que le fallback ne se déclenche PAS si time filter présent.
    """
    # Setup
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection

    mock_result_empty = AsyncMock(spec=Result)
    mock_mappings_empty = MagicMock()
    mock_mappings_empty.all.return_value = []
    mock_result_empty.mappings.return_value = mock_mappings_empty

    mock_connection.execute.return_value = mock_result_empty

    query_vector = [0.1] * 768
    ts_start = datetime.datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock_query = text("SELECT ... WHERE timestamp >= ...")
    mock_params = {"vec_query": str(query_vector), "ts_start": ts_start, "dist_threshold": 0.3}
    mock_builder.build_search_vector_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder

    # Action: recherche avec time filter
    events, total_hits = await repository.search_vector(
        vector=query_vector,
        ts_start=ts_start,  # Time filter présent
        distance_threshold=0.3,
        enable_fallback=True
    )

    # Vérifications
    assert len(events) == 0, "Devrait retourner 0 résultats (pas de fallback)"
    assert mock_builder.build_search_vector_query.call_count == 1
    assert mock_connection.execute.call_count == 1


# === Test 4: Désactivation du fallback ===

@pytest.mark.anyio
async def test_fallback_disabled_with_enable_fallback_false(
    mock_engine, mock_connection, mock_builder
):
    """
    Test que le fallback peut être désactivé avec enable_fallback=False.
    """
    # Setup
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection

    mock_result_empty = AsyncMock(spec=Result)
    mock_mappings_empty = MagicMock()
    mock_mappings_empty.all.return_value = []
    mock_result_empty.mappings.return_value = mock_mappings_empty

    mock_connection.execute.return_value = mock_result_empty

    query_vector = [0.1] * 768
    mock_query = text("SELECT ... WHERE dist <= 0.3")
    mock_params = {"vec_query": str(query_vector), "dist_threshold": 0.3}
    mock_builder.build_search_vector_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder

    # Action: fallback désactivé explicitement
    events, total_hits = await repository.search_vector(
        vector=query_vector,
        distance_threshold=0.3,
        enable_fallback=False  # Désactivé
    )

    # Vérifications
    assert len(events) == 0, "Devrait retourner 0 résultats (fallback désactivé)"
    assert mock_builder.build_search_vector_query.call_count == 1, "Builder appelé 1 seule fois"


# === Test 5: Warning pour threshold < 0.6 ===

@pytest.mark.anyio
async def test_warning_on_strict_threshold(
    mock_engine, mock_connection, mock_builder, caplog, sample_event_dict
):
    """
    Test qu'un warning est émis pour threshold < 0.6 (très strict).
    """
    # Setup
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection

    mock_result = AsyncMock(spec=Result)
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = [sample_event_dict]
    mock_result.mappings.return_value = mock_mappings

    mock_connection.execute.return_value = mock_result

    query_vector = [0.1] * 768
    mock_query = text("SELECT ...")
    mock_params = {"vec_query": str(query_vector), "dist_threshold": 0.4}
    mock_builder.build_search_vector_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder

    # Capturer les logs au niveau WARNING
    with caplog.at_level(logging.WARNING):
        events, total_hits = await repository.search_vector(
            vector=query_vector,
            distance_threshold=0.4,  # < 0.6
            enable_fallback=False
        )

    # Vérifications
    assert "very strict" in caplog.text.lower(), "Warning 'very strict' devrait être émis"
    assert "0.4" in caplog.text, "Threshold 0.4 devrait être mentionné"


# === Test 6: Warning pour threshold > 2.0 ===

@pytest.mark.anyio
async def test_warning_on_high_threshold(
    mock_engine, mock_connection, mock_builder, caplog, sample_event_dict
):
    """
    Test qu'un warning est émis pour threshold > 2.0 (inhabituel).
    """
    # Setup
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection

    mock_result = AsyncMock(spec=Result)
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = [sample_event_dict]
    mock_result.mappings.return_value = mock_mappings

    mock_connection.execute.return_value = mock_result

    query_vector = [0.1] * 768
    mock_query = text("SELECT ...")
    mock_params = {"vec_query": str(query_vector), "dist_threshold": 3.5}
    mock_builder.build_search_vector_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder

    # Capturer les logs
    with caplog.at_level(logging.WARNING):
        events, total_hits = await repository.search_vector(
            vector=query_vector,
            distance_threshold=3.5,  # > 2.0
            enable_fallback=False
        )

    # Vérifications
    assert "unusually high" in caplog.text.lower(), "Warning 'unusually high' devrait être émis"
    assert "3.5" in caplog.text, "Threshold 3.5 devrait être mentionné"


# === Test 7: ValueError pour threshold < 0.0 ===

@pytest.mark.anyio
async def test_error_on_negative_threshold(
    mock_engine, mock_connection, mock_builder
):
    """
    Test qu'une ValueError est levée pour threshold < 0.0.
    """
    # Setup minimal (pas besoin de configure execute car exception levée avant)
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder

    query_vector = [0.1] * 768

    # Action & Vérification
    with pytest.raises(ValueError) as exc_info:
        await repository.search_vector(
            vector=query_vector,
            distance_threshold=-0.5,  # Négatif
            enable_fallback=False
        )

    assert "must be >= 0.0" in str(exc_info.value), "Message d'erreur devrait mentionner >= 0.0"
    assert "-0.5" in str(exc_info.value), "Message devrait mentionner la valeur -0.5"


# === Test 8: Pas de fallback si threshold=None (top-K mode) ===

@pytest.mark.anyio
async def test_no_fallback_if_threshold_none(
    mock_engine, mock_connection, mock_builder, sample_event_dict
):
    """
    Test que le fallback ne se déclenche pas si threshold=None (mode top-K).

    Scénario: threshold=None signifie "retourner top-K sans filtrage par distance"
    → Pas besoin de fallback
    """
    # Setup
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection

    mock_result = AsyncMock(spec=Result)
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = [sample_event_dict]
    mock_result.mappings.return_value = mock_mappings

    mock_connection.execute.return_value = mock_result

    query_vector = [0.1] * 768
    mock_query = text("SELECT ... ORDER BY dist")
    mock_params = {"vec_query": str(query_vector), "lim": 10, "off": 0}
    mock_builder.build_search_vector_query.return_value = (mock_query, mock_params)

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder

    # Action: threshold=None (top-K mode)
    events, total_hits = await repository.search_vector(
        vector=query_vector,
        distance_threshold=None,  # Top-K mode
        enable_fallback=True
    )

    # Vérifications
    assert len(events) == 1
    assert mock_builder.build_search_vector_query.call_count == 1, "Builder appelé 1 seule fois"
    assert mock_connection.execute.call_count == 1, "Pas de fallback nécessaire"


# === Test 9: Logging du fallback ===

@pytest.mark.anyio
async def test_fallback_logs_warning(
    mock_engine, mock_connection, mock_builder, caplog, sample_event_dict
):
    """
    Test que le fallback log un warning quand il se déclenche.
    """
    # Setup
    mock_engine.connect.return_value.__aenter__.return_value = mock_connection

    # Première requête → vide
    mock_result_empty = AsyncMock(spec=Result)
    mock_mappings_empty = MagicMock()
    mock_mappings_empty.all.return_value = []
    mock_result_empty.mappings.return_value = mock_mappings_empty

    # Fallback → résultat
    mock_result_fallback = AsyncMock(spec=Result)
    mock_mappings_fallback = MagicMock()
    mock_mappings_fallback.all.return_value = [sample_event_dict]
    mock_result_fallback.mappings.return_value = mock_mappings_fallback

    mock_connection.execute.side_effect = [mock_result_empty, mock_result_fallback]

    query_vector = [0.1] * 768
    mock_query_1 = text("SELECT ... WHERE dist <= 0.3")
    mock_params_1 = {"vec_query": str(query_vector), "dist_threshold": 0.3}
    mock_query_2 = text("SELECT ... ORDER BY dist")
    mock_params_2 = {"vec_query": str(query_vector)}
    mock_builder.build_search_vector_query.side_effect = [
        (mock_query_1, mock_params_1),
        (mock_query_2, mock_params_2),
    ]

    repository = EventRepository(engine=mock_engine)
    repository.query_builder = mock_builder

    # Capturer les logs
    with caplog.at_level(logging.WARNING):
        events, total_hits = await repository.search_vector(
            vector=query_vector,
            distance_threshold=0.3,
            enable_fallback=True
        )

    # Vérifications
    assert "falling back to top-k mode" in caplog.text.lower(), "Log de fallback devrait être présent"
    assert "0.3" in caplog.text, "Threshold 0.3 devrait être mentionné"
    assert len(events) == 1, "Fallback devrait retourner 1 résultat"
