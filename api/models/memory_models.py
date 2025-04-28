import uuid
from pydantic import BaseModel, Field
import datetime
from typing import Optional, Dict, Any

# Modèles de données pour la mémoire

class MemoryBase(BaseModel):
    memory_type: str = Field(..., description="Type de mémoire (episodic, semantic, etc)")
    event_type: str = Field(..., description="Type d'événement (prompt, response, etc)")
    role_id: int = Field(..., description="ID du rôle")
    content: Dict[str, Any] = Field(..., description="Contenu de la mémoire")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Métadonnées")


class MemoryCreate(MemoryBase):
    expiration: Optional[datetime.datetime] = Field(None, description="Date d'expiration")


class Memory(MemoryBase):
    id: uuid.UUID = Field(..., description="ID unique")
    timestamp: datetime.datetime = Field(..., description="Date de création")
    expiration: Optional[datetime.datetime] = Field(None, description="Date d'expiration")


class MemoryUpdate(BaseModel):
    memory_type: Optional[str] = None
    event_type: Optional[str] = None
    role_id: Optional[int] = None
    content: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    expiration: Optional[datetime.datetime] = None 