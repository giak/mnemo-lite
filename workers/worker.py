#!/usr/bin/env python
"""
MnemoLite Worker - Main entry point for worker processes

This worker monitors PGMQ queues for tasks and processes them
according to task type and requirements.
"""

import os
import asyncio
import signal
import json
import time
import structlog
from datetime import datetime
from pgmq import Queue, Notification
import asyncpg
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
import importlib

from config.settings import Settings
from utils.redis_utils import get_redis_client, close_redis_client
from utils.db import get_pg_pool, close_pg_pool

# Set up console for nice output
console = Console()

# Get settings
settings = Settings()

# Configure logger
logger = structlog.get_logger()

# Setup structlog config based on environment
log_processors = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
]

if settings.environment == "development":
    # Pretty logs for development
    log_processors.extend([
        structlog.dev.ConsoleRenderer(),
    ])
else:
    # JSON logs for production
    log_processors.extend([
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ])

structlog.configure(
    processors=log_processors,
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

# Task types with corresponding handlers
TASK_HANDLERS = {
    "embedding_generation": "embedding_task",
    "document_chunking": "document_task",
    "memory_search": "memory_task"
}

class Worker:
    def __init__(self):
        self.exit_handler = GracefulExit()
        self.settings = Settings()
        self.pool = None
        self.redis = None
        self.queues = {}
        self.task_count = 0
    
    async def connect(self):
        """Connect to PostgreSQL and Redis"""
        self.pool = await get_pg_pool()
        self.redis = await get_redis_client()
        
        # Setup queues
        for queue_name in TASK_HANDLERS.keys():
            self.queues[queue_name] = Queue(
                self.pool,
                queue_name=f"mnemo_{queue_name}_queue"
            )
            logger.info("queue_initialized", queue=queue_name)
    
    async def process_task(self, queue_name, message):
        """Process a task from a queue"""
        task_type = queue_name.split("_")[0]  # Extract task type from queue name
        handler_module = TASK_HANDLERS.get(task_type)
        
        if not handler_module:
            logger.error("unknown_task_type", task_type=task_type)
            return False
        
        try:
            # Dynamically import task handler
            module = importlib.import_module(f"tasks.{handler_module}")
            handler = module.TaskHandler()
            
            # Process the task
            logger.info("processing_task", task_id=message.msg_id, task_type=task_type)
            result = await handler.process(message.content)
            
            # Update task status
            self.task_count += 1
            
            return result
        except ImportError as e:
            logger.error("task_handler_import_error", module=handler_module, error=str(e))
            return False
        except Exception as e:
            logger.error("task_processing_error", task_id=message.msg_id, error=str(e))
            return False
    
    async def poll_queue(self, queue_name):
        """Poll a specific queue for messages"""
        queue = self.queues.get(queue_name)
        if not queue:
            logger.error("queue_not_initialized", queue=queue_name)
            return
        
        try:
            # Get a message with visibility timeout
            message = await queue.get(visibility_timeout=30)
            
            if message:
                # Process the message
                success = await self.process_task(queue_name, message)
                
                if success:
                    # Delete the message from the queue
                    await queue.delete([message.msg_id])
                    logger.info("task_completed", task_id=message.msg_id, queue=queue_name)
                else:
                    # Return the message to the queue (will be retried)
                    await queue.release([message.msg_id])
                    logger.info("task_released", task_id=message.msg_id, queue=queue_name)
        except Exception as e:
            logger.error("queue_polling_error", queue=queue_name, error=str(e))
    
    async def poll_all_queues(self):
        """Poll all queues for messages"""
        for queue_name in self.queues.keys():
            await self.poll_queue(queue_name)
    
    async def run(self):
        """Main worker loop"""
        # Connect to services
        await self.connect()
        
        # Create worker log file to signal for health checks
        with open("/app/logs/worker.log", "w") as f:
            f.write(f"Worker started at {datetime.now().isoformat()}\n")
        
        # Print startup message
        console.print(Panel.fit(
            "🔄 [bold green]MnemoLite Worker Started[/bold green]\n"
            f"PostgreSQL: {self.settings.postgres_host}:{self.settings.postgres_port}\n"
            f"Redis: {self.settings.redis_host}:{self.settings.redis_port}\n"
            f"Environment: {self.settings.environment.upper()}\n"
            "Monitoring queues: " + ", ".join(self.queues.keys()),
            title="MnemoLite Worker"
        ))
        
        with Progress(
            SpinnerColumn(),
            *Progress.get_default_columns(),
            TimeElapsedColumn(),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("[green]Processing tasks...", total=None)
            
            # Main loop
            while not self.exit_handler.exit:
                try:
                    # Poll all queues
                    await self.poll_all_queues()
                    
                    # Update progress
                    progress.update(task, description=f"[green]Processing tasks... (completed: {self.task_count})")
                    
                    # Short sleep to prevent tight loop
                    await asyncio.sleep(1)
                
                except Exception as e:
                    logger.error("worker_loop_error", error=str(e))
                    # Wait a bit longer after an error
                    await asyncio.sleep(5)
        
        # Cleanup connections
        await close_redis_client()
        await close_pg_pool()
        
        logger.info("worker_shutdown_complete")
        console.print("[bold green]Worker shutdown complete[/bold green]")

async def main():
    """Main entry point"""
    worker = Worker()
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main()) 