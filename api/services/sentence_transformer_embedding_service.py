"""
Service d'embedding utilisant Sentence-Transformers.
Implémentation production pour génération d'embeddings sémantiques.

Supports:
- nomic-embed-text-v1.5 (default, 768D, fast)
- nomic-embed-text-v2-moe (MoE multilingual, 768D, requires GPU/xformers)
- multilingual-e5-base (768D, best French quality, recommended)
- multilingual-e5-small (384D, fast multilingual)
"""

import os
import logging
import asyncio
from typing import List, Optional, Literal
from enum import Enum
import hashlib

from sentence_transformers import SentenceTransformer
import numpy as np

logger = logging.getLogger(__name__)


class TextType(str, Enum):
    """Text type for embedding generation (affects prompt prefix)."""
    QUERY = "query"      # For search queries
    DOCUMENT = "passage"  # For documents being indexed (memories, code chunks)


# Model configurations
# Each model has different requirements for query/document prefixes
EMBEDDING_MODELS = {
    # Nomic models
    "nomic-ai/nomic-embed-text-v1.5": {
        "version": "v1.5",
        "dimension": 768,
        "uses_prompt_name": False,
        "uses_prefix": False,  # Works fine without prefixes
        "query_prefix": "",
        "document_prefix": "",
    },
    "nomic-ai/nomic-embed-text-v2-moe": {
        "version": "v2-moe",
        "dimension": 768,
        "uses_prompt_name": True,  # Uses prompt_name parameter
        "uses_prefix": False,
        "query_prefix": None,
        "document_prefix": None,
    },
    # E5 multilingual models (best for French)
    "intfloat/multilingual-e5-base": {
        "version": "e5-base",
        "dimension": 768,
        "uses_prompt_name": False,
        "uses_prefix": True,  # Requires "query: " and "passage: " prefixes
        "query_prefix": "query: ",
        "document_prefix": "passage: ",
    },
    "intfloat/multilingual-e5-small": {
        "version": "e5-small",
        "dimension": 384,
        "uses_prompt_name": False,
        "uses_prefix": True,
        "query_prefix": "query: ",
        "document_prefix": "passage: ",
    },
    "intfloat/multilingual-e5-large": {
        "version": "e5-large",
        "dimension": 1024,
        "uses_prompt_name": False,
        "uses_prefix": True,
        "query_prefix": "query: ",
        "document_prefix": "passage: ",
    },
}

# Backward compatibility alias
NOMIC_MODELS = EMBEDDING_MODELS


class SentenceTransformerEmbeddingService:
    """
    Service d'embedding basé sur Sentence-Transformers.
    Fournit des embeddings sémantiques réels pour la recherche vectorielle.

    Supported models:
    - nomic-ai/nomic-embed-text-v1.5 (default, 137M params, 768D, fast)
    - intfloat/multilingual-e5-base (278M params, 768D, best French quality)
    - intfloat/multilingual-e5-small (118M params, 384D, fast multilingual)
    - nomic-ai/nomic-embed-text-v2-moe (475M params, 768D, requires GPU)

    Features:
    - Lazy model loading (avoids cold start blocking)
    - LRU cache for repeated queries
    - Async execution via ThreadPoolExecutor
    - Text type support (query vs document) with appropriate prefixes
    - Batch encoding for performance
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        dimension: Optional[int] = None,
        cache_size: int = 1000,
        device: str = "cpu"
    ):
        """
        Initialize the embedding service.

        Args:
            model_name: Sentence-Transformers model name
                        Options: "nomic-ai/nomic-embed-text-v1.5" (default, fast)
                                 "intfloat/multilingual-e5-base" (best French)
                                 "intfloat/multilingual-e5-small" (fast multilingual)
            dimension: Expected vector dimension (for validation)
            cache_size: LRU cache size (0 to disable)
            device: PyTorch device ('cpu', 'cuda', 'mps')
        """
        self.model_name = model_name or os.getenv(
            "EMBEDDING_MODEL",
            "nomic-ai/nomic-embed-text-v1.5"
        )
        self.dimension = dimension or int(os.getenv("EMBEDDING_DIMENSION", "768"))
        self.cache_size = cache_size
        self.device = device

        # Get model config
        self.model_config = EMBEDDING_MODELS.get(self.model_name, {
            "version": "unknown",
            "dimension": 768,
            "uses_prompt_name": False,
            "uses_prefix": False,
            "query_prefix": "",
            "document_prefix": "",
        })

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
                "model_version": self.model_config.get("version", "unknown"),
                "dimension": self.dimension,
                "cache_size": cache_size,
                "device": device,
                "uses_prompt_name": self.model_config.get("uses_prompt_name", False),
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

    async def generate_embedding(
        self,
        text: str,
        text_type: TextType = TextType.DOCUMENT
    ) -> List[float]:
        """
        Génère un embedding sémantique pour un texte.

        Args:
            text: Texte à encoder
            text_type: Type de texte (QUERY pour recherches, DOCUMENT pour indexation)
                       Important for v2 models which use different prompts.

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

        # Build cache key with text_type to avoid collisions
        cache_key_base = f"{text_type.value}:{text}"

        # Check cache
        if self._cache is not None:
            cache_key = self._get_cache_key(cache_key_base)

            if cache_key in self._cache:
                # Cache hit
                self._cache_access[cache_key] = asyncio.get_event_loop().time()
                logger.debug(f"Cache hit for text (len={len(text)}, type={text_type.value})")
                return self._cache[cache_key]

        # Cache miss - generate embedding
        try:
            loop = asyncio.get_event_loop()

            # Prepare text based on model requirements
            text_to_encode = text

            if self.model_config.get("uses_prompt_name"):
                # Nomic v2 models: use prompt_name parameter
                prompt_name = text_type.value  # "query" or "passage"
                embedding_array = await loop.run_in_executor(
                    None,
                    lambda: self._model.encode(text_to_encode, prompt_name=prompt_name)
                )
            elif self.model_config.get("uses_prefix"):
                # E5 models: require "query: " or "passage: " prefix
                if text_type == TextType.QUERY:
                    prefix = self.model_config.get("query_prefix", "query: ")
                else:
                    prefix = self.model_config.get("document_prefix", "passage: ")
                text_to_encode = f"{prefix}{text}"
                embedding_array = await loop.run_in_executor(
                    None,
                    self._model.encode,
                    text_to_encode
                )
            else:
                # Nomic v1.5 and other models: no prefix needed
                embedding_array = await loop.run_in_executor(
                    None,
                    self._model.encode,
                    text_to_encode
                )

            embedding = embedding_array.tolist()

            # Store in cache
            if self._cache is not None:
                cache_key = self._get_cache_key(cache_key_base)
                self._evict_lru_from_cache()
                self._cache[cache_key] = embedding
                self._cache_access[cache_key] = loop.time()

            logger.debug(
                f"Generated embedding",
                extra={
                    "text_len": len(text),
                    "embedding_dim": len(embedding),
                    "text_type": text_type.value,
                    "model_version": self.model_config.get("version", "unknown"),
                }
            )

            return embedding

        except Exception as e:
            logger.error(
                f"Failed to generate embedding",
                exc_info=True,
                extra={
                    "error": str(e),
                    "text_len": len(text),
                    "text_type": text_type.value,
                }
            )
            raise ValueError(f"Embedding generation failed: {e}") from e

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        text_type: TextType = TextType.DOCUMENT
    ) -> List[List[float]]:
        """
        Génère des embeddings pour plusieurs textes (optimisé).

        Args:
            texts: Liste de textes à encoder
            text_type: Type de texte (QUERY ou DOCUMENT)

        Returns:
            Liste de vecteurs d'embedding
        """
        if not texts:
            return []

        await self._ensure_model_loaded()

        try:
            loop = asyncio.get_event_loop()

            # Prepare texts based on model requirements
            texts_to_encode = texts

            if self.model_config.get("uses_prompt_name"):
                # Nomic v2 models: use prompt_name parameter
                prompt_name = text_type.value
                embeddings_array = await loop.run_in_executor(
                    None,
                    lambda: self._model.encode(
                        texts_to_encode,
                        batch_size=32,
                        convert_to_numpy=True,
                        prompt_name=prompt_name
                    )
                )
            elif self.model_config.get("uses_prefix"):
                # E5 models: require prefix
                if text_type == TextType.QUERY:
                    prefix = self.model_config.get("query_prefix", "query: ")
                else:
                    prefix = self.model_config.get("document_prefix", "passage: ")
                texts_to_encode = [f"{prefix}{t}" for t in texts]
                embeddings_array = await loop.run_in_executor(
                    None,
                    lambda: self._model.encode(texts_to_encode, batch_size=32, convert_to_numpy=True)
                )
            else:
                # Nomic v1.5 and other models: no prefix needed
                embeddings_array = await loop.run_in_executor(
                    None,
                    lambda: self._model.encode(texts_to_encode, batch_size=32, convert_to_numpy=True)
                )

            embeddings = [emb.tolist() for emb in embeddings_array]

            # Cache les résultats
            if self._cache is not None:
                current_time = loop.time()
                for text, embedding in zip(texts, embeddings):
                    cache_key_base = f"{text_type.value}:{text}"
                    cache_key = self._get_cache_key(cache_key_base)
                    self._evict_lru_from_cache()
                    self._cache[cache_key] = embedding
                    self._cache_access[cache_key] = current_time

            logger.info(
                f"Generated {len(embeddings)} embeddings in batch",
                extra={"text_type": text_type.value}
            )

            return embeddings

        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}", exc_info=True)
            raise ValueError(f"Batch embedding failed: {e}") from e

    # Convenience methods for common use cases

    async def embed_query(self, query: str) -> List[float]:
        """
        Embed a search query (uses QUERY text type for v2 models).

        Args:
            query: Search query text

        Returns:
            Query embedding vector
        """
        return await self.generate_embedding(query, text_type=TextType.QUERY)

    async def embed_document(self, document: str) -> List[float]:
        """
        Embed a document for indexing (uses DOCUMENT text type for v2 models).

        Args:
            document: Document text to index

        Returns:
            Document embedding vector
        """
        return await self.generate_embedding(document, text_type=TextType.DOCUMENT)

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
