import uuid
import datetime
import json
from typing import List, Dict, Any, Optional, Tuple

# Imports SQLAlchemy nécessaires
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection
from sqlalchemy.sql import text, Select, ColumnElement, insert, select, update, delete
from sqlalchemy.sql.expression import literal_column
from sqlalchemy.sql.elements import False_ # Import spécifique pour la vérification
from sqlalchemy.engine import Result

# Importations liées à Pydantic pour la validation et la sérialisation
from pydantic import BaseModel, Field, field_validator

# Importation pour le logging
import logging

# Import RepositoryError from base
from .base import RepositoryError

# Configuration du logger
logging.basicConfig(level=logging.INFO) # Ou logging.DEBUG pour plus de détails

# --- Pydantic Models ---

class EventCreate(BaseModel):
    """Modèle Pydantic pour la création d'un événement."""
    content: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    embedding: Optional[List[float]] = None
    timestamp: Optional[datetime.datetime] = None

    @field_validator('timestamp', mode='before')
    @classmethod
    def set_default_timestamp(cls, v):
        """Définit le timestamp actuel si non fourni."""
        return v or datetime.datetime.now(datetime.timezone.utc)

    @field_validator('embedding', mode='before')
    @classmethod
    def validate_embedding_format(cls, v):
        """Valide que l'embedding est une liste de floats."""
        if v is not None:
            if not isinstance(v, list) or not all(isinstance(item, (float, int)) for item in v):
                raise ValueError("Embedding must be a list of floats or integers.")
        return v

class EventModel(EventCreate):
    """Modèle Pydantic représentant un événement complet (avec ID)."""
    id: uuid.UUID
    similarity_score: Optional[float] = None # Pour les résultats de recherche vectorielle

    class Config:
        from_attributes = True # Permet de créer le modèle depuis un objet avec attributs

    @classmethod
    def _format_embedding_for_db(cls, embedding: Optional[List[float]]) -> Optional[str]:
        """Convertit une liste de floats en chaîne pour pgvector."""
        if embedding is None:
            return None
        # Convertit en chaîne formatée [f1,f2,...] exigée par pgvector
        return '[' + ','.join(map(str, embedding)) + ']'

    @classmethod
    def _parse_embedding_from_db(cls, embedding_str: Optional[str]) -> Optional[List[float]]:
        """Convertit une chaîne pgvector en liste de floats."""
        if embedding_str is None:
            return None
        try:
            # Utilise json.loads pour parser la chaîne '[f1,f2,...]'
            return json.loads(embedding_str)
        except (json.JSONDecodeError, TypeError):
            # Gérer le cas où le format n'est pas correct ou ce n'est pas une chaîne
            logging.error(f"Could not parse embedding from DB: {embedding_str}")
            return None # Ou lever une exception si c'est un cas critique

    @classmethod
    def from_db_record(cls, record: Dict[str, Any]) -> 'EventModel':
        """Crée une instance EventModel depuis un enregistrement de DB (dict)."""
        return cls(
            id=record['id'],
            timestamp=record['timestamp'],
            content=json.loads(record['content']) if isinstance(record['content'], str) else record['content'],
            metadata=json.loads(record['metadata']) if isinstance(record['metadata'], str) else record['metadata'],
            embedding=cls._parse_embedding_from_db(record.get('embedding')),
            similarity_score=record.get('similarity_score') # Peut être None
        )


# --- Query Builder ---

class EventQueryBuilder:
    """Construit les requêtes SQL pour EventRepository en utilisant SQLAlchemy Core."""

    def _get_vector_dimensions(self) -> int:
        """Retourne la dimension attendue pour les vecteurs (à configurer)."""
        # TODO: Rendre configurable ou récupérer depuis une source externe
        return 1536 # Exemple: dimension pour text-embedding-ada-002

    def build_add_query(self, event_data: EventCreate) -> Tuple[ColumnElement, Dict[str, Any]]:
        """Construit la requête INSERT."""
        params = {
            "content": json.dumps(event_data.content),
            "metadata": json.dumps(event_data.metadata) if event_data.metadata else None,
            "embedding": EventModel._format_embedding_for_db(event_data.embedding),
            "timestamp": event_data.timestamp
        }
        query = insert(text("events")).values(
            content=text(":content"),
            metadata=text(":metadata"),
            embedding=text(":embedding"),
            timestamp=text(":timestamp")
        ).returning(
            literal_column("id"),
            literal_column("timestamp"),
            literal_column("content"),
            literal_column("metadata"),
            literal_column("embedding")
        )
        return query, params

    def build_get_by_id_query(self, event_id: uuid.UUID) -> Tuple[ColumnElement, Dict[str, Any]]:
        """Construit la requête SELECT par ID."""
        query = select(
            literal_column("id"),
            literal_column("timestamp"),
            literal_column("content"),
            literal_column("metadata"),
            literal_column("embedding")
        ).select_from(text("events")).where(literal_column("id") == text(":event_id"))
        params = {"event_id": event_id}
        return query, params

    def build_update_metadata_query(self, event_id: uuid.UUID, metadata_update: Dict[str, Any]) -> Tuple[ColumnElement, Dict[str, Any]]:
        """Construit la requête UPDATE pour fusionner les métadonnées."""
        query = update(text("events")).where(
            literal_column("id") == text(":event_id")
        ).values(
            # Utilise l'opérateur || de JSONB pour fusionner les objets
            metadata=literal_column("metadata").op('||')(text(":metadata_update::jsonb"))
        ).returning(
            literal_column("id"),
            literal_column("timestamp"),
            literal_column("content"),
            literal_column("metadata"),
            literal_column("embedding")
        )
        params = {"event_id": event_id, "metadata_update": json.dumps(metadata_update)}
        return query, params

    def build_delete_query(self, event_id: uuid.UUID) -> Tuple[ColumnElement, Dict[str, Any]]:
        """Construit la requête DELETE par ID."""
        query = delete(text("events")).where(literal_column("id") == text(":event_id"))
        params = {"event_id": event_id}
        return query, params

    def build_filter_by_metadata_query(self, metadata_criteria: Dict[str, Any]) -> Tuple[ColumnElement, Dict[str, Any]]:
        """Construit la requête SELECT filtrée par métadonnées."""
        query = select(
            literal_column("id"),
            literal_column("timestamp"),
            literal_column("content"),
            literal_column("metadata"),
            literal_column("embedding")
        ).select_from(
            text("events")
        ).where(
            # Utilise l'opérateur @> de JSONB pour vérifier si metadata contient les critères
            literal_column("metadata").op('@>')(text(":criteria::jsonb"))
        ).order_by(
            literal_column("timestamp").desc() # Tri par défaut
        )
        params = {"criteria": json.dumps(metadata_criteria)}
        return query, params

    def build_search_vector_query(
        self,
        vector: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ts_start: Optional[datetime.datetime] = None,
        ts_end: Optional[datetime.datetime] = None,
        limit: int = 10,
        offset: int = 0,
        distance_threshold: Optional[float] = 5.0 # Seuil de distance L2 par défaut (très large)
    ) -> Tuple[ColumnElement, Dict[str, Any]]:
        """
        Construit la requête SELECT pour la recherche vectorielle et/ou par filtres.
        Combine dynamiquement les filtres et le tri.
        """
        params: Dict[str, Any] = {}
        conditions = []

        # Sélection de base avec calcul de similarité (distance L2) si vecteur fourni
        select_columns = [
            literal_column("id"),
            literal_column("timestamp"),
            literal_column("content"),
            literal_column("metadata"),
            literal_column("embedding")
        ]
        if vector is not None:
            expected_dim = self._get_vector_dimensions()
            if len(vector) != expected_dim:
                raise ValueError(f"Invalid vector dimension: expected {expected_dim}, got {len(vector)}")
            select_columns.append(
                # '<->' est l'opérateur de distance L2 pour pgvector
                literal_column("embedding").op('<->')(text(":vec_query")).label("similarity_score")
            )
            params["vec_query"] = EventModel._format_embedding_for_db(vector)
            # Ajout de la condition de seuil si un vecteur et un seuil sont fournis
            if distance_threshold is not None:
                conditions.append(literal_column("embedding").op('<->')(text(":vec_query")) < text(":distance_threshold"))
                params["distance_threshold"] = distance_threshold
        else:
            # Inclure la colonne similarity_score avec une valeur nulle si pas de recherche vectorielle
             select_columns.append(literal_column("NULL").label("similarity_score"))


        query_base = select(*select_columns).select_from(text("events"))

        # Ajout des conditions de filtre
        if metadata is not None:
            conditions.append(literal_column("metadata").op('@>')(text(":md_filter::jsonb")))
            params["md_filter"] = json.dumps(metadata)
        if ts_start is not None:
            conditions.append(literal_column("timestamp") >= text(":ts_start"))
            params["ts_start"] = ts_start
        if ts_end is not None:
            conditions.append(literal_column("timestamp") <= text(":ts_end"))
            params["ts_end"] = ts_end

        # Construction de la clause WHERE
        if conditions:
            final_query = query_base.where(*conditions)
        else:
            # Si aucun critère n'est fourni (ni vecteur, ni metadata, ni temps),
            # on retourne une requête qui ne sélectionne rien pour éviter de scanner toute la table.
            # Ou on pourrait choisir de lever une erreur.
            final_query = query_base.where(False_())
            params = {} # Aucun paramètre n'est nécessaire pour `WHERE false`

        # Tri: par similarité si vecteur fourni, sinon par timestamp descendant
        if vector is not None and "vec_query" in params:
             final_query = final_query.order_by(literal_column("embedding").op('<->')(text(":vec_query")))
        elif conditions: # Tri par timestamp seulement si d'autres filtres sont actifs
             final_query = final_query.order_by(literal_column("timestamp").desc())
        # Pas de ORDER BY si aucun critère n'est spécifié (la requête sera `WHERE false` de toute façon)


        # Ajout de la limite et de l'offset (uniquement si la requête n'est pas vide)
        if conditions or vector is not None: # Appliquer seulement si des critères existent
             final_query = final_query.limit(text(":lim")).offset(text(":off"))
             params["lim"] = limit
             params["off"] = offset

        return final_query, params


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
            async with connection.begin() if is_mutation else connection.begin_nested():
                try:
                    result = await connection.execute(query, params)
                    if is_mutation:
                         await connection.commit() # Commit explicite pour INSERT/UPDATE/DELETE
                    return result
                except Exception as e:
                    self.logger.error(f"Database query execution failed: {e}", exc_info=True)
                    if is_mutation:
                        await connection.rollback() # Rollback en cas d'erreur de mutation
                    raise # Relancer l'exception pour gestion supérieure


    async def add(self, event_data: EventCreate) -> EventModel:
        """Ajoute un nouvel événement (utilise EventQueryBuilder)."""
        try:
            query, params = self.query_builder.build_add_query(event_data)
            result = await self._execute_query(query, params, is_mutation=True)
            added_record = result.mappings().first()
            if added_record:
                 return EventModel.from_db_record(added_record)
            else:
                 # Ce cas ne devrait pas arriver si RETURNING est utilisé et l'insertion réussit
                 raise RuntimeError("INSERT query did not return the added record.")
        except Exception as e:
            self.logger.error(f"Failed to add event: {e}", exc_info=True)
            # TODO: Gérer l'exception plus spécifiquement (ex: contrainte unique)
            raise


    async def get_by_id(self, event_id: uuid.UUID) -> Optional[EventModel]:
        """Récupère un événement par ID (utilise EventQueryBuilder)."""
        try:
            query, params = self.query_builder.build_get_by_id_query(event_id)
            result = await self._execute_query(query, params)
            record = result.mappings().first()
            return EventModel.from_db_record(record) if record else None
        except Exception as e:
            self.logger.error(f"Failed to get event by ID {event_id}: {e}", exc_info=True)
            raise


    async def update_metadata(self, event_id: uuid.UUID, metadata_update: Dict[str, Any]) -> Optional[EventModel]:
        """Met à jour (fusionne) les métadonnées d'un événement (utilise EventQueryBuilder)."""
        try:
            query, params = self.query_builder.build_update_metadata_query(event_id, metadata_update)
            result = await self._execute_query(query, params, is_mutation=True)
            updated_record = result.mappings().first()
            if updated_record:
                return EventModel.from_db_record(updated_record)
            else:
                # L'événement n'a pas été trouvé pour la mise à jour
                return None
        except Exception as e:
             self.logger.error(f"Failed to update metadata for event {event_id}: {e}", exc_info=True)
             raise


    async def delete(self, event_id: uuid.UUID) -> bool:
        """Supprime un événement par ID (utilise EventQueryBuilder)."""
        try:
            query, params = self.query_builder.build_delete_query(event_id)
            result = await self._execute_query(query, params, is_mutation=True)
            # rowcount indique si une ligne a été affectée (supprimée)
            return result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Failed to delete event {event_id}: {e}", exc_info=True)
            raise


    async def filter_by_metadata(self, metadata_criteria: Dict[str, Any]) -> List[EventModel]:
        """Filtre les événements par critères de métadonnées (utilise EventQueryBuilder)."""
        try:
            query, params = self.query_builder.build_filter_by_metadata_query(metadata_criteria)
            result = await self._execute_query(query, params)
            records = result.mappings().all()
            self.logger.debug(f"filter_by_metadata raw results count={len(records)}")
            return [EventModel.from_db_record(record) for record in records]
        except Exception as e:
            self.logger.error(f"Failed to filter events by metadata: {e}", exc_info=True)
            raise


    async def search_vector(
        self,
        vector: Optional[List[float]] = None,
        top_k: int = 10, # Note: top_k n'est pas utilisé directement par le builder mais gardé pour compatibilité?
        metadata: Optional[Dict[str, Any]] = None,
        ts_start: Optional[datetime.datetime] = None,
        ts_end: Optional[datetime.datetime] = None,
        limit: int = 10,
        offset: int = 0,
        distance_threshold: Optional[float] = 5.0 # Ajout du seuil ici aussi
    ) -> List[EventModel]:
        """
        Recherche des événements (utilise EventQueryBuilder).
        Combine la recherche vectorielle et/ou par filtres (metadata, timestamp).
        """
        # Construire la requête et les paramètres en utilisant le builder
        try:
             query, params = self.query_builder.build_search_vector_query(
                  vector=vector,
                  metadata=metadata,
                  ts_start=ts_start,
                  ts_end=ts_end,
                  limit=limit, # Passer le limit/offset au builder
                  offset=offset,
                  distance_threshold=distance_threshold # Passer le seuil au builder
             )
             # Si le builder retourne une requête vide (aucun critère)
             # La vérification utilise l'objet False_ importé
             if isinstance(query.whereclause, False_):
                 self.logger.warning("search_vector called without any valid search criteria. Returning empty list.")
                 return []
        except ValueError as ve: # Capturer l'erreur de dimension du vecteur du builder
             self.logger.error(f"Error building search query: {ve}")
             return [] # Retourner vide si la dimension est invalide
        except Exception as build_e: # Autres erreurs de construction
             self.logger.error(f"Error building search query: {build_e}", exc_info=True)
             raise # Relancer les erreurs inattendues de construction

        # Exécuter la requête construite
        try:
             result = await self._execute_query(query, params)
             records = result.mappings().all()
             self.logger.debug(f"search_vector raw results count={len(records)}")
             # Mapper les résultats en EventModel
             return [EventModel.from_db_record(record) for record in records]
        except Exception as exec_e:
             self.logger.error(f"Failed to execute search query: {exec_e}", exc_info=True)
             raise

# --- Fin du fichier ---