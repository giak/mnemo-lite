import uuid
import json
import datetime
from typing import List, Dict, Any, Optional, Tuple, Union

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.sql import text
from sqlalchemy.engine import Result

from models.memory_models import Memory, MemoryCreate, MemoryUpdate

import logging
# Configurer le logger pour ce module
logging.basicConfig(level=logging.INFO)

# Constante pour le nom de la table
TABLE_NAME = "events"

class MemoryRepository:
    def __init__(self, connection: Union[AsyncConnection, AsyncEngine]):
        """Initialise le repository avec une connexion ou un engine SQL Alchemy."""
        self.engine = connection if isinstance(connection, AsyncEngine) else None
        self.connection = connection if isinstance(connection, AsyncConnection) else None
        self.logger = logging.getLogger(__name__)
        self.logger.info('MemoryRepository initialized')
        
    async def _get_connection(self):
        """Retourne la connexion existante ou en crée une nouvelle depuis le moteur."""
        if self.connection:
            return self.connection
        if self.engine:
            return await self.engine.connect()
        raise ValueError("No connection or engine provided to repository")
        
    def _prepare_embedding(self, embedding):
        """Prépare l'embedding pour l'enregistrement en DB.
        Accepte une liste de float ou None, et retourne une valeur appropriée pour la BD.
        """
        if embedding is None:
            return None
        
        # Si l'embedding est déjà une chaîne, le retourner
        if isinstance(embedding, str):
            return embedding
            
        # Convertir une liste en chaîne
        if isinstance(embedding, list):
            return str(embedding)
            
        # Autre cas, retourner tel quel
        return embedding
    
    def _parse_embedding(self, embedding):
        """Parse l'embedding stocké en DB en une liste de float.
        Accepte une chaîne ou None et retourne une liste de float ou None.
        """
        if embedding is None:
            return None
            
        # Si c'est déjà une liste, la retourner
        if isinstance(embedding, list):
            return embedding
            
        # Tenter de convertir une chaîne en liste
        if isinstance(embedding, str):
            try:
                import ast
                return ast.literal_eval(embedding)
            except (ValueError, SyntaxError):
                self.logger.warning(f"Impossible de parser l'embedding: {embedding}")
                return embedding  # Retourner tel quel en cas d'erreur
        
        # Autre cas, retourner tel quel
        return embedding
            
    async def get_by_id(self, memory_id: uuid.UUID) -> Optional[Memory]:
        """Récupère une mémoire par son ID depuis la table events."""
        try:
            # Construire la requête SQL pour sélectionner un événement par ID
            query = text(f"""
                SELECT
                    id,
                    content,
                    metadata,
                    embedding,
                    timestamp
                FROM
                    {TABLE_NAME}
                WHERE
                    id = :memory_id
            """)
            
            conn = await self._get_connection()
            result = await conn.execute(query, {"memory_id": memory_id})
            row = result.mappings().first()
            
            if not row:
                return None
                
            # Construire l'objet Memory à partir de l'événement
            # Note: les champs memory_type, event_type et role_id doivent être extraits des métadonnées
            metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"] or {}
            
            memory = Memory(
                id=row["id"],
                memory_type=metadata.get("memory_type", "event"),  # Valeur par défaut "event"
                event_type=metadata.get("event_type", "log"),      # Valeur par défaut "log"
                role_id=metadata.get("role_id", 1),                # Valeur par défaut 1 = system
                content=json.loads(row["content"]) if isinstance(row["content"], str) else row["content"],
                metadata={k: v for k, v in metadata.items() if k not in ["memory_type", "event_type", "role_id", "expiration"]},
                timestamp=row["timestamp"],
                embedding=self._parse_embedding(row["embedding"]),
                expiration=metadata.get("expiration")
            )
            return memory
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération de la mémoire {memory_id}: {e}")
            raise
            
    async def add(self, memory_data: MemoryCreate) -> Memory:
        """Ajoute une nouvelle mémoire à la table events."""
        try:
            # Générer un UUID pour l'ID si non fourni
            memory_id = uuid.uuid4()
            
            # Préparer les métadonnées en incluant les champs spécifiques de Memory
            metadata = memory_data.metadata or {}
            metadata["memory_type"] = memory_data.memory_type
            metadata["event_type"] = memory_data.event_type
            metadata["role_id"] = memory_data.role_id
            if memory_data.expiration:
                metadata["expiration"] = memory_data.expiration.isoformat()
                
            # Construire la requête SQL pour insérer un nouvel événement
            query = text(f"""
                INSERT INTO {TABLE_NAME} (id, content, metadata, embedding, timestamp) 
                VALUES (:id, CAST(:content AS JSONB), CAST(:metadata AS JSONB), :embedding, :timestamp)
                RETURNING id, content, metadata, embedding, timestamp
            """)
            
            # Préparer les paramètres
            params = {
                "id": memory_id,
                "content": json.dumps(memory_data.content),
                "metadata": json.dumps(metadata),
                "embedding": self._prepare_embedding(memory_data.embedding),
                "timestamp": memory_data.timestamp or datetime.datetime.now(datetime.timezone.utc)
            }
            
            # Exécuter la requête
            conn = await self._get_connection()
            async with conn.begin():
                result = await conn.execute(query, params)
                row = result.mappings().first()
            
            # Créer l'objet Memory à partir du résultat
            return Memory(
                id=row["id"],
                memory_type=memory_data.memory_type,
                event_type=memory_data.event_type,
                role_id=memory_data.role_id,
                content=json.loads(row["content"]) if isinstance(row["content"], str) else row["content"],
                metadata=memory_data.metadata or {},
                timestamp=row["timestamp"],
                embedding=self._parse_embedding(row["embedding"]),
                expiration=memory_data.expiration
            )
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'ajout d'une mémoire: {e}")
            raise
            
    async def update(self, memory_id: uuid.UUID, memory_data: MemoryUpdate) -> Optional[Memory]:
        """Met à jour une mémoire existante dans la table events."""
        try:
            # Récupérer d'abord la mémoire existante
            existing_memory = await self.get_by_id(memory_id)
            if not existing_memory:
                return None
                
            # Préparer les champs à mettre à jour
            update_fields = []
            params = {"memory_id": memory_id}
            
            # Mettre à jour le contenu si fourni
            if memory_data.content is not None:
                update_fields.append("content = CAST(:content AS JSONB)")
                params["content"] = json.dumps(memory_data.content)
                
            # Mettre à jour les métadonnées si fournies
            if memory_data.metadata is not None or memory_data.memory_type is not None or memory_data.event_type is not None or memory_data.role_id is not None or memory_data.expiration is not None:
                # Extraire les champs spécifiques de Memory des métadonnées existantes
                existing_metadata = existing_memory.metadata or {}
                
                # Récupérer les champs spécifiques qui pourraient ne pas être dans existing_memory.metadata
                existing_full_metadata = existing_metadata.copy()
                existing_full_metadata["memory_type"] = existing_memory.memory_type
                existing_full_metadata["event_type"] = existing_memory.event_type
                existing_full_metadata["role_id"] = existing_memory.role_id
                if existing_memory.expiration:
                    existing_full_metadata["expiration"] = existing_memory.expiration.isoformat()
                
                # Préparer les nouvelles métadonnées
                new_metadata = existing_full_metadata.copy()
                
                # Mettre à jour les métadonnées génériques
                if memory_data.metadata is not None:
                    new_metadata.update(memory_data.metadata)
                
                # Ajouter les champs spécifiques de Memory
                if memory_data.memory_type:
                    new_metadata["memory_type"] = memory_data.memory_type
                if memory_data.event_type:
                    new_metadata["event_type"] = memory_data.event_type
                if memory_data.role_id:
                    new_metadata["role_id"] = memory_data.role_id
                if memory_data.expiration:
                    new_metadata["expiration"] = memory_data.expiration.isoformat()
                
                update_fields.append("metadata = CAST(:metadata AS JSONB)")
                params["metadata"] = json.dumps(new_metadata)
                
            # Mettre à jour l'embedding si fourni
            if memory_data.embedding is not None:
                update_fields.append("embedding = :embedding")
                params["embedding"] = self._prepare_embedding(memory_data.embedding)
                
            # Si aucun champ à mettre à jour, retourner la mémoire existante
            if not update_fields:
                return existing_memory
                
            # Construire la requête SQL pour la mise à jour
            query = text(f"""
                UPDATE {TABLE_NAME}
                SET {', '.join(update_fields)}
                WHERE id = :memory_id
                RETURNING id, content, metadata, embedding, timestamp
            """)
            
            # Exécuter la requête
            conn = await self._get_connection()
            result = await conn.execute(query, params)
            row = result.mappings().first()
            
            if not row:
                return None
                
            # Créer l'objet Memory à partir du résultat
            metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"] or {}
            
            return Memory(
                id=row["id"],
                memory_type=metadata.get("memory_type", existing_memory.memory_type),
                event_type=metadata.get("event_type", existing_memory.event_type),
                role_id=metadata.get("role_id", existing_memory.role_id),
                content=json.loads(row["content"]) if isinstance(row["content"], str) else row["content"],
                metadata={k: v for k, v in metadata.items() if k not in ["memory_type", "event_type", "role_id", "expiration"]},
                timestamp=row["timestamp"],
                embedding=self._parse_embedding(row["embedding"]),
                expiration=metadata.get("expiration")
            )
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la mise à jour de la mémoire {memory_id}: {e}")
            raise
            
    async def delete(self, memory_id: uuid.UUID) -> bool:
        """Supprime une mémoire de la table events."""
        try:
            # Construire la requête SQL pour supprimer un événement
            query = text(f"""
                DELETE FROM {TABLE_NAME}
                WHERE id = :memory_id
                RETURNING id
            """)
            
            # Exécuter la requête
            conn = await self._get_connection()
            async with conn.begin():
                result = await conn.execute(query, {"memory_id": memory_id})
                
            # Vérifier si un enregistrement a été supprimé
            deleted = result.rowcount > 0
            
            return deleted
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la suppression de la mémoire {memory_id}: {e}")
            raise

    async def list_memories(
            self,
            limit: int = 10,
            skip: int = 0,
            offset: int = None,  # Alias pour skip, pour compatibilité avec les tests
            memory_type: str = None,
            event_type: str = None,
            role_id: int = None,
            session_id: str = None,
            metadata_filter: Optional[Dict[str, Any]] = None,
            ts_start: Optional[datetime.datetime] = None,
            ts_end: Optional[datetime.datetime] = None
        ) -> Tuple[List[Memory], int]:
            """
            Liste les mémoires (events) avec filtres optionnels

            ⚠️ DEPRECATED (Phase 3.2): This method is kept for backward compatibility with existing tests.
            New code should use EventRepository.search_vector(vector=None, metadata=..., ts_start=..., ts_end=...)
            which provides the same functionality with better performance and maintainability.

            Rationale:
            - EventRepository.search_vector() uses SQLAlchemy Core properly
            - Supports same filters: metadata, ts_start, ts_end, limit, offset
            - Returns EventModel (can be converted to Memory via _event_to_memory)
            - Already used by MemorySearchService.search_by_metadata() since Phase 3.2

            Args:
                limit: Nombre maximum d'enregistrements à retourner
                skip: Nombre d'enregistrements à sauter (pour pagination)
                offset: Alias pour skip (pour compatibilité avec les tests)
                memory_type: Filtre sur le type de mémoire
                event_type: Filtre sur le type d'événement
                role_id: Filtre sur l'ID de rôle
                session_id: Filtre sur l'ID de session (dans metadata)
                metadata_filter: Filtre sur les métadonnées (format dict)
                ts_start: Timestamp de début pour filtrer par date
                ts_end: Timestamp de fin pour filtrer par date

            Returns:
                Tuple contenant (liste des mémoires, nombre total de résultats)
            """
            try:
                # Convertir offset en skip s'il est fourni (pour compatibilité API)
                if offset is not None and skip == 0:
                    skip = offset
                    
                # Construire les requêtes en utilisant text() de SQLAlchemy pour le SQL brut
                base_query = f"""
                    SELECT id, content, metadata, embedding, timestamp
                    FROM {TABLE_NAME}
                    WHERE 1=1
                """
                
                count_query = f"""
                    SELECT COUNT(*) as total
                    FROM {TABLE_NAME}
                    WHERE 1=1
                """
                
                conditions = []
                params = {}
                
                # Fusionner les conditions spécifiques avec metadata_filter
                combined_metadata_filter = metadata_filter.copy() if metadata_filter else {}
                
                # Ajouter conditions de metadata spécifiques
                if memory_type:
                    combined_metadata_filter["memory_type"] = memory_type
                    
                if event_type:
                    combined_metadata_filter["event_type"] = event_type
                    
                if role_id:
                    combined_metadata_filter["role_id"] = role_id
                    
                if session_id:
                    combined_metadata_filter["session_id"] = session_id
                
                # Ajout des conditions pour le filtre de métadonnées si fourni
                if combined_metadata_filter:
                    for i, (key, value) in enumerate(combined_metadata_filter.items()):
                        conditions.append(f"metadata @> CAST(:meta_{i} AS JSONB)")
                        params[f"meta_{i}"] = json.dumps({key: value})
                
                # Ajout des conditions pour les timestamps
                if ts_start:
                    conditions.append("timestamp >= :ts_start")
                    params["ts_start"] = ts_start
                
                if ts_end:
                    conditions.append("timestamp <= :ts_end")
                    params["ts_end"] = ts_end
                
                # Ajouter les conditions aux requêtes
                if conditions:
                    condition_str = " AND " + " AND ".join(conditions)
                    base_query += condition_str
                    count_query += condition_str
                
                # Finaliser la requête principale avec tri et pagination
                final_query = base_query + " ORDER BY timestamp DESC LIMIT :limit OFFSET :skip"
                params["limit"] = limit
                params["skip"] = skip
                
                # Obtenir une connexion
                conn = await self._get_connection()
                
                # Exécuter les requêtes avec SQLAlchemy
                # Requête de comptage
                count_result = await conn.execute(text(count_query), params)
                count_row = count_result.fetchone()
                total_count = count_row[0] if count_row else 0
                
                # Requête principale
                result = await conn.execute(text(final_query), params)
                records = result.mappings().all()
                
                # Convertir les résultats en objets Memory
                memories = []
                for record in records:
                    # Extraire les données
                    raw_content = record["content"]
                    raw_metadata = record["metadata"]
                    
                    # Normaliser le contenu et les métadonnées
                    content = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
                    metadata = json.loads(raw_metadata) if isinstance(raw_metadata, str) else raw_metadata or {}
                    
                    # Extraire les champs spécifiques à Memory des métadonnées
                    memory_type_value = metadata.get("memory_type", "event")
                    event_type_value = metadata.get("event_type", "log")
                    role_id_value = metadata.get("role_id", 1)
                    expiration_value = metadata.get("expiration")
                    
                    # Retirer les champs spécifiques des métadonnées génériques
                    general_metadata = {k: v for k, v in metadata.items() 
                                       if k not in ["memory_type", "event_type", "role_id", "expiration"]}
                    
                    # Construire l'objet Memory
                    memory = Memory(
                        id=record["id"],
                        memory_type=memory_type_value,
                        event_type=event_type_value,
                        role_id=role_id_value,
                        content=content,
                        metadata=general_metadata,
                        timestamp=record["timestamp"],
                        embedding=self._parse_embedding(record["embedding"]),
                        expiration=expiration_value
                    )
                    memories.append(memory)
                
                return memories, total_count
                
            except Exception as e:
                self.logger.error(f"Error in list_memories: {str(e)}", exc_info=True)
                return [], 0
