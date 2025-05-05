import uuid
import datetime
import json
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.sql import text, bindparam # We might switch to Core DSL later
from sqlalchemy.exc import SQLAlchemyError
import structlog
from sqlalchemy.engine import Result, RowMapping

# Importer les modèles depuis api.models
from models.memory_models import Memory, MemoryCreate, MemoryUpdate

class MemoryRepository:
    """Couche d'accès aux données pour les mémoires (table 'events').
    
    Note: La classe Memory est un wrapper autour des événements dans la table 'events'.
    Les champs spécifiques à Memory (memory_type, event_type, role_id, etc.) sont stockés
    dans le champ JSONB 'metadata' de la table events.
    """

    TABLE_NAME = "events"

    def __init__(self, engine: AsyncEngine):
        """Initialise le repository avec un moteur SQLAlchemy."""
        self.engine = engine
        self.logger = structlog.get_logger(__name__)

    def _map_record_to_memory(self, record: tuple) -> Memory:
        """Mappe un enregistrement tuple de base de données en objet Memory.
        
        Structure de la table events:
        - id: UUID
        - timestamp: TIMESTAMPTZ
        - content: JSONB
        - metadata: JSONB
        - embedding: VECTOR(1536)
        
        Les champs spécifiques à Memory sont stockés dans metadata.
        """
        # Accès par index aux valeurs retournées par la DB
        record_id = record[0]
        record_timestamp = record[1]
        raw_content = record[2] # Content JSONB
        raw_metadata = record[3] # Metadata JSONB
        # embedding est à l'index 4 si présent, mais nous n'en avons pas besoin ici
        
        # Conversion du contenu en dictionnaire si c'est une chaîne JSON
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

        # Conversion des métadonnées en dictionnaire si c'est une chaîne JSON
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        if isinstance(raw_metadata, str):
            try:
                metadata = json.loads(raw_metadata)
            except json.JSONDecodeError:
                self.logger.warning("Could not parse metadata JSON from DB", raw_metadata=raw_metadata, record_id=record_id)
                metadata = {}
        elif not isinstance(raw_metadata, dict):
            self.logger.warning("Unexpected metadata type from DB", metadata_type=type(raw_metadata), record_id=record_id)
            metadata = {} # Fallback to empty dict

        # Extraction des champs spécifiques à Memory depuis metadata
        memory_metadata = metadata.copy() # Copie pour éviter de modifier l'original
        
        # Extraire les champs spécifiques à Memory avec des valeurs par défaut
        memory_type = memory_metadata.pop("memory_type", "unknown")
        event_type = memory_metadata.pop("event_type", "unknown")
        role_id = memory_metadata.pop("role_id", -1)
        expiration_str = memory_metadata.pop("expiration", None)
        
        # Conversion de la date d'expiration si présente
        expiration_dt = None
        if expiration_str:
            try:
                expiration_dt = datetime.datetime.fromisoformat(expiration_str.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                self.logger.warning("Could not parse expiration date from metadata", raw_expiration=expiration_str, record_id=record_id)

        # Création de l'objet Memory avec les données extraites
        return Memory(
            id=record_id,
            timestamp=record_timestamp,
            memory_type=memory_type,
            event_type=event_type,
            role_id=role_id,
            content=content,
            metadata=memory_metadata, # Les métadonnées restantes après extraction des champs spécifiques
            expiration=expiration_dt
        )

    async def add(self, memory_data: MemoryCreate) -> Memory:
        """Ajoute une nouvelle mémoire à la base de données."""
        self.logger.debug("Adding memory", memory_type=memory_data.memory_type)

        # Combiner les métadonnées spécifiques à Memory avec les métadonnées générales
        combined_metadata = memory_data.metadata.copy() if memory_data.metadata else {}
        combined_metadata['memory_type'] = memory_data.memory_type
        combined_metadata['event_type'] = memory_data.event_type
        combined_metadata['role_id'] = memory_data.role_id
        if memory_data.expiration:
            combined_metadata['expiration'] = memory_data.expiration.isoformat()

        # Générer un UUID
        memory_id = uuid.uuid4()

        # Préparer les paramètres
        params_dict = {
            "id": memory_id,
            "content": json.dumps(memory_data.content),
            "metadata": json.dumps(combined_metadata)
        }
        
        # Requête d'insertion
        query = text(f"""
        INSERT INTO {self.TABLE_NAME} (id, timestamp, content, metadata)
        VALUES (:id, NOW() AT TIME ZONE 'utc', :content, :metadata)
        RETURNING id, timestamp, content, metadata
        """)

        async with self.engine.connect() as conn:
            try:
                result: Result = await conn.execute(query, params_dict)
                record = result.fetchone()
                await conn.commit()
                self.logger.info("Memory added successfully", memory_id=str(memory_id))
            except SQLAlchemyError as e:
                await conn.rollback()
                self.logger.error("Database error adding memory", error=str(e), **params_dict)
                raise ConnectionError(f"Failed to add memory to database: {e}") from e
            except Exception as e:
                await conn.rollback()
                self.logger.error("Unexpected error adding memory", error=str(e), **params_dict)
                raise RuntimeError(f"An unexpected error occurred: {e}") from e

        if record:
            return self._map_record_to_memory(record)
        else:
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
            return None
        except Exception as e:
            self.logger.error("Unexpected error getting memory by ID", memory_id=str(memory_id), error=str(e))
            return None

        if record:
            try:
                return self._map_record_to_memory(record)
            except Exception as map_e:
                self.logger.error("Error mapping DB record to Memory model", error=str(map_e))
                return None
        else:
            self.logger.debug("Memory not found by ID", memory_id=str(memory_id))
            return None

    async def update(self, memory_id: uuid.UUID, memory_update_data: MemoryUpdate) -> Optional[Memory]:
        """Met à jour une mémoire existante."""
        self.logger.debug("Updating memory", memory_id=str(memory_id), update_data=memory_update_data.model_dump(exclude_unset=True))

        update_dict = memory_update_data.model_dump(exclude_unset=True)

        if not update_dict:
            self.logger.info("No fields provided for update, returning current memory", memory_id=str(memory_id))
            return await self.get_by_id(memory_id)

        # Préparer les données pour la fusion JSONB
        metadata_to_merge: Dict[str, Any] = {}
        content_to_merge: Optional[Dict[str, Any]] = None

        if "content" in update_dict:
            content_to_merge = update_dict["content"]

        # Champs spécifiques à mettre dans metadata
        if "memory_type" in update_dict:
            metadata_to_merge["memory_type"] = update_dict["memory_type"]
        if "event_type" in update_dict:
            metadata_to_merge["event_type"] = update_dict["event_type"]
        if "role_id" in update_dict:
            metadata_to_merge["role_id"] = update_dict["role_id"]
        if "expiration" in update_dict:
            expiration_dt = update_dict["expiration"]
            metadata_to_merge["expiration"] = expiration_dt.isoformat() if expiration_dt else None
        
        # Fusionner les métadonnées fournies
        if "metadata" in update_dict and isinstance(update_dict["metadata"], dict):
            metadata_to_merge.update(update_dict["metadata"]) 
            
        # Vérifier s'il y a des données à mettre à jour
        if not content_to_merge and not metadata_to_merge:
            self.logger.warning("Update called but no valid fields could be prepared", memory_id=str(memory_id))
            return await self.get_by_id(memory_id)

        # Approche plus simple: construire une requête SQL dynamique avec les champs à mettre à jour
        try:
            # Approche directe avec SQL pur pour éviter les problèmes de paramètres
            if content_to_merge and metadata_to_merge:
                # Conversion directe en SQL avec les valeurs littérales
                content_json = json.dumps(content_to_merge).replace("'", "''")
                metadata_json = json.dumps(metadata_to_merge).replace("'", "''")
                
                query = text(f"""
                    UPDATE {self.TABLE_NAME}
                    SET content = content || '{content_json}'::jsonb,
                        metadata = metadata || '{metadata_json}'::jsonb
                    WHERE id = :memory_id
                    RETURNING id, timestamp, content, metadata
                """)
                
            elif content_to_merge:
                # Seulement contenu à mettre à jour
                content_json = json.dumps(content_to_merge).replace("'", "''")
                
                query = text(f"""
                    UPDATE {self.TABLE_NAME}
                    SET content = content || '{content_json}'::jsonb
                    WHERE id = :memory_id
                    RETURNING id, timestamp, content, metadata
                """)
                
            else:
                # Seulement métadonnées à mettre à jour
                metadata_json = json.dumps(metadata_to_merge).replace("'", "''")
                
                query = text(f"""
                    UPDATE {self.TABLE_NAME}
                    SET metadata = metadata || '{metadata_json}'::jsonb
                    WHERE id = :memory_id
                    RETURNING id, timestamp, content, metadata
                """)
                
            params = {"memory_id": memory_id}
            
            # Exécution avec une seule requête
            async with self.engine.begin() as conn:
                result = await conn.execute(query, params)
                record = result.fetchone()
                
                if record:
                    self.logger.info("Memory updated successfully", memory_id=str(memory_id))
                else:
                    self.logger.warning("Record not found after update", memory_id=str(memory_id))
                    
        except SQLAlchemyError as e:
            self.logger.error("Database error updating memory", memory_id=str(memory_id), error=str(e))
            raise ConnectionError(f"Failed to update memory in database: {e}") from e
        except Exception as e:
            self.logger.error("Unexpected error updating memory", memory_id=str(memory_id), error=str(e))
            raise RuntimeError(f"An unexpected error occurred during update: {e}") from e

        if record:
            try:
                return self._map_record_to_memory(record)
            except Exception as map_e:
                self.logger.error("Error mapping updated DB record to Memory model", error=str(map_e))
                raise ValueError(f"Memory was updated, but failed to map the result: {map_e}") from map_e
        else:
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
                raise ConnectionError(f"Failed to delete memory from database: {e}") from e
            except Exception as e:
                await conn.rollback()
                self.logger.error("Unexpected error deleting memory", memory_id=str(memory_id), error=str(e))
                raise RuntimeError(f"An unexpected error occurred during delete: {e}") from e

        return deleted_count > 0

    async def list_memories(
        self,
        limit: int = 10,
        skip: int = 0,
        memory_type: Optional[str] = None,
        event_type: Optional[str] = None,
        role_id: Optional[int] = None,
        session_id: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        ts_start: Optional[datetime.datetime] = None,
        ts_end: Optional[datetime.datetime] = None,
        offset: Optional[int] = None
    ) -> tuple[List[Memory], int]:
        """Liste les mémoires avec filtres et pagination.
        
        Filtre sur les champs stockés dans metadata: memory_type, event_type, role_id, etc.
        
        Returns:
            tuple contenant (Liste des mémoires trouvées, nombre total de résultats)
        """
        try:
            # Valeurs de pagination sécurisées
            effective_offset = offset if offset is not None else skip
            effective_limit = max(1, limit) if limit > 0 else 10
            effective_offset = max(0, effective_offset)
            
            # Construction de la requête de base
            base_query = f"""
                SELECT id, timestamp, content, metadata, embedding
                FROM {self.TABLE_NAME}
                WHERE 1=1
            """
            
            count_query = f"""
                SELECT COUNT(*)
                FROM {self.TABLE_NAME}
                WHERE 1=1
            """
            
            # Préparation des paramètres
            params_dict = {}
            
            # Ajout des conditions de filtrage
            if memory_type:
                base_query += " AND metadata->>'memory_type' = :memory_type"
                count_query += " AND metadata->>'memory_type' = :memory_type"
                params_dict["memory_type"] = memory_type
                
            if event_type:
                base_query += " AND metadata->>'event_type' = :event_type"
                count_query += " AND metadata->>'event_type' = :event_type"
                params_dict["event_type"] = event_type
                
            if role_id:
                base_query += " AND (metadata->>'role_id')::int = :role_id"
                count_query += " AND (metadata->>'role_id')::int = :role_id"
                params_dict["role_id"] = role_id
                
            if session_id:
                base_query += " AND metadata->>'session_id' = :session_id"
                count_query += " AND metadata->>'session_id' = :session_id"
                params_dict["session_id"] = session_id
                
            # Filtre sur timestamp
            if ts_start:
                base_query += " AND timestamp >= :ts_start"
                count_query += " AND timestamp >= :ts_start"
                params_dict["ts_start"] = ts_start
                
            if ts_end:
                base_query += " AND timestamp <= :ts_end"
                count_query += " AND timestamp <= :ts_end"
                params_dict["ts_end"] = ts_end
                
            # Filtrage avancé sur metadata
            if metadata_filter:
                for key, value in metadata_filter.items():
                    param_name = f"metadata_{key}"
                    if isinstance(value, dict):
                        # Filtrage sur un objet JSON imbriqué
                        base_query += f" AND metadata->'{key}' @> :{param_name}::jsonb"
                        count_query += f" AND metadata->'{key}' @> :{param_name}::jsonb"
                        params_dict[param_name] = json.dumps(value)
                    else:
                        # Filtrage sur une valeur simple
                        base_query += f" AND metadata->>'{key}' = :{param_name}"
                        count_query += f" AND metadata->>'{key}' = :{param_name}"
                        params_dict[param_name] = str(value)
            
            # Exécution de la requête de comptage
            async with self.engine.connect() as conn:
                count_query_obj = text(count_query)
                result = await conn.execute(count_query_obj, params_dict)
                total_count = result.scalar() or 0
                
                # Cas spécial: si limit=0, retourner une liste vide mais le compte total
                if limit == 0:
                    return [], total_count
                
                # Si aucun résultat, retourner une liste vide
                if total_count == 0:
                    return [], 0
                    
                # Tri et pagination
                base_query += """
                    ORDER BY timestamp DESC
                    LIMIT :limit
                    OFFSET :offset
                """
                
                params_dict["limit"] = effective_limit
                params_dict["offset"] = effective_offset
                    
                # Exécution de la requête principale
                query_obj = text(base_query)
                result = await conn.execute(query_obj, params_dict)
                rows = result.fetchall()
                
                # Conversion des résultats en objets Memory
                memories: List[Memory] = []
                for row in rows:
                    memory = self._map_record_to_memory(row)
                    memories.append(memory)
                    
                return memories, total_count
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la liste des mémoires: {str(e)}")
            return [], 0

    async def search_by_embedding(
        self,
        embedding: List[float],
        limit: int = 10,
        skip: int = 0,
        ts_start: Optional[datetime.datetime] = None,
        ts_end: Optional[datetime.datetime] = None
    ) -> tuple[List[Memory], int]:
        """
        Recherche des mémoires par similarité vectorielle.
        
        Returns:
            Tuple contenant (liste des mémoires trouvées, nombre total de résultats)
        """
        try:
            # Précaution en cas d'embedding nul ou invalide
            if not embedding or not isinstance(embedding, list):
                return [], 0
                
            # Vérification des valeurs de pagination
            effective_limit = max(1, limit) if limit > 0 else 10
            effective_skip = max(0, skip)
            
            # Construction de la requête SQL pour la similitude cosinus
            base_query = f"""
                SELECT id, timestamp, content, metadata, embedding 
                FROM {self.TABLE_NAME}
                WHERE embedding IS NOT NULL
            """
            
            count_query = f"""
                SELECT COUNT(*) 
                FROM {self.TABLE_NAME}
                WHERE embedding IS NOT NULL
            """
            
            # Format the embedding as a PostgreSQL array string
            # This is critical for pgvector compatibility
            embedding_str = "[" + ",".join(str(float(x)) for x in embedding) + "]"
            
            # Préparation des paramètres
            params_dict = {}
                
            # Ajouter des filtres temporels si nécessaires
            if ts_start:
                base_query += " AND timestamp >= :ts_start"
                count_query += " AND timestamp >= :ts_start"
                params_dict["ts_start"] = ts_start
                
            if ts_end:
                base_query += " AND timestamp <= :ts_end"
                count_query += " AND timestamp <= :ts_end"
                params_dict["ts_end"] = ts_end
            
            # Calcul de la similarité cosinus et tri
            vector_query = f"""
                {base_query}
                ORDER BY embedding <=> '{embedding_str}'::vector
                LIMIT :limit OFFSET :skip
            """
            
            params_dict["limit"] = effective_limit
            params_dict["skip"] = effective_skip
            
            async with self.engine.connect() as conn:
                # Exécuter la requête de comptage
                count_sql = text(count_query)
                count_result = await conn.execute(count_sql, params_dict)
                total_count = count_result.scalar() or 0
                
                if total_count == 0:
                    return [], 0
                
                # Exécuter la requête principale
                vector_sql = text(vector_query)
                result = await conn.execute(vector_sql, params_dict)
                rows = result.fetchall()
                
                # Convertir les résultats en objets Memory
                memories = []
                for row in rows:
                    memory = self._map_record_to_memory(row)
                    memories.append(memory)
                
                return memories, total_count
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la recherche par embedding: {str(e)}")
            return [], 0 