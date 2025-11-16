"""
Conversation Worker - Consumes from Redis Streams and saves to API.
"""
import asyncio
import time
import structlog
from dataclasses import dataclass
from typing import Optional
import httpx
from redis import Redis
from tenacity import retry, stop_after_attempt, wait_exponential
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

logger = structlog.get_logger(__name__)

# Global tracer and metrics
tracer = None
messages_processed_counter = None
messages_failed_counter = None
processing_duration_histogram = None


@dataclass
class ConversationMessage:
    """Message from Redis Streams."""
    id: str
    user_message: str
    user_message_clean: str
    assistant_message: str
    project_name: str
    session_id: str
    timestamp: str


class ConversationWorker:
    """
    Worker that consumes conversations from Redis Streams
    and saves them via API.
    """

    def __init__(
        self,
        redis_client: Redis,
        api_url: str = "http://api:8001",
        stream_name: str = "conversations:autosave",
        group_name: str = "workers",
        consumer_name: str = "worker1"
    ):
        self.redis = redis_client
        self.api_url = api_url
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name
        self._http_client: Optional[httpx.AsyncClient] = None
        self._running = False

    async def start(self):
        """Start the worker loop."""
        self._running = True
        self._http_client = httpx.AsyncClient(timeout=30.0)

        logger.info(
            "worker_started",
            stream=self.stream_name,
            group=self.group_name,
            consumer=self.consumer_name
        )

        try:
            while self._running:
                await self._poll_and_process()
                await asyncio.sleep(0.1)  # 100ms poll interval
        finally:
            if self._http_client:
                await self._http_client.aclose()

    async def stop(self):
        """Stop the worker gracefully."""
        logger.info("worker_stopping")
        self._running = False

    async def _poll_and_process(self):
        """Poll Redis and process one batch of messages."""
        try:
            # Read from stream (block for 1 second)
            messages = self.redis.xreadgroup(
                groupname=self.group_name,
                consumername=self.consumer_name,
                streams={self.stream_name: ">"},
                count=10,
                block=1000
            )

            if not messages:
                return

            # Process each message
            for stream, msg_list in messages:
                for msg_id, data in msg_list:
                    await self._handle_message(msg_id.decode(), data)

        except Exception as e:
            logger.error("poll_error", error=str(e))
            await asyncio.sleep(1)  # Backoff on error

    async def _handle_message(self, msg_id: str, data: dict):
        """Handle a single message with OpenTelemetry tracing."""
        # Start measuring time
        start_time = time.time()

        # Create a span for this message processing
        if tracer:
            with tracer.start_as_current_span("process_conversation") as span:
                try:
                    # Parse message
                    message = ConversationMessage(
                        id=msg_id,
                        user_message=data[b'user_message'].decode(),
                        user_message_clean=data.get(b'user_message_clean', b'').decode(),
                        assistant_message=data[b'assistant_message'].decode(),
                        project_name=data[b'project_name'].decode(),
                        session_id=data[b'session_id'].decode(),
                        timestamp=data[b'timestamp'].decode()
                    )

                    # Add span attributes
                    span.set_attribute("message.id", msg_id)
                    span.set_attribute("message.project", message.project_name)
                    span.set_attribute("message.session_id", message.session_id)

                    # Process with retry
                    success = await self.process_message(message)

                    if success:
                        # Acknowledge message (remove from pending)
                        self.redis.xack(self.stream_name, self.group_name, msg_id)

                        # Record metrics
                        duration_ms = (time.time() - start_time) * 1000
                        if messages_processed_counter:
                            messages_processed_counter.add(1, {"project": message.project_name})
                        if processing_duration_histogram:
                            processing_duration_histogram.record(duration_ms, {"project": message.project_name})

                        span.set_attribute("success", True)
                        span.set_attribute("duration_ms", duration_ms)

                        logger.info(
                            "message_processed",
                            msg_id=msg_id,
                            project=message.project_name,
                            duration_ms=duration_ms
                        )
                    else:
                        # Record failure
                        if messages_failed_counter:
                            messages_failed_counter.add(1, {"project": message.project_name})

                        span.set_attribute("success", False)
                        logger.error("message_failed_permanently", msg_id=msg_id)

                except Exception as e:
                    # Record exception in span and metrics
                    if messages_failed_counter:
                        messages_failed_counter.add(1, {"error": type(e).__name__})

                    span.set_attribute("error", True)
                    span.record_exception(e)
                    logger.error("handle_message_error", msg_id=msg_id, error=str(e))
        else:
            # Fallback if OpenTelemetry not configured
            try:
                message = ConversationMessage(
                    id=msg_id,
                    user_message=data[b'user_message'].decode(),
                    user_message_clean=data.get(b'user_message_clean', b'').decode(),
                    assistant_message=data[b'assistant_message'].decode(),
                    project_name=data[b'project_name'].decode(),
                    session_id=data[b'session_id'].decode(),
                    timestamp=data[b'timestamp'].decode()
                )

                success = await self.process_message(message)

                if success:
                    self.redis.xack(self.stream_name, self.group_name, msg_id)
                    logger.info("message_processed", msg_id=msg_id, project=message.project_name)
                else:
                    logger.error("message_failed_permanently", msg_id=msg_id)

            except Exception as e:
                logger.error("handle_message_error", msg_id=msg_id, error=str(e))

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        reraise=True
    )
    async def process_message(
        self,
        message: ConversationMessage,
        max_retries: int = 5
    ) -> bool:
        """
        Process a message by calling the API.
        Returns True if successful, False if permanently failed.
        """
        if not self._http_client:
            raise RuntimeError("HTTP client not initialized")

        try:
            response = await self._http_client.post(
                f"{self.api_url}/v1/conversations/save",
                json={
                    "user_message": message.user_message,
                    "user_message_clean": message.user_message_clean,
                    "assistant_message": message.assistant_message,
                    "project_name": message.project_name,
                    "session_id": message.session_id,
                    "timestamp": message.timestamp
                }
            )

            if response.status_code == 200:
                return True
            elif response.status_code >= 500:
                # Retry on server errors
                logger.warning(
                    "api_server_error",
                    status=response.status_code,
                    msg_id=message.id
                )
                raise httpx.HTTPStatusError(
                    f"Server error: {response.status_code}",
                    request=response.request,
                    response=response
                )
            else:
                # Don't retry on client errors (4xx)
                logger.error(
                    "api_client_error",
                    status=response.status_code,
                    msg_id=message.id,
                    body=response.text
                )
                return False

        except httpx.HTTPStatusError:
            # Re-raise for retry (5xx errors)
            raise
        except httpx.TimeoutException:
            logger.warning("api_timeout", msg_id=message.id)
            raise  # Retry
        except httpx.ConnectError:
            logger.warning("api_connect_error", msg_id=message.id)
            raise  # Retry
        except Exception as e:
            logger.error("api_unexpected_error", msg_id=message.id, error=str(e))
            return False  # Don't retry on unexpected errors


async def main():
    """Main entry point."""
    import os
    from redis import Redis

    # Configuration from environment
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    api_url = os.getenv("API_URL", "http://api:8001")

    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ]
    )

    # Configure OpenTelemetry
    global tracer, messages_processed_counter, messages_failed_counter, processing_duration_histogram

    otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://openobserve:5080/api/default/v1/traces")
    otlp_metrics_endpoint = os.getenv("OTLP_METRICS_ENDPOINT", "http://openobserve:5080/api/default/v1/metrics")

    # OpenObserve authentication
    import base64
    auth_string = "admin@mnemolite.local:Complexpass#123"
    auth_bytes = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    otlp_headers = {"Authorization": f"Basic {auth_bytes}"}

    # Create resource with service name
    resource = Resource.create({"service.name": "conversation-worker"})

    # Configure tracing with authentication
    trace.set_tracer_provider(TracerProvider(resource=resource))
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(
            endpoint=otlp_endpoint,
            headers=otlp_headers
        ))
    )
    tracer = trace.get_tracer(__name__)

    # Configure metrics with authentication
    metrics.set_meter_provider(MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(
            OTLPMetricExporter(
                endpoint=otlp_metrics_endpoint,
                headers=otlp_headers
            ),
            export_interval_millis=5000  # Export every 5 seconds
        )]
    ))

    meter = metrics.get_meter(__name__)
    messages_processed_counter = meter.create_counter(
        "conversations.processed",
        description="Number of conversations processed successfully"
    )
    messages_failed_counter = meter.create_counter(
        "conversations.failed",
        description="Number of conversations that failed permanently"
    )
    processing_duration_histogram = meter.create_histogram(
        "conversations.processing_duration_ms",
        description="Time to process conversation (milliseconds)"
    )

    logger.info("opentelemetry_configured", otlp_endpoint=otlp_endpoint)

    # Create Redis client
    redis_client = Redis(
        host=redis_host,
        port=redis_port,
        decode_responses=False
    )

    # Create and start worker
    worker = ConversationWorker(redis_client, api_url=api_url)

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("received_sigint")
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
