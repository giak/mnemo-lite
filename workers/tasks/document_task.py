"""
Document chunking task handler
"""
import json
import structlog
import uuid
from typing import Dict, Any, List, Tuple

from utils.db import execute, execute_transaction
from utils.redis_utils import publish_message
from config.settings import Settings

logger = structlog.get_logger(__name__)
settings = Settings()

class TaskHandler:
    def __init__(self):
        pass
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        """Split text into overlapping chunks"""
        if not text or len(text) <= chunk_size:
            return [text] if text else []
            
        chunks = []
        start = 0
        
        while start < len(text):
            # Get the chunk
            end = min(start + chunk_size, len(text))
            
            # If we're not at the end, try to find a good break point
            if end < len(text):
                # Look for newline or period within the last 20% of the chunk
                lookback_range = int(chunk_size * 0.2)
                best_break = end
                
                # Look for paragraph break first
                for i in range(end, max(end - lookback_range, start), -1):
                    if text[i-1:i+1] == '\n\n':
                        best_break = i
                        break
                
                # If no paragraph break, look for a newline
                if best_break == end:
                    for i in range(end, max(end - lookback_range, start), -1):
                        if text[i-1:i] == '\n':
                            best_break = i
                            break
                
                # If no newline, look for a period followed by space
                if best_break == end:
                    for i in range(end, max(end - lookback_range, start), -1):
                        if i < len(text)-1 and text[i-1:i+1] in ['. ', '? ', '! ']:
                            best_break = i
                            break
                
                end = best_break
            
            # Add the chunk
            chunks.append(text[start:end])
            
            # Move start position for next chunk, considering overlap
            start = max(start + 1, end - overlap)
        
        return chunks
    
    def create_chunk_metadata(self, doc_id: str, index: int, total: int, 
                             doc_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create metadata for a chunk"""
        metadata = {
            "doc_id": doc_id,
            "chunk_index": index,
            "total_chunks": total,
        }
        
        # Add document metadata if available
        if doc_metadata:
            for key, value in doc_metadata.items():
                if key not in metadata:
                    metadata[key] = value
        
        return metadata
    
    async def save_chunks_to_outbox(self, chunks: List[str], doc_id: str, 
                                   doc_metadata: Dict[str, Any]) -> List[str]:
        """Save chunks to the chroma outbox table"""
        chunk_ids = []
        queries = []
        
        for i, chunk in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            chunk_ids.append(chunk_id)
            
            metadata = self.create_chunk_metadata(doc_id, i, len(chunks), doc_metadata)
            
            queries.append((
                """
                INSERT INTO chroma_outbox (id, content, op_type, metadata)
                VALUES ($1, $2, $3, $4)
                """,
                chunk_id, chunk, "upsert", json.dumps(metadata)
            ))
        
        # Execute all inserts in a transaction
        if queries:
            await execute_transaction(queries)
            logger.info("chunks_saved_to_outbox", count=len(chunks), doc_id=doc_id)
        
        return chunk_ids
    
    async def process(self, content: Dict[str, Any]) -> bool:
        """Process a document chunking task"""
        try:
            task_id = content.get("id")
            logger.info("processing_document_task", task_id=task_id)
            
            # Extract data from the content
            document = content.get("document")
            doc_id = content.get("doc_id")
            metadata = content.get("metadata", {})
            chunk_size = content.get("chunk_size", 500)
            chunk_overlap = content.get("chunk_overlap", 100)
            
            if not document or not doc_id:
                logger.error("invalid_document_task", task_id=task_id, reason="missing document or document ID")
                return False
            
            # Chunk the document
            chunks = self.chunk_text(document, chunk_size=chunk_size, overlap=chunk_overlap)
            
            if not chunks:
                logger.warning("empty_document", task_id=task_id, doc_id=doc_id)
                # Notify that processing is complete but no chunks were created
                await publish_message(
                    "document_processing_complete", 
                    json.dumps({"task_id": task_id, "doc_id": doc_id, "chunk_count": 0})
                )
                return True
            
            # Save chunks to outbox
            chunk_ids = await self.save_chunks_to_outbox(chunks, doc_id, metadata)
            
            # Notify that processing is complete
            await publish_message(
                "document_processing_complete", 
                json.dumps({
                    "task_id": task_id, 
                    "doc_id": doc_id, 
                    "chunk_count": len(chunks),
                    "chunk_ids": chunk_ids
                })
            )
            
            logger.info("document_processing_completed", task_id=task_id, doc_id=doc_id, chunk_count=len(chunks))
            return True
            
        except Exception as e:
            logger.error("document_processing_error", error=str(e))
            # Notify of failure via Redis
            if content and content.get("id"):
                await publish_message(
                    "document_processing_complete", 
                    json.dumps({
                        "task_id": content.get("id"), 
                        "doc_id": content.get("doc_id", "unknown"), 
                        "success": False, 
                        "error": str(e)
                    })
                )
            return False 