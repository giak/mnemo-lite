"""
Generates and inserts a large volume of test data into the 'events' table
for performance benchmarking (STORY-03.4 PoC).
"""
import asyncio
import asyncpg
import argparse
import numpy as np
import json
import uuid
import os
import random
from datetime import datetime, timedelta, timezone

# --- Configuration ---
DB_URL = os.getenv("DATABASE_URL", "postgresql://mnemo:mnemo@localhost:5432/mnemolite")
TABLE_NAME = "events"
EMBEDDING_DIM = 1536 # Assuming OpenAI text-embedding-3-small

# --- Helper Functions ---

def generate_random_timestamp(start_date=datetime(2023, 1, 1, tzinfo=timezone.utc), 
                              end_date=datetime.now(timezone.utc)):
    """Generates a random timestamp between start and end dates."""
    delta = end_date - start_date
    random_seconds = random.uniform(0, delta.total_seconds())
    return start_date + timedelta(seconds=random_seconds)

def generate_random_metadata():
    """Generates varied JSONB metadata for filtering tests."""
    # Example: Mix of simple tags and nested data
    metadata = {
        "source_system": random.choice(["SystemA", "SystemB", "SystemC", "LegacySys"]),
        "event_type": random.choice(["USER_LOGIN", "ITEM_PURCHASED", "NOTIFICATION_SENT", "ERROR_LOGGED"]),
        "region": random.choice(["us-east-1", "eu-west-1", "ap-southeast-2", "us-west-2"]),
        "priority": random.randint(1, 5),
        "is_critical": random.choice([True, False]),
    }
    if random.random() < 0.2: # Add nested data occasionally
        metadata["details"] = {
            "user_id": random.randint(1000, 9999),
            "session_id": str(uuid.uuid4())
        }
    return json.dumps(metadata)

def generate_random_content():
    """Generates simple placeholder JSON content."""
    return json.dumps({
        "message": f"Event {random.randint(1000, 9999)} occurred.",
        "payload_size": random.randint(10, 1024),
        "processed": random.choice([True, False])
    })

async def insert_batch_with_insert(pool, batch_data):
    """Inserts a batch of data using INSERT statements (slower but vector-compatible)."""
    query = """
    INSERT INTO events (id, timestamp, content, metadata, embedding)
    VALUES ($1, $2, $3, $4, $5::vector) -- Explicitly cast to vector
    """
    # Prepare data for executemany: list of tuples
    # Convert embedding list to string representation '[...]' for text protocol
    records_to_insert = [
        (
            d["id"],
            d["timestamp"],
            d["content"],
            d["metadata"],
            # Convert list to string '[num, num, ...]' expected by pgvector text input
            str(d["embedding"]).replace(" ", "") 
        )
        for d in batch_data
    ]
    
    async with pool.acquire() as conn:
        async with conn.transaction(): # Use a transaction for the batch
            try:
                status = await conn.executemany(query, records_to_insert)
                # executemany doesn't return a count, assume success if no exception
                return len(records_to_insert)
            except Exception as e:
                print(f"Error during batch INSERT: {e}")
                # Consider logging the failing batch data
                return 0

# --- Main Execution ---

async def main(num_events, batch_size):
    """Main function to generate and insert data."""
    # Increase pool size slightly for potentially more concurrent inserts
    pool = await asyncpg.create_pool(DB_URL, min_size=5, max_size=20) 
    print(f"Connected to database. Target: {num_events} events, Batch size: {batch_size}")
    print("Using INSERT statements (slower than COPY)...")

    total_inserted = 0
    start_time = datetime.now()

    try:
        while total_inserted < num_events:
            current_batch_size = min(batch_size, num_events - total_inserted)
            batch_data = []
            
            # Generate batch
            embeddings = np.random.normal(size=(current_batch_size, EMBEDDING_DIM)).astype('float32')
            embeddings /= np.linalg.norm(embeddings, axis=1, keepdims=True) # Normalize

            for i in range(current_batch_size):
                event = {
                    "id": uuid.uuid4(), # Use 'id'
                    "timestamp": generate_random_timestamp(),
                    "content": generate_random_content(),
                    "metadata": generate_random_metadata(),
                    # asyncpg expects list/tuple for vector type
                    "embedding": embeddings[i].tolist() 
                }
                batch_data.append(event)

            # Insert batch using INSERT
            # inserted_count = await insert_batch(pool, batch_data) # Old COPY call
            inserted_count = await insert_batch_with_insert(pool, batch_data)
            total_inserted += inserted_count

            # Progress reporting
            elapsed_time = (datetime.now() - start_time).total_seconds()
            rate = total_inserted / elapsed_time if elapsed_time > 0 else 0
            print(f"Inserted {total_inserted}/{num_events} events... ({rate:.2f} events/sec)", end="\r")

            if inserted_count < current_batch_size:
                print("\nInsertion issue encountered, stopping generation.")
                break
                
    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        await pool.close()
        print(f"\nFinished. Total events inserted: {total_inserted}")
        final_elapsed_time = (datetime.now() - start_time).total_seconds()
        final_rate = total_inserted / final_elapsed_time if final_elapsed_time > 0 else 0
        print(f"Total time: {final_elapsed_time:.2f} seconds. Average rate: {final_rate:.2f} events/sec")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate test data for MnemoLite events table.")
    parser.add_argument("-n", "--num-events", type=int, required=True, help="Total number of events to generate.")
    parser.add_argument("-b", "--batch-size", type=int, default=1000, help="Number of events per insertion batch.")
    args = parser.parse_args()

    asyncio.run(main(args.num_events, args.batch_size)) 