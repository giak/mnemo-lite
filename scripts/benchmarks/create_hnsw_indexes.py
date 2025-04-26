"""
Creates HNSW indexes concurrently on all partitions of the 'events' table.
Assumes pg_partman has created partitions named like 'events_pYYYYMMDD'.
"""
import asyncio
import asyncpg
import os
import argparse
from datetime import datetime

# --- Configuration ---
DB_URL = os.getenv("DATABASE_URL", "postgresql://mnemo:mnemo@localhost:5432/mnemolite")
PARENT_TABLE = "public.events"
INDEX_TYPE = "hnsw"
INDEX_COLUMN = "embedding"
# HNSW parameters (adjust based on PoC tuning later)
M_PARAM = 16
EF_CONSTRUCTION_PARAM = 64
VECTOR_OPS = "vector_cosine_ops" # or vector_l2_ops, vector_ip_ops

# --- Functions ---

async def get_partitions(pool, parent_table_name, schema_name='public'):
    """Retrieves a list of partition table names for a given parent table."""
    query = """
    SELECT c.relname AS partition_name
    FROM pg_inherits i
    JOIN pg_class c ON i.inhrelid = c.oid
    JOIN pg_class p ON i.inhparent = p.oid
    JOIN pg_namespace np ON p.relnamespace = np.oid
    WHERE p.relname = $1 AND np.nspname = $2;
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, parent_table_name, schema_name)
        return [row['partition_name'] for row in rows]

async def create_index_concurrently(pool, table_name, index_name, index_type, 
                                    index_column, m, ef_construction, vector_ops):
    """Creates an index using CREATE INDEX CONCURRENTLY."""
    # Note: CONCURRENTLY cannot run inside a transaction block
    query = f"""
    CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name}
    ON public.{table_name} -- Assuming public schema
    USING {index_type} ({index_column} {vector_ops})
    WITH (m = {m}, ef_construction = {ef_construction});
    """
    print(f"Attempting to create index {index_name} on {table_name}...", end=" ", flush=True)
    start_time = datetime.now()
    async with pool.acquire() as conn:
        # Set statement_timeout to avoid blocking indefinitely if something goes wrong
        await conn.execute("SET statement_timeout = '4h'") # 4 hours timeout for index creation
        try:
            status = await conn.execute(query)
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"Done. Status: {status}. Time: {elapsed:.2f}s")
            return True
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"Failed! Error: {e}. Time: {elapsed:.2f}s")
            # IF EXISTS was used, so errors might be less common unless it's a syntax issue
            # or a fundamental problem (like wrong column name).
            return False
        finally:
            # Reset timeout just in case connection is reused
            await conn.execute("SET statement_timeout = 0") 

# --- Main Execution ---

async def main(parent_table_schema, parent_table_base_name):
    """Main function to find partitions and create indexes."""
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5) # Index creation is heavy, less concurrency
    print(f"Connected to database. Finding partitions for {parent_table_schema}.{parent_table_base_name}...")
    
    parent_full_name = f"{parent_table_schema}.{parent_table_base_name}"

    try:
        partitions = await get_partitions(pool, parent_table_base_name, parent_table_schema)
        if not partitions:
            print("No partitions found.")
            return

        print(f"Found {len(partitions)} partitions. Creating HNSW indexes...")

        overall_start_time = datetime.now()
        success_count = 0
        fail_count = 0

        for partition_name in partitions:
            # Construct a unique index name
            # Example: ix_events_p20240101_embedding_hnsw
            index_name = f"ix_{partition_name}_{INDEX_COLUMN}_{INDEX_TYPE}"
            
            success = await create_index_concurrently(
                pool,
                partition_name,
                index_name,
                INDEX_TYPE,
                INDEX_COLUMN,
                M_PARAM,
                EF_CONSTRUCTION_PARAM,
                VECTOR_OPS
            )
            if success:
                success_count += 1
            else:
                fail_count += 1
        
        overall_elapsed = (datetime.now() - overall_start_time).total_seconds()
        print(f"\nIndex creation process finished.")
        print(f"Successful: {success_count}, Failed: {fail_count}")
        print(f"Total time: {overall_elapsed:.2f} seconds")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        await pool.close()
        print("Disconnected from database.")


if __name__ == "__main__":
    # Assuming parent table is always public.events for now
    # Could add arguments later if needed
    asyncio.run(main(parent_table_schema='public', parent_table_base_name='events')) 