"""
Cross-encoder Reranking Service.

EPIC-24 P2: Improves search quality by 20-30% using cross-encoder reranking.

Cross-encoders score query-document pairs directly (vs bi-encoders which encode separately).
This allows more nuanced relevance scoring but is slower (~10ms per pair).

Architecture:
    Top-K from Hybrid Search
           ↓
    ┌──────────────┐
    │ Cross-Encoder│  ← Score each (query, doc) pair
    └──────────────┘
           ↓
       Reranked Top-K

Supported models:
- cross-encoder/ms-marco-MiniLM-L-6-v2 (default, 22M params, fast)
- BAAI/bge-reranker-base (110M params, better quality, multilingual)
- BAAI/bge-reranker-v2-m3 (568M params, best quality, requires GPU)

Usage:
    service = CrossEncoderRerankService()
    reranked = await service.rerank(
        query="Jordan Bardella critique",
        documents=["Doc 1 content...", "Doc 2 content..."],
        top_k=10
    )
"""

import os
import logging
import asyncio
from typing import List, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Model configurations
RERANKER_MODELS = {
    "cross-encoder/ms-marco-MiniLM-L-6-v2": {
        "name": "MS-MARCO MiniLM L6",
        "params": "22M",
        "speed": "fast",
        "quality": "good",
        "multilingual": False,
    },
    "cross-encoder/ms-marco-MiniLM-L-12-v2": {
        "name": "MS-MARCO MiniLM L12",
        "params": "33M",
        "speed": "medium",
        "quality": "better",
        "multilingual": False,
    },
    "BAAI/bge-reranker-base": {
        "name": "BGE Reranker Base",
        "params": "110M",
        "speed": "medium",
        "quality": "excellent",
        "multilingual": True,  # Good for French
    },
    "BAAI/bge-reranker-v2-m3": {
        "name": "BGE Reranker v2 M3",
        "params": "568M",
        "speed": "slow",
        "quality": "best",
        "multilingual": True,
    },
}


@dataclass
class RerankResult:
    """Result from cross-encoder reranking."""
    original_index: int  # Index in the original list
    score: float  # Cross-encoder relevance score
    document: str  # Original document text


class CrossEncoderRerankService:
    """
    Cross-encoder reranking service for improving search quality.

    Cross-encoders process (query, document) pairs together, allowing
    full attention between query and document tokens. This produces
    more accurate relevance scores than bi-encoder similarity.

    Typical improvement: +20-30% quality over RRF fusion alone.
    Latency overhead: ~10ms per document (batch optimized).
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: str = "cpu",
        max_length: int = 512,
    ):
        """
        Initialize cross-encoder reranking service.

        Args:
            model_name: Cross-encoder model name (default: from env or ms-marco-MiniLM-L-6-v2)
            device: PyTorch device ('cpu', 'cuda', 'mps')
            max_length: Maximum sequence length for tokenization (default: 512)
        """
        self.model_name = model_name or os.getenv(
            "RERANKER_MODEL",
            "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        self.device = device
        self.max_length = max_length

        # Model config
        self.model_config = RERANKER_MODELS.get(self.model_name, {
            "name": "Unknown",
            "params": "?",
            "speed": "unknown",
            "quality": "unknown",
            "multilingual": False,
        })

        # Lazy loading
        self._model = None
        self._lock = asyncio.Lock()
        self._load_attempted = False

        logger.info(
            f"CrossEncoderRerankService initialized",
            extra={
                "model": self.model_name,
                "model_name": self.model_config.get("name"),
                "params": self.model_config.get("params"),
                "multilingual": self.model_config.get("multilingual"),
                "device": device,
            }
        )

    async def _ensure_model_loaded(self):
        """Load model if not already loaded (thread-safe)."""
        if self._model is not None:
            return

        async with self._lock:
            # Double-check locking
            if self._model is not None:
                return

            if self._load_attempted:
                raise RuntimeError(
                    "Cross-encoder model loading failed previously. Restart service to retry."
                )

            self._load_attempted = True

            try:
                logger.info(f"Loading cross-encoder model: {self.model_name}")
                logger.info("This may take 5-15 seconds on first load...")

                # Load in executor to avoid blocking event loop
                loop = asyncio.get_event_loop()
                self._model = await loop.run_in_executor(
                    None,
                    self._load_model_sync
                )

                logger.info(
                    "Cross-encoder model loaded successfully",
                    extra={
                        "model": self.model_name,
                        "device": self.device
                    }
                )

            except Exception as e:
                logger.error(
                    "Failed to load cross-encoder model",
                    exc_info=True,
                    extra={"error": str(e), "model": self.model_name}
                )
                self._model = None
                raise RuntimeError(f"Failed to load cross-encoder model: {e}") from e

    def _load_model_sync(self):
        """Load model synchronously (for executor)."""
        from sentence_transformers import CrossEncoder
        return CrossEncoder(
            self.model_name,
            device=self.device,
            max_length=self.max_length,
        )

    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
    ) -> List[RerankResult]:
        """
        Rerank documents by relevance to query using cross-encoder.

        Args:
            query: Search query
            documents: List of document texts to rerank
            top_k: Return only top K results (default: all)

        Returns:
            List of RerankResult sorted by relevance score (descending)

        Example:
            results = await service.rerank(
                query="Jordan Bardella agriculture",
                documents=["Doc about Bardella...", "Doc about farming..."],
                top_k=5
            )
        """
        if not documents:
            return []

        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        await self._ensure_model_loaded()

        try:
            # Prepare query-document pairs
            pairs = [(query, doc) for doc in documents]

            # Score pairs in executor (batch)
            loop = asyncio.get_event_loop()
            scores = await loop.run_in_executor(
                None,
                self._model.predict,
                pairs
            )

            # Build results with original indices
            results = [
                RerankResult(
                    original_index=i,
                    score=float(score),
                    document=doc
                )
                for i, (doc, score) in enumerate(zip(documents, scores))
            ]

            # Sort by score descending
            results.sort(key=lambda x: x.score, reverse=True)

            # Apply top_k limit
            if top_k is not None:
                results = results[:top_k]

            logger.debug(
                "Cross-encoder reranking completed",
                extra={
                    "query_len": len(query),
                    "documents": len(documents),
                    "top_k": top_k or len(documents),
                    "top_score": results[0].score if results else 0,
                }
            )

            return results

        except Exception as e:
            logger.error(
                "Cross-encoder reranking failed",
                exc_info=True,
                extra={"error": str(e), "query": query[:50]}
            )
            raise ValueError(f"Reranking failed: {e}") from e

    async def rerank_with_ids(
        self,
        query: str,
        documents: List[Tuple[str, str]],  # (id, text)
        top_k: Optional[int] = None,
    ) -> List[Tuple[str, float, str]]:
        """
        Rerank documents and return with their IDs.

        Args:
            query: Search query
            documents: List of (id, text) tuples
            top_k: Return only top K results

        Returns:
            List of (id, score, text) tuples sorted by score
        """
        if not documents:
            return []

        # Extract texts for reranking
        ids = [doc_id for doc_id, _ in documents]
        texts = [text for _, text in documents]

        # Rerank
        results = await self.rerank(query, texts, top_k=top_k)

        # Map back to IDs
        return [
            (ids[r.original_index], r.score, r.document)
            for r in results
        ]

    def get_stats(self) -> dict:
        """Return service statistics."""
        return {
            "model_name": self.model_name,
            "model_config": self.model_config,
            "model_loaded": self._model is not None,
            "device": self.device,
            "max_length": self.max_length,
        }
