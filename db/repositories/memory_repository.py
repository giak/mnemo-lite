import uuid
import json
import datetime
from typing import List, Dict, Any, Optional, Tuple, Union

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.sql import text
from sqlalchemy.engine import Result

# Import models
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
            # Les métadonnées contiennent les champs spécifiques, mais nous les extrayons
            # également séparément pour les attributs directs de l'objet Memory
            metadata_from_db = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"] or {}
            
            # Extraire les champs spécifiques avec les valeurs par défaut attendues par les tests
            memory_type = metadata_from_db.get("memory_type", "event")    # Valeur par défaut "event"
            event_type = metadata_from_db.get("event_type", "log")        # Valeur par défaut "log"
            role_id = metadata_from_db.get("role_id", 1)                  # Valeur par défaut 1
            
            # Traiter l'expiration qui peut être une chaîne ou None
            expiration_str = metadata_from_db.get("expiration")
            expiration = None
            if expiration_str:
                try:
                    if isinstance(expiration_str, str):
                        expiration = datetime.datetime.fromisoformat(expiration_str)
                except (ValueError, TypeError):
                    self.logger.warning(f"Impossible de parser l'expiration: {expiration_str}")
            
            # Pour les tests, nous conservons les métadonnées telles qu'elles sont dans la BD,
            # y compris les champs spécifiques
            metadata_for_memory = metadata_from_db
            
            memory = Memory(
                id=row["id"],
                memory_type=memory_type,
                event_type=event_type,
                role_id=role_id,
                content=json.loads(row["content"]) if isinstance(row["content"], str) else row["content"],
                metadata=metadata_for_memory,  # Métadonnées incluant les champs spécifiques
                timestamp=row["timestamp"],
                embedding=self._parse_embedding(row["embedding"]),
                expiration=expiration
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
            # Pour la BD, on stocke tout dans metadata
            metadata_for_db = memory_data.metadata.copy() if memory_data.metadata else {}
            metadata_for_db["memory_type"] = memory_data.memory_type
            metadata_for_db["event_type"] = memory_data.event_type
            metadata_for_db["role_id"] = memory_data.role_id
            if memory_data.expiration:
                metadata_for_db["expiration"] = memory_data.expiration.isoformat()
                
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
                "metadata": json.dumps(metadata_for_db),
                "embedding": self._prepare_embedding(memory_data.embedding),
                "timestamp": memory_data.timestamp or datetime.datetime.now(datetime.timezone.utc)
            }
            
            # Exécuter la requête
            conn = await self._get_connection()
            async with conn.begin():
                result = await conn.execute(query, params)
                row = result.mappings().first()
            
            # Pour l'objet Memory retourné, les tests s'attendent à ce que metadata
            # contienne également les champs spécifiques. Nous devons donc retourner
            # un objet avec la même structure que ce qui est stocké dans la BD.
            # C'est différent de notre conception initiale, mais requis pour les tests.
            metadata_for_memory = metadata_for_db.copy()
            
            return Memory(
                id=row["id"],
                memory_type=memory_data.memory_type,
                event_type=memory_data.event_type,
                role_id=memory_data.role_id,
                content=json.loads(row["content"]) if isinstance(row["content"], str) else row["content"],
                metadata=metadata_for_memory,
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
            self.logger.info(f"Début update pour memory_id={memory_id}, memory_data={memory_data}")
            
            # Récupérer d'abord la mémoire existante
            existing_memory = await self.get_by_id(memory_id)
            if not existing_memory:
                self.logger.warning(f"Mémoire {memory_id} non trouvée pour mise à jour")
                return None
            
            self.logger.info(f"Mémoire existante trouvée: id={existing_memory.id}, memory_type={existing_memory.memory_type}")
                
            # Préparer les champs à mettre à jour
            update_fields = []
            params = {"memory_id": memory_id}
            
            # Récupérer les métadonnées et le contenu existants de la BD pour fusion
            conn = await self._get_connection()
            metadata_query = text(f"""
                SELECT metadata, content FROM {TABLE_NAME} WHERE id = :memory_id
            """)
            result = await conn.execute(metadata_query, {"memory_id": memory_id})
            row = result.mappings().first()
            
            if not row:
                self.logger.warning(f"Aucune donnée trouvée pour id={memory_id} lors de la récupération des métadonnées")
                return None
                
            # Extraire et traiter les métadonnées existantes
            db_metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"] or {}
            self.logger.info(f"Métadonnées existantes dans DB: {db_metadata}")
            
            # Récupérer le contenu existant pour fusion éventuelle
            existing_content = json.loads(row["content"]) if isinstance(row["content"], str) else row["content"] or {}
            
            # --- GESTION DES MÉTADONNÉES SPÉCIFIQUES ---
            
            # Mettre à jour les champs spécifiques s'ils sont fournis
            if memory_data.memory_type is not None:
                self.logger.info(f"Mise à jour du memory_type: {memory_data.memory_type}")
                db_metadata["memory_type"] = memory_data.memory_type
            if memory_data.event_type is not None:
                self.logger.info(f"Mise à jour du event_type: {memory_data.event_type}")
                db_metadata["event_type"] = memory_data.event_type
            if memory_data.role_id is not None:
                self.logger.info(f"Mise à jour du role_id: {memory_data.role_id}")
                db_metadata["role_id"] = memory_data.role_id
                
            # Gestion explicite de l'expiration
            # Modifier seulement si 'expiration' est explicitement fourni dans les données de mise à jour
            if 'expiration' in memory_data.model_fields_set:
                self.logger.info(f"Le champ expiration a été explicitement fourni: {memory_data.expiration}")
                db_metadata["expiration"] = memory_data.expiration.isoformat() if memory_data.expiration else None

            # --- GESTION DES MÉTADONNÉES GÉNÉRIQUES (CHAMP metadata) ---
            if memory_data.metadata is not None:
                self.logger.info(f"Mise à jour des métadonnées génériques: {memory_data.metadata}")
                # Fusionner les métadonnées existantes avec les nouvelles
                # Les nouvelles valeurs écrasent les anciennes en cas de conflit
                for key, value in memory_data.metadata.items():
                    db_metadata[key] = value

            # Ajouter les métadonnées au champ de mise à jour et aux paramètres
            update_fields.append("metadata = CAST(:metadata AS JSONB)")
            params["metadata"] = json.dumps(db_metadata)
            self.logger.info(f"Métadonnées après fusion: {db_metadata}")

            # --- GESTION DU CONTENU ---
            if memory_data.content is not None:
                self.logger.info(f"Mise à jour du content: {memory_data.content}")
                current_content = existing_content # Utiliser le contenu déjà récupéré
                
                # Logique de fusion pour le contenu (si nécessaire)
                # Exemple simple: écraser le contenu existant.
                # Pour une fusion plus complexe, adapter la logique ici.
                # Par exemple, si le contenu est un dictionnaire:
                # if isinstance(current_content, dict) and isinstance(memory_data.content, dict):
                #     current_content.update(memory_data.content)
                #     final_content = current_content
                # else:
                #     final_content = memory_data.content # Écraser si pas de fusion de dict
                final_content = memory_data.content # Actuellement, on écrase

                update_fields.append("content = CAST(:content AS JSONB)")
                params["content"] = json.dumps(final_content)
                self.logger.info(f"Contenu après mise à jour: {final_content}")

            # --- GESTION DE L'EMBEDDING ---
            if memory_data.embedding is not None:
                self.logger.info(f"Mise à jour de embedding: {memory_data.embedding}")
                update_fields.append("embedding = :embedding")
                params["embedding"] = self._prepare_embedding(memory_data.embedding)

            if not update_fields:
                self.logger.info("Aucun champ à mettre à jour, retour de la mémoire existante.")
                # Retourner la mémoire existante telle quelle car aucun champ n'a été modifié
                # Note: les tests s'attendent à ce que les métadonnées incluent les champs spécifiques
                # Il faut donc s'assurer que existing_memory a la bonne structure de métadonnées.
                
                # Reconstruire l'objet Memory avec les métadonnées de la BD
                # pour s'assurer qu'il est conforme aux attentes des tests.
                metadata_for_return = db_metadata.copy()

                return Memory(
                    id=existing_memory.id,
                    memory_type=metadata_for_return.get("memory_type", existing_memory.memory_type),
                    event_type=metadata_for_return.get("event_type", existing_memory.event_type),
                    role_id=metadata_for_return.get("role_id", existing_memory.role_id),
                    content=existing_content, # Utiliser le contenu récupéré et potentiellement fusionné
                    metadata=metadata_for_return,
                    timestamp=existing_memory.timestamp, # Le timestamp n'est pas dans params s'il n'est pas mis à jour
                    embedding=existing_memory.embedding, # Idem pour l'embedding
                    expiration=datetime.datetime.fromisoformat(metadata_for_return["expiration"]) if metadata_for_return.get("expiration") else None
                )

            # Construire la requête SQL de mise à jour
            set_clause = ", ".join(update_fields)
            query = text(f"""
                UPDATE {TABLE_NAME}
                SET {set_clause}
                WHERE id = :memory_id
                RETURNING id, content, metadata, embedding, timestamp
            """)
            self.logger.info(f"Requête de mise à jour: {query}")
            self.logger.info(f"Paramètres de mise à jour: {params}")

            # Exécuter la requête
            result = await conn.execute(query, params)
            updated_row = result.mappings().first()

            if not updated_row:
                self.logger.warning(f"La mise à jour pour {memory_id} n'a retourné aucune ligne.")
                return None # Ou lever une exception si c'est inattendu

            self.logger.info(f"Ligne mise à jour: {updated_row}")
            
            # Retourner l'objet Memory mis à jour
            # Les métadonnées retournées par la BD sont déjà fusionnées.
            updated_db_metadata = json.loads(updated_row["metadata"]) if isinstance(updated_row["metadata"], str) else updated_row["metadata"] or {}
            
            # S'assurer que l'expiration est correctement parsée pour l'objet Memory
            updated_expiration_str = updated_db_metadata.get("expiration")
            updated_expiration = None
            if updated_expiration_str:
                try:
                    if isinstance(updated_expiration_str, str):
                        updated_expiration = datetime.datetime.fromisoformat(updated_expiration_str)
                except (ValueError, TypeError):
                    self.logger.warning(f"Impossible de parser l'expiration de la ligne mise à jour: {updated_expiration_str}")

            return Memory(
                id=updated_row["id"],
                memory_type=updated_db_metadata.get("memory_type"), # Extraire de metadata
                event_type=updated_db_metadata.get("event_type"), # Extraire de metadata
                role_id=updated_db_metadata.get("role_id"),       # Extraire de metadata
                content=json.loads(updated_row["content"]) if isinstance(updated_row["content"], str) else updated_row["content"],
                metadata=updated_db_metadata, # Les métadonnées de la BD sont déjà correctes
                timestamp=updated_row["timestamp"],
                embedding=self._parse_embedding(updated_row["embedding"]),
                expiration=updated_expiration 
            )

        except Exception as e:
            self.logger.error(f"Erreur lors de la mise à jour de la mémoire {memory_id}: {e}")
            # Log supplémentaire pour le débogage des tests
            if memory_data:
                 self.logger.error(f"Données de mise à jour (MemoryUpdate): memory_type={memory_data.memory_type}, event_type={memory_data.event_type}, role_id={memory_data.role_id}, expiration={memory_data.expiration}, metadata={memory_data.metadata}, content={memory_data.content}, embedding_provided={memory_data.embedding is not None}")
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