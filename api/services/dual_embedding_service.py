"""
Dual Embedding Service for TEXT + CODE domains.

Phase 0 Story 0.2 - Manages two SentenceTransformer models simultaneously:
- TEXT: nomic-embed-text-v1.5 (137M params, 768D, ~260 MB RAM)
- CODE: jina-embeddings-v2-base-code (161M params, 768D, ~400 MB RAM)

Features:
- Lazy loading (models loaded on-demand)
- Domain-specific selection (TEXT | CODE | HYBRID)
- RAM monitoring via psutil
- Double-checked locking (thread-safe)
- Backward compatible via generate_embedding_legacy()

EPIC-12 Story 12.1: Added timeout protection for embedding generation.
EPIC-12 Story 12.3: Added circuit breaker to prevent fail-forever behavior.
"""

import os
import logging
import asyncio
from typing import List, Dict, Optional
from enum import Enum

from sentence_transformers import SentenceTransformer
import psutil
import numpy as np

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

from utils.timeout import with_timeout, TimeoutError
from config.timeouts import get_timeout
from utils.circuit_breaker import CircuitBreaker
from config.circuit_breakers import EMBEDDING_CIRCUIT_CONFIG
from utils.circuit_breaker_registry import register_circuit_breaker

logger = logging.getLogger(__name__)


class EmbeddingDomain(str, Enum):
    """
    Embedding domain types for model selection.

    TEXT: General text, conversations, documents (nomic-embed-text-v1.5)
    CODE: Code snippets, functions, classes (jina-embeddings-v2-base-code)
    HYBRID: Generate both embeddings (for code with docstrings)
    """
    TEXT = "text"
    CODE = "code"
    HYBRID = "hybrid"


class DualEmbeddingService:
    """
    Service managing dual embeddings for text and code.

    Models:
    - TEXT: nomic-embed-text-v1.5 (137M params, 768D, ~260 MB RAM)
    - CODE: jina-embeddings-v2-base-code (161M params, 768D, ~400 MB RAM)
    - Total: ~660-700 MB RAM (< 1 GB target)

    Features:
    - Lazy loading (models loaded on-demand)
    - Domain-specific selection (TEXT | CODE | HYBRID)
    - RAM monitoring via psutil
    - Double-checked locking (thread-safe)

    Example:
        >>> service = DualEmbeddingService()
        >>>
        >>> # TEXT domain (conversations, docs)
        >>> result = await service.generate_embedding(
        ...     "Hello world",
        ...     domain=EmbeddingDomain.TEXT
        ... )
        >>> # {'text': [0.1, 0.2, ...]}
        >>>
        >>> # CODE domain (code snippets)
        >>> result = await service.generate_embedding(
        ...     "def foo(): pass",
        ...     domain=EmbeddingDomain.CODE
        ... )
        >>> # {'code': [0.3, 0.4, ...]}
        >>>
        >>> # HYBRID domain (both)
        >>> result = await service.generate_embedding(
        ...     "def foo():\\n  '''Docstring'''",
        ...     domain=EmbeddingDomain.HYBRID
        ... )
        >>> # {'text': [...], 'code': [...]}
    """

    def __init__(
        self,
        text_model_name: Optional[str] = None,
        code_model_name: Optional[str] = None,
        dimension: int = 768,
        device: str = "cpu",
        cache_size: int = 1000
    ):
        """
        Initialize dual embedding service.

        Args:
            text_model_name: Sentence-Transformers model for text
                            (default: nomic-ai/nomic-embed-text-v1.5)
            code_model_name: Sentence-Transformers model for code
                            (default: jinaai/jina-embeddings-v2-base-code)
            dimension: Expected embedding dimension (must be 768)
            device: PyTorch device ('cpu', 'cuda', 'mps')
            cache_size: Not used (kept for backward compat)
        """
        # EPIC-18 Fix: Check EMBEDDING_MODE to support mock mode
        self._embedding_mode = os.getenv("EMBEDDING_MODE", "real").lower()
        self._mock_mode = (self._embedding_mode == "mock")

        self.text_model_name = text_model_name or os.getenv(
            "EMBEDDING_MODEL",
            "nomic-ai/nomic-embed-text-v1.5"
        )
        self.code_model_name = code_model_name or os.getenv(
            "CODE_EMBEDDING_MODEL",
            "jinaai/jina-embeddings-v2-base-code"
        )
        self.dimension = dimension
        self.device = device

        # Models (lazy loaded, EXCEPT in mock mode)
        self._text_model: Optional[SentenceTransformer] = None
        self._code_model: Optional[SentenceTransformer] = None

        # Locks for thread-safe lazy loading
        self._text_lock = asyncio.Lock()
        self._code_lock = asyncio.Lock()

        # EPIC-12 Story 12.3: Circuit breaker (removes fail-forever behavior)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=EMBEDDING_CIRCUIT_CONFIG.failure_threshold,
            recovery_timeout=EMBEDDING_CIRCUIT_CONFIG.recovery_timeout,
            half_open_max_calls=EMBEDDING_CIRCUIT_CONFIG.half_open_max_calls,
            name="embedding_service"
        )

        # Register for health monitoring
        register_circuit_breaker(self.circuit_breaker)

        if self._mock_mode:
            logger.warning(
                "🔶 DUAL EMBEDDING SERVICE: MOCK MODE (development/testing) 🔶",
                extra={
                    "embedding_mode": "mock",
                    "text_model": "MOCK",
                    "code_model": "MOCK",
                    "dimension": dimension
                }
            )
        else:
            logger.info(
                "DualEmbeddingService initialized",
                extra={
                    "text_model": self.text_model_name,
                    "code_model": self.code_model_name,
                    "dimension": dimension,
                    "device": device
                }
            )

    def _load_text_model_sync(self) -> SentenceTransformer:
        """
        Synchronous text model loading (runs in executor).

        Returns:
            Loaded SentenceTransformer model for text
        """
        logger.info(f"Loading TEXT model: {self.text_model_name}")
        model = SentenceTransformer(
            self.text_model_name,
            device=self.device,
            trust_remote_code=True
        )

        # Validate dimension
        test_emb = model.encode("test")
        if len(test_emb) != self.dimension:
            raise ValueError(
                f"TEXT model dimension mismatch: "
                f"expected {self.dimension}, got {len(test_emb)}"
            )

        logger.info(
            f"✅ TEXT model loaded: {self.text_model_name} ({self.dimension}D)"
        )
        return model

    def _load_code_model_sync(self) -> SentenceTransformer:
        """
        Synchronous code model loading (runs in executor).

        Returns:
            Loaded SentenceTransformer model for code
        """
        logger.info(f"Loading CODE model: {self.code_model_name}")
        model = SentenceTransformer(
            self.code_model_name,
            device=self.device,
            trust_remote_code=True
        )

        # Validate dimension
        test_emb = model.encode("def test(): pass")
        if len(test_emb) != self.dimension:
            raise ValueError(
                f"CODE model dimension mismatch: "
                f"expected {self.dimension}, got {len(test_emb)}"
            )

        logger.info(
            f"✅ CODE model loaded: {self.code_model_name} ({self.dimension}D)"
        )
        return model

    def _encode_single_with_no_grad(self, model: SentenceTransformer, text: str):
        """
        Encode single text with torch.no_grad() to prevent memory accumulation.

        PyTorch accumulates gradient tracking state during forward passes even
        for inference. Using no_grad() disables this completely.

        Args:
            model: Loaded SentenceTransformer model
            text: Text or code to encode

        Returns:
            Embedding vector (numpy array)
        """
        if TORCH_AVAILABLE and torch is not None:
            with torch.no_grad():
                embedding = model.encode(text, convert_to_numpy=True)

            # Clear CUDA cache if using GPU
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            return embedding
        else:
            # Fallback without torch.no_grad() (shouldn't happen)
            return model.encode(text, convert_to_numpy=True)

    def _encode_batch_with_no_grad(
        self,
        model: SentenceTransformer,
        texts: List[str],
        show_progress_bar: bool = True
    ):
        """
        Encode batch of texts with torch.no_grad() to prevent memory accumulation.

        Critical for large batches where memory can accumulate significantly.

        Args:
            model: Loaded SentenceTransformer model
            texts: List of texts/code to encode
            show_progress_bar: Show tqdm progress bar

        Returns:
            Embedding matrix (numpy array)
        """
        if TORCH_AVAILABLE and torch is not None:
            with torch.no_grad():
                embeddings = model.encode(
                    texts,
                    show_progress_bar=show_progress_bar,
                    convert_to_numpy=True
                )

            # Clear CUDA cache if using GPU
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            return embeddings
        else:
            # Fallback without torch.no_grad()
            return model.encode(
                texts,
                show_progress_bar=show_progress_bar,
                convert_to_numpy=True
            )

    async def _ensure_text_model(self):
        """
        Load text model if not already loaded (thread-safe with double-checked locking).

        EPIC-12 Story 12.3: Protected with circuit breaker (no more fail-forever).
        EPIC-18 Fix: Skip model loading in mock mode.

        Raises:
            RuntimeError: If model loading failed or circuit breaker is OPEN
        """
        # EPIC-18 Fix: Skip model loading in mock mode
        if self._mock_mode:
            return

        # First check (no lock)
        if self._text_model is not None:
            return

        # EPIC-12 Story 12.3: Check circuit breaker
        if not self.circuit_breaker.can_execute():
            raise RuntimeError(
                f"Embedding service circuit breaker is {self.circuit_breaker.state.value}. "
                f"Model loading temporarily unavailable (will retry after {EMBEDDING_CIRCUIT_CONFIG.recovery_timeout}s)."
            )

        async with self._text_lock:
            # Double-checked locking
            if self._text_model is not None:
                return

            try:
                loop = asyncio.get_running_loop()
                self._text_model = await loop.run_in_executor(
                    None,
                    self._load_text_model_sync
                )

                # EPIC-12 Story 12.3: Record success
                self.circuit_breaker.record_success()

            except Exception as e:
                # EPIC-12 Story 12.3: Record failure
                self.circuit_breaker.record_failure()

                logger.error(
                    f"❌ Failed to load TEXT model: {e}",
                    extra={
                        "circuit_state": self.circuit_breaker.state.value,
                        "failure_count": self.circuit_breaker._failure_count
                    },
                    exc_info=True
                )
                self._text_model = None
                raise RuntimeError(f"Failed to load TEXT model: {e}") from e

    async def _ensure_code_model(self):
        """
        Load code model if not already loaded (thread-safe with double-checked locking).

        EPIC-12 Story 12.3: Protected with circuit breaker for automatic recovery.
        EPIC-18 Fix: Skip model loading in mock mode.

        Raises:
            RuntimeError: If model loading fails or circuit breaker is OPEN
        """
        # EPIC-18 Fix: Skip model loading in mock mode
        if self._mock_mode:
            return

        # First check (no lock)
        if self._code_model is not None:
            return

        # EPIC-12 Story 12.3: Check circuit breaker before attempting load
        if not self.circuit_breaker.can_execute():
            raise RuntimeError(
                f"Embedding service circuit breaker is {self.circuit_breaker.state.value}. "
                f"Model loading temporarily unavailable (will retry after {EMBEDDING_CIRCUIT_CONFIG.recovery_timeout}s)."
            )

        async with self._code_lock:
            # Double-checked locking
            if self._code_model is not None:
                return

            try:
                # Check RAM before loading CODE model
                ram_usage = self.get_ram_usage_mb()
                if ram_usage['process_rss_mb'] > 2500:  # > 2.5 GB (increased for 4GB container)
                    logger.warning(
                        "⚠️ RAM limit approaching, refusing to load CODE model",
                        extra={"ram_mb": ram_usage['process_rss_mb']}
                    )
                    raise RuntimeError(
                        f"RAM budget exceeded ({ram_usage['process_rss_mb']:.1f} MB > 2500 MB). "
                        "CODE model loading disabled to prevent OOM."
                    )

                loop = asyncio.get_running_loop()
                self._code_model = await loop.run_in_executor(
                    None,
                    self._load_code_model_sync
                )

                # EPIC-12 Story 12.3: Record successful load
                self.circuit_breaker.record_success()

            except Exception as e:
                # EPIC-12 Story 12.3: Record failure
                self.circuit_breaker.record_failure()

                logger.error(
                    f"❌ Failed to load CODE model: {e}",
                    exc_info=True,
                    extra={"circuit_state": self.circuit_breaker.state.value}
                )
                self._code_model = None
                raise RuntimeError(f"Failed to load CODE model: {e}") from e

    def _generate_mock_embedding(self, text: str) -> List[float]:
        """
        Generate mock embedding (deterministic based on text hash).

        EPIC-18 Fix: Mock embeddings for EMBEDDING_MODE=mock.

        Args:
            text: Input text

        Returns:
            Mock embedding vector (768D, deterministic)
        """
        # Use hash of text for deterministic mock embeddings
        import hashlib
        text_hash = int(hashlib.md5(text.encode()).hexdigest(), 16)

        # Use hash as seed for reproducible random vector
        rng = np.random.default_rng(text_hash % (2**32))
        mock_emb = rng.random(self.dimension).astype(np.float32)

        # Normalize to unit vector (like real embeddings)
        norm = np.linalg.norm(mock_emb)
        if norm > 0:
            mock_emb = mock_emb / norm

        return mock_emb.tolist()

    async def preload_models(self):
        """
        Pre-load both TEXT and CODE models at startup.

        This method should be called during application startup to avoid
        lazy loading delays on first upload request.

        EPIC-18 Fix: Skip pre-loading in mock mode.

        Raises:
            RuntimeError: If either model fails to load
        """
        # EPIC-18 Fix: Skip pre-loading in mock mode
        if self._mock_mode:
            logger.info("⏭️ Skipping model pre-loading (MOCK MODE)")
            return

        logger.info("🚀 Pre-loading both embedding models...")

        try:
            # Load TEXT model first (smaller, faster)
            await self._ensure_text_model()
            logger.info("✅ TEXT model pre-loaded successfully")

            # Load CODE model second
            await self._ensure_code_model()
            logger.info("✅ CODE model pre-loaded successfully")

            # Log RAM usage after loading
            ram_usage = self.get_ram_usage_mb()
            logger.info(
                "✅ Both models pre-loaded successfully",
                extra={
                    "ram_mb": ram_usage['process_rss_mb'],
                    "estimated_models_mb": ram_usage['estimated_models_mb']
                }
            )

        except Exception as e:
            logger.error(f"❌ Failed to pre-load models: {e}", exc_info=True)
            raise RuntimeError(f"Model pre-loading failed: {e}") from e

    async def generate_embedding(
        self,
        text: str,
        domain: EmbeddingDomain = EmbeddingDomain.TEXT
    ) -> Dict[str, List[float]]:
        """
        Generate embedding(s) based on domain.

        Args:
            text: Text or code to embed
            domain: TEXT (text model), CODE (code model), HYBRID (both)

        Returns:
            Dict with keys 'text' and/or 'code' containing embeddings

        Examples:
            # TEXT domain (conversations, docs)
            result = await svc.generate_embedding(
                "Hello world",
                domain=EmbeddingDomain.TEXT
            )
            # {'text': [0.1, 0.2, ...]}

            # CODE domain (code snippets)
            result = await svc.generate_embedding(
                "def foo(): pass",
                domain=EmbeddingDomain.CODE
            )
            # {'code': [0.3, 0.4, ...]}

            # HYBRID domain (code with docstrings)
            result = await svc.generate_embedding(
                "def foo():\\n  '''Docstring'''",
                domain=EmbeddingDomain.HYBRID
            )
            # {'text': [...], 'code': [...]}
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            # Return zero vector(s) with correct keys based on domain
            zero_vector = [0.0] * self.dimension
            result = {}
            if domain in (EmbeddingDomain.TEXT, EmbeddingDomain.HYBRID):
                result['text'] = zero_vector.copy()
            if domain in (EmbeddingDomain.CODE, EmbeddingDomain.HYBRID):
                result['code'] = zero_vector.copy()
            return result

        result = {}

        # EPIC-18 Fix: Use mock embeddings in mock mode
        if self._mock_mode:
            if domain in (EmbeddingDomain.TEXT, EmbeddingDomain.HYBRID):
                result['text'] = self._generate_mock_embedding(text + "_text")
            if domain in (EmbeddingDomain.CODE, EmbeddingDomain.HYBRID):
                result['code'] = self._generate_mock_embedding(text + "_code")
            return result

        if domain in (EmbeddingDomain.TEXT, EmbeddingDomain.HYBRID):
            # Generate text embedding with timeout protection
            # EPIC-12 Story 12.1: Prevent infinite hangs on large/pathological inputs
            await self._ensure_text_model()

            loop = asyncio.get_running_loop()
            encode_coro = loop.run_in_executor(
                None,
                self._encode_single_with_no_grad,
                self._text_model,
                text
            )

            try:
                text_emb = await with_timeout(
                    encode_coro,
                    timeout=get_timeout("embedding_generation_single"),
                    operation_name="embedding_generation_text_single",
                    context={"domain": "text", "text_length": len(text)},
                    raise_on_timeout=True
                )
                result['text'] = text_emb.tolist()

            except TimeoutError as e:
                logger.error(
                    f"Text embedding generation timed out after {get_timeout('embedding_generation_single')}s",
                    extra={"text_length": len(text), "error": str(e)}
                )
                raise

        if domain in (EmbeddingDomain.CODE, EmbeddingDomain.HYBRID):
            # Generate code embedding with timeout protection
            # EPIC-12 Story 12.1: Prevent infinite hangs on large/pathological inputs
            await self._ensure_code_model()

            loop = asyncio.get_running_loop()
            encode_coro = loop.run_in_executor(
                None,
                self._encode_single_with_no_grad,
                self._code_model,
                text
            )

            try:
                code_emb = await with_timeout(
                    encode_coro,
                    timeout=get_timeout("embedding_generation_single"),
                    operation_name="embedding_generation_code_single",
                    context={"domain": "code", "text_length": len(text)},
                    raise_on_timeout=True
                )
                result['code'] = code_emb.tolist()

            except TimeoutError as e:
                logger.error(
                    f"Code embedding generation timed out after {get_timeout('embedding_generation_single')}s",
                    extra={"text_length": len(text), "error": str(e)}
                )
                raise

        return result

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        domain: EmbeddingDomain = EmbeddingDomain.TEXT,
        show_progress_bar: bool = True
    ) -> List[Dict[str, List[float]]]:
        """
        Generate embeddings for multiple texts in a single batch (MUCH faster).

        Args:
            texts: List of texts/code to embed
            domain: TEXT (text model), CODE (code model), HYBRID (both)
            show_progress_bar: Show tqdm progress bar

        Returns:
            List of dicts with keys 'text' and/or 'code' containing embeddings

        Example:
            >>> texts = ["Hello", "World", "Test"]
            >>> results = await svc.generate_embeddings_batch(texts, domain=EmbeddingDomain.TEXT)
            >>> # [{'text': [...]}, {'text': [...]}, {'text': [...]}]
        """
        if not texts:
            return []

        # Filter empty texts
        valid_indices = [i for i, t in enumerate(texts) if t and t.strip()]
        valid_texts = [texts[i] for i in valid_indices]

        if not valid_texts:
            # All texts empty - return zero vectors
            zero_vector = [0.0] * self.dimension
            results = []
            for _ in texts:
                result = {}
                if domain in (EmbeddingDomain.TEXT, EmbeddingDomain.HYBRID):
                    result['text'] = zero_vector.copy()
                if domain in (EmbeddingDomain.CODE, EmbeddingDomain.HYBRID):
                    result['code'] = zero_vector.copy()
                results.append(result)
            return results

        # Generate embeddings for all valid texts at once
        results = [None] * len(texts)

        # EPIC-18 Fix: Use mock embeddings in mock mode
        if self._mock_mode:
            for i, text in enumerate(texts):
                if text and text.strip():
                    result = {}
                    if domain in (EmbeddingDomain.TEXT, EmbeddingDomain.HYBRID):
                        result['text'] = self._generate_mock_embedding(text + "_text")
                    if domain in (EmbeddingDomain.CODE, EmbeddingDomain.HYBRID):
                        result['code'] = self._generate_mock_embedding(text + "_code")
                    results[i] = result
                else:
                    # Empty text - use zero vector
                    zero_vector = [0.0] * self.dimension
                    result = {}
                    if domain in (EmbeddingDomain.TEXT, EmbeddingDomain.HYBRID):
                        result['text'] = zero_vector.copy()
                    if domain in (EmbeddingDomain.CODE, EmbeddingDomain.HYBRID):
                        result['code'] = zero_vector.copy()
                    results[i] = result
            return results

        if domain in (EmbeddingDomain.TEXT, EmbeddingDomain.HYBRID):
            # Batch encode with TEXT model with timeout protection
            # EPIC-12 Story 12.1: Prevent infinite hangs on large batches
            await self._ensure_text_model()

            loop = asyncio.get_running_loop()
            encode_coro = loop.run_in_executor(
                None,
                lambda: self._text_model.encode(
                    valid_texts,
                    show_progress_bar=show_progress_bar,
                    convert_to_numpy=True
                )
            )

            try:
                text_embeddings = await with_timeout(
                    encode_coro,
                    timeout=get_timeout("embedding_generation_batch"),
                    operation_name="embedding_generation_text_batch",
                    context={"domain": "text", "batch_size": len(valid_texts)},
                    raise_on_timeout=True
                )

            except TimeoutError as e:
                logger.error(
                    f"Text batch embedding generation timed out after {get_timeout('embedding_generation_batch')}s",
                    extra={"batch_size": len(valid_texts), "error": str(e)}
                )
                raise

            # Distribute results back to original positions
            for i, valid_idx in enumerate(valid_indices):
                if results[valid_idx] is None:
                    results[valid_idx] = {}
                results[valid_idx]['text'] = text_embeddings[i].tolist()

        if domain in (EmbeddingDomain.CODE, EmbeddingDomain.HYBRID):
            # Batch encode with CODE model with timeout protection
            # EPIC-12 Story 12.1: Prevent infinite hangs on large batches
            await self._ensure_code_model()

            loop = asyncio.get_running_loop()
            encode_coro = loop.run_in_executor(
                None,
                lambda: self._code_model.encode(
                    valid_texts,
                    show_progress_bar=show_progress_bar,
                    convert_to_numpy=True
                )
            )

            try:
                code_embeddings = await with_timeout(
                    encode_coro,
                    timeout=get_timeout("embedding_generation_batch"),
                    operation_name="embedding_generation_code_batch",
                    context={"domain": "code", "batch_size": len(valid_texts)},
                    raise_on_timeout=True
                )

            except TimeoutError as e:
                logger.error(
                    f"Code batch embedding generation timed out after {get_timeout('embedding_generation_batch')}s",
                    extra={"batch_size": len(valid_texts), "error": str(e)}
                )
                raise

            # Distribute results back to original positions
            for i, valid_idx in enumerate(valid_indices):
                if results[valid_idx] is None:
                    results[valid_idx] = {}
                results[valid_idx]['code'] = code_embeddings[i].tolist()

        # Fill empty positions with zero vectors
        zero_vector = [0.0] * self.dimension
        for i, result in enumerate(results):
            if result is None:
                result = {}
                if domain in (EmbeddingDomain.TEXT, EmbeddingDomain.HYBRID):
                    result['text'] = zero_vector.copy()
                if domain in (EmbeddingDomain.CODE, EmbeddingDomain.HYBRID):
                    result['code'] = zero_vector.copy()
                results[i] = result

        return results

    async def generate_embedding_legacy(self, text: str) -> List[float]:
        """
        Backward compatible method (returns text embedding only).

        Used by existing EventService, MemorySearchService, etc.
        Ensures zero breaking changes for existing code.

        Args:
            text: Text to embed

        Returns:
            Text embedding (list of floats)

        Example:
            >>> # Old API still works
            >>> embedding = await service.generate_embedding_legacy("Hello")
            >>> assert isinstance(embedding, list)
            >>> assert len(embedding) == 768
        """
        result = await self.generate_embedding(text, domain=EmbeddingDomain.TEXT)
        return result['text']

    async def compute_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        # Convert to numpy arrays
        emb1 = np.array(embedding1)
        emb2 = np.array(embedding2)

        # Compute cosine similarity
        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)

        # Clip to [0, 1] range
        return float(np.clip(similarity, 0.0, 1.0))

    def get_ram_usage_mb(self) -> Dict[str, float]:
        """
        Get current RAM usage in MB.

        Returns:
            Dict with process RAM and model estimates

        Example:
            >>> ram = service.get_ram_usage_mb()
            >>> print(ram)
            {
                'process_rss_mb': 850.5,
                'process_vms_mb': 2048.3,
                'text_model_loaded': True,
                'code_model_loaded': True,
                'estimated_models_mb': 660.0
            }
        """
        process = psutil.Process()
        mem_info = process.memory_info()

        return {
            "process_rss_mb": mem_info.rss / 1024 / 1024,
            "process_vms_mb": mem_info.vms / 1024 / 1024,
            "text_model_loaded": self._text_model is not None,
            "code_model_loaded": self._code_model is not None,
            "estimated_models_mb": (
                (260 if self._text_model else 0) +
                (400 if self._code_model else 0)
            )
        }

    def get_stats(self) -> dict:
        """
        Return service statistics.

        Returns:
            Dict with model info and RAM usage

        Example:
            >>> stats = service.get_stats()
            >>> print(stats['text_model_name'])
            'nomic-ai/nomic-embed-text-v1.5'
        """
        ram_usage = self.get_ram_usage_mb()

        return {
            "text_model_name": self.text_model_name,
            "code_model_name": self.code_model_name,
            "dimension": self.dimension,
            "device": self.device,
            "text_model_loaded": self._text_model is not None,
            "code_model_loaded": self._code_model is not None,
            **ram_usage
        }

    def force_memory_cleanup(self):
        """
        Force PyTorch and Python garbage collection.

        Call this after processing each file to ensure memory is released.
        Particularly important when processing many files sequentially.
        """
        import gc

        # Force Python garbage collection
        gc.collect()

        # Clear CUDA cache if using GPU
        if TORCH_AVAILABLE and torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()
