"""Registre central des modeles d'embedding.

Single Source of Truth pour les dimensions, backends, et prefixes.
Ajouter un nouveau modele = 1 ligne ici. Tout le reste auto-deduit.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ModelSpec:
    """Specification immuable d'un modele d'embedding."""
    name: str
    dimension: int
    backend: str = "pytorch"
    max_seq_length: int = 512
    query_prefix: str = ""
    document_prefix: str = ""
    trust_remote_code: bool = False
    supports_onnx: bool = False


KNOWN_MODELS: dict[str, ModelSpec] = {
    # BGE series (BAAI) — multilingue, dense+sparse+ColBERT
    "BAAI/bge-m3": ModelSpec(
        name="BAAI/bge-m3",
        dimension=1024,
        backend="pytorch",
        max_seq_length=8192,
        query_prefix="Represent this sentence for retrieving relevant documents: ",
        document_prefix="Represent this passage for retrieval: ",
        trust_remote_code=True,
        supports_onnx=True,
    ),

    # Nomic series — 768D
    "nomic-ai/nomic-embed-text-v1.5": ModelSpec(
        name="nomic-ai/nomic-embed-text-v1.5",
        dimension=768,
        backend="pytorch",
        max_seq_length=2048,
        trust_remote_code=True,
    ),
    "nomic-ai/nomic-embed-text-v2-moe": ModelSpec(
        name="nomic-ai/nomic-embed-text-v2-moe",
        dimension=768,
        backend="pytorch",
        max_seq_length=2048,
        trust_remote_code=True,
    ),

    # E5 series (intfloat) — multilingue
    "intfloat/multilingual-e5-base": ModelSpec(
        name="intfloat/multilingual-e5-base",
        dimension=768,
        backend="pytorch",
        max_seq_length=512,
        query_prefix="query: ",
        document_prefix="passage: ",
    ),
    "intfloat/multilingual-e5-large": ModelSpec(
        name="intfloat/multilingual-e5-large",
        dimension=1024,
        backend="pytorch",
        max_seq_length=512,
        query_prefix="query: ",
        document_prefix="passage: ",
    ),
    "intfloat/multilingual-e5-small": ModelSpec(
        name="intfloat/multilingual-e5-small",
        dimension=384,
        backend="pytorch",
        max_seq_length=512,
        query_prefix="query: ",
        document_prefix="passage: ",
    ),

    # Jina series — code + text
    "jinaai/jina-embeddings-v2-base-code": ModelSpec(
        name="jinaai/jina-embeddings-v2-base-code",
        dimension=768,
        backend="pytorch",
        max_seq_length=8192,
        trust_remote_code=True,
    ),
    "jinaai/jina-embeddings-v5-text-small": ModelSpec(
        name="jinaai/jina-embeddings-v5-text-small",
        dimension=1024,
        backend="pytorch",
        max_seq_length=8192,
    ),
    "jinaai/jina-embeddings-v5-text-nano": ModelSpec(
        name="jinaai/jina-embeddings-v5-text-nano",
        dimension=768,
        backend="pytorch",
        max_seq_length=8192,
    ),
}


def get_model_spec(model_name: str) -> Optional[ModelSpec]:
    """Recupere la spec d'un modele, ou None si inconnu."""
    return KNOWN_MODELS.get(model_name)
