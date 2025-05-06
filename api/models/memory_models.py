import uuid
from pydantic import BaseModel, Field, field_validator
import datetime
from typing import Optional, Dict, Any, List, Union

# Modèles de données pour la mémoire


class MemoryBase(BaseModel):
    memory_type: str = Field(
        ..., description="Type de mémoire (episodic, semantic, etc)"
    )
    event_type: str = Field(..., description="Type d'événement (prompt, response, etc)")
    role_id: int = Field(..., description="ID du rôle")
    content: Dict[str, Any] = Field(..., description="Contenu de la mémoire")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Métadonnées")
    embedding: Optional[Union[List[float], str]] = Field(None, description="Vecteur d'embedding")
    
    @field_validator('embedding')
    @classmethod
    def validate_embedding(cls, v):
        """Valide et convertit l'embedding si nécessaire.
        Accepte une liste de floats ou une chaîne représentant un vecteur.
        """
        if v is None:
            return None
            
        # Si c'est déjà une liste, on la retourne
        if isinstance(v, list):
            return v
            
        # Si c'est une chaîne, on tente de la convertir en liste
        if isinstance(v, str):
            try:
                # Méthode simple: évaluer la chaîne comme liste Python
                # Cette méthode fonctionne pour les chaînes comme "[0.1, 0.2, 0.3]"
                import ast
                parsed = ast.literal_eval(v)
                if isinstance(parsed, list) and all(isinstance(x, (int, float)) for x in parsed):
                    return parsed
            except (ValueError, SyntaxError):
                pass
                
        # En cas d'échec, on retourne la valeur telle quelle
        # Elle sera reprise par la validation Pydantic normale
        return v


class MemoryCreate(MemoryBase):
    expiration: Optional[datetime.datetime] = Field(
        None, description="Date d'expiration"
    )
    timestamp: Optional[datetime.datetime] = Field(None, description="Date de création (optionnel)")


class Memory(MemoryBase):
    id: uuid.UUID = Field(..., description="ID unique")
    timestamp: datetime.datetime = Field(..., description="Date de création")
    expiration: Optional[datetime.datetime] = Field(
        None, description="Date d'expiration"
    )
    similarity_score: Optional[float] = Field(None, description="Score de similarité (pour les recherches)")


class MemoryUpdate(BaseModel):
    memory_type: Optional[str] = None
    event_type: Optional[str] = None
    role_id: Optional[int] = None
    content: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    expiration: Optional[datetime.datetime] = None
    embedding: Optional[Union[List[float], str]] = None
