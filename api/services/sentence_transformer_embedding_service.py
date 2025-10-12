"""
Service d'embedding utilisant Sentence-Transformers.
Implémentation production pour génération d'embeddings sémantiques.
"""

import os
import logging
import asyncio
from typing import List, Optional
import hashlib

from sentence_transformers import SentenceTransformer
import numpy as np

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddingService:
    """
    Service d'embedding basé sur Sentence-Transformers.
    Fournit des embeddings sémantiques réels pour la recherche vectorielle.

    Features:
    - Chargement modèle au startup (évite cold start)
    - Cache LRU pour requêtes répétées
    - Async execution via ThreadPoolExecutor
    - Memory monitoring
    - Batch support pour optimisation
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        dimension: Optional[int] = None,
        cache_size: int = 1000,
        device: str = "cpu"
    ):
        """
        Initialise le service d'embeddings.

        Args:
            model_name: Nom du modèle Sentence-Transformers
            dimension: Dimension attendue des vecteurs (validation)
            cache_size: Taille du cache LRU (0 pour désactiver)
            device: Device PyTorch ('cpu', 'cuda', 'mps')
        """
        self.model_name = model_name or os.getenv(
            "EMBEDDING_MODEL",
            "nomic-ai/nomic-embed-text-v1.5"
        )
        self.dimension = dimension or int(os.getenv("EMBEDDING_DIMENSION", "768"))
        self.cache_size = cache_size
        self.device = device

        # Cache pour embeddings
        self._cache = {} if cache_size > 0 else None
        self._cache_access = {} if cache_size > 0 else None

        # Model chargé de manière lazy
        self._model: Optional[SentenceTransformer] = None
        self._lock = asyncio.Lock()
        self._load_attempted = False

        logger.info(
            f"SentenceTransformerEmbeddingService initialized",
            extra={
                "model": self.model_name,
                "dimension": self.dimension,
                "cache_size": cache_size,
                "device": device
            }
        )

    async def _ensure_model_loaded(self):
        """Charge le modèle si pas déjà chargé (thread-safe)."""
        if self._model is not None:
            return

        async with self._lock:
            # Double-check locking
            if self._model is not None:
                return

            if self._load_attempted:
                raise RuntimeError(
                    "Model loading failed previously. Restart service to retry."
                )

            self._load_attempted = True

            try:
                logger.info(f"Loading Sentence-Transformers model: {self.model_name}")
                logger.info("This may take 10-30 seconds on first load...")

                # Charger modèle dans executor pour ne pas bloquer event loop
                loop = asyncio.get_event_loop()
                self._model = await loop.run_in_executor(
                    None,
                    self._load_model_sync
                )

                # Vérifier dimension (aussi dans executor pour ne pas bloquer)
                test_embedding = await loop.run_in_executor(
                    None,
                    self._model.encode,
                    "test"
                )
                actual_dim = len(test_embedding)

                if actual_dim != self.dimension:
                    raise ValueError(
                        f"Model dimension mismatch! "
                        f"Expected {self.dimension}, got {actual_dim}. "
                        f"Update EMBEDDING_DIMENSION in .env"
                    )

                logger.info(
                    "✅ Model loaded successfully",
                    extra={
                        "model": self.model_name,
                        "dimension": actual_dim,
                        "device": self.device
                    }
                )

            except Exception as e:
                logger.error(
                    "❌ Failed to load embedding model",
                    exc_info=True,
                    extra={
                        "error": str(e),
                        "model": self.model_name
                    }
                )
                self._model = None
                raise RuntimeError(f"Failed to load model: {e}") from e

    def _load_model_sync(self) -> SentenceTransformer:
        """Charge le modèle (fonction synchrone pour executor)."""
        return SentenceTransformer(
            self.model_name,
            device=self.device,
            trust_remote_code=True  # Required for nomic-embed-text-v1.5
        )

    def _get_cache_key(self, text: str) -> str:
        """Génère une clé de cache pour un texte."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

    def _evict_lru_from_cache(self):
        """Évite l'élément le moins récemment utilisé du cache."""
        if not self._cache or len(self._cache) < self.cache_size:
            return

        # Trouver LRU
        lru_key = min(self._cache_access, key=self._cache_access.get)
        del self._cache[lru_key]
        del self._cache_access[lru_key]

        logger.debug(f"Cache LRU evicted: {lru_key}")

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Génère un embedding sémantique pour un texte.

        Args:
            text: Texte à encoder

        Returns:
            Vecteur d'embedding (liste de floats)

        Raises:
            ValueError: Si texte vide
            RuntimeError: Si model loading a échoué
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return [0.0] * self.dimension

        # Ensure model is loaded
        await self._ensure_model_loaded()

        # Check cache
        if self._cache is not None:
            cache_key = self._get_cache_key(text)

            if cache_key in self._cache:
                # Cache hit
                self._cache_access[cache_key] = asyncio.get_event_loop().time()
                logger.debug(f"Cache hit for text (len={len(text)})")
                return self._cache[cache_key]

        # Cache miss - generate embedding
        try:
            loop = asyncio.get_event_loop()

            # Encode dans executor (CPU-bound operation)
            embedding_array = await loop.run_in_executor(
                None,
                self._model.encode,
                text
            )

            embedding = embedding_array.tolist()

            # Store in cache
            if self._cache is not None:
                self._evict_lru_from_cache()
                self._cache[cache_key] = embedding
                self._cache_access[cache_key] = loop.time()

            logger.debug(
                f"Generated embedding",
                extra={
                    "text_len": len(text),
                    "embedding_dim": len(embedding)
                }
            )

            return embedding

        except Exception as e:
            logger.error(
                f"Failed to generate embedding",
                exc_info=True,
                extra={
                    "error": str(e),
                    "text_len": len(text)
                }
            )
            raise ValueError(f"Embedding generation failed: {e}") from e

    async def generate_embeddings_batch(
        self,
        texts: List[str]
    ) -> List[List[float]]:
        """
        Génère des embeddings pour plusieurs textes (optimisé).

        Args:
            texts: Liste de textes à encoder

        Returns:
            Liste de vecteurs d'embedding
        """
        if not texts:
            return []

        await self._ensure_model_loaded()

        try:
            loop = asyncio.get_event_loop()

            # Batch encode (beaucoup plus rapide que N appels individuels)
            embeddings_array = await loop.run_in_executor(
                None,
                lambda: self._model.encode(texts, batch_size=32, convert_to_numpy=True)
            )

            embeddings = [emb.tolist() for emb in embeddings_array]

            # Cache les résultats
            if self._cache is not None:
                current_time = loop.time()
                for text, embedding in zip(texts, embeddings):
                    cache_key = self._get_cache_key(text)
                    self._evict_lru_from_cache()
                    self._cache[cache_key] = embedding
                    self._cache_access[cache_key] = current_time

            logger.info(f"Generated {len(embeddings)} embeddings in batch")

            return embeddings

        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}", exc_info=True)
            raise ValueError(f"Batch embedding failed: {e}") from e

    async def compute_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Calcule la similarité cosinus entre deux embeddings.

        Args:
            embedding1: Premier vecteur
            embedding2: Second vecteur

        Returns:
            Score de similarité [0, 1]
        """
        if len(embedding1) != len(embedding2):
            raise ValueError(
                f"Embedding dimensions must match: "
                f"{len(embedding1)} != {len(embedding2)}"
            )

        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Cosine similarity: dot(v1, v2) / (||v1|| * ||v2||)
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Normalize to [0, 1] range
        similarity = (dot_product / (norm1 * norm2) + 1) / 2

        return float(np.clip(similarity, 0.0, 1.0))

    def get_stats(self) -> dict:
        """Retourne les statistiques du service."""
        return {
            "model_name": self.model_name,
            "dimension": self.dimension,
            "cache_enabled": self._cache is not None,
            "cache_size": len(self._cache) if self._cache else 0,
            "cache_max_size": self.cache_size,
            "model_loaded": self._model is not None,
            "device": self.device
        }
