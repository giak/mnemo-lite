"""
Runs KNN benchmark queries against the partitioned 'events' table.
"""
import asyncio
import asyncpg
import os
import argparse
import numpy as np
import time
from datetime import timedelta
from pgvector.utils import from_db, to_db

# --- Configuration ---
DB_URL = os.getenv("DATABASE_URL", "postgresql://mnemo:mnemo@localhost:5432/mnemolite")
TABLE_NAME = "public.events"
EMBEDDING_DIMENSION = 1536 # Assuming OpenAI embeddings

# --- Functions ---

async def fetch_sample_vectors(pool, count=100):
    """Fetches a few existing vectors from the DB to use as query vectors."""
    # Select embedding directly, pgvector handles parsing
    query = f"SELECT embedding FROM {TABLE_NAME} TABLESAMPLE SYSTEM (1) LIMIT {count};"
    # TABLESAMPLE SYSTEM(1) gets approx 1% of rows, then LIMIT
    # Adjust sampling percentage if needed for performance/representativeness
    print(f"Fetching up to {count} sample vectors for queries...")
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)
        if not rows:
            print("Warning: Could not fetch sample vectors. Falling back to random.")
            # Generate random vectors if table is empty or sampling failed
            return [np.random.rand(EMBEDDING_DIMENSION).astype(np.float32) for _ in range(count)] 
        print(f"Fetched {len(rows)} sample vectors.")
        # Placeholder: return random if conversion logic is complex
        # TODO: Implement proper conversion from memoryview/bytea if needed
        # Use pgvector.utils.from_db to parse the string representation
        return [from_db(row['embedding']) for row in rows]
        # return [np.random.rand(EMBEDDING_DIMENSION).astype(np.float32) for _ in range(len(rows))] 

async def run_knn_query(pool, query_vector, k, ef_search=None):
    """Runs a single KNN query and returns the latency."""
    query = f"""
    SELECT id, timestamp 
    FROM {TABLE_NAME} 
    ORDER BY embedding <=> $1::vector -- Ensure type casting
    LIMIT $2;
    """
    
    start_time = time.monotonic()
    async with pool.acquire()as conn:
        # Set ef_search for this transaction if provided
        if ef_search:
            await conn.execute(f"SET LOCAL hnsw.ef_search = {ef_search};")
        
        # Prepare statement might be beneficial if running many queries
        # stmt = await conn.prepare(query)
        # results = await stmt.fetch(query_vector, k)
        # Convert numpy array back to string format for query parameter
        results = await conn.fetch(query, to_db(query_vector), k)
        
        # Optionally reset local setting if needed, but connection release handles it
        # if ef_search:
        #     await conn.execute("RESET hnsw.ef_search;")
            
    end_time = time.monotonic()
    return end_time - start_time, results # Return latency and results (optional)

# --- Main Execution ---

async def main(num_queries, k_neighbors, ef_search):
    """Main function to run the benchmark."""
    pool = await asyncpg.create_pool(DB_URL, min_size=5, max_size=10)
    print(f"Connected to database. Preparing for {num_queries} queries (k={k_neighbors})...")
    if ef_search:
        print(f"Using hnsw.ef_search = {ef_search}")

    try:
        query_vectors = await fetch_sample_vectors(pool, count=max(100, num_queries // 10)) # Fetch enough samples
        if not query_vectors:
             print("Error: No query vectors available. Exiting.")
             return

        latencies = []
        print("Starting benchmark...")
        overall_start_time = time.monotonic()

        for i in range(num_queries):
            # Cycle through sample vectors
            vector_to_query = query_vectors[i % len(query_vectors)]
            
            latency, _ = await run_knn_query(pool, vector_to_query, k_neighbors, ef_search)
            latencies.append(latency)
            
            # Optional: Print progress
            if (i + 1) % (num_queries // 10) == 0:
                 print(f"  Completed {i+1}/{num_queries} queries...")

        overall_end_time = time.monotonic()
        overall_duration = overall_end_time - overall_start_time
        print("Benchmark finished.")

        # --- Calculate Statistics ---
        if not latencies:
            print("No queries were run.")
            return

        latencies_ms = [l * 1000 for l in latencies] # Convert to milliseconds
        avg_latency = np.mean(latencies_ms)
        p95_latency = np.percentile(latencies_ms, 95)
        p99_latency = np.percentile(latencies_ms, 99)
        qps = num_queries / overall_duration if overall_duration > 0 else float('inf')

        print("\n--- Benchmark Results ---")
        print(f"Total Queries: {num_queries}")
        print(f"K-Neighbors:   {k_neighbors}")
        print(f"ef_search:     {ef_search if ef_search else 'Default'}")
        print(f"Total Time:    {overall_duration:.3f} seconds")
        print(f"QPS:           {qps:.2f}")
        print(f"Avg Latency:   {avg_latency:.2f} ms")
        print(f"P95 Latency:   {p95_latency:.2f} ms")
        print(f"P99 Latency:   {p99_latency:.2f} ms")

    except Exception as e:
        print(f"\nAn error occurred during the benchmark: {e}")
    finally:
        await pool.close()
        print("Disconnected from database.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run KNN benchmark on 'events' table.")
    parser.add_argument("-n", "--num-queries", type=int, default=1000, help="Number of queries to run.")
    parser.add_argument("-k", "--k-neighbors", type=int, default=10, help="Number of nearest neighbors (K).")
    parser.add_argument("--ef-search", type=int, default=None, help="HNSW ef_search parameter for the session.")
    
    args = parser.parse_args()

    asyncio.run(main(args.num_queries, args.k_neighbors, args.ef_search)) 