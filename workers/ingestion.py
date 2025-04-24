import os
import asyncio
import signal
import json
import time
import structlog
import psycopg2
from psycopg2.extras import Json, DictCursor
import httpx
import asyncpg
from datetime import datetime
import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import rich
from rich.console import Console
from rich.panel import Panel

# Set up console for nice output
console = Console()

# Configure logger
logger = structlog.get_logger()

# Environment variables
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "mnemo")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mnemopass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "mnemolite")

CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = os.getenv("CHROMA_PORT", "8000")

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Configure structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Setup signal handler for graceful shutdown
class GracefulExit:
    def __init__(self):
        self.exit = False
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, sig, frame):
        logger.info("shutdown_signal_received", signal=sig)
        self.exit = True

# ChromaDB client
class ChromaClient:
    def __init__(self):
        self.client = chromadb.HttpClient(host=CHROMA_HOST, port=int(CHROMA_PORT))
        self.collection_name = "memories"
        self.collection = None
        self.setup_collection()
        
    def setup_collection(self):
        try:
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Memories collection for MnemoLite"}
            )
            logger.info("chromadb_collection_ready", collection=self.collection_name)
        except Exception as e:
            logger.error("chromadb_setup_error", error=str(e))
            raise e
    
    def upsert(self, id, embedding, metadata=None):
        try:
            metadata = metadata or {}
            # ChromaDB expects string IDs
            self.collection.upsert(
                ids=[str(id)],
                embeddings=[embedding],
                metadatas=[metadata]
            )
            logger.info("chromadb_upsert_success", id=str(id))
            return True
        except Exception as e:
            logger.error("chromadb_upsert_error", id=str(id), error=str(e))
            return False
    
    def delete(self, id):
        try:
            self.collection.delete(ids=[str(id)])
            logger.info("chromadb_delete_success", id=str(id))
            return True
        except Exception as e:
            logger.error("chromadb_delete_error", id=str(id), error=str(e))
            return False

# Database connection with retry
@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=60))
def get_pg_connection():
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB,
            cursor_factory=DictCursor
        )
        conn.autocommit = False  # Manually manage transactions
        logger.info("postgres_connection_established")
        return conn
    except Exception as e:
        logger.error("postgres_connection_error", error=str(e))
        raise e

# Class for generating embeddings
class EmbeddingGenerator:
    def __init__(self):
        self.model = None
        self.load_model()
    
    def load_model(self):
        try:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("embedding_model_loaded")
        except Exception as e:
            logger.error("embedding_model_loading_error", error=str(e))
            raise e
    
    def generate(self, text):
        try:
            if not text or len(text.strip()) == 0:
                # Return a zero vector for empty text
                return [0.0] * 384  # Default dimension for all-MiniLM-L6-v2
            
            embedding = self.model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error("embedding_generation_error", error=str(e))
            raise e

# Main worker class
class IngestionWorker:
    def __init__(self):
        self.chroma_client = ChromaClient()
        self.exit_handler = GracefulExit()
        self.embedding_generator = EmbeddingGenerator()
        self.poll_interval = 5  # seconds
        self.batch_size = 50
        self.create_outbox_table_if_not_exists()
        
    def create_outbox_table_if_not_exists(self):
        """Create outbox table if it doesn't exist yet."""
        try:
            conn = get_pg_connection()
            cur = conn.cursor()
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chroma_outbox (
                    id UUID PRIMARY KEY,
                    content TEXT NOT NULL,
                    op_type VARCHAR(10) NOT NULL,
                    metadata JSONB,
                    embedding JSONB,
                    retry_count INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            conn.commit()
            logger.info("outbox_table_checked")
            cur.close()
            conn.close()
        except Exception as e:
            logger.error("outbox_table_check_error", error=str(e))
    
    def process_outbox_batch(self):
        """Process a batch of items from the outbox table."""
        try:
            conn = get_pg_connection()
            cur = conn.cursor()
            
            # Get items to process
            cur.execute("""
                SELECT id, content, op_type, metadata, embedding, retry_count 
                FROM chroma_outbox
                WHERE retry_count < 3
                ORDER BY created_at ASC
                LIMIT %s
            """, (self.batch_size,))
            
            items = cur.fetchall()
            
            if not items:
                logger.debug("no_items_to_process")
                cur.close()
                conn.close()
                return 0
            
            processed_count = 0
            
            for item in items:
                id = item["id"]
                op_type = item["op_type"]
                
                try:
                    if op_type == "upsert":
                        # Generate embedding if not already present
                        embedding = item["embedding"]
                        if not embedding:
                            embedding = self.embedding_generator.generate(item["content"])
                        
                        # Upsert to ChromaDB
                        success = self.chroma_client.upsert(
                            id, 
                            embedding, 
                            item["metadata"] or {}
                        )
                        
                        if success:
                            # Remove from outbox
                            cur.execute(
                                "DELETE FROM chroma_outbox WHERE id = %s", (id,)
                            )
                            processed_count += 1
                        else:
                            # Increment retry count
                            cur.execute(
                                "UPDATE chroma_outbox SET retry_count = retry_count + 1 WHERE id = %s", 
                                (id,)
                            )
                    
                    elif op_type == "delete":
                        # Delete from ChromaDB
                        success = self.chroma_client.delete(id)
                        
                        if success:
                            # Remove from outbox
                            cur.execute(
                                "DELETE FROM chroma_outbox WHERE id = %s", (id,)
                            )
                            processed_count += 1
                        else:
                            # Increment retry count
                            cur.execute(
                                "UPDATE chroma_outbox SET retry_count = retry_count + 1 WHERE id = %s", 
                                (id,)
                            )
                    
                    conn.commit()
                    logger.info("item_processed", id=str(id), op_type=op_type)
                
                except Exception as e:
                    conn.rollback()
                    logger.error("item_processing_error", id=str(id), op_type=op_type, error=str(e))
                    # Increment retry count
                    cur.execute(
                        "UPDATE chroma_outbox SET retry_count = retry_count + 1 WHERE id = %s", 
                        (id,)
                    )
                    conn.commit()
            
            cur.close()
            conn.close()
            return processed_count
        
        except Exception as e:
            logger.error("batch_processing_error", error=str(e))
            return 0
    
    def listen_for_notifications(self):
        """Listen for database notifications when new items are added to the outbox."""
        try:
            # This is a placeholder for a future implementation
            # For now, we'll just use polling
            pass
        except Exception as e:
            logger.error("notification_listener_error", error=str(e))
    
    def run(self):
        """Main execution loop."""
        console.print(Panel.fit(
            "🔄 [bold green]Ingestion Worker Started[/bold green]\n"
            f"Connected to ChromaDB at {CHROMA_HOST}:{CHROMA_PORT}\n"
            f"Connected to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT}\n"
            "Processing outbox items...",
            title="MnemoLite Ingestion Worker"
        ))
        
        logger.info("worker_started")
        
        while not self.exit_handler.exit:
            try:
                processed_count = self.process_outbox_batch()
                if processed_count > 0:
                    logger.info("batch_processed", count=processed_count)
                    console.print(f"✅ Processed {processed_count} items")
                
                # Wait before processing the next batch
                time.sleep(self.poll_interval)
            
            except Exception as e:
                logger.error("worker_execution_error", error=str(e))
                console.print(f"❌ [bold red]Error:[/bold red] {str(e)}")
                # Wait before retrying
                time.sleep(self.poll_interval * 2)
        
        logger.info("worker_stopping")
        console.print("[bold yellow]Worker shutting down gracefully...[/bold yellow]")

def main():
    # Create and run the worker
    worker = IngestionWorker()
    
    try:
        # Create worker log file to signal health checks
        with open("/app/logs/worker.log", "w") as f:
            f.write(f"Worker started at {datetime.now().isoformat()}\n")
        
        worker.run()
    except Exception as e:
        logger.error("worker_fatal_error", error=str(e))
        console.print(f"[bold red]Fatal error:[/bold red] {str(e)}")
    finally:
        logger.info("worker_shutdown_complete")
        console.print("[bold green]Worker shutdown complete[/bold green]")

if __name__ == "__main__":
    main() 