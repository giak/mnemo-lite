import uuid
from datetime import datetime, timezone
import json
from typing import List, Dict, Any, Optional, Tuple, Union
from typing_extensions import TypeAlias

# Imports SQLAlchemy nécessaires
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection
from sqlalchemy.sql import text, Select, ColumnElement, insert, select, update, delete
from sqlalchemy.sql.expression import literal_column, TextClause
from sqlalchemy.sql.elements import False_ # Import spécifique pour la vérification
from sqlalchemy.engine import Result
from sqlalchemy import Table, Column, String, MetaData, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import VECTOR # Import VECTOR type

# Importations liées à Pydantic pour la validation et la sérialisation
from pydantic import BaseModel, Field, field_validator

# Importation pour le logging
import logging

# Import RepositoryError from base
from .base import RepositoryError

# Import the canonical EventModel using absolute path
from models.event_models import EventModel, EventCreate, EventUpdate

# Import the extracted query builder
from db.query_builders import EventQueryBuilder

# Import ContextLogger for better logging
from utils.context_logger import get_repository_logger

# Configuration du logger
logging.basicConfig(level=logging.INFO) # Ou logging.DEBUG pour plus de détails

# Type aliases for better readability
QueryParams: TypeAlias = Dict[str, Any]
SearchResult: TypeAlias = Tuple[List[EventModel], int]

# Définition de la table events pour SQLAlchemy Core
metadata_obj = MetaData()
events_table = Table(
    "events",
    metadata_obj,
    Column("id", String, primary_key=True),
    Column("content", JSONB), # Utiliser JSONB pour PostgreSQL
    Column("metadata", JSONB, nullable=True),
    Column("embedding", VECTOR(768), nullable=True), # Dimension for nomic-embed-text-v1.5
    Column("timestamp", TIMESTAMP(timezone=True), nullable=False),
)

# --- Repository ---

class EventRepository:
    """
    Repository for event database operations.

    Handles CRUD operations and search queries for events using SQLAlchemy Core
    with async support. Uses QueryBuilder pattern for clean separation of concerns.

    Attributes:
        engine: SQLAlchemy async engine for database connections
        query_builder: Builder for constructing SQL queries
        logger: Context-aware logger for operation tracking
    """

    def __init__(self, engine: AsyncEngine) -> None:
        """
        Initialize the event repository.

        Args:
            engine: SQLAlchemy async engine for database operations
        """
        self.engine: AsyncEngine = engine
        self.query_builder: EventQueryBuilder = EventQueryBuilder()
        self.logger = get_repository_logger("event")
        self.logger.info("Repository initialized")

    async def _execute_query(
        self,
        query: Union[ColumnElement, TextClause],
        params: QueryParams,
        is_mutation: bool = False
    ) -> Result:
        """
        Execute a database query with proper connection and transaction handling.

        Args:
            query: SQLAlchemy query object or text clause
            params: Query parameters as dictionary
            is_mutation: Whether this is a mutation (INSERT/UPDATE/DELETE) requiring a transaction

        Returns:
            SQLAlchemy Result object

        Raises:
            RepositoryError: If query execution fails
        """
        async with self.engine.connect() as connection:
            transaction = await connection.begin() if is_mutation else None
            try:
                self.logger.info(f"_execute_query: Received Query Type: {type(query)}")
                if hasattr(query, 'compile') and not isinstance(query, TextClause): # Don't compile TextClause here again
                    compiled = query.compile(bind=self.engine, compile_kwargs={"literal_binds": False})
                    self.logger.info(f"_execute_query: Received Compiled Query: {str(compiled)}")
                    self.logger.info(f"_execute_query: Received Compiled Params: {compiled.params}")
                elif isinstance(query, TextClause):
                    self.logger.info(f"_execute_query: Received Query String (TextClause): {str(query)}")
                else:
                    self.logger.info(f"_execute_query: Query is {type(query)}, not directly logging compilation.")

                self.logger.info(f"_execute_query: Executing with Params: {params}")
                result = await connection.execute(query, params)
                
                if transaction:
                    await transaction.commit()
                return result
            except Exception as e:
                if transaction:
                    await transaction.rollback()
                self.logger.error(f"Database query execution failed: {e}", exc_info=True)
                raise RepositoryError(f"Query execution failed: {e}") from e


    async def add(self, event_data: EventCreate) -> EventModel:
        """Ajoute un nouvel événement."""
        event_id = str(uuid.uuid4())
        log = self.logger.bind(method="add", event_id=event_id)

        query, params = self.query_builder.build_add_query(
            event_id=event_id,
            content=event_data.content,
            metadata=event_data.metadata,
            embedding=event_data.embedding,
            timestamp=event_data.timestamp
        )
        try:
            db_result = await self._execute_query(query, params, is_mutation=True)
            row = db_result.mappings().first()
            if not row:
                raise RepositoryError("Failed to add event: No data returned.")
            log.debug("Event added successfully")
            return EventModel.from_db_record(row)
        except Exception as e:
            log.error(f"Failed to add event: {e}", exc_info=True)
            raise RepositoryError(f"Failed to add event: {e}") from e

    async def get_by_id(self, event_id: Union[uuid.UUID, str]) -> Optional[EventModel]:
        """Récupère un événement par son ID."""
        # Ensure event_id is a string
        event_id_str = str(event_id) if isinstance(event_id, uuid.UUID) else event_id
        query, params = self.query_builder.build_get_by_id_query(event_id_str)
        try:
            db_result = await self._execute_query(query, params)
            row = db_result.mappings().first()
            return EventModel.from_db_record(row) if row else None
        except Exception as e:
            self.logger.error(f"Failed to get event by ID {event_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to get event by ID {event_id}: {e}") from e

    async def update_metadata(self, event_id: Union[uuid.UUID, str], metadata_update: Dict[str, Any]) -> Optional[EventModel]:
        """Met à jour (fusionne) les métadonnées d'un événement existant."""
        event_id_str = str(event_id) if isinstance(event_id, uuid.UUID) else event_id
        query, params = self.query_builder.build_update_metadata_query(event_id_str, metadata_update)
        try:
            db_result = await self._execute_query(query, params, is_mutation=True)
            row = db_result.mappings().first()
            return EventModel.from_db_record(row) if row else None
        except Exception as e:
            self.logger.error(f"Failed to update metadata for event {event_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to update metadata for event {event_id}: {e}") from e

    async def delete(self, event_id: Union[uuid.UUID, str]) -> bool:
        """Supprime un événement par ID."""
        event_id_str = str(event_id) if isinstance(event_id, uuid.UUID) else event_id
        query, params = self.query_builder.build_delete_query(event_id_str)
        try:
            db_result = await self._execute_query(query, params, is_mutation=True)
            return db_result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Failed to delete event {event_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to delete event {event_id}: {e}") from e

    async def filter_by_metadata(
        self,
        metadata_criteria: Dict[str, Any],
        limit: int = 10,
        offset: int = 0
    ) -> List[EventModel]:
        """Filtre les événements par critères de métadonnées avec pagination."""
        query, params = self.query_builder.build_filter_by_metadata_query(
            metadata_criteria, limit, offset
        )
        try:
            db_result = await self._execute_query(query, params)
            rows = db_result.mappings().all()
            return [EventModel.from_db_record(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Failed to filter events by metadata: {e}", exc_info=True)
            raise RepositoryError(f"Failed to filter events by metadata: {e}") from e

    async def search_vector(
        self,
        vector: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None,
        limit: int = 10,
        offset: int = 0,
        distance_threshold: Optional[float] = None,
        enable_fallback: bool = True
    ) -> SearchResult:
        """
        Effectue une recherche combinée (vecteur, métadonnées, temps) avec fallback automatique.

        Args:
            vector: Vecteur d'embedding pour la recherche sémantique
            metadata: Filtres de métadonnées
            ts_start: Timestamp de début
            ts_end: Timestamp de fin
            limit: Nombre maximum de résultats
            offset: Offset pour pagination
            distance_threshold: Seuil de distance L2 (None = pas de filtrage)
            enable_fallback: Si True, réessaie sans threshold si 0 résultat en recherche pure vectorielle

        Returns:
            Tuple[List[EventModel], int]: (événements, nombre total estimé)

        Fallback Logic:
            Si threshold défini ET 0 résultats ET recherche vectorielle pure (pas de metadata/time filters)
            → Réessaie en mode top-K (sans threshold) pour garantir des résultats pertinents
        """

        # === Phase 3: VALIDATION & WARNINGS ===
        if distance_threshold is not None:
            if distance_threshold < 0.0:
                raise ValueError(f"distance_threshold must be >= 0.0, got {distance_threshold}")

            if distance_threshold > 2.0:
                self.logger.warning(
                    f"distance_threshold {distance_threshold} > 2.0 is unusually high. "
                    f"Max L2 distance for normalized vectors is ~2.0. Consider using None instead."
                )

            if distance_threshold < 0.6 and vector is not None:
                self.logger.warning(
                    f"distance_threshold {distance_threshold} < 0.6 is very strict. "
                    f"You may get 0 results. Recommended: 0.8-1.2 for balanced recall/precision."
                )

        # === Première tentative avec threshold ===
        query_data, params_data = self.query_builder.build_search_vector_query(
            vector=vector,
            metadata=metadata,
            ts_start=ts_start,
            ts_end=ts_end,
            limit=limit,
            offset=offset,
            distance_threshold=distance_threshold
        )
        self.logger.info(f"search_vector: Built query type: {type(query_data)}")
        self.logger.debug(f"search_vector: Executing with params: {params_data}")

        try:
            db_result = await self._execute_query(query_data, params_data)
            rows = db_result.mappings().all()
            events = [EventModel.from_db_record(row) for row in rows]

            # === Phase 2: FALLBACK LOGIC ===
            should_fallback = (
                len(events) == 0  # Aucun résultat
                and enable_fallback  # Fallback activé
                and distance_threshold is not None  # Threshold était défini
                and vector is not None  # C'est une recherche vectorielle
                and not metadata  # Pas de filtre metadata (= vectoriel pur)
                and not ts_start  # Pas de filtre temporel
                and not ts_end
            )

            if should_fallback:
                self.logger.warning(
                    f"Vector search with threshold {distance_threshold} returned 0 results. "
                    f"Falling back to top-K mode (no threshold)."
                )

                # Réessayer sans threshold
                query_data_fallback, params_data_fallback = self.query_builder.build_search_vector_query(
                    vector=vector,
                    metadata=metadata,
                    ts_start=ts_start,
                    ts_end=ts_end,
                    limit=limit,
                    offset=offset,
                    distance_threshold=None  # Désactiver threshold
                )

                db_result_fallback = await self._execute_query(query_data_fallback, params_data_fallback)
                rows_fallback = db_result_fallback.mappings().all()
                events = [EventModel.from_db_record(row) for row in rows_fallback]

                self.logger.info(f"Fallback returned {len(events)} results in top-K mode.")

            # Calculate total hits with a separate COUNT query
            # Only do this if we have results or if no fallback was triggered
            if len(events) > 0 or not should_fallback:
                count_query, count_params = self.query_builder.build_count_query(
                    vector=vector,
                    metadata=metadata,
                    ts_start=ts_start,
                    ts_end=ts_end,
                    distance_threshold=distance_threshold if not should_fallback else None
                )

                try:
                    count_result = await self._execute_query(count_query, count_params)
                    count_row = count_result.mappings().first()
                    total_hits = count_row["total"] if count_row else 0
                except Exception as e:
                    self.logger.warning(f"Failed to get total count, using result length: {e}")
                    total_hits = len(events)
            else:
                # No results and no fallback, total is 0
                total_hits = 0

            return events, total_hits
        except Exception as e:
            self.logger.error(f"Failed to search events: {e}", exc_info=True)
            raise RepositoryError(f"Failed to search events: {e}") from e
