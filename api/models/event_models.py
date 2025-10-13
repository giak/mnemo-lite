import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
import json
import ast  # Import ast for literal_eval
import structlog  # Import structlog

# Configuration du logger
logger = structlog.get_logger()


# Modèle pour la création d'un événement
class EventCreate(BaseModel):
    content: Dict[str, Any] = Field(..., description="Contenu JSON de l'événement.")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Métadonnées JSON."
    )
    embedding: Optional[List[float]] = Field(
        None, description="Vecteur embedding (optionnel)."
    )
    timestamp: Optional[datetime] = Field(
        None, description="Timestamp spécifique (optionnel, sinon NOW() est utilisé)."
    )


# Modèle pour la mise à jour d'un événement
class EventUpdate(BaseModel):
    content: Optional[Dict[str, Any]] = Field(None, description="Contenu JSON à mettre à jour.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Métadonnées JSON à mettre à jour.")
    embedding: Optional[List[float]] = Field(None, description="Vecteur embedding à mettre à jour.")


# Modèle Pydantic pour la réponse API (représente un événement)
class EventModel(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    content: Dict[str, Any]
    metadata: Dict[str, Any]
    embedding: Optional[List[float]]
    similarity_score: Optional[float] = None

    # Add Pydantic config for ORM mode / from_attributes
    model_config = ConfigDict(from_attributes=True)

    @staticmethod
    def _format_embedding_for_db(embedding: Optional[List[float]]) -> Optional[str]:
        """Formats a list of floats into a string suitable for pgvector/DB text insert."""
        if embedding is None:
            return None
        # Format as a string '[0.1, 0.2, ...]'
        # This format works for both raw INSERT and for pgvector type adapter
        return "[" + ",".join(map(str, embedding)) + "]"

    @classmethod
    def from_db_record(cls, record_data: Any) -> "EventModel":
        """Crée une instance EventModel à partir d'un dict, Row ou RowMapping."""
        
        try:
            # Attempt to convert the input to a dictionary directly.
            # This should work for dict, Row, and RowMapping.
            record_dict = dict(record_data)
        except (TypeError, ValueError) as e:
            # Log and raise error if conversion fails
            logger.error(
                "from_db_record failed to convert input data to dict", 
                error=str(e), 
                type=type(record_data).__name__, 
                data=record_data
            )
            raise TypeError(
                f"Expected dict-like or SQLAlchemy Row/RowMapping, got {type(record_data).__name__}"
            ) from e

        # Parser content et metadata si ce sont des chaînes JSON
        for field in ["content", "metadata"]:
            value = record_dict.get(field)
            if isinstance(value, str):
                try:
                    record_dict[field] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    logger.warn(
                        "Failed to parse JSON field from DB", field=field, value=value
                    )
                    record_dict[field] = {}  # Mettre un dict vide par défaut

        # Parser embedding si c'est une chaîne (représentation de liste)
        embedding_value = record_dict.get("embedding")
        if isinstance(embedding_value, str):
            try:
                # Utiliser ast.literal_eval pour parser la chaîne de liste Python en toute sécurité
                parsed_embedding = ast.literal_eval(embedding_value)
                if isinstance(parsed_embedding, list) and all(
                    isinstance(x, (int, float)) for x in parsed_embedding
                ):
                    record_dict["embedding"] = parsed_embedding
                else:
                    # Si ce n'est pas une liste de nombres, définir comme None ou lever une erreur
                    logger.warn(
                        "Parsed embedding string is not a list of numbers",
                        value=embedding_value,
                    )
                    record_dict["embedding"] = None
            except (ValueError, SyntaxError, TypeError):
                # En cas d'échec du parsing, logguer et définir comme None
                logger.warn(
                    "Failed to parse embedding string from DB", value=embedding_value
                )
                record_dict["embedding"] = None
        elif embedding_value is not None and not isinstance(embedding_value, list):
            # pgvector retourne parfois un ndarray (numpy array)
            # Essayons de le convertir en liste
            try:
                # Si c'est un objet avec .tolist() (comme numpy ndarray)
                if hasattr(embedding_value, 'tolist'):
                    record_dict["embedding"] = embedding_value.tolist()
                # Sinon tenter une conversion directe
                elif hasattr(embedding_value, '__iter__'):
                    record_dict["embedding"] = list(embedding_value)
                else:
                    logger.warn(
                        "Unexpected type for embedding from DB",
                        type=type(embedding_value).__name__,
                    )
                    record_dict["embedding"] = None
            except (TypeError, AttributeError) as e:
                logger.warn(
                    "Failed to convert embedding to list",
                    type=type(embedding_value).__name__,
                    error=str(e)
                )
                record_dict["embedding"] = None

        # Le score de similarité peut être absent
        if "similarity_score" not in record_dict:
            record_dict["similarity_score"] = None

        # Validation finale avec Pydantic
        try:
            model_instance = cls.model_validate(record_dict)
        except Exception as e:
            logger.error(
                "Pydantic validation failed for DB record",
                record=record_dict,
                error=str(e),
            )
            # Que faire en cas d'échec de validation ? Retourner un modèle par défaut ou relancer ?
            # Pour l'instant, relançons pour être explicite
            raise ValueError(f"Failed to validate data from DB: {e}") from e

        return model_instance
