import uuid
import asyncpg
from typing import Optional, Dict, Any, List
import datetime
from pydantic import BaseModel, Field
import json
import builtins

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
             
        return cls.model_validate(record_dict)

class EventRepository:
    """Couche d'accès aux données pour la table 'events'."""

    def __init__(self, pool: asyncpg.Pool):
        """Initialise le repository avec un pool de connexions asyncpg."""
        self.pool = pool
        # On pourrait aussi initialiser ici des requêtes SQL préparées si nécessaire

    async def add(self, event_data: EventCreate) -> EventModel:
        """Ajoute un nouvel événement à la base de données."""
        query = """
        INSERT INTO events (content, metadata, embedding, timestamp) 
        VALUES ($1, $2, $3, NOW()) 
        RETURNING id, timestamp, content, metadata, embedding
        """
        # Note: embedding ($3) doit être une liste de floats ou None.
        # asyncpg sait généralement convertir les listes Python en ARRAY postgresql.
        # Pour pgvector, il faut que le driver (ou une conversion explicite) le formate
        # correctement en chaîne si nécessaire, ex: '[1,2,3]'::vector.
        # Cependant, avec les versions récentes, asyncpg peut mieux gérer les types.
        # On passe la liste directement, ou None.
        
        # Convertir l'embedding en chaîne si présent, sinon None
        embedding_str = json.dumps(event_data.embedding) if event_data.embedding is not None else None
        
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                query, 
                json.dumps(event_data.content),
                json.dumps(event_data.metadata),
                embedding_str
            )
        
        if record:
            # Convertir l'enregistrement DB en dict AVANT de le passer
            record_dict = dict(record)
            return EventModel.from_db_record(record_dict)
        else:
            raise Exception("Failed to create event or retrieve returning values.")

    async def get_by_id(self, event_id: uuid.UUID) -> Optional[EventModel]:
        """Récupère un événement par son ID."""
        query = """SELECT id, timestamp, content, metadata, embedding 
                   FROM events WHERE id = $1"""
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(query, event_id)
        
        if record:
            # Convertir l'enregistrement DB en dict AVANT de le passer
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
        async with self.pool.acquire() as conn:
            # Convertir le dict Python en chaîne JSON pour l'opérateur ||
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
        async with self.pool.acquire() as conn:
            status = await conn.execute(query, event_id)
            # conn.execute retourne une chaîne comme 'DELETE 1' ou 'DELETE 0'
            # On vérifie si le nombre après l'opération est supérieur à 0
            deleted_count = int(status.split(" ")[-1])
            return deleted_count > 0

    # Ajouter d'autres méthodes si nécessaire (ex: search_semantic, list_events, etc.)

# Note: Il faudra également mettre en place la gestion du pool de connexions
# dans api/main.py (via le lifespan) et l'injection de dépendance
# pour que les routes puissent obtenir une instance de EventRepository. 