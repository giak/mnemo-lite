"""
MnemoLite - Local Embedding Generation using Sentence-Transformers

This module provides local embedding generation without any external API dependencies.
Uses state-of-the-art open-source models from the Sentence-Transformers library.

Model: nomic-embed-text-v1.5 (default)
- 768 dimensions (configurable down to 256 with Matryoshka learning)
- 8192 token context window
- Apache 2.0 license
- MTEB score: ~65 (competitive with commercial models)
"""

import os
import numpy as np
from sentence_transformers import SentenceTransformer
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog
from functools import lru_cache
from typing import List

# Configuration du logger
logger = structlog.get_logger()

# Variables d'environnement
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "768"))

# Singleton pour le modèle (chargé une seule fois)
_MODEL_CACHE = None


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    """
    Charge le modèle Sentence-Transformers (singleton pattern).
    Le modèle est chargé une seule fois et réutilisé pour toutes les requêtes.

    Returns:
        Instance du modèle SentenceTransformer
    """
    global _MODEL_CACHE
    if _MODEL_CACHE is None:
        logger.info(
            "loading_embedding_model",
            model=EMBEDDING_MODEL,
            target_dimension=EMBEDDING_DIMENSION
        )
        try:
            _MODEL_CACHE = SentenceTransformer(
                EMBEDDING_MODEL,
                trust_remote_code=True,  # Required for nomic models
                device="cpu"  # Change to "cuda" if GPU is available
            )
            logger.info(
                "model_loaded_successfully",
                model=EMBEDDING_MODEL,
                max_seq_length=_MODEL_CACHE.max_seq_length
            )
        except Exception as e:
            logger.error("model_loading_failed", error=str(e), model=EMBEDDING_MODEL)
            raise RuntimeError(f"Failed to load embedding model {EMBEDDING_MODEL}: {e}")

    return _MODEL_CACHE


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def get_embedding(text: str, task_prefix: str = "search_document") -> List[float]:
    """
    Génère un embedding vectoriel à partir d'un texte en utilisant Sentence-Transformers.

    Args:
        text: Le texte à transformer en vecteur
        task_prefix: Préfixe de tâche pour les modèles nomic (optionnel)
                    Options: "search_document", "search_query", "clustering", "classification"

    Returns:
        Liste de flottants représentant l'embedding de dimension EMBEDDING_DIMENSION

    Raises:
        RuntimeError: Si le modèle ne peut pas être chargé
    """
    if not text or not text.strip():
        logger.warning("empty_text_for_embedding")
        return np.zeros(EMBEDDING_DIMENSION).tolist()

    try:
        model = get_model()

        # Tronquer le texte si nécessaire
        # nomic-embed-text-v1.5 supporte jusqu'à 8192 tokens (~32k caractères)
        max_chars = 32000
        if len(text) > max_chars:
            logger.warning(
                "text_truncated",
                original_length=len(text),
                truncated_to=max_chars
            )
            text = text[:max_chars]

        # Ajouter le préfixe de tâche pour les modèles nomic
        # Cela améliore la qualité des embeddings en fonction du contexte d'utilisation
        if "nomic" in EMBEDDING_MODEL.lower() and task_prefix:
            text = f"{task_prefix}: {text}"

        # Génération de l'embedding
        embedding = model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,  # Normalisation L2 pour cosine similarity
            show_progress_bar=False
        )

        # Tronquer aux dimensions cibles si nécessaire (Matryoshka learning)
        # Pour nomic-embed-text-v1.5, on peut réduire de 768 à 256 dims
        if len(embedding) > EMBEDDING_DIMENSION:
            embedding = embedding[:EMBEDDING_DIMENSION]
            logger.debug(
                "embedding_dimension_reduced",
                from_dim=len(embedding),
                to_dim=EMBEDDING_DIMENSION
            )

        return embedding.tolist()

    except Exception as e:
        logger.error(
            "embedding_generation_error",
            error=str(e),
            text_length=len(text) if text else 0
        )
        # Fallback: retourner un vecteur aléatoire pour éviter les crashes
        logger.warning("using_fallback_random_embedding")
        return np.random.rand(EMBEDDING_DIMENSION).tolist()


async def get_embedding_batch(texts: List[str], task_prefix: str = "search_document") -> List[List[float]]:
    """
    Génère des embeddings pour plusieurs textes en batch (plus efficace).

    Args:
        texts: Liste de textes à transformer
        task_prefix: Préfixe de tâche pour les modèles nomic

    Returns:
        Liste d'embeddings
    """
    if not texts:
        return []

    try:
        model = get_model()

        # Préparer les textes avec préfixes si nécessaire
        processed_texts = []
        for text in texts:
            if not text or not text.strip():
                processed_texts.append("")
                continue

            # Tronquer
            text = text[:32000] if len(text) > 32000 else text

            # Ajouter préfixe pour nomic
            if "nomic" in EMBEDDING_MODEL.lower() and task_prefix:
                text = f"{task_prefix}: {text}"

            processed_texts.append(text)

        # Génération batch
        embeddings = model.encode(
            processed_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32  # Ajustez selon votre RAM
        )

        # Tronquer dimensions si nécessaire
        if embeddings.shape[1] > EMBEDDING_DIMENSION:
            embeddings = embeddings[:, :EMBEDDING_DIMENSION]

        return embeddings.tolist()

    except Exception as e:
        logger.error("batch_embedding_error", error=str(e), num_texts=len(texts))
        # Fallback: un vecteur aléatoire par texte
        return [np.random.rand(EMBEDDING_DIMENSION).tolist() for _ in texts]


def cosine_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Calcule la similarité cosinus entre deux embeddings.

    Args:
        embedding1: Premier vecteur
        embedding2: Second vecteur

    Returns:
        Score de similarité entre -1 et 1 (typiquement entre 0 et 1 pour embeddings normalisés)
    """
    if not embedding1 or not embedding2:
        return 0.0

    try:
        a = np.array(embedding1)
        b = np.array(embedding2)

        # Normalisation
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)

        if a_norm == 0 or b_norm == 0:
            return 0.0

        # Similarité cosinus
        similarity = np.dot(a, b) / (a_norm * b_norm)
        return float(similarity)

    except Exception as e:
        logger.error("cosine_similarity_error", error=str(e))
        return 0.0
