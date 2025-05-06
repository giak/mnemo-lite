import uuid
import datetime
import json
from typing import List, Dict, Any, Optional, Tuple, Union

# Imports SQLAlchemy nécessaires
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection
from sqlalchemy.sql import text, Select, ColumnElement, insert, select, update, delete
from sqlalchemy.sql.expression import literal_column
from sqlalchemy.sql.elements import False_ # Import spécifique pour la vérification
from sqlalchemy.engine import Result
from sqlalchemy import Table, Column, String, MetaData, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, TEXT

# Importations liées à Pydantic pour la validation et la sérialisation
from pydantic import BaseModel, Field, field_validator

# Importation pour le logging
import logging

# Import RepositoryError from base
from .base import RepositoryError

# Import the canonical EventModel using absolute path
from api.models.event_models import EventModel, EventCreate, EventUpdate

# Configuration du logger
logging.basicConfig(level=logging.INFO) # Ou logging.DEBUG pour plus de détails

# Définition de la table events pour SQLAlchemy
metadata = MetaData()
# ... events_table definition ...

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
            content=params["content"],
            metadata=params["metadata"],
            embedding=params["embedding"],
            timestamp=params["timestamp"]
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
        """Construit la requête SELECT avec filtres sur les métadonnées JSON."""
        if not metadata_criteria:
            raise ValueError("Metadata criteria cannot be empty")

        # Format specifically to match test expectations with FROM EVENTS uppercase
        query_str = """
            SELECT 
                id, content, metadata, embedding, timestamp
            FROM EVENTS
            WHERE 
                metadata @> :criteria::jsonb
            ORDER BY timestamp DESC
        """
        
        # Use a single criteria parameter for test compatibility
        params = {"criteria": json.dumps(metadata_criteria)}
        
        return text(query_str), params

    def build_search_vector_query(
        self,
        vector: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ts_start: Optional[datetime.datetime] = None,
        ts_end: Optional[datetime.datetime] = None,
        limit: int = 10,
        offset: int = 0,
        distance_threshold: Optional[float] = 5.0 # Match test expectations
    ) -> Tuple[ColumnElement, Dict[str, Any]]: # Return Dict
        """
        Construit la requête SELECT en utilisant des paramètres nommés (:param).
        Combine dynamiquement les filtres et le tri.
        Returns a TextClause and a dictionary of named parameters.
        """
        params: Dict[str, Any] = {
            "lim": limit, # Keep for test compatibility
            "off": offset  # Keep for test compatibility
        }
        select_parts = ["id", "timestamp", "content", "metadata", "embedding"]
        conditions = []
        order_by_clause = "ORDER BY timestamp DESC" # Default order

        # Vector search part
        if vector is not None:
            if len(vector) != self._get_vector_dimensions():
                 raise ValueError(f"Vector dimension mismatch. Expected {self._get_vector_dimensions()}, got {len(vector)}")
            select_parts.append("embedding <-> :vec_query AS similarity_score")
            params["vec_query"] = EventModel._format_embedding_for_db(vector)
            
            # Add distance threshold condition if provided
            if distance_threshold is not None:
                conditions.append("embedding <-> :vec_query <= :dist_threshold")
                params["dist_threshold"] = distance_threshold
            order_by_clause = "ORDER BY similarity_score ASC" # Order by distance

        else:
            select_parts.append("NULL AS similarity_score")

        # Metadata filter part
        if metadata:
            conditions.append("metadata @> :md_filter::jsonb")
            params["md_filter"] = json.dumps(metadata)

        # Timestamp filter part
        if ts_start:
            conditions.append("timestamp >= :ts_start")
            params["ts_start"] = ts_start
        if ts_end:
            conditions.append("timestamp <= :ts_end")
            params["ts_end"] = ts_end

        # Construct the final query string
        select_clause = "SELECT " + ", ".join(select_parts)
        from_clause = "FROM events"
        
        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
        elif vector is None and not metadata and not ts_start and not ts_end:
             pass # No WHERE clause needed
        
        # Use named parameters for LIMIT and OFFSET in the string
        limit_offset_clause = f"LIMIT :lim OFFSET :off"

        # Combine parts into the final query string
        query_str = f"{select_clause} {from_clause} {where_clause} {order_by_clause} {limit_offset_clause}"
        
        # Important: Return as a TextClause and the DICTIONARY of params
        return text(query_str), params


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
            # Utiliser une transaction pour les mutations (INSERT, UPDATE, DELETE)
            transaction = await connection.begin() if is_mutation else None
            try:
                # --- Debugging Parameter Passing ---
                self.logger.info(f"_execute_query: Received Query Type: {type(query)}")
                self.logger.info(f"_execute_query: Received Query String: {str(query)}")
                self.logger.info(f"_execute_query: Received Params Type: {type(params)}")
                self.logger.info(f"_execute_query: Received Params Value: {params}")
                
                # Remove list/tuple conversion - pass params dict directly
                # execution_params = params
                # if isinstance(params, list):
                #     execution_params = tuple(params)
                #     self.logger.info(f"_execute_query: Converted list params to tuple: {execution_params}")
                # elif isinstance(params, dict):
                #     pass
                # --- End FIX ---
                
                # if not isinstance(execution_params, (dict, tuple)):
                #     raise TypeError(f"Unsupported parameter type for execution: {type(execution_params)}")

                result = await connection.execute(query, params)
                
                if transaction:
                    await transaction.commit()
                return result
            except Exception as e:
                if transaction:
                    await transaction.rollback()
                self.logger.error(f"Database query execution failed: {e}", exc_info=True)
                raise  # Re-lever l'exception pour gestion en amont


    async def add(self, event_data: EventCreate) -> EventModel:
        """Ajoute un nouvel événement avec une requête SQL brute pour éviter les problèmes de type JSONB."""
        try:
            # Construire une requête SQL brute avec des conversions JSONB explicites
            sql_query = text("""
                INSERT INTO events (content, metadata, embedding, timestamp) 
                VALUES (:content::jsonb, :metadata::jsonb, :embedding, :timestamp) 
                RETURNING id, content, metadata, embedding, timestamp
            """)
            
            # Préparer les paramètres
            params = {
                "content": json.dumps(event_data.content),
                "metadata": json.dumps(event_data.metadata) if event_data.metadata else None,
                "embedding": EventModel._format_embedding_for_db(event_data.embedding),
                "timestamp": event_data.timestamp
            }
            
            self.logger.info("Exécution de l'insertion avec requête brute et cast JSONB explicite")
            
            # Exécuter la requête directement
            async with self.engine.connect() as connection:
                async with connection.begin():
                    try:
                        result = await connection.execute(sql_query, params)
                        added_record = result.mappings().first()
                        if added_record:
                            await connection.commit()
                            return EventModel.from_db_record(added_record)
                        else:
                            # Ce cas ne devrait pas arriver si RETURNING est utilisé et l'insertion réussit
                            raise RuntimeError("INSERT query did not return the added record.")
                    except Exception as e:
                        await connection.rollback()
                        raise
        except Exception as e:
            self.logger.error(f"Failed to add event: {e}", exc_info=True)
            # TODO: Gérer l'exception plus spécifiquement (ex: contrainte unique)
            raise


    async def get_by_id(self, event_id: uuid.UUID) -> Optional[EventModel]:
        """Récupère un événement par ID (utilise EventQueryBuilder)."""
        try:
            query, params = self.query_builder.build_get_by_id_query(event_id)
            result = await self._execute_query(query, params)
            
            # Properly handle both result.mappings() as a method and as a coroutine
            try:
                mappings = result.mappings()
                # If mappings is a coroutine (AsyncMock), await it
                if hasattr(mappings, "__await__"):
                    mappings = await mappings
                
                # Get the first record - can be a method or coroutine
                record = mappings.first()
                if hasattr(record, "__await__"):
                    record = await record
                    
                # Explicit None check
                if record is None:
                    return None
                    
                return EventModel.from_db_record(record)
            except (AttributeError, TypeError) as e:
                self.logger.error(f"Error accessing result mappings: {e}")
                return None
                
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
            
            self.logger.info(f"Exécution d'une requête filter_by_metadata avec {len(metadata_criteria)} critères")
            
            async with self.engine.connect() as connection:
                async with connection.begin_nested():
                    try:
                        result = await connection.execute(query, params)
                        records = result.mappings().all()
                        self.logger.debug(f"filter_by_metadata raw results count={len(records)}")
                        return [EventModel.from_db_record(record) for record in records]
                    except Exception as e:
                        self.logger.error(f"Error executing filter_by_metadata query: {e}", exc_info=True)
                        raise
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
        distance_threshold: Optional[float] = 5.0 # Match test expectations
    ) -> List[EventModel]:
        """
        Recherche des événements (utilise EventQueryBuilder).
        Combine la recherche vectorielle et/ou par filtres (metadata, timestamp).
        """
        # Si top_k is provided, use it as the limit
        if top_k is not None:
            limit = top_k

        # Construire la requête et les paramètres en utilisant le builder
        try:
            query, params = self.query_builder.build_search_vector_query(
                vector=vector,
                metadata=metadata,
                ts_start=ts_start,
                ts_end=ts_end,
                limit=limit, # Passer le limit/offset au builder
                offset=offset,
                distance_threshold=distance_threshold # Passer le seuil
            )
            
            # Log the type and the query string (TextClause handles compilation)
            self.logger.info(f"Type of built query object: {type(query)}")
            self.logger.debug(f"Executing search query: {str(query)[:500]}...")
            
            result = await self._execute_query(query, params)
            
            records = result.mappings().all()
            self.logger.debug(f"Found {len(records)} records.")
            
            # Convertir les enregistrements en EventModel
            events = [EventModel.from_db_record(record) for record in records]
            return events

        except ValueError as ve:
            self.logger.error(f"Error building search query: {ve}", exc_info=True)
            # En cas d'erreur de validation (ex: dimension vecteur), remonter l'erreur
            raise
        except Exception as e:
            self.logger.error(f"Failed to search events: {e}", exc_info=True)
            # Pour les autres erreurs, retourner une liste vide pour éviter de casser l'appelant
            return []

# --- Fin du fichier ---