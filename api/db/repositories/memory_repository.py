import uuid
import datetime
import json
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.sql import text # We might switch to Core DSL later
from sqlalchemy.exc import SQLAlchemyError
import structlog
from sqlalchemy.engine import Result, RowMapping

# Importer les modèles depuis api.models
from models.memory_models import Memory, MemoryCreate, MemoryUpdate

class MemoryRepository:
    """Couche d'accès aux données pour les mémoires (table 'events')."""

    TABLE_NAME = "events"

    def __init__(self, engine: AsyncEngine):
        """Initialise le repository avec un moteur SQLAlchemy."""
        self.engine = engine
        self.logger = structlog.get_logger(__name__)
        # TODO: Consider adding a MemoryQueryBuilder if logic becomes complex

    def _map_record_to_memory(self, record: tuple) -> Memory:
        """Mappe un enregistrement tuple de base de données en objet Memory."""
        # Access by index since fetchone() likely returned a tuple here
        record_id = record[0]
        record_timestamp = record[1]
        raw_content = record[2] # Might be dict or JSON string
        raw_metadata = record[3] # Might be dict or JSON string

        # record_dict = dict(record) # <-- Remove this conversion
        
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        # Handle potential JSON string in metadata or content if needed
        if isinstance(raw_metadata, str):
            try:
                metadata = json.loads(raw_metadata)
            except json.JSONDecodeError:
                self.logger.warning("Could not parse metadata JSON from DB", raw_metadata=raw_metadata, record_id=record_id)
                metadata = {}
        elif not isinstance(raw_metadata, dict):
             self.logger.warning("Unexpected metadata type from DB", metadata_type=type(raw_metadata), record_id=record_id)
             metadata = {} # Fallback to empty dict

        content = raw_content if isinstance(raw_content, dict) else {}
        if isinstance(raw_content, str):
             try:
                content = json.loads(raw_content)
             except json.JSONDecodeError:
                self.logger.warning("Could not parse content JSON from DB", raw_content=raw_content, record_id=record_id)
                content = {}
        elif not isinstance(raw_content, dict):
            self.logger.warning("Unexpected content type from DB", content_type=type(raw_content), record_id=record_id)
            content = {} # Fallback to empty dict

        # Extract memory-specific fields from metadata, providing defaults
        memory_type = metadata.pop("memory_type", "unknown") # Use pop to remove them from metadata dict
        event_type = metadata.pop("event_type", "unknown")
        role_id = metadata.pop("role_id", -1) # Use a sensible default like -1 or None
        expiration_str = metadata.pop("expiration", None)
        
        expiration_dt = None
        if expiration_str:
            try:
                # Attempt to parse ISO format datetime string
                expiration_dt = datetime.datetime.fromisoformat(expiration_str.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                self.logger.warning("Could not parse expiration date from metadata", raw_expiration=expiration_str, record_id=record_id)

        return Memory(
            id=record_id,
            timestamp=record_timestamp,
            memory_type=memory_type,
            event_type=event_type,
            role_id=role_id,
            content=content,
            metadata=metadata, # Remaining metadata after popping specific fields
            expiration=expiration_dt
        )

    async def add(self, memory_data: MemoryCreate) -> Memory:
        """Ajoute une nouvelle mémoire à la base de données."""
        self.logger.debug("Adding memory", memory_type=memory_data.memory_type)

        # Combine specific fields into metadata
        combined_metadata = memory_data.metadata.copy() if memory_data.metadata else {}
        combined_metadata['memory_type'] = memory_data.memory_type
        combined_metadata['event_type'] = memory_data.event_type
        combined_metadata['role_id'] = memory_data.role_id
        if memory_data.expiration:
            combined_metadata['expiration'] = memory_data.expiration.isoformat()

        # Generate UUID here, as the original route did
        memory_id = uuid.uuid4()

        # Prepare params as dict
        params_dict = {
            "id": memory_id,
            "content": json.dumps(memory_data.content),
            "metadata": json.dumps(combined_metadata)
        }
        
        # Use named parameters :name
        query = text(f"""
        INSERT INTO {self.TABLE_NAME} (id, timestamp, content, metadata)
        VALUES (:id, NOW() AT TIME ZONE 'utc', :content, :metadata)
        RETURNING id, timestamp, content, metadata
        """)

        # Parameters tuple is no longer needed
        # params_tuple = (
        #     params_dict["id"],
        #     params_dict["content"],
        #     params_dict["metadata"]
        # )

        async with self.engine.connect() as conn:
            try:
                # Use the dict for execute with named parameters
                result: Result = await conn.execute(query, params_dict)
                record = result.fetchone()
                await conn.commit()
                self.logger.info("Memory added successfully", memory_id=str(memory_id))
            except SQLAlchemyError as e:
                await conn.rollback()
                # Use the dict for logging
                self.logger.error("Database error adding memory", error=str(e), **params_dict)
                # Reraise a more generic error or a custom one
                raise ConnectionError(f"Failed to add memory to database: {e}") from e
            except Exception as e:
                 await conn.rollback()
                 # Use the dict for logging here too, just in case
                 self.logger.error("Unexpected error adding memory", error=str(e), **params_dict)
                 raise RuntimeError(f"An unexpected error occurred: {e}") from e

        if record:
            # Map the raw DB record to the Memory Pydantic model
            return self._map_record_to_memory(record)
        else:
            # This should ideally not happen if RETURNING is used and insert succeeds
            self.logger.error("Failed to retrieve returned record after insert", memory_id=str(memory_id))
            raise Exception("Failed to create memory or retrieve returning values.")

    async def get_by_id(self, memory_id: uuid.UUID) -> Optional[Memory]:
        """Récupère une mémoire par son ID unique."""
        self.logger.debug("Getting memory by ID", memory_id=str(memory_id))

        query = text(f"""
            SELECT id, timestamp, content, metadata 
            FROM {self.TABLE_NAME} 
            WHERE id = :memory_id
        """)
        params = {"memory_id": memory_id}
        record = None

        try:
            async with self.engine.connect() as conn:
                result: Result = await conn.execute(query, params)
                record = result.fetchone()
        except SQLAlchemyError as e:
            self.logger.error("Database error getting memory by ID", memory_id=str(memory_id), error=str(e))
            # Do not raise here, just return None as per function signature
            return None
        except Exception as e:
            self.logger.error("Unexpected error getting memory by ID", memory_id=str(memory_id), error=str(e))
            return None # Return None on unexpected errors too

        if record:
            try:
                return self._map_record_to_memory(record)
            except Exception as map_e: # Catch potential mapping errors
                self.logger.error("Error mapping DB record to Memory model", record_data=dict(record), error=str(map_e))
                return None # Return None if mapping fails
        else:
            self.logger.debug("Memory not found by ID", memory_id=str(memory_id))
            return None

    async def update(self, memory_id: uuid.UUID, memory_update_data: MemoryUpdate) -> Optional[Memory]:
        """Met à jour une mémoire existante.

        Met à jour le champ `content` et/ou les champs stockés dans `metadata` 
        (`memory_type`, `event_type`, `role_id`, `expiration`, `metadata`).
        Utilise l'opérateur de fusion JSONB `||`.
        """
        self.logger.debug("Updating memory", memory_id=str(memory_id), update_data=memory_update_data.model_dump(exclude_unset=True))

        update_dict = memory_update_data.model_dump(exclude_unset=True) # Pydantic V2

        if not update_dict:
            self.logger.info("No fields provided for update, returning current memory", memory_id=str(memory_id))
            # If no data to update, just fetch and return the current state
            return await self.get_by_id(memory_id)

        set_clauses = []
        params: Dict[str, Any] = {"memory_id": memory_id}

        # --- Préparer les données pour la fusion JSONB --- 
        metadata_to_merge: Dict[str, Any] = {}
        content_to_merge: Optional[Dict[str, Any]] = None

        if "content" in update_dict:
            content_to_merge = update_dict["content"]
            params["p_content"] = json.dumps(content_to_merge)
            set_clauses.append(f"content = content || :p_content")

        # Champs spécifiques à mettre dans metadata
        if "memory_type" in update_dict:
            metadata_to_merge["memory_type"] = update_dict["memory_type"]
        if "event_type" in update_dict:
            metadata_to_merge["event_type"] = update_dict["event_type"]
        if "role_id" in update_dict:
            metadata_to_merge["role_id"] = update_dict["role_id"]
        if "expiration" in update_dict:
            # Convertir datetime en string ISO pour JSON
            expiration_dt = update_dict["expiration"]
            metadata_to_merge["expiration"] = expiration_dt.isoformat() if expiration_dt else None
        
        # Fusionner le dict metadata fourni
        if "metadata" in update_dict and isinstance(update_dict["metadata"], dict):
            metadata_to_merge.update(update_dict["metadata"]) 
        
        # Ajouter la clause SET pour metadata seulement s'il y a quelque chose à merger
        if metadata_to_merge:
            params["p_metadata"] = json.dumps(metadata_to_merge)
            set_clauses.append(f"metadata = metadata || :p_metadata")
            
        # --- Construire et Exécuter la Requête --- 
        if not set_clauses:
             self.logger.warning("Update called but no valid fields could be prepared for SET clause.", memory_id=str(memory_id))
             return await self.get_by_id(memory_id) # Retourne l'état actuel

        set_sql = ", ".join(set_clauses)
        query = text(f"""
            UPDATE {self.TABLE_NAME}
            SET {set_sql}
            WHERE id = :memory_id
            RETURNING id, timestamp, content, metadata
        """)

        record = None
        async with self.engine.connect() as conn:
            try:
                result: Result = await conn.execute(query, params)
                record = result.fetchone()
                await conn.commit()
                if record:
                     self.logger.info("Memory updated successfully", memory_id=str(memory_id))
                else:
                     # Should not happen with RETURNING if ID exists, but good to check
                     # Maybe the ID didn't exist initially?
                     self.logger.warning("Update executed but no record returned (memory might not exist?)", memory_id=str(memory_id))
            except SQLAlchemyError as e:
                await conn.rollback()
                self.logger.error("Database error updating memory", memory_id=str(memory_id), error=str(e), params=params)
                raise ConnectionError(f"Failed to update memory in database: {e}") from e
            except Exception as e:
                await conn.rollback()
                self.logger.error("Unexpected error updating memory", memory_id=str(memory_id), error=str(e), params=params)
                raise RuntimeError(f"An unexpected error occurred during update: {e}") from e

        if record:
            try:
                return self._map_record_to_memory(record)
            except Exception as map_e:
                self.logger.error("Error mapping updated DB record to Memory model", record_data=dict(record), error=str(map_e))
                # If update succeeded but mapping failed, maybe return None or raise?
                # Returning None might be confusing. Let's raise an error.
                raise ValueError(f"Memory was updated, but failed to map the result: {map_e}") from map_e
        else:
            # L'enregistrement n'existait probablement pas
            return None

    async def delete(self, memory_id: uuid.UUID) -> bool:
        """Supprime une mémoire par son ID."""
        self.logger.debug("Deleting memory", memory_id=str(memory_id))
        
        query = text(f"DELETE FROM {self.TABLE_NAME} WHERE id = :memory_id")
        params = {"memory_id": memory_id}
        deleted_count = 0

        async with self.engine.connect() as conn:
            try:
                result: Result = await conn.execute(query, params)
                await conn.commit()
                deleted_count = result.rowcount if result.rowcount is not None else 0
                if deleted_count > 0:
                    self.logger.info("Memory deleted successfully", memory_id=str(memory_id))
                else:
                    self.logger.warning("Attempted to delete non-existent memory", memory_id=str(memory_id))
            except SQLAlchemyError as e:
                await conn.rollback()
                self.logger.error("Database error deleting memory", memory_id=str(memory_id), error=str(e))
                # Reraise a more generic error or a custom one
                raise ConnectionError(f"Failed to delete memory from database: {e}") from e
            except Exception as e:
                await conn.rollback()
                self.logger.error("Unexpected error deleting memory", memory_id=str(memory_id), error=str(e))
                raise RuntimeError(f"An unexpected error occurred during delete: {e}") from e

        return deleted_count > 0

    async def list_memories(
        self,
        limit: int = 10,
        offset: int = 0,
        memory_type: Optional[str] = None,
        event_type: Optional[str] = None,
        role_id: Optional[int] = None,
        session_id: Optional[str] = None # Assuming session_id is in metadata
    ) -> List[Memory]:
        """Liste les mémoires avec filtres et pagination.
        
        Filtre sur les champs `memory_type`, `event_type`, `role_id`, `session_id` 
        qui sont stockés comme clés dans la colonne `metadata` JSONB.
        """
        self.logger.debug(
            "Listing memories", 
            limit=limit, offset=offset, memory_type=memory_type, 
            event_type=event_type, role_id=role_id, session_id=session_id
        )
        
        where_clauses: List[str] = []
        params: Dict[str, Any] = {"limit": limit, "offset": offset}

        # Construire dynamiquement la clause WHERE
        if memory_type is not None:
            where_clauses.append(f"metadata->>'memory_type' = :memory_type")
            params["memory_type"] = memory_type
            
        if event_type is not None:
            where_clauses.append(f"metadata->>'event_type' = :event_type")
            params["event_type"] = event_type
            
        if role_id is not None:
            # Important: Cast JSONB text value to integer for comparison
            where_clauses.append(f"(metadata->>'role_id')::integer = :role_id") 
            params["role_id"] = role_id
            
        if session_id is not None:
            where_clauses.append(f"metadata->>'session_id' = :session_id")
            params["session_id"] = session_id
        
        where_sql = ""
        if where_clauses:
            where_sql = f"WHERE {' AND '.join(where_clauses)}"
        
        # Requête finale
        query = text(f"""
            SELECT id, timestamp, content, metadata
            FROM {self.TABLE_NAME}
            {where_sql}
            ORDER BY timestamp DESC
            LIMIT :limit OFFSET :offset
        """)

        records = []
        try:
            async with self.engine.connect() as conn:
                result: Result = await conn.execute(query, params)
                records = result.fetchall() # Fetch all records
                self.logger.debug(f"Fetched {len(records)} records for list_memories")
        except SQLAlchemyError as e:
            self.logger.error("Database error listing memories", error=str(e), filters=params)
            raise ConnectionError(f"Failed to list memories from database: {e}") from e
        except Exception as e:
            self.logger.error("Unexpected error listing memories", error=str(e), filters=params)
            raise RuntimeError(f"An unexpected error occurred listing memories: {e}") from e
            
        # Mapper les résultats
        mapped_results = []
        for record in records:
             try:
                 mapped_results.append(self._map_record_to_memory(record))
             except Exception as map_e:
                 self.logger.error("Error mapping DB record to Memory model during list", record_data=dict(record), error=str(map_e))
                 # Skip records that fail mapping
                 continue 
                 
        return mapped_results 