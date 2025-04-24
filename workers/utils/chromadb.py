"""
ChromaDB utilities for vector embeddings and storage
"""
import chromadb
import structlog
from typing import List, Dict, Any, Optional
from chromadb.config import Settings as ChromaSettings

from config.settings import Settings

logger = structlog.get_logger(__name__)
settings = Settings()

# Global ChromaDB client
_chroma_client: Optional[chromadb.Client] = None
_default_collection = None

def get_chroma_client() -> chromadb.Client:
    """Get or create a ChromaDB client"""
    global _chroma_client
    
    if _chroma_client is None:
        logger.info("Creating ChromaDB client")
        
        _chroma_client = chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
            settings=ChromaSettings(
                chroma_client_auth_provider="token" if settings.chromadb_token else None,
                chroma_client_auth_credentials=settings.chromadb_token if settings.chromadb_token else None,
            )
        )
        
        logger.info("ChromaDB client created")
    
    return _chroma_client

def get_collection(collection_name: str = "mnemo_collection"):
    """Get or create a ChromaDB collection"""
    global _default_collection
    
    client = get_chroma_client()
    
    try:
        # Try to get existing collection
        collection = client.get_collection(name=collection_name)
        logger.info("Found existing ChromaDB collection", collection=collection_name)
    except Exception:
        # Create collection if it doesn't exist
        collection = client.create_collection(
            name=collection_name,
            metadata={"description": "MnemoLite vector collection"}
        )
        logger.info("Created new ChromaDB collection", collection=collection_name)
    
    if collection_name == "mnemo_collection":
        _default_collection = collection
    
    return collection

async def store_embeddings(
    ids: List[str],
    embeddings: List[List[float]],
    metadatas: List[Dict[str, Any]],
    documents: List[str],
    collection_name: str = "mnemo_collection"
) -> None:
    """Store embeddings in ChromaDB"""
    collection = get_collection(collection_name)
    
    try:
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )
        logger.info("Stored embeddings in ChromaDB", count=len(ids), collection=collection_name)
    except Exception as e:
        logger.error("Failed to store embeddings", error=str(e), collection=collection_name)
        raise

async def query_embeddings(
    query_embedding: List[float],
    n_results: int = 5,
    collection_name: str = "mnemo_collection"
) -> Dict[str, Any]:
    """Query embeddings from ChromaDB"""
    collection = get_collection(collection_name)
    
    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        logger.info("Queried embeddings from ChromaDB", n_results=n_results, collection=collection_name)
        return results
    except Exception as e:
        logger.error("Failed to query embeddings", error=str(e), collection=collection_name)
        raise 