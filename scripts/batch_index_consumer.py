#!/usr/bin/env python3
"""
Batch indexing consumer CLI: Runs consumer as daemon.

Usage:
    python scripts/batch_index_consumer.py --repository code_test

Options:
    --repository REPO    Repository name to process (required)
    --redis-url URL      Redis URL (default: redis://redis:6379/0)
    --db-url URL         Database URL (default: from env DATABASE_URL)
    --verbose            Enable verbose logging

EPIC-27: Batch Processing with Redis Streams
Task 11: CLI Script for running consumer as daemon
"""

import asyncio
import argparse
import logging
import sys
import signal
from pathlib import Path

# Add api directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from services.batch_indexing_consumer import BatchIndexingConsumer

# Global stop event for graceful shutdown
stop_event = asyncio.Event()


def signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM for graceful shutdown."""
    print("\n🛑 Received signal to stop. Finishing current batch...")
    stop_event.set()


async def main():
    """Main entry point for batch indexing consumer daemon."""
    parser = argparse.ArgumentParser(
        description="Batch indexing consumer daemon for EPIC-27",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run consumer for code_test repository
    python scripts/batch_index_consumer.py --repository code_test

    # Run with verbose logging
    python scripts/batch_index_consumer.py --repository code_test --verbose

    # Run with custom Redis URL
    python scripts/batch_index_consumer.py --repository code_test --redis-url redis://localhost:6379/1

    # Run in Docker container
    docker exec -it mnemo-api python /app/scripts/batch_index_consumer.py --repository code_test --verbose

Graceful Shutdown:
    - Press Ctrl+C to stop gracefully
    - Consumer will finish current batch before exiting
    - SIGINT/SIGTERM signals handled automatically
        """
    )
    parser.add_argument(
        "--repository",
        required=True,
        help="Repository name to process (must match producer job)"
    )
    parser.add_argument(
        "--redis-url",
        default="redis://redis:6379/0",
        help="Redis URL (default: redis://redis:6379/0)"
    )
    parser.add_argument(
        "--db-url",
        help="Database URL (default: from DATABASE_URL env variable)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging"
    )
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger = logging.getLogger(__name__)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create consumer
    consumer = BatchIndexingConsumer(
        redis_url=args.redis_url,
        db_url=args.db_url
    )

    try:
        logger.info("=" * 80)
        logger.info("🚀 Starting batch indexing consumer daemon")
        logger.info("=" * 80)
        logger.info(f"   Repository: {args.repository}")
        logger.info(f"   Redis URL:  {args.redis_url}")
        logger.info(f"   Database:   {args.db_url or 'from DATABASE_URL env'}")
        logger.info(f"   Verbose:    {args.verbose}")
        logger.info("")
        logger.info("📡 Press Ctrl+C to stop gracefully (will finish current batch)")
        logger.info("=" * 80)
        logger.info("")

        # Connect to Redis
        await consumer.connect()

        # Process repository until completion or stop signal
        stats = await consumer.process_repository(
            repository=args.repository,
            stop_event=stop_event
        )

        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ Consumer finished successfully")
        logger.info("=" * 80)
        logger.info(f"   Repository:        {args.repository}")
        logger.info(f"   Batches processed: {stats.get('batches_processed', 0)}")
        logger.info(f"   Files processed:   {stats.get('processed_files', 0)}")
        logger.info(f"   Files failed:      {stats.get('failed_files', 0)}")
        logger.info(f"   Final status:      {stats.get('status', 'unknown')}")
        logger.info(f"   Completed at:      {stats.get('completed_at', 'N/A')}")
        logger.info("=" * 80)

        # Exit code based on status
        if stats.get('status') == 'completed':
            sys.exit(0)
        elif stats.get('failed_files', 0) > 0:
            logger.warning("⚠️  Some files failed processing, but job completed")
            sys.exit(0)  # Still success if partial completion
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("")
        logger.info("🛑 Keyboard interrupt received, stopping consumer...")
        sys.exit(130)  # Standard exit code for Ctrl+C

    except Exception as e:
        logger.error("")
        logger.error("=" * 80)
        logger.error("❌ Consumer error")
        logger.error("=" * 80)
        logger.error(f"   Error: {e}", exc_info=args.verbose)
        logger.error("=" * 80)
        sys.exit(1)

    finally:
        try:
            await consumer.close()
            logger.info("👋 Consumer stopped, Redis connection closed")
        except Exception as e:
            logger.warning(f"Error closing consumer: {e}")


if __name__ == "__main__":
    # Run async main
    asyncio.run(main())
