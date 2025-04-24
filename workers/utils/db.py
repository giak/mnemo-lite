"""
Database utilities for PostgreSQL connections
"""
import os
import asyncpg
import psycopg2
from psycopg2.extras import DictCursor
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog
from typing import Optional

from config.settings import Settings

# Configuration du logger
logger = structlog.get_logger(__name__)

# Récupération des variables d'environnement
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "mnemo")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mnemopass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "mnemolite")

settings = Settings()

# Global connection pool
_pool: Optional[asyncpg.Pool] = None

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=60))
async def get_pg_pool() -> asyncpg.Pool:
    """Get or create a PostgreSQL connection pool"""
    global _pool
    
    if _pool is None or _pool.closed:
        logger.info("Creating PostgreSQL connection pool")
        
        try:
            _pool = await asyncpg.create_pool(
                host=settings.postgres_host,
                port=settings.postgres_port,
                user=settings.postgres_user,
                password=settings.postgres_password,
                database=settings.postgres_db
            )
            
            # Test connection
            async with _pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                logger.info("PostgreSQL connection pool created", version=version)
        except Exception as e:
            logger.error("Failed to create PostgreSQL connection pool", error=str(e))
            raise
    
    return _pool

async def close_pg_pool() -> None:
    """Close the PostgreSQL connection pool"""
    global _pool
    
    if _pool:
        logger.info("Closing PostgreSQL connection pool")
        await _pool.close()
        _pool = None

async def execute_transaction(queries):
    """Execute multiple queries in a single transaction"""
    pool = await get_pg_pool()
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            results = []
            for query, *args in queries:
                result = await conn.execute(query, *args)
                results.append(result)
            return results

async def fetch_one(query, *args):
    """Fetch a single row from the database"""
    pool = await get_pg_pool()
    
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)

async def fetch_all(query, *args):
    """Fetch all rows from the database"""
    pool = await get_pg_pool()
    
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)

async def execute(query, *args):
    """Execute a query"""
    pool = await get_pg_pool()
    
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)

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

async def get_db_pool() -> asyncpg.Pool:
    """Get or create a connection pool to PostgreSQL"""
    global _pool
    
    if _pool is None:
        logger.info("Creating database connection pool")
        
        _pool = await asyncpg.create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            database=settings.postgres_db,
            min_size=5,
            max_size=20
        )
        
        logger.info("Database connection pool created")
        
        # Ensure pgmq extension is available
        async with _pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pgmq;")
    
    return _pool

async def close_db_pool() -> None:
    """Close the database connection pool"""
    global _pool
    
    if _pool is not None:
        logger.info("Closing database connection pool")
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed") 