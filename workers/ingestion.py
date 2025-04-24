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

# Configuration du logger
logger = structlog.get_logger()

# Récupération des variables d'environnement
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "mnemo")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mnemopass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "mnemolite")

CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = os.getenv("CHROMA_PORT", "8000")

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Configuration du logger
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Client ChromaDB
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
            # Conversion en str car ChromaDB attend des strings pour les IDs
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


# Connexion à la base de données PostgreSQL avec retry
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
        conn.autocommit = False  # Nous gérons manuellement les transactions
        logger.info("postgres_connection_established")
        return conn
    except Exception as e:
        logger.error("postgres_connection_error", error=str(e))
        raise e


# Gestionnaire d'interruption pour arrêt propre
class GracefulExit:
    def __init__(self):
        self.exit = False
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, sig, frame):
        logger.info("shutdown_signal_received", signal=sig)
        self.exit = True


# Classe principale du worker
class OutboxProcessor:
    def __init__(self):
        self.chroma_client = ChromaClient()
        self.exit_handler = GracefulExit()
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def get_embedding(self, text):
        """
        Méthode simulée pour générer un embedding en utilisant un service externe.
        En production, remplacez cette implémentation par un appel à un API d'embedding.
        """
        try:
            # Simulation d'un embedding aléatoire
            # À remplacer par un vrai appel API en production
            embedding = np.random.rand(1536).tolist()
            return embedding
        except Exception as e:
            logger.error("embedding_generation_error", error=str(e))
            raise e
    
    def process_outbox_item(self, item, conn, cur):
        """
        Traite un élément de l'outbox et synchronise avec ChromaDB.
        """
        try:
            id = item["id"]
            op_type = item["op_type"]
            
            if op_type == "upsert":
                embedding = item["embedding"]
                if embedding:
                    # Récupérer les métadonnées de l'événement
                    cur.execute(
                        "SELECT event_type, memory_type, role_id, metadata FROM events WHERE id = %s", 
                        (id,)
                    )
                    event_data = cur.fetchone()
                    
                    if event_data:
                        metadata = {
                            "event_type": event_data["event_type"],
                            "memory_type": event_data["memory_type"],
                            "role_id": str(event_data["role_id"]),
                            **(event_data["metadata"] or {})
                        }
                        
                        # Upsert dans ChromaDB
                        success = self.chroma_client.upsert(id, embedding, metadata)
                        
                        if success:
                            # Supprimer de l'outbox en cas de succès
                            cur.execute(
                                "DELETE FROM chroma_outbox WHERE id = %s", 
                                (id,)
                            )
                            conn.commit()
                            logger.info("outbox_item_processed", id=str(id), operation="upsert")
                        else:
                            # Incrémenter le compteur d'essais
                            cur.execute(
                                "UPDATE chroma_outbox SET retry_count = retry_count + 1 WHERE id = %s", 
                                (id,)
                            )
                            conn.commit()
                            logger.warning("outbox_item_retry", id=str(id), operation="upsert")
                    else:
                        # L'événement n'existe pas ou plus
                        cur.execute(
                            "DELETE FROM chroma_outbox WHERE id = %s", 
                            (id,)
                        )
                        conn.commit()
                        logger.warning("outbox_item_orphaned", id=str(id))
                else:
                    # Pas d'embedding disponible pour cet élément
                    cur.execute(
                        "UPDATE chroma_outbox SET retry_count = retry_count + 1 WHERE id = %s", 
                        (id,)
                    )
                    conn.commit()
                    logger.warning("outbox_item_missing_embedding", id=str(id))
            
            elif op_type == "delete":
                # Supprimer de ChromaDB
                success = self.chroma_client.delete(id)
                
                if success or item["retry_count"] >= 3:
                    # Supprimer de l'outbox en cas de succès ou après trop d'essais
                    cur.execute(
                        "DELETE FROM chroma_outbox WHERE id = %s", 
                        (id,)
                    )
                    conn.commit()
                    logger.info("outbox_item_processed", id=str(id), operation="delete")
                else:
                    # Incrémenter le compteur d'essais
                    cur.execute(
                        "UPDATE chroma_outbox SET retry_count = retry_count + 1 WHERE id = %s", 
                        (id,)
                    )
                    conn.commit()
                    logger.warning("outbox_item_retry", id=str(id), operation="delete")
            
            return True
        
        except Exception as e:
            conn.rollback()
            logger.error("outbox_processing_error", id=str(item["id"]), error=str(e))
            return False
    
    def process_outbox(self):
        """
        Traite les éléments en attente dans l'outbox.
        """
        try:
            conn = get_pg_connection()
            cur = conn.cursor()
            
            # Récupérer les éléments à traiter, limités à 50 à la fois
            cur.execute(
                """
                SELECT id, embedding, op_type, retry_count 
                FROM chroma_outbox 
                WHERE retry_count < 3
                ORDER BY created_at ASC
                LIMIT 50
                """
            )
            
            items = cur.fetchall()
            if items:
                logger.info("processing_outbox_batch", count=len(items))
                
                for item in items:
                    if self.exit_handler.exit:
                        break
                    
                    self.process_outbox_item(item, conn, cur)
            
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error("outbox_batch_processing_error", error=str(e))
            if 'conn' in locals() and conn:
                try:
                    conn.rollback()
                    conn.close()
                except:
                    pass
    
    def listen_for_notifications(self):
        """
        Écoute les notifications de la base de données pour traiter les nouveaux éléments.
        """
        try:
            logger.info("starting_notification_listener")
            
            conn = get_pg_connection()
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            cur = conn.cursor()
            
            cur.execute("LISTEN outbox_new")
            
            logger.info("notification_listener_ready")
            
            while not self.exit_handler.exit:
                if select.select([conn], [], [], 5) == ([], [], []):
                    # Timeout
                    continue
                
                conn.poll()
                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    logger.debug("notification_received", channel=notify.channel)
                    self.process_outbox()
            
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error("notification_listener_error", error=str(e))
            raise e
    
    def run(self):
        """
        Démarre le processeur d'outbox principal.
        """
        logger.info("ingestion_worker_starting", environment=ENVIRONMENT)
        
        import select
        
        try:
            # Traitement initial
            self.process_outbox()
            
            # Démarrage de l'écouteur de notifications
            self.listen_for_notifications()
            
        except Exception as e:
            logger.error("ingestion_worker_error", error=str(e))
        
        finally:
            logger.info("ingestion_worker_stopped")


if __name__ == "__main__":
    processor = OutboxProcessor()
    processor.run() 