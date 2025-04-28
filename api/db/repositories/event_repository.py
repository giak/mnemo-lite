import uuid
# Remove asyncpg import
# import asyncpg 
from typing import Optional, Dict, Any, List
import datetime
from pydantic import BaseModel, Field
import json
from datetime import timezone
# Import SQLAlchemy async engine and text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.sql import text, literal
from models.event_models import EventCreate, EventModel # Import the correct models
import logging # Keep standard logging import for now, though unused directly by repo
from sqlalchemy import text, select, Table, Column, MetaData, JSON, TIMESTAMP, String, Uuid, cast, Integer, Float, desc # Add desc
from sqlalchemy.dialects.postgresql import JSONB # Add VECTOR type # Removed VECTOR from here
from pgvector.sqlalchemy import Vector # Correct import
from sqlalchemy import and_ # Add and_ import
from sqlalchemy import bindparam # Add bindparam import
from sqlalchemy import func # Add func
from sqlalchemy.exc import SQLAlchemyError
import structlog # <<< Import structlog
from sqlalchemy.sql.expression import ClauseElement # Add ClauseElement for type hinting
from sqlalchemy.sql.elements import False_

# logger = logging.getLogger(__name__) # <<< REMOVE MODULE-LEVEL LOGGER

class EventModel(BaseModel):
    id: uuid.UUID
    timestamp: datetime.datetime
    content: Dict[str, Any]
    metadata: Dict[str, Any]
    embedding: Optional[List[float]]
    similarity_score: Optional[float] = None

    @staticmethod
    def _format_embedding_for_db(embedding: List[float]) -> str:
        """Converts a list of floats to a pgvector-compatible string."""
        return "[" + ",".join(map(str, embedding)) + "]"

    @staticmethod
    def _parse_embedding_from_db(embedding_str: Optional[str]) -> Optional[List[float]]:
        """Converts a pgvector string representation back to a list of floats."""
        if embedding_str is None:
            return None
        try:
            # Remove brackets and split by comma
            cleaned_str = embedding_str.strip("[]")
            if not cleaned_str: # Handle empty list case '[]'
                return []
            return [float(x) for x in cleaned_str.split(',')]
        except (ValueError, TypeError) as e:
            # Depending on requirements, either return None or raise an error
            # For now, return None to avoid breaking if invalid data exists
            # Log the error (maybe at a higher level later)
            structlog.get_logger().warning("Invalid embedding format from DB", embedding_str=embedding_str, error=e)
            return None

    @classmethod
    def from_db_record(cls, record_data: Dict[str, Any]) -> "EventModel":
        """Crée une instance EventModel à partir d'un dict de données brutes de la DB."""
        record_dict = record_data.copy()
        
        # Parser content et metadata si ce sont des chaînes JSON
        for field in ['content', 'metadata']:
            if isinstance(record_dict.get(field), str):
                try:
                    record_dict[field] = json.loads(record_dict[field])
                except (json.JSONDecodeError, TypeError):
                    structlog.get_logger().warning(f"Could not parse {field} JSON from DB", field_value=record_dict.get(field))
                    record_dict[field] = {} # Default to empty dict on parsing error

        # Parse embedding using the static method if it's a string
        if isinstance(record_dict.get('embedding'), str):
             record_dict['embedding'] = cls._parse_embedding_from_db(record_dict['embedding'])
        # If it's already a list (e.g., from SQLAlchemy ORM mapping), leave it as is.
        # If it's None, leave it as None.
        
        # Le score de similarité peut être absent (si pas de recherche vectorielle)
        # Ensure it defaults to None if missing
        record_dict['similarity_score'] = record_dict.get('similarity_score', None)
            
        # Use model_validate for Pydantic v2
        return cls.model_validate(record_dict)

# Define table structure for SQLAlchemy Core 
# (Ideally defined once, but included here for context)
metadata_obj = MetaData()
events_table = Table(
    'events', metadata_obj,
    Column('id', Uuid, primary_key=True),
    Column('timestamp', TIMESTAMP(timezone=True)),
    Column('content', JSONB), # Assuming JSONB for content as well for consistency
    Column('metadata', JSONB),
    Column('embedding', Vector(1536)) # Use correct case: Vector
) 

class EventQueryBuilder:
    """Construit les requêtes SQL (SQLAlchemy Core DSL) pour EventRepository."""

    def _get_vector_dimensions(self) -> int:
        # Keep dimension info accessible if needed by builder methods
        return 1536

    def build_add_query(self, event_data: EventCreate) -> tuple[ClauseElement, Dict[str, Any]]:
        """Construit la requête INSERT et les paramètres pour ajouter un événement."""
        timestamp_to_use = event_data.timestamp if event_data.timestamp else datetime.datetime.now(timezone.utc)
        embedding_str = None
        if event_data.embedding is not None:
             embedding_str = EventModel._format_embedding_for_db(event_data.embedding)

        query = text("""
        INSERT INTO events (content, metadata, embedding, timestamp)
        VALUES (:content, :metadata, :embedding, :timestamp)
        RETURNING id, timestamp, content, metadata, embedding
        """)
        
        params = {
            "content": json.dumps(event_data.content),
            "metadata": json.dumps(event_data.metadata),
            "embedding": embedding_str,
            "timestamp": timestamp_to_use
        }
        return query, params

    def build_get_by_id_query(self, event_id: uuid.UUID) -> tuple[ClauseElement, Dict[str, Any]]:
        """Construit la requête SELECT pour récupérer un événement par ID."""
        query = text("""
            SELECT id, timestamp, content, metadata, embedding
            FROM events WHERE id = :event_id
        """)
        params = {"event_id": event_id}
        return query, params

    def build_update_metadata_query(self, event_id: uuid.UUID, metadata_update: Dict[str, Any]) -> tuple[ClauseElement, Dict[str, Any]]:
        """Construit la requête UPDATE pour fusionner les métadonnées."""
        query = text("""
        UPDATE events
        SET metadata = metadata || :metadata_update::jsonb
        WHERE id = :event_id
        RETURNING id, timestamp, content, metadata, embedding
        """)
        params = {
            "event_id": event_id,
            "metadata_update": json.dumps(metadata_update)
        }
        return query, params

    def build_delete_query(self, event_id: uuid.UUID) -> tuple[ClauseElement, Dict[str, Any]]:
        """Construit la requête DELETE pour supprimer un événement par ID."""
        query = text("DELETE FROM events WHERE id = :event_id")
        params = {"event_id": event_id}
        return query, params

    def build_filter_by_metadata_query(self, metadata_criteria: Dict[str, Any]) -> tuple[ClauseElement, Dict[str, Any]]:
        """Construit la requête SELECT pour filtrer par métadonnées."""
        # Utiliser Core DSL ici pour être cohérent avec search_vector serait mieux,
        # mais pour l'instant, gardons text() pour cette étape.
        query = text("""
        SELECT id, timestamp, content, metadata, embedding
        FROM events
        WHERE metadata @> :criteria::jsonb
        ORDER BY timestamp DESC
        """)
        params = {"criteria": json.dumps(metadata_criteria)}
        return query, params

    # La méthode build_search_vector_query sera ajoutée dans une étape suivante
    def build_search_vector_query(
        self,
        vector: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ts_start: Optional[datetime.datetime] = None,
        ts_end: Optional[datetime.datetime] = None,
        limit: int = 10,
        offset: int = 0,
        # Note: top_k n'est plus directement utilisé ici, limit contrôle le nombre de résultats
        # distance_threshold pourrait être un paramètre ici si on veut le rendre configurable
        distance_threshold: float = 5.0
    ) -> tuple[ClauseElement, Dict[str, Any]]:
        """Construit la requête SELECT dynamique pour la recherche vectorielle/metadata/temps."""
        
        vector_dim = self._get_vector_dimensions()
        limit = max(0, limit)
        offset = max(0, offset)

        # Input validation (peut rester ici ou être remonté avant l'appel du builder)
        if vector is None and metadata is None and ts_start is None and ts_end is None:
             # Le builder peut retourner une requête vide ou lever une erreur
             # Retourner une requête qui ne renvoie rien est plus sûr
             return select(events_table).where(literal(False)), {} # Requête vide

        if vector is not None and len(vector) != vector_dim:
             raise ValueError(f"Incorrect vector dimension. Expected {vector_dim}, got {len(vector)}")

        params: Dict[str, Any] = {}
        md_param = bindparam('md_filter', value=metadata, type_=JSONB) if metadata else None
        ts_start_param = None
        if ts_start:
            if ts_start.tzinfo is None: ts_start = ts_start.replace(tzinfo=timezone.utc)
            ts_start_param = bindparam('ts_start', value=ts_start, type_=TIMESTAMP(timezone=True))
            params['ts_start'] = ts_start

        ts_end_param = None
        if ts_end:
            if ts_end.tzinfo is None: ts_end = ts_end.replace(tzinfo=timezone.utc)
            ts_end_param = bindparam('ts_end', value=ts_end, type_=TIMESTAMP(timezone=True))
            params['ts_end'] = ts_end

        limit_param = bindparam('lim', value=limit, type_=Integer)
        params['lim'] = limit
        offset_param = bindparam('off', value=offset, type_=Integer)
        params['off'] = offset

        # Base select clause based on vector presence
        if vector is not None:
             vector_param = bindparam('vec_query', value=vector, type_=Vector(vector_dim))
             params['vec_query'] = vector
             select_clause = select(
                 events_table.c.id,
                 events_table.c.timestamp,
                 events_table.c.content,
                 events_table.c.metadata,
                 events_table.c.embedding,
                 (events_table.c.embedding.l2_distance(vector_param)).label('similarity_score')
             )
        else:
             select_clause = select(
                 events_table.c.id,
                 events_table.c.timestamp,
                 events_table.c.content,
                 events_table.c.metadata,
                 cast(literal(None), Vector(vector_dim)).label('embedding'),
                 cast(literal(None), Float).label('similarity_score')
             )

        # Where clause conditions
        conditions = []
        if md_param is not None:
            conditions.append(events_table.c.metadata.op('@>')(md_param))
            params['md_filter'] = metadata # Add to params dict

        if ts_start_param is not None:
            conditions.append(events_table.c.timestamp >= ts_start_param)
        if ts_end_param is not None:
            conditions.append(events_table.c.timestamp <= ts_end_param)

        # Add distance threshold for hybrid searches (vector + other filters)
        is_hybrid = vector is not None and (metadata is not None or ts_start is not None or ts_end is not None)
        if is_hybrid:
             distance_param = bindparam('distance_threshold', value=distance_threshold, type_=Float)
             conditions.append(events_table.c.embedding.l2_distance(vector_param) < distance_param)
             params['distance_threshold'] = distance_threshold

        # Apply WHERE conditions
        if conditions:
            query = select_clause.where(and_(*conditions))
        else:
            query = select_clause

        # Add ORDER BY clause
        if vector is not None:
            query = query.order_by(events_table.c.embedding.l2_distance(vector_param))
        else:
            query = query.order_by(desc(events_table.c.timestamp))

        # Add LIMIT and OFFSET
        query = query.limit(limit_param).offset(offset_param)
        
        return query, params

class EventRepository:
    """Couche d'accès aux données pour la table 'events'."""

    def __init__(self, engine: AsyncEngine):
        """Initialise le repository avec un moteur SQLAlchemy et un query builder."""
        self.engine = engine
        self.logger = structlog.get_logger(__name__)
        self.query_builder = EventQueryBuilder() # Instance du builder

    async def add(self, event_data: EventCreate) -> EventModel:
        """Ajoute un nouvel événement (utilise EventQueryBuilder)."""
        query, params = self.query_builder.build_add_query(event_data)

        async with self.engine.connect() as conn:
            try:
                result = await conn.execute(query, params)
                record = result.fetchone()
                await conn.commit()
            except Exception as e:
                await conn.rollback()
                self.logger.error(f"Error adding event: {e}", method="add", **params)
                raise

        if record:
            return EventModel.from_db_record(record._asdict())
        else:
            raise Exception("Failed to create event or retrieve returning values.")

    async def get_by_id(self, event_id: uuid.UUID) -> Optional[EventModel]:
        """Récupère un événement par ID (utilise EventQueryBuilder)."""
        query, params = self.query_builder.build_get_by_id_query(event_id)

        async with self.engine.connect() as conn:
            result = await conn.execute(query, params)
            record = result.fetchone()

        if record:
            return EventModel.from_db_record(record._asdict())
        return None

    async def update_metadata(self, event_id: uuid.UUID, metadata_update: Dict[str, Any]) -> Optional[EventModel]:
        """Met à jour les métadonnées (utilise EventQueryBuilder)."""
        query, params = self.query_builder.build_update_metadata_query(event_id, metadata_update)

        async with self.engine.connect() as conn:
            try:
                result = await conn.execute(query, params)
                record = result.fetchone()
                await conn.commit()
            except Exception as e:
                await conn.rollback()
                # Log simplifié, params peuvent contenir des données sensibles
                self.logger.error(f"Error updating metadata for event {event_id}: {e}", method="update_metadata")
                raise

        if record:
            return EventModel.from_db_record(record._asdict())
        return None

    async def delete(self, event_id: uuid.UUID) -> bool:
        """Supprime un événement par ID (utilise EventQueryBuilder)."""
        query, params = self.query_builder.build_delete_query(event_id)
        deleted = False

        async with self.engine.connect() as conn:
            try:
                result = await conn.execute(query, params)
                await conn.commit()
                deleted = result.rowcount > 0 if result.rowcount is not None and result.rowcount >= 0 else True
            except Exception as e:
                await conn.rollback()
                self.logger.error(f"Error deleting event {event_id}: {e}", method="delete")
                raise

        return deleted

    async def filter_by_metadata(self, metadata_criteria: Dict[str, Any]) -> List[EventModel]:
        """Filtre par métadonnées (utilise EventQueryBuilder)."""
        query, params = self.query_builder.build_filter_by_metadata_query(metadata_criteria)
        raw_records = []

        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(query, params)
                raw_records = result.mappings().all() # Utiliser mappings pour obtenir des dicts
                self.logger.debug("filter_by_metadata raw results count=%d", len(raw_records))
        except Exception as e:
            self.logger.error(f"filter_by_metadata error during query: {e!s}", method="filter_by_metadata")
            raise

        # Convertir les résultats bruts en EventModel
        return [EventModel.from_db_record(record) for record in raw_records]

    async def search_vector(
        self,
        vector: Optional[List[float]] = None,
        top_k: int = 10,
        metadata: Optional[Dict[str, Any]] = None,
        ts_start: Optional[datetime.datetime] = None,
        ts_end: Optional[datetime.datetime] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[EventModel]:
        """
        Recherche des événements (utilise EventQueryBuilder).
        """
        
        # Construire la requête et les paramètres en utilisant le builder
        try:
             query, params = self.query_builder.build_search_vector_query(
                  vector=vector,
                  metadata=metadata,
                  ts_start=ts_start,
                  ts_end=ts_end,
                  limit=limit,
                  offset=offset
                  # On pourrait passer distance_threshold ici si nécessaire
             )
             # Si le builder retourne une requête vide (aucun critère)
             if isinstance(query.whereclause, False_):
                  self.logger.warning("search_vector called without any valid search criteria.")
                  return []
        except ValueError as ve: # Capturer l'erreur de dimension du vecteur du builder
             self.logger.error("Invalid vector dimension provided", error=ve)
             raise # Re-lever l'erreur
        except Exception as build_e: # Autres erreurs potentielles du builder
             self.logger.error("Error building search query", error=build_e, exc_info=True)
             raise

        # Logging des paramètres (sans le vecteur potentiellement large)
        log_params = {k: v for k, v in params.items() if k != 'vec_query'}
        if 'vec_query' in params: log_params['vec_query_present'] = True
        self.logger.debug("Executing search_vector", method="search_vector", params=log_params)

        results_raw = []
        async with self.engine.connect() as conn:
            try:
                result = await conn.execute(query, params)
                results_raw = result.mappings().all()
                self.logger.debug(f"search_vector: Fetched {len(results_raw)} records")

            except SQLAlchemyError as e:
                 self.logger.error("Database error during search_vector", error=e, sql=str(query), params=log_params, exc_info=True)
                 raise # Re-raise to fail tests clearly
            except Exception as e:
                 # Catch other potential errors (less likely here)
                 self.logger.error("Unexpected error during search_vector execution", error=e, exc_info=True)
                 raise

        # Process results into EventModel outside the try block (or handle parsing errors)
        final_results = []
        for row_dict in results_raw: # row_dict is a RowMapping
            try:
                # Convert RowMapping to a standard dict before passing
                final_results.append(EventModel.from_db_record(dict(row_dict))) 
            except Exception as e:
                 self.logger.error(f"Failed to parse DB record into EventModel: {row_dict}", error=str(e), exc_info=True)
                 # Decide how to handle parsing errors - skip record or raise? Skip for now.
                 continue

        return final_results # Return list of EventModel instances

# Note: Il faudra également mettre en place la gestion du pool de connexions
# dans api/main.py (via le lifespan) et l'injection de dépendance
# pour que les routes puissent obtenir une instance de EventRepository. 