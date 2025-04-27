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

# logger = logging.getLogger(__name__) # <<< REMOVE MODULE-LEVEL LOGGER

class EventModel(BaseModel):
    id: uuid.UUID
    timestamp: datetime.datetime
    content: Dict[str, Any]
    metadata: Dict[str, Any]
    embedding: Optional[List[float]]
    similarity_score: Optional[float] = None

    @classmethod
    def from_db_record(cls, record_data: Dict[str, Any]) -> "EventModel":
        """Crée une instance EventModel à partir d'un dict de données."""
        record_dict = record_data.copy()
        
        # Parser content et metadata si ce sont des chaînes
        for field in ['content', 'metadata']:
            if isinstance(record_dict.get(field), str):
                try:
                    record_dict[field] = json.loads(record_dict[field])
                except (json.JSONDecodeError, TypeError):
                    # Gérer l'erreur si le JSON de la DB est invalide (peu probable ici)
                    # Pour l'instant, on pourrait lever une erreur ou mettre None/dict vide
                    record_dict[field] = {} # Mettre un dict vide par défaut
        
        # Parse embedding if it's a string
        if isinstance(record_dict.get('embedding'), str):
            try:
                # Try using json.loads first
                record_dict['embedding'] = json.loads(record_dict['embedding'])
            except (json.JSONDecodeError, TypeError):
                try:
                    # Try manual parsing as backup
                    record_dict['embedding'] = _parse_embedding_from_db(record_dict['embedding'])
                except:
                    record_dict['embedding'] = None
        
        # Le score de similarité peut être absent (si pas de recherche vectorielle)
        if 'similarity_score' not in record_dict:
            record_dict['similarity_score'] = None 
            
        # Use model_validate for Pydantic v2
        return cls.model_validate(record_dict)

def _format_embedding_for_db(embedding: List[float]) -> str:
    """Converts a list of floats to a pgvector-compatible string."""
    return "[" + ",".join(map(str, embedding)) + "]"

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
        return None # Or raise ValueError("Invalid embedding format")
    # except (ValueError, TypeError) as e:  # <<< REMOVE logging call from helper
    #     # Potentially pass logger instance if needed later
    #     # logger.error(f"Error parsing embedding string '{embedding_str}': {e}") 
    #     return None

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

class EventRepository:
    """Couche d'accès aux données pour la table 'events'."""

    # Change __init__ to accept SQLAlchemy AsyncEngine
    def __init__(self, engine: AsyncEngine):
        """Initialise le repository avec un moteur SQLAlchemy asynchrone."""
        self.engine = engine
        # self.pool: asyncpg.Pool = pool # Keep the old pool reference commented out for now
        self.logger = structlog.get_logger(__name__) # Use structlog logger

    def _get_vector_dimensions(self) -> int:
        """Returns the configured vector embedding dimension."""
        return 1536

    async def add(self, event_data: EventCreate) -> EventModel:
        """Ajoute un nouvel événement à la base de données."""
        timestamp_to_use = event_data.timestamp if event_data.timestamp else datetime.datetime.now(timezone.utc)
        
        # Convert embedding list to string format expected by pgvector
        # Example: [0.1, 0.2] -> '[0.1,0.2]' (Verify exact format if needed)
        embedding_str = None
        if event_data.embedding is not None:
             # Convert list of floats to comma-separated string within brackets
             embedding_str = '[' + ','.join(map(str, event_data.embedding)) + ']'

        query = text("""
        INSERT INTO events (content, metadata, embedding, timestamp) 
        VALUES (:content, :metadata, :embedding, :timestamp)
        RETURNING id, timestamp, content, metadata, embedding
        """)
        
        params = {
            "content": json.dumps(event_data.content),
            "metadata": json.dumps(event_data.metadata),
            # Pass the string representation or None
            "embedding": embedding_str, 
            "timestamp": timestamp_to_use 
        }

        async with self.engine.connect() as conn:
            try:
                result = await conn.execute(query, params)
                record = result.fetchone()
                await conn.commit()
            except Exception as e:
                await conn.rollback()
                self.logger.error(f"Error adding event: {e}", exc_info=True)
                raise

        if record:
            record_dict = record._asdict()
            # Handle potential string format returned from DB for embedding
            if isinstance(record_dict.get('embedding'), str):
                 try:
                     # Attempt to parse string back to list of floats
                     # This assumes the DB returns in '[...]' format
                     record_dict['embedding'] = json.loads(record_dict['embedding'])
                 except (json.JSONDecodeError, TypeError):
                      self.logger.warning("Could not parse embedding string from DB back to list", exc_info=True)
                      record_dict['embedding'] = None # Or handle as error

            return EventModel.from_db_record(record_dict)
        else:
            raise Exception("Failed to create event or retrieve returning values.")

    async def get_by_id(self, event_id: uuid.UUID) -> Optional[EventModel]:
        """Récupère un événement par son ID."""
        query = text("""
            SELECT id, timestamp, content, metadata, embedding 
            FROM events WHERE id = :event_id
        """)
        params = {"event_id": event_id}
        
        # Use the engine
        async with self.engine.connect() as conn:
            result = await conn.execute(query, params)
            record = result.fetchone()
        
        if record:
            record_dict = record._asdict() 
            return EventModel.from_db_record(record_dict)
        return None

    async def update_metadata(self, event_id: uuid.UUID, metadata_update: Dict[str, Any]) -> Optional[EventModel]:
        """Met à jour (fusionne) les métadonnées d'un événement existant."""
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
        
        async with self.engine.connect() as conn:
            try:
                result = await conn.execute(query, params)
                record = result.fetchone()
                await conn.commit()
            except Exception as e:
                await conn.rollback()
                self.logger.error(f"Error updating metadata for event {event_id}: {e}", exc_info=True)
                raise

        if record:
            record_dict = record._asdict()
            # Handle potential string format for embedding
            if isinstance(record_dict.get('embedding'), str):
                 try: record_dict['embedding'] = json.loads(record_dict['embedding'])
                 except: record_dict['embedding'] = None
            return EventModel.from_db_record(record_dict)
        return None

    async def delete(self, event_id: uuid.UUID) -> bool:
        """Supprime un événement par son ID. Retourne True si réussi."""
        query = text("DELETE FROM events WHERE id = :event_id")
        params = {"event_id": event_id}
        deleted = False
        # Use the engine
        async with self.engine.connect() as conn:
            try:
                result = await conn.execute(query, params)
                # Check rowcount if available and meaningful, otherwise assume success if no exception
                # For asyncpg, rowcount might not be reliable for DELETE.
                # If result.rowcount is reliably > 0, use that. Otherwise, True on no exception.
                # Let's assume True for now if execute completes without error.
                await conn.commit() # Commit transaction
                # Check if result.rowcount works reliably with your setup, otherwise this is optimistic
                deleted = result.rowcount > 0 if result.rowcount is not None and result.rowcount >= 0 else True 
            except Exception as e:
                await conn.rollback()
                self.logger.error(f"Error deleting event {event_id}: {e}", exc_info=True)
                # Re-raise or return False based on desired error handling
                raise # Re-raise the exception for now

        return deleted # Return status based on execution

    async def filter_by_metadata(self, metadata_criteria: Dict[str, Any]) -> List[EventModel]:
        """Récupère une liste d'événements filtrés par critères de métadonnées."""
        query = text("""
        SELECT id, timestamp, content, metadata, embedding 
        FROM events 
        WHERE metadata @> :criteria::jsonb
        ORDER BY timestamp DESC
        """)
        params = {"criteria": json.dumps(metadata_criteria)}
        
        records = []
        try:
            async with self.engine.connect() as conn:
                self.logger.debug("Executing filter_by_metadata query=%s criteria_json=%s", str(query), params["criteria"])
                result = await conn.execute(query, params)
                records = result.fetchall()
                self.logger.debug("filter_by_metadata raw results count=%d", len(records))
        except Exception as e:
            self.logger.error(f"filter_by_metadata error during query: {e!s}", exc_info=True)
            raise # Re-raise for now

        event_models = []
        for record in records:
            record_dict = record._asdict()
            if isinstance(record_dict.get('embedding'), str):
                 try: record_dict['embedding'] = json.loads(record_dict['embedding'])
                 except: record_dict['embedding'] = None
            event_models.append(EventModel.from_db_record(record_dict))
            
        return event_models

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
        Search for events using vector similarity, metadata filtering, and time range.
        Supports vector-only, metadata-only, and hybrid searches using SQLAlchemy Core.
        """
        self.logger.debug(
            "Searching events (Core)",
            has_vector=vector is not None,
            metadata_filter=metadata,
            # top_k=top_k, # Removed top_k log as it's indirectly used by limit
            ts_start=ts_start,
            ts_end=ts_end,
            limit=limit,
            offset=offset,
        )
        results_raw = []
        limit = max(0, limit)
        offset = max(0, offset)

        async with self.engine.connect() as conn:
            try:
                # Prepare parameters using bindparam for safety and type handling
                # Pass the Python dict directly to bindparam for JSONB
                md_param = bindparam('md_filter', value=metadata, type_=JSONB) if metadata else None 
                ts_start_param = bindparam('ts_start', value=ts_start, type_=TIMESTAMP(timezone=True)) if ts_start else None
                ts_end_param = bindparam('ts_end', value=ts_end, type_=TIMESTAMP(timezone=True)) if ts_end else None
                limit_param = bindparam('lim', value=limit, type_=Integer)
                offset_param = bindparam('off', value=offset, type_=Integer)

                # Select based on whether vector search is needed
                if vector:
                    # --- Hybrid or Vector-Only Search (Using Core DSL - seems okay) ---
                    self.logger.debug("Executing hybrid/vector search using SQLAlchemy Core DSL")
                    # Ensure vector param uses the helper function --- NON ! Le bind processor s'en charge
                    # Pass the raw list/numpy array directly to bindparam
                    vector_param = bindparam('vec_query', value=vector, type_=Vector(self._get_vector_dimensions())) 

                    selectable_columns = [
                        events_table.c.id,
                        events_table.c.timestamp,
                        events_table.c.content,
                        events_table.c.metadata,
                        events_table.c.embedding,
                        events_table.c.embedding.l2_distance(vector_param).label('similarity_score')
                    ]
                    stmt = select(*selectable_columns)

                    where_conditions = []
                    if md_param is not None: # Check if bindparam was created
                        # Use the md_param which now holds the dictionary directly
                        where_conditions.append(events_table.c.metadata.op('@>')(md_param)) 
                    if ts_start_param is not None:
                        where_conditions.append(events_table.c.timestamp >= ts_start_param)
                    if ts_end_param is not None:
                        where_conditions.append(events_table.c.timestamp <= ts_end_param)

                    if where_conditions:
                        stmt = stmt.where(and_(*where_conditions))

                    stmt = stmt.order_by(events_table.c.embedding.l2_distance(vector_param))
                    stmt = stmt.limit(limit_param).offset(offset_param)

                    compiled_stmt = stmt.compile(self.engine, compile_kwargs={"literal_binds": False})
                    # Log params correctly - bindparams handle the dictionary internally now
                    self.logger.debug(f"Compiled hybrid/vector search (Core DSL): {compiled_stmt}\nParams: {compiled_stmt.params}") 

                    # Extract parameters for vector search
                    params = {
                        'vec_query': vector
                    }
                    if md_param is not None:
                        params['md_filter'] = metadata
                    if ts_start_param is not None:
                        params['ts_start'] = ts_start
                    if ts_end_param is not None:
                        params['ts_end'] = ts_end
                    params['lim'] = limit
                    params['off'] = offset
                    
                    result = await conn.execute(stmt, params)
                    results_raw = result.mappings().all()
                    self.logger.debug(f"search_vector (hybrid/vector): Fetched {len(results_raw)} records")


                elif metadata or ts_start or ts_end:
                    # --- Metadata / Time Filter Only Path (Using Core DSL) ---
                    self.logger.debug("Executing metadata/time only search using SQLAlchemy Core DSL")
                    
                    # Use Core DSL for consistency with other code paths
                    selectable_columns = [
                        events_table.c.id,
                        events_table.c.timestamp,
                        events_table.c.content,
                        events_table.c.metadata,
                        cast(None, Vector(self._get_vector_dimensions())).label('embedding'),
                        cast(None, Float).label('similarity_score')
                    ]
                    stmt = select(*selectable_columns)
                    
                    # Build where conditions using Core DSL
                    where_conditions = []
                    if md_param is not None:
                        where_conditions.append(events_table.c.metadata.op('@>')(md_param))
                    if ts_start_param is not None:
                        where_conditions.append(events_table.c.timestamp >= ts_start_param)
                    if ts_end_param is not None:
                        where_conditions.append(events_table.c.timestamp <= ts_end_param)
                    
                    if where_conditions:
                        stmt = stmt.where(and_(*where_conditions))
                    
                    # Apply consistent ordering and pagination
                    stmt = stmt.order_by(desc(events_table.c.timestamp))
                    stmt = stmt.limit(limit_param).offset(offset_param)
                    
                    # Log the compiled statement for debugging
                    compiled_stmt = stmt.compile(self.engine, compile_kwargs={"literal_binds": False})
                    self.logger.debug(f"Compiled metadata/time search (Core DSL): {compiled_stmt}\nParams: {compiled_stmt.params}")
                    
                    # Extract parameters from bindparams
                    params = {}
                    if md_param is not None:
                        params['md_filter'] = metadata
                    if ts_start_param is not None:
                        params['ts_start'] = ts_start
                    if ts_end_param is not None:
                        params['ts_end'] = ts_end
                    params['lim'] = limit
                    params['off'] = offset
                    
                    # Execute the query with explicit parameters
                    result = await conn.execute(stmt, params)
                    results_raw = result.mappings().all()
                    self.logger.debug(f"search_vector (metadata/time): Fetched {len(results_raw)} records")
                    
                    # Add validation check for unexpected result counts
                    if len(results_raw) > limit and limit > 0:
                        self.logger.warning(
                            f"Query returned more results ({len(results_raw)}) than requested limit ({limit}). "
                            f"This may indicate a pagination issue."
                        )

                else:
                    # --- No Filters Path (Get recent events - Using Core DSL - seems okay) ---
                    self.logger.debug("Executing default search (no filters) using SQLAlchemy Core DSL")
                    # Re-define limit/offset params here using the original names for clarity in this scope
                    limit_param_no_filter = bindparam('lim_no_f', value=limit, type_=Integer)
                    offset_param_no_filter = bindparam('off_no_f', value=offset, type_=Integer)
                    # selectable_columns = [...] # Already defined is fine, or redefine for clarity
                    selectable_columns = [
                        events_table.c.id,
                        events_table.c.timestamp,
                        events_table.c.content,
                        events_table.c.metadata,
                        cast(None, Vector(self._get_vector_dimensions())).label('embedding'),
                        cast(None, Float).label('similarity_score')
                    ]
                    stmt = select(*selectable_columns)
                    stmt = stmt.order_by(desc(events_table.c.timestamp))
                    # Use the specific bind params for this no-filter branch
                    stmt = stmt.limit(limit_param_no_filter).offset(offset_param_no_filter)

                    compiled_stmt = stmt.compile(self.engine, compile_kwargs={"literal_binds": False})
                    self.logger.debug(f"Compiled default search (Core DSL): {compiled_stmt}\nParams: {compiled_stmt.params}") # Params automatically extracted

                    result = await conn.execute(stmt) # Pass the statement object
                    results_raw = result.mappings().all()
                    self.logger.debug(f"search_vector (default): Fetched {len(results_raw)} records")


            except SQLAlchemyError as e:
                self.logger.error(f"Database error during search: {e}", exc_info=True)
                raise # Re-raise to fail tests clearly
            except Exception as e:
                self.logger.error(f"Unexpected error during search: {e}", exc_info=True)
                raise # Re-raise

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