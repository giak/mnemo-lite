import uuid
import datetime
import json
from typing import List, Dict, Any, Optional, Tuple, Union

# Imports SQLAlchemy nécessaires
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection
from sqlalchemy.sql import (
    select, column, and_, or_, func, text, bindparam, delete, update, insert, 
    Select, Delete, Update, Insert
)
from sqlalchemy.sql.expression import literal_column
# Import spécifique pour la vérification
from sqlalchemy.sql.elements import False_, ColumnElement
from sqlalchemy.engine import Result
from sqlalchemy import Table, Column, String, MetaData, TIMESTAMP, cast
# Import specific functions/types for expression language
from sqlalchemy.dialects.postgresql import JSONB, TEXT
# Import VECTOR type
from pgvector.sqlalchemy import VECTOR

# Importations liées à Pydantic pour la validation et la sérialisation
from pydantic import BaseModel, Field, field_validator

# Importation pour le logging
import logging

# Import RepositoryError from base
from .base import RepositoryError

# Import the canonical EventModel using absolute path
from api.models.event_models import EventModel, EventCreate, EventUpdate

# Définition de la table events pour SQLAlchemy
metadata = MetaData()
events_table = Table(
    'events',
    metadata,
    Column('id', String, primary_key=True),
    Column('content', String),
    Column('metadata', String),
    Column('embedding', String),
    Column('timestamp', TIMESTAMP(timezone=True))
)

# Configuration du logger
# Ou logging.DEBUG pour plus de détails
logging.basicConfig(level=logging.INFO)

# --- Query Builder ---

class EventQueryBuilder:
    """Construit les requêtes SQL pour EventRepository en utilisant SQLAlchemy Core."""

    def _get_vector_dimensions(self) -> int:
        """Retourne la dimension attendue pour les vecteurs (à configurer)."""
        # TODO: Rendre configurable ou récupérer depuis une source externe
        return 1536  # Align with bdd_schema.md

    def build_add_query(
        self, event_data: EventCreate) -> Tuple[Any, Dict[str, Any]]:
        """Construit la requête INSERT."""
        params = {
    "content": json.dumps(
        event_data.content),
        "metadata": json.dumps(
            event_data.metadata) if event_data.metadata else None,
            "embedding": EventModel._format_embedding_for_db(
                event_data.embedding),
                 "timestamp": event_data.timestamp}
        query = insert(events_table).values(
            content=params["content"],
            metadata=params["metadata"],
            embedding=params["embedding"],
            timestamp=params["timestamp"]
        ).returning(
            events_table.c.id,
            events_table.c.content,
            events_table.c.metadata,
            events_table.c.embedding,
            events_table.c.timestamp
        )
        return query, params

    def build_get_by_id_query(
        self, event_id: uuid.UUID) -> Tuple[str, Dict[str, Any]]:
        """Construit la requête SELECT par ID."""
        query = text("""
            SELECT
                id,
                content,
                metadata,
                embedding,
                timestamp
            FROM
                events
            WHERE
                id = :event_id
        """)
        
        return query, {"event_id": event_id}

    def build_update_metadata_query(self,
    event_id: uuid.UUID,
    metadata_update: Dict[str,
    Any]) -> Tuple[Any,
    Dict[str,
     Any]]:
        """Construit la requête UPDATE pour mettre à jour les métadonnées d'un événement."""
        # Utilise JSONB || pour fusionner les objets JSON
        # Note: SQLAlchemy Core might not directly support || operator easily across dialects.
        # Using text() here is still a reasonable approach for this specific operation.
        update_query = text("""
            UPDATE events 
            SET metadata = metadata || CAST(:metadata_update AS JSONB)
            WHERE id = :event_id
            RETURNING id, content, metadata, embedding, timestamp
        """)
        params = {
            "event_id": event_id,
            "metadata_update": json.dumps(metadata_update)
        }
        return update_query, params # Keep returning text/dict for this one

    def build_delete_query(
        self, event_id: uuid.UUID) -> Delete: # Return Delete object
        """Construit la requête DELETE par ID avec paramètre lié."""
        # Paramètre lié directement dans la requête
        query = delete(events_table).where(
            events_table.c.id == bindparam('event_id', value=str(event_id)) # Bind here
        ).returning(
            events_table.c.id
        )
        # Ne retourne que l'objet requête
        return query 

    def build_filter_by_metadata_query(
        self, metadata_criteria: Dict[str, Any]) -> Select: # Return Select object
        """Construit la requête SELECT avec filtres sur les métadonnées JSON (SQLAlchemy Core)."""
        if not metadata_criteria:
            raise ValueError("Metadata criteria cannot be empty")

        # Bind param without type_
        criteria_param = bindparam('criteria', value=json.dumps(metadata_criteria))

        query = select(
            events_table.c.id,
            events_table.c.content,
            events_table.c.metadata,
            events_table.c.embedding,
            events_table.c.timestamp
        ).select_from(events_table).where(
            # Cast the column to JSONB and use op()
            cast(events_table.c.metadata, JSONB).op('@>')(criteria_param) 
        ).order_by(events_table.c.timestamp.desc())

        # Ne retourne que l'objet requête, les paramètres sont liés
        return query

    def build_search_vector_query(
        self,
        vector: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ts_start: Optional[datetime.datetime] = None,
        ts_end: Optional[datetime.datetime] = None,
        limit: Optional[int] = 10, # Allow None
        offset: Optional[int] = 0, # Allow None
        distance_threshold: Optional[float] = 5.0,
        select_count: bool = False # New flag
    ) -> Optional[Select]: # Can return None if invalid state?
        """
        Construit la requête SELECT pour la recherche vectorielle/filtrée.
        Peut retourner une requête pour compter les résultats (select_count=True) 
        ou pour récupérer les données (select_count=False).
        Retourne None si vector est fourni mais invalide.
        """
        # Common conditions and parameter setup
        conditions = []
        order_by_expression = events_table.c.timestamp.desc() # Default order

        # Vector processing (only if vector provided)
        vector_param = None
        if vector is not None:
            if len(vector) != self._get_vector_dimensions():
                 # Return None for invalid dimension? Or raise earlier?
                 # Raising earlier in the main repo method is better.
                 # Let's assume the check happened before calling this.
                 raise ValueError(f"Vector dimension mismatch. Expected {self._get_vector_dimensions()}, got {len(vector)}")
            
            # Format handled by pgvector adapter now
            # Use plain VECTOR, dimension is defined by the column
            vector_param = bindparam('vec_query', value=vector, type_=VECTOR) 
            
            # Add distance threshold condition
            dist_thresh_param = bindparam('dist_thresh', value=distance_threshold)
            # Use text() for the operator
            conditions.append(text("(embedding <-> :vec_query) <= :dist_thresh").bindparams(vector_param, dist_thresh_param))
            order_by_expression = text("similarity_score ASC") # Order by similarity if vector used

        # Metadata filter part
        if metadata:
            metadata_param = bindparam('md_filter', value=json.dumps(metadata))
            conditions.append(events_table.c.metadata.op('@>')(cast(metadata_param, JSONB)))

        # Timestamp filter part
        if ts_start:
            ts_start_param = bindparam('ts_start', value=ts_start)
            conditions.append(events_table.c.timestamp >= ts_start_param)
        if ts_end:
            ts_end_param = bindparam('ts_end', value=ts_end)
            conditions.append(events_table.c.timestamp <= ts_end_param)
        
        # --- Select Clause --- 
        if select_count:
            # Select COUNT(*)
            select_expression = select(func.count(events_table.c.id).label("total_hits"))
        else:
            # Select data columns + similarity score if applicable
            select_columns = [
                events_table.c.id,
                events_table.c.timestamp,
                events_table.c.content,
                events_table.c.metadata,
                events_table.c.embedding
            ]
            if vector is not None:
                distance_select_expression = text("(embedding <-> :vec_query) AS similarity_score").bindparams(vector_param) 
                select_columns.append(distance_select_expression)
            else:
                # Add NULL similarity score if no vector search
                select_columns.append(literal_column("NULL").label("similarity_score"))
                
            select_expression = select(*select_columns)

        # Combine conditions if any
        final_query = select_expression.select_from(events_table)
        if conditions:
            final_query = final_query.where(and_(*conditions))

        # Apply ordering, limit, offset only if fetching data rows
        if not select_count:
            final_query = final_query.order_by(order_by_expression)
            if limit is not None:
                 final_query = final_query.limit(limit)
            if offset is not None:
                 final_query = final_query.offset(offset)

        return final_query


# --- Repository ---

class EventRepository:
    """Gère les opérations CRUD et de recherche pour les événements dans la base de données."""

    def __init__(self, engine: AsyncEngine):
        """Initialise le repository avec une engine SQLAlchemy async."""
        self.engine = engine
        self.query_builder = EventQueryBuilder()
        self.logger = logging.getLogger(__name__)
        self.logger.info("EventRepository initialized.")

    async def _execute_query(self, query: ColumnElement, params: Optional[Union[Dict[str, Any], List[Any], Tuple[Any, ...]]] = None, is_mutation: bool = False) -> Result:
        """Exécute une requête SQLAlchemy Core ou TextClause."""
        async with self.engine.connect() as connection:
            transaction = await connection.begin() if is_mutation else None
            try:
                # --- Enhanced Debugging --- 
                self.logger.info(f"_execute_query executing:")
                self.logger.info(f"  Query Type: {type(query)}")
                # Try compiling for logging
                try:
                    # Check if it's a Compilable object before trying to compile
                    if hasattr(query, 'compile'):
                        compiled = query.compile(bind=self.engine, compile_kwargs={"literal_binds": False})
                        self.logger.info(f"  Compiled Query: {str(compiled)}")
                        self.logger.info(f"  Compiled Params: {compiled.params}") 
                    # Use isinstance against the imported 'text' function object
                    elif isinstance(query, text): 
                         self.logger.info(f"  Query String (text function): {str(query)}")
                    else:
                        self.logger.info(f"  Query object is not directly compilable or text: {type(query)}")

                except Exception as compile_err:
                    self.logger.warning(f"  Could not compile query for logging: {compile_err}")
                    # Fallback check using text function object
                    if isinstance(query, text): 
                        self.logger.info(f"  Query String (text function): {str(query)}")
                        
                self.logger.info(f"  Params Dict/List Received (should usually be None for Core): {params}")
                # --- End Debugging ---
                
                # Execute, passing params ONLY if they are provided externally
                # (Primarily for text() queries not built via Core expressions)
                if params:
                    result = await connection.execute(query, params)
                else:
                    result = await connection.execute(query) # Core objects have params bound
                
                if transaction:
                    await transaction.commit()
                return result
            except Exception as e:
                if transaction:
                    await transaction.rollback()
                self.logger.error(f"Database query execution failed: {e}", exc_info=True)
                raise  # Re-lever l'exception pour gestion en amont

    async def add(self, event_data: EventCreate) -> EventModel:
        """Ajoute un nouvel événement en utilisant des paramètres nommés cohérents."""
        try:
            # Colonnes et placeholders nommés pour la requête INSERT
            columns_to_insert = ["content", "metadata", "embedding"]
            # Utiliser des paramètres nommés pour TOUTES les colonnes
            value_placeholders = [":content", ":metadata", ":embedding"]
            
            # Préparer les paramètres de base
            params = {
                "content": json.dumps(event_data.content),
                "metadata": json.dumps(event_data.metadata) if event_data.metadata else None,
                "embedding": EventModel._format_embedding_for_db(event_data.embedding),
            }

            # Ajouter conditionnellement le timestamp
            if event_data.timestamp is not None:
                columns_to_insert.append("timestamp")
                value_placeholders.append(":timestamp") # Placeholder nommé
                params["timestamp"] = event_data.timestamp
                self.logger.info(f"Using provided timestamp: {event_data.timestamp}")
            else:
                self.logger.info("Timestamp not provided by EventCreate, relying on DB default.")

            # Construire la requête SQL dynamique SANS casts explicites ::jsonb
            columns_sql_part = ", ".join(columns_to_insert)
            values_sql_part = ", ".join(value_placeholders)
            
            sql_query_str = f"""
                INSERT INTO events ({columns_sql_part}) 
                VALUES ({values_sql_part}) 
                RETURNING id, content, metadata, embedding, timestamp
            """
            sql_query = text(sql_query_str)
            
            self.logger.info(f"Executing INSERT with named parameters: Query starts with '{sql_query_str[:100]}...'")
            # self.logger.debug(f"Params for insert: {params}") # Log params if needed
            
            async with self.engine.connect() as connection:
                async with connection.begin():
                    result = await connection.execute(sql_query, params)
                    added_record = result.mappings().first()
                    if added_record:
                        return EventModel.from_db_record(added_record)
                    else:
                        self.logger.error("INSERT query did not return the added record despite success indication.")
                        raise RepositoryError("Failed to retrieve record after insert.")
        except Exception as e:
            self.logger.error(f"Database error in add_event: {e}", exc_info=True)
            raise RepositoryError(f"Failed to add event due to database error: {e}") from e

    async def get_by_id(self, event_id: uuid.UUID) -> Optional[EventModel]:
        """Récupère un événement par ID (utilise EventQueryBuilder)."""
        try:
            query, params = self.query_builder.build_get_by_id_query(event_id)
            result = await self._execute_query(query, params=params)
            record = result.mappings().first()
            return EventModel.from_db_record(record) if record else None
        except Exception as e:
            self.logger.error(
    f"Failed to get event by ID {event_id}: {e}",
     exc_info=True)
            raise

    async def update_metadata(self, event_id: uuid.UUID, metadata_update: Dict[str, Any]) -> Optional[EventModel]:
        """Met à jour (fusionne) les métadonnées d'un événement."""
        try:
            # Using text() here due to JSONB || operator
            query, params = self.query_builder.build_update_metadata_query(event_id, metadata_update)
            result = await self._execute_query(query, params=params, is_mutation=True)
            updated_record = result.mappings().first()
            if updated_record:
                return EventModel.from_db_record(updated_record)
            else:
                # L'événement n'a pas été trouvé pour la mise à jour
                return None
        except Exception as e:
            self.logger.error(
    f"Failed to update metadata for event {event_id}: {e}",
     exc_info=True)
            raise

    async def delete(self, event_id: uuid.UUID) -> bool:
        """Supprime un événement par ID."""
        try:
            query = self.query_builder.build_delete_query(event_id) # Get query object
            # Execute query without separate params dict
            result = await self._execute_query(query, is_mutation=True) 
            deleted_id = result.scalar_one_or_none()
            return deleted_id is not None
        except Exception as e:
            self.logger.error(
    f"Failed to delete event {event_id}: {e}",
     exc_info=True)
            raise

    async def filter_by_metadata(self, metadata_criteria: Dict[str, Any]) -> List[EventModel]:
        """Filtre les événements par critères de métadonnées."""
        try:
            query = self.query_builder.build_filter_by_metadata_query(metadata_criteria) # Get query object
            # Execute query without separate params dict
            result = await self._execute_query(query) 
            records = result.mappings().all()
            self.logger.debug(f"filter_by_metadata raw results count={len(records)}")
            return [EventModel.from_db_record(record) for record in records]
        except Exception as e:
            self.logger.error(f"Failed to filter events by metadata: {e}", exc_info=True)
            raise

    async def search_vector(
        self,
        vector: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ts_start: Optional[datetime.datetime] = None,
        ts_end: Optional[datetime.datetime] = None,
        limit: int = 10,
        offset: int = 0,
        distance_threshold: Optional[float] = 5.0
    ) -> Tuple[List[EventModel], int]: # Return Tuple now
        """
        Recherche des événements (utilise EventQueryBuilder).
        Combine la recherche vectorielle et/ou par filtres (metadata, timestamp).
        Returns a list of events and the total potential hit count for pagination.
        """
        
        try:
            # 1. Build and execute the COUNT query (without limit/offset)
            count_query = self.query_builder.build_search_vector_query(
                vector=vector,
                metadata=metadata,
                ts_start=ts_start,
                ts_end=ts_end,
                distance_threshold=distance_threshold,
                limit=None,  # Explicitly None for count
                offset=None, # Explicitly None for count
                select_count=True # Add flag for builder to select count(*)
            )
            
            total_hits = 0
            if count_query is not None: # build_search_vector_query might return None if no criteria for count?
                async with self.engine.connect() as connection:
                    count_result = await connection.execute(count_query)
                    total_hits = count_result.scalar_one_or_none() or 0
            else:
                 # If no criteria were provided for count, maybe count all?
                 # This logic needs refinement based on builder behavior.
                 # For now, assume 0 if count_query is None.
                 self.logger.warning("Count query was None in search_vector")

            # 2. Build and execute the main data query (with limit/offset)
            data_query = self.query_builder.build_search_vector_query(
                vector=vector,
                metadata=metadata,
                ts_start=ts_start,
                ts_end=ts_end,
                limit=limit,
                offset=offset,
                distance_threshold=distance_threshold,
                select_count=False # Explicitly get data rows
            )

            events = []
            if data_query is not None:
                async with self.engine.connect() as connection:
                    result = await connection.execute(data_query)
                    records = result.mappings().all()
                    events = [
                        EventModel.from_db_record(record) for record in records
                    ]
            else:
                self.logger.warning("Data query was None in search_vector")

            return events, total_hits

        except ValueError as ve:
            self.logger.error(f"ValueError during vector search: {ve}") 
            raise RepositoryError(f"Invalid input for search: {ve}") from ve
        except Exception as e:
            self.logger.exception("Database error during vector search", exc_info=e)
            raise RepositoryError(f"Database error during search: {e}") from e

# --- Fin du fichier ---
