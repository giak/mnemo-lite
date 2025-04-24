"""
Embedding generation task handler
"""
import json
import structlog
from typing import Dict, Any, List
from sentence_transformers import SentenceTransformer

from utils.chromadb import store_embeddings, get_collection
from utils.redis_utils import publish_message
from config.settings import Settings

logger = structlog.get_logger(__name__)
settings = Settings()

class TaskHandler:
    def __init__(self):
        self.model = None
        self.load_model()
    
    def load_model(self):
        """Load the sentence transformer model"""
        try:
            self.model = SentenceTransformer(settings.embedding_model)
            logger.info("embedding_model_loaded", model=settings.embedding_model)
        except Exception as e:
            logger.error("embedding_model_loading_error", error=str(e))
            raise
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        try:
            if not texts or all(not text or len(text.strip()) == 0 for text in texts):
                # Return zero vectors for empty texts
                embedding_dim = 384  # Default dimension for all-MiniLM-L6-v2
                return [[0.0] * embedding_dim for _ in range(len(texts))]
            
            # Filter out empty texts and keep track of indices
            non_empty_texts = []
            non_empty_indices = []
            for i, text in enumerate(texts):
                if text and len(text.strip()) > 0:
                    non_empty_texts.append(text)
                    non_empty_indices.append(i)
            
            # Generate embeddings for non-empty texts
            non_empty_embeddings = self.model.encode(non_empty_texts)
            non_empty_embeddings = [embedding.tolist() for embedding in non_empty_embeddings]
            
            # Create result list with zero vectors for empty texts
            embedding_dim = len(non_empty_embeddings[0]) if non_empty_embeddings else 384
            result = [[0.0] * embedding_dim for _ in range(len(texts))]
            
            # Fill in embeddings for non-empty texts
            for i, idx in enumerate(non_empty_indices):
                result[idx] = non_empty_embeddings[i]
            
            return result
        except Exception as e:
            logger.error("embedding_generation_error", error=str(e))
            raise
    
    async def process(self, content: Dict[str, Any]) -> bool:
        """Process an embedding generation task"""
        try:
            task_id = content.get("id")
            logger.info("processing_embedding_task", task_id=task_id)
            
            # Extract data from the content
            documents = content.get("documents", [])
            metadata_list = content.get("metadata", [])
            ids = content.get("ids", [])
            collection_name = content.get("collection", "mnemo_collection")
            
            if not documents or not ids:
                logger.error("invalid_embedding_task", task_id=task_id, reason="missing documents or IDs")
                return False
            
            if len(documents) != len(ids):
                logger.error("invalid_embedding_task", task_id=task_id, reason="documents and IDs length mismatch")
                return False
            
            # Generate embeddings if not already provided
            embeddings = content.get("embeddings")
            if not embeddings:
                embeddings = self.generate_embeddings(documents)
            
            # Store in ChromaDB
            await store_embeddings(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadata_list if metadata_list else [{}] * len(ids),
                documents=documents,
                collection_name=collection_name
            )
            
            # Notify via Redis that embedding is complete
            await publish_message(
                "embedding_complete", 
                json.dumps({"task_id": task_id, "success": True})
            )
            
            logger.info("embedding_task_completed", task_id=task_id)
            return True
            
        except Exception as e:
            logger.error("embedding_task_error", error=str(e))
            # Notify of failure via Redis
            if content and content.get("id"):
                await publish_message(
                    "embedding_complete", 
                    json.dumps({"task_id": content.get("id"), "success": False, "error": str(e)})
                )
            return False 