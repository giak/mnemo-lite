"""
Modèles de données pour les embeddings.
Définit les schémas Pydantic pour les requêtes et réponses d'embedding.
"""

from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Union, Any

class EmbeddingRequest(BaseModel):
    """
    Modèle de requête pour la génération d'embedding.
    """
    text: str = Field(..., description="Texte à transformer en vecteur d'embedding")
    
    @model_validator(mode='after')
    def validate_text_not_empty(self) -> 'EmbeddingRequest':
        """Valide que le texte n'est pas vide."""
        if not self.text or not self.text.strip():
            raise ValueError("Le texte ne peut pas être vide")
        return self
        
class EmbeddingResponse(BaseModel):
    """
    Modèle de réponse pour un embedding généré.
    """
    embedding: List[float] = Field(..., description="Vecteur d'embedding généré")
    dimension: int = Field(..., description="Dimension du vecteur d'embedding")
    model: str = Field(..., description="Modèle utilisé pour générer l'embedding")
    
class SimilarityRequest(BaseModel):
    """
    Modèle de requête pour calculer la similarité entre deux textes.
    """
    text1: str = Field(..., description="Premier texte à comparer")
    text2: str = Field(..., description="Second texte à comparer")
    
    @model_validator(mode='after')
    def validate_texts_not_empty(self) -> 'SimilarityRequest':
        """Valide que les textes ne sont pas vides."""
        if not self.text1 or not self.text1.strip():
            raise ValueError("Le premier texte ne peut pas être vide")
        if not self.text2 or not self.text2.strip():
            raise ValueError("Le second texte ne peut pas être vide")
        return self
        
class SimilarityResponse(BaseModel):
    """
    Modèle de réponse pour un calcul de similarité.
    """
    similarity: float = Field(..., description="Score de similarité entre 0 et 1")
    model: str = Field(..., description="Modèle utilisé pour calculer la similarité") 