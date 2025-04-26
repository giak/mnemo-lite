import uuid
import asyncpg
from typing import Optional, Dict, Any, List
import datetime
from pydantic import BaseModel, Field
import json
import builtins
import logging

logger = logging.getLogger(__name__) # Initialisation du logger

# Modèles Pydantic (Esquisse)
# Placeholder pour les modèles Pydantic (à définir/importer plus tard)
class EventModel:
    # Définir les champs correspondant à la table 'events'
    # ex: id: uuid.UUID, timestamp: datetime, content: Dict, metadata: Dict, embedding: Optional[List[float]]
    pass

class EventCreate(BaseModel):
    content: Dict[str, Any] = Field(..., description="Contenu JSON de l'événement.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées JSON.")
    embedding: Optional[List[float]] = Field(None, description="Vecteur embedding (optionnel).")

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
        
        # Gestion spécifique pour le type VECTOR
        embedding_val = record_dict.get('embedding')
        if isinstance(embedding_val, str):
            try:
                record_dict['embedding'] = json.loads(embedding_val)
            except (json.JSONDecodeError, TypeError):
                record_dict['embedding'] = None
        elif not isinstance(embedding_val, (list, type(None))):
             record_dict['embedding'] = None
             
        # Le score de similarité peut être absent (si pas de recherche vectorielle)
        if 'similarity_score' not in record_dict:
            record_dict['similarity_score'] = None 
            
        return cls.model_validate(record_dict)

class EventRepository:
    """Couche d'accès aux données pour la table 'events'."""

    def __init__(self, pool: asyncpg.Pool):
        """Initialise le repository avec un pool de connexions asyncpg."""
        self.pool = pool
        # self.conn = conn # Ancienne initialisation

    async def add(self, event_data: EventCreate) -> EventModel:
        """Ajoute un nouvel événement à la base de données."""
        query = """
        INSERT INTO events (content, metadata, embedding, timestamp) 
        VALUES ($1, $2, $3, NOW()) 
        RETURNING id, timestamp, content, metadata, embedding
        """
        # Pass the embedding list directly; asyncpg + pgvector codec handle conversion
        embedding_str = json.dumps(event_data.embedding) if event_data.embedding is not None else None
        
        # Utiliser le pool
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                query, 
                json.dumps(event_data.content),
                json.dumps(event_data.metadata),
                embedding_str # Pass the JSON string representation
            )
        
        if record:
            record_dict = dict(record)
            return EventModel.from_db_record(record_dict)
        else:
            raise Exception("Failed to create event or retrieve returning values.")

    async def get_by_id(self, event_id: uuid.UUID) -> Optional[EventModel]:
        """Récupère un événement par son ID."""
        query = """SELECT id, timestamp, content, metadata, embedding 
                   FROM events WHERE id = $1"""
        # Utiliser le pool
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(query, event_id)
        
        if record:
            record_dict = dict(record)
            return EventModel.from_db_record(record_dict)
        return None

    async def update_metadata(self, event_id: uuid.UUID, metadata_update: Dict[str, Any]) -> Optional[EventModel]:
        """Met à jour (fusionne) les métadonnées d'un événement existant.
        Retourne l'événement mis à jour ou None si l'ID n'existe pas.
        """
        query = """
        UPDATE events 
        SET metadata = metadata || $2::jsonb
        WHERE id = $1 
        RETURNING id, timestamp, content, metadata, embedding
        """
        # Utiliser le pool
        async with self.pool.acquire() as conn:
            metadata_update_json = json.dumps(metadata_update)
            record = await conn.fetchrow(
                query, 
                event_id,
                metadata_update_json
            )
        
        if record:
            record_dict = dict(record)
            return EventModel.from_db_record(record_dict)
        return None

    async def delete(self, event_id: uuid.UUID) -> bool:
        """Supprime un événement par son ID. Retourne True si supprimé, False sinon."""
        query = "DELETE FROM events WHERE id = $1"
        # Utiliser le pool
        async with self.pool.acquire() as conn:
            status = await conn.execute(query, event_id)
        deleted_count = int(status.split(" ")[-1])
        return deleted_count > 0

    async def filter_by_metadata(self, metadata_criteria: Dict[str, Any]) -> List[EventModel]:
        """Récupère une liste d'événements filtrés par critères de métadonnées.
        Utilise l'opérateur JSONB @> pour vérifier si metadata contient les critères.
        """
        query = """
        SELECT id, timestamp, content, metadata, embedding 
        FROM events 
        WHERE metadata @> $1::jsonb
        ORDER BY timestamp DESC -- Optionnel: trier par défaut
        """
        records = [] # Initialiser en cas d'erreur
        try:
            async with self.pool.acquire() as conn:
                criteria_json = json.dumps(metadata_criteria)
                logger.debug("Executing filter_by_metadata", query=query, criteria_json=criteria_json) # DEBUG LOG
                records = await conn.fetch(query, criteria_json)
                logger.debug("filter_by_metadata raw results count", count=len(records)) # DEBUG LOG
        except Exception as e:
            logger.error(f"filter_by_metadata error during query: {e!s}", exc_info=True)
            # Propager l'erreur ou retourner liste vide ? Pour l'instant, propage implicitement.
            # Potentiellement, on devrait gérer ça plus finement.

        return [EventModel.from_db_record(dict(record)) for record in records]

    async def search_vector(
        self, 
        vector: Optional[List[float]],
        top_k: int = 10, 
        metadata: Optional[Dict[str, Any]] = None,
        ts_start: Optional[datetime.datetime] = None,
        ts_end: Optional[datetime.datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[EventModel]:
        """Exécute une recherche hybride (vectorielle + métadonnées + temps).
        
        Utilise une stratégie de post-filtrage :
        1. Recherche des K voisins les plus proches (avec sur-échantillonnage).
        2. Filtre les résultats par métadonnées et timestamp.
        3. Applique la limite et l'offset finaux.
        """
        query_params = []
        where_clauses = []
        param_index = 1

        if vector:
            # --- Construction requête avec recherche vectorielle (KNN + filtres) ---
            # Convert vector list to string format '[...]' expected by pgvector
            vector_str_param = str(vector).replace(" ", "") # Simple conversion, remove spaces

            base_query = """
            SELECT id, timestamp, content, metadata, embedding, similarity_score
            FROM (
                SELECT id, timestamp, content, metadata, embedding, (embedding <=> $1::vector) as similarity_score
                FROM events
                ORDER BY embedding <=> $1::vector
                LIMIT $2 -- Sur-échantillonnage
            ) AS vector_results
            WHERE 1=1"""
            
            query_params.extend([vector_str_param, top_k * 5]) # Utiliser le string formaté
            param_index = 3 # Les params $1 et $2 sont utilisés par KNN
        else:
            # --- Construction requête SANS recherche vectorielle (Filtres + Tri) ---
            base_query = """
            SELECT id, timestamp, content, metadata, embedding, 0.0 as similarity_score 
            FROM events
            WHERE 1=1""" 
            # Pas de params $1, $2 ici

        # --- Ajout des filtres communs (metadata, timestamp) ---
        if metadata:
            where_clauses.append(f"metadata @> ${param_index}::jsonb")
            query_params.append(json.dumps(metadata))
            param_index += 1
            
        if ts_start:
            where_clauses.append(f"timestamp >= ${param_index}")
            query_params.append(ts_start)
            param_index += 1
        if ts_end:
            where_clauses.append(f"timestamp <= ${param_index}")
            query_params.append(ts_end)
            param_index += 1

        # Combiner les clauses WHERE
        if where_clauses:
            base_query += " AND " + " AND ".join(where_clauses)
            
        # --- Ajout ORDER BY, LIMIT, OFFSET finaux ---
        if not vector:
             # Trier par timestamp si pas de recherche vectorielle
             base_query += "\nORDER BY timestamp DESC" 
        # else: Le tri par similarité est implicite via la sous-requête si vector
        
        base_query += f"\nLIMIT ${param_index}"
        query_params.append(limit)
        param_index += 1
        
        base_query += f"\nOFFSET ${param_index}"
        query_params.append(offset)
        # param_index += 1 # Plus nécessaire après le dernier ajout

        # --- Exécution de la requête ---
        records = []
        try:
            async with self.pool.acquire() as conn:
                # Les paramètres sont déjà dans query_params, y compris le vecteur correctement formaté
                prepared_params = query_params
                                 
                # Debug log
                logging.debug(f"Executing search_vector query: {base_query}")
                logging.debug(f"With parameters: {prepared_params}") # Log params too
                
                records = await conn.fetch(base_query, *prepared_params)
                
                logger.debug("search_vector raw results count", count=len(records)) # DEBUG LOG
        except asyncpg.exceptions.UndefinedFunctionError as e:
            logger.error(f"pgvector UndefinedFunctionError: Is the pgvector extension enabled? Query: {base_query} Params: {prepared_params}", exc_info=True)
            raise RuntimeError("Database query failed due to potential missing pgvector extension or incorrect function call.") from e
        except Exception as e:
            # logger.error(f"search_vector error during query: {base_query} Params: {prepared_params}", error=str(e), exc_info=True)
            logger.exception(f"search_vector error during query: {base_query} Params: {prepared_params} Error: {e!s}") # Use logger.exception to include traceback and format error
            # Propager une erreur générique pour ne pas fuiter de détails
            raise RuntimeError("Database query failed unexpectedly.") from e

        # Conversion des résultats
        return [EventModel.from_db_record(dict(record)) for record in records]

# Note: Il faudra également mettre en place la gestion du pool de connexions
# dans api/main.py (via le lifespan) et l'injection de dépendance
# pour que les routes puissent obtenir une instance de EventRepository. 