import os
import asyncpg
import psycopg2
from psycopg2.extras import DictCursor
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog

# Configuration du logger
logger = structlog.get_logger()

# Récupération des variables d'environnement
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "mnemo")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mnemopass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "mnemolite")


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=60))
def get_pg_connection():
    """
    Établit une connexion à PostgreSQL avec des tentatives en cas d'échec.
    """
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB,
            cursor_factory=DictCursor
        )
        logger.info("postgres_connection_established")
        return conn
    except Exception as e:
        logger.error("postgres_connection_error", error=str(e))
        raise e


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=60))
async def get_asyncpg_connection():
    """
    Établit une connexion asyncpg à PostgreSQL avec des tentatives en cas d'échec.
    """
    try:
        conn = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB
        )
        logger.info("asyncpg_connection_established")
        return conn
    except Exception as e:
        logger.error("asyncpg_connection_error", error=str(e))
        raise e


def execute_query(query, params=None, fetch_one=False, fetch_all=False, commit=True):
    """
    Exécute une requête SQL et renvoie les résultats selon les options spécifiées.
    """
    conn = None
    try:
        conn = get_pg_connection()
        cur = conn.cursor()
        cur.execute(query, params or ())
        
        result = None
        if fetch_one:
            result = cur.fetchone()
        elif fetch_all:
            result = cur.fetchall()
            
        if commit:
            conn.commit()
            
        cur.close()
        conn.close()
        return result
    
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        logger.error("execute_query_error", error=str(e), query=query)
        raise e


async def execute_async_query(query, params=None, fetch_one=False, fetch_all=False):
    """
    Exécute une requête SQL de manière asynchrone et renvoie les résultats selon les options spécifiées.
    """
    conn = None
    try:
        conn = await get_asyncpg_connection()
        
        result = None
        if fetch_one:
            result = await conn.fetchrow(query, *(params or ()))
        elif fetch_all:
            result = await conn.fetch(query, *(params or ()))
        else:
            result = await conn.execute(query, *(params or ()))
            
        await conn.close()
        return result
    
    except Exception as e:
        if conn:
            await conn.close()
        logger.error("execute_async_query_error", error=str(e), query=query)
        raise e 