import uuid
from datetime import datetime, timezone
import json
from typing import List, Dict, Any, Optional, Tuple, Union

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

# Configuration du logger
logging.basicConfig(level=logging.INFO) # Ou logging.DEBUG pour plus de détails

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

# --- Query Builder ---

class EventQueryBuilder:
    """Construit les requêtes SQL pour EventRepository en utilisant SQLAlchemy Core."""

    def _get_vector_dimensions(self) -> int:
        """Retourne la dimension attendue pour les vecteurs (à configurer)."""
        # TODO: Rendre configurable ou récupérer depuis une source externe
        return 768  # Dimension pour nomic-embed-text-v1.5

    def build_add_query(self, event_data: EventCreate) -> Tuple[TextClause, Dict[str, Any]]:
        """Construit la requête INSERT en utilisant text() et CAST pour JSONB."""
        
        query_str = text("""
            INSERT INTO events (id, content, metadata, embedding, timestamp) 
            VALUES (:id, CAST(:content AS JSONB), CAST(:metadata AS JSONB), :embedding, :timestamp) 
            RETURNING id, content, metadata, embedding, timestamp
        """)
        
        event_id = str(uuid.uuid4()) 

        params = {
            "id": event_id, 
            "content": json.dumps(event_data.content), # Pass as string, cast in SQL
            "metadata": json.dumps(event_data.metadata) if event_data.metadata else None, # Pass as string
            "embedding": EventModel._format_embedding_for_db(event_data.embedding),
            "timestamp": event_data.timestamp if event_data.timestamp else datetime.now(timezone.utc) # Default to now() if None
        }
        
        return query_str, params

    def build_get_by_id_query(self, event_id: uuid.UUID) -> Tuple[ColumnElement, Dict[str, Any]]:
        """Construit la requête SELECT par ID."""
        query = select(
            events_table.c.id,
            events_table.c.timestamp,
            events_table.c.content,
            events_table.c.metadata,
            events_table.c.embedding
        ).select_from(events_table).where(events_table.c.id == text(":event_id"))
        params = {"event_id": str(event_id)} # Ensure UUID is string for text binding
        return query, params

    def build_update_metadata_query(self, event_id: uuid.UUID, metadata_update: Dict[str, Any]) -> Tuple[ColumnElement, Dict[str, Any]]:
        """Construit la requête UPDATE pour fusionner les métadonnées."""
        query = update(events_table).where(
            events_table.c.id == text(":event_id")
        ).values(
            metadata=events_table.c.metadata.op('||')(text(":metadata_update::jsonb"))
        ).returning(
            events_table.c.id,
            events_table.c.timestamp,
            events_table.c.content,
            events_table.c.metadata,
            events_table.c.embedding
        )
        params = {"event_id": str(event_id), "metadata_update": json.dumps(metadata_update)}
        return query, params

    def build_delete_query(self, event_id: uuid.UUID) -> Tuple[ColumnElement, Dict[str, Any]]:
        """Construit la requête DELETE par ID."""
        query = delete(events_table).where(events_table.c.id == text(":event_id"))
        params = {"event_id": str(event_id)}
        return query, params

    def build_filter_by_metadata_query(self, metadata_criteria: Dict[str, Any]) -> Tuple[TextClause, Dict[str, Any]]:
        """Construit la requête SELECT avec filtres sur les métadonnées JSON."""
        if not metadata_criteria:
            raise ValueError("Metadata criteria cannot be empty")

        query_str = """
            SELECT 
                id, content, metadata, embedding, timestamp
            FROM events
            WHERE 
                metadata @> :criteria::jsonb
            ORDER BY timestamp DESC
        """
        params = {"criteria": json.dumps(metadata_criteria)}
        return text(query_str), params

    def build_search_vector_query(
        self,
        vector: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ts_start: Optional[datetime] = None,
        ts_end: Optional[datetime] = None,
        limit: int = 10,
        offset: int = 0,
        distance_threshold: Optional[float] = 5.0
    ) -> Tuple[TextClause, Dict[str, Any]]:
        """
        Construit la requête SELECT en utilisant des paramètres nommés (:param).
        Combine dynamiquement les filtres et le tri.
        Returns a TextClause and a dictionary of named parameters.
        """
        params_dict: Dict[str, Any] = { # Renamed to avoid conflict
            "lim": limit,
            "off": offset
        }
        select_parts = ["id", "timestamp", "content", "metadata", "embedding"]
        conditions = []
        order_by_clause = "ORDER BY timestamp DESC" 

        if vector is not None:
            if len(vector) != self._get_vector_dimensions():
                 raise ValueError(f"Vector dimension mismatch. Expected {self._get_vector_dimensions()}, got {len(vector)}")
            select_parts.append("embedding <-> :vec_query AS similarity_score")
            params_dict["vec_query"] = EventModel._format_embedding_for_db(vector)
            
            if distance_threshold is not None:
                conditions.append("embedding <-> :vec_query <= :dist_threshold")
                params_dict["dist_threshold"] = distance_threshold
            order_by_clause = "ORDER BY similarity_score ASC"
        else:
            select_parts.append("NULL AS similarity_score")

        if metadata:
            conditions.append("metadata @> :md_filter ::jsonb")
            params_dict["md_filter"] = json.dumps(metadata)

        if ts_start:
            conditions.append("timestamp >= :ts_start")
            params_dict["ts_start"] = ts_start
        if ts_end:
            conditions.append("timestamp <= :ts_end")
            params_dict["ts_end"] = ts_end

        select_clause = "SELECT " + ", ".join(select_parts)
        from_clause = "FROM events"
        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
        
        limit_offset_clause = "LIMIT :lim OFFSET :off"
        query_str = f"{select_clause} {from_clause} {where_clause} {order_by_clause} {limit_offset_clause}"
        
        return text(query_str), params_dict


# --- Repository ---

class EventRepository:
    """Gère les opérations CRUD et de recherche pour les événements dans la base de données."""

    def __init__(self, engine: AsyncEngine):
        """Initialise le repository avec une engine SQLAlchemy async."""
        self.engine = engine
        self.query_builder = EventQueryBuilder()
        self.logger = logging.getLogger(__name__)
        self.logger.info("EventRepository initialized.")

    async def _execute_query(self, query: ColumnElement, params: Dict[str, Any], is_mutation: bool = False) -> Result:
        """Exécute une requête avec gestion de connexion et de transaction."""
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
        query, params = self.query_builder.build_add_query(event_data)
        try:
            db_result = await self._execute_query(query, params, is_mutation=True)
            row = db_result.mappings().first()
            if not row:
                raise RepositoryError("Failed to add event: No data returned.")
            return EventModel.from_db_record(row)
        except Exception as e:
            self.logger.error(f"Failed to add event: {e}", exc_info=True)
            raise RepositoryError(f"Failed to add event: {e}") from e

    async def get_by_id(self, event_id: uuid.UUID) -> Optional[EventModel]:
        """Récupère un événement par son ID."""
        query, params = self.query_builder.build_get_by_id_query(event_id)
        try:
            db_result = await self._execute_query(query, params)
            row = db_result.mappings().first()
            return EventModel.from_db_record(row) if row else None
        except Exception as e:
            self.logger.error(f"Failed to get event by ID {event_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to get event by ID {event_id}: {e}") from e

    async def update_metadata(self, event_id: uuid.UUID, metadata_update: Dict[str, Any]) -> Optional[EventModel]:
        """Met à jour (fusionne) les métadonnées d'un événement existant."""
        query, params = self.query_builder.build_update_metadata_query(event_id, metadata_update)
        try:
            db_result = await self._execute_query(query, params, is_mutation=True)
            row = db_result.mappings().first()
            return EventModel.from_db_record(row) if row else None
        except Exception as e:
            self.logger.error(f"Failed to update metadata for event {event_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to update metadata for event {event_id}: {e}") from e
            
    async def delete(self, event_id: uuid.UUID) -> bool:
        """Supprime un événement par ID."""
        query, params = self.query_builder.build_delete_query(event_id)
        try:
            db_result = await self._execute_query(query, params, is_mutation=True)
            return db_result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Failed to delete event {event_id}: {e}", exc_info=True)
            raise RepositoryError(f"Failed to delete event {event_id}: {e}") from e

    async def filter_by_metadata(self, metadata_criteria: Dict[str, Any]) -> List[EventModel]:
        """Filtre les événements par critères de métadonnées."""
        query, params = self.query_builder.build_filter_by_metadata_query(metadata_criteria)
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
        distance_threshold: Optional[float] = 5.0
    ) -> Tuple[List[EventModel], int]:
        """
        Effectue une recherche combinée (vecteur, métadonnées, temps) et retourne les événements et le nombre total.
        NOTE: Le nombre total n'est pas encore implémenté de manière optimisée. Pour l'instant, retourne 0.
        """
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
            
            # TODO: Implement total_hits calculation correctly without re-querying if possible,
            # or by a separate count query if necessary.
            total_hits = len(events) # Placeholder, not accurate if limit < total matches

            return events, total_hits
        except Exception as e:
            self.logger.error(f"Failed to search events: {e}", exc_info=True)
            raise RepositoryError(f"Failed to search events: {e}") from e
