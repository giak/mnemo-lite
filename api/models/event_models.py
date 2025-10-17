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
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None
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

        # Handle asyncpg UUID type
        if "id" in record_dict:
            id_value = record_dict["id"]
            # Check if it's asyncpg UUID type
            if hasattr(id_value, '__class__') and 'asyncpg' in str(id_value.__class__):
                record_dict["id"] = str(id_value)
            elif not isinstance(id_value, (str, uuid.UUID)):
                record_dict["id"] = str(id_value)

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
            elif value is None:
                # Set empty dict for None metadata to avoid validation error
                record_dict[field] = {}

        # Parser embedding si c'est une chaîne (représentation de liste)
        embedding_value = record_dict.get("embedding")
        if isinstance(embedding_value, str):
            try:
                # Handle PostgreSQL array format: [0.1,0.2,0.3,...]
                if embedding_value.startswith('[') and embedding_value.endswith(']'):
                    # Remove brackets and split by comma
                    embedding_str = embedding_value[1:-1]
                    if embedding_str:  # Non-empty array
                        parsed_embedding = [float(x.strip()) for x in embedding_str.split(',')]
                        record_dict["embedding"] = parsed_embedding
                    else:
                        record_dict["embedding"] = None
                else:
                    # Try ast.literal_eval as fallback
                    parsed_embedding = ast.literal_eval(embedding_value)
                    if isinstance(parsed_embedding, list) and all(
                        isinstance(x, (int, float)) for x in parsed_embedding
                    ):
                        record_dict["embedding"] = parsed_embedding
                    else:
                        logger.warn(
                            "Parsed embedding string is not a list of numbers",
                            value=embedding_value[:100],  # Log only first 100 chars
                        )
                        record_dict["embedding"] = None
            except (ValueError, SyntaxError, TypeError) as e:
                # En cas d'échec du parsing, logguer et définir comme None
                logger.warn(
                    "Failed to parse embedding string from DB",
                    value=embedding_value[:100] if embedding_value else None,
                    error=str(e)
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
