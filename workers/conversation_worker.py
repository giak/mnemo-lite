"""
Conversation Worker - Consumes from Redis Streams and saves to API.
Also consumes entity extraction requests and processes them via LM Studio.
"""
import asyncio
import time
import os
import json
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

        # Setup entity extraction stream
        entity_stream = "entity:extraction"
        try:
            self.redis.xgroup_create(entity_stream, self.group_name, mkstream=True)
        except Exception:
            pass  # Group may already exist

        # Setup memory relationships stream
        rel_stream = "memory:relationships"
        try:
            self.redis.xgroup_create(rel_stream, self.group_name, mkstream=True)
        except Exception:
            pass  # Group may already exist

        logger.info(
            "worker_started",
            stream=self.stream_name,
            entity_stream=entity_stream,
            rel_stream=rel_stream,
            group=self.group_name,
            consumer=self.consumer_name
        )

        try:
            while self._running:
                # Poll both streams simultaneously (non-blocking)
                try:
                    conv_messages = self.redis.xreadgroup(
                        groupname=self.group_name,
                        consumername=self.consumer_name,
                        streams={self.stream_name: ">"},
                        count=10,
                        block=100  # 100ms timeout
                    )
                    entity_messages = self.redis.xreadgroup(
                        groupname=self.group_name,
                        consumername=self.consumer_name,
                        streams={entity_stream: ">"},
                        count=1,
                        block=100  # 100ms timeout
                    )
                    rel_messages = self.redis.xreadgroup(
                        groupname=self.group_name,
                        consumername=self.consumer_name,
                        streams={rel_stream: ">"},
                        count=1,
                        block=100  # 100ms timeout
                    )
                except Exception:
                    conv_messages = None
                    entity_messages = None
                    rel_messages = None

                # Process conversation messages
                if conv_messages:
                    for _stream, stream_messages in conv_messages:
                        for msg_id, data in stream_messages:
                            await self._handle_conversation_message(msg_id, data)

                # Process entity extraction messages
                if entity_messages:
                    for _stream, stream_messages in entity_messages:
                        for msg_id, data in stream_messages:
                            await self._handle_entity_extraction_message(msg_id, data, entity_stream)

                # Process memory relationship messages
                if rel_messages:
                    for _stream, stream_messages in rel_messages:
                        for msg_id, data in stream_messages:
                            await self._handle_relationship_message(msg_id, data, rel_stream)

                await asyncio.sleep(0.1)
        finally:
            if self._http_client:
                await self._http_client.aclose()

    async def _handle_conversation_message(self, msg_id, data):
        """Handle a single conversation message."""
        msg_id_str = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
        try:
            message = ConversationMessage(
                id=msg_id_str,
                user_message=data[b'user_message'].decode(),
                user_message_clean=data.get(b'user_message_clean', b'').decode(),
                assistant_message=data[b'assistant_message'].decode(),
                project_name=data[b'project_name'].decode(),
                session_id=data[b'session_id'].decode(),
                timestamp=data[b'timestamp'].decode()
            )

            success = await self.process_message(message)
            if success:
                self.redis.xack(self.stream_name, self.group_name, msg_id_str)
        except Exception as e:
            logger.error("handle_conversation_error", msg_id=msg_id_str, error=str(e))

    async def _handle_entity_extraction_message(self, msg_id, data, stream_name):
        """Handle a single entity extraction message."""
        msg_id_str = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
        payload = data.get(b"payload", b"{}").decode()

        try:
            entity_data = json.loads(payload)
            success = await self._process_entity_extraction(entity_data)

            if success:
                self.redis.xack(stream_name, self.group_name, msg_id_str)
                logger.info(
                    "entity_extraction_completed",
                    memory_id=entity_data.get("memory_id"),
                )
            else:
                logger.warning(
                    "entity_extraction_failed",
                    memory_id=entity_data.get("memory_id"),
                )
        except json.JSONDecodeError as e:
            logger.error("entity_extraction_invalid_payload", error=str(e))
            self.redis.xack(stream_name, self.group_name, msg_id_str)
        except Exception as e:
            logger.error("entity_extraction_error", error=str(e))

    async def _handle_relationship_message(self, msg_id, data, stream_name):
        """Handle a memory relationship computation message."""
        msg_id_str = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
        payload = data.get(b"payload", b"{}").decode()

        try:
            rel_data = json.loads(payload)
            memory_id = rel_data.get("memory_id")
            entities = rel_data.get("entities", [])
            concepts = rel_data.get("concepts", [])
            tags = rel_data.get("tags", [])
            auto_tags = rel_data.get("auto_tags", [])

            if not memory_id:
                self.redis.xack(stream_name, self.group_name, msg_id_str)
                return

            # Call API to compute relationships
            if self._http_client:
                response = await self._http_client.post(
                    f"{self.api_url}/api/v1/memories/{memory_id}/compute-relationships",
                    json={
                        "entities": entities,
                        "concepts": concepts,
                        "tags": tags,
                        "auto_tags": auto_tags,
                    },
                )
                if response.status_code == 200:
                    self.redis.xack(stream_name, self.group_name, msg_id_str)
                    logger.info("relationships_computed", memory_id=memory_id)
                else:
                    logger.warning("relationship_compute_failed", memory_id=memory_id, status=response.status_code)
            else:
                self.redis.xack(stream_name, self.group_name, msg_id_str)
        except json.JSONDecodeError as e:
            logger.error("relationship_invalid_payload", error=str(e))
            self.redis.xack(stream_name, self.group_name, msg_id_str)
        except Exception as e:
            logger.error("relationship_error", error=str(e))

    async def stop(self):
        """Stop the worker gracefully."""
        logger.info("worker_stopping")
        self._running = False

    async def _process_entity_extraction(self, data: dict) -> bool:
        """Process entity extraction using GLiNER directly."""
        try:
            from gliner import GLiNER
            import json as _json
            from sqlalchemy import create_engine
            from sqlalchemy.sql import text as sql_text

            # Load GLiNER model
            model_path = os.getenv("GLINER_MODEL_PATH", "/app/models/gliner_multi-v2.1")
            model = GLiNER.from_pretrained(model_path)

            # Extract entities
            text_content = f"{data['title']}\n\n{data['content']}"
            entity_types = ["technology", "product", "file", "person", "organization", "concept", "location"]
            raw_entities = model.predict_entities(text_content, entity_types)

            # Post-process: deduplicate, validate, clean types
            type_map = {
                "tech": "technology", "product": "technology",
                "org": "organization", "company": "organization",
                "per": "person", "loc": "location",
            }
            seen = {}
            for e in raw_entities:
                name = e.get("text", "").strip()
                if not name or len(name) < 2:
                    continue
                if name.lower() not in text_content.lower():
                    continue
                key = name.lower()
                if key not in seen:
                    raw_type = e.get("label", "concept").lower()
                    seen[key] = {"name": name, "type": type_map.get(raw_type, raw_type)}

            entities = list(seen.values())
            concepts = [e["name"] for e in entities if e["type"] == "concept"]
            auto_tags = list(set(e["name"].lower().replace(" ", "-") for e in entities))

            # Save to DB
            db_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://mnemo:mnemopass@db:5432/mnemolite")
            engine = create_engine(db_url)
            with engine.begin() as conn:
                conn.execute(sql_text("""
                    UPDATE memories
                    SET entities = :entities,
                        concepts = :concepts,
                        auto_tags = :auto_tags
                    WHERE id = :memory_id
                """), {
                    "memory_id": data["memory_id"],
                    "entities": _json.dumps(entities),
                    "concepts": _json.dumps(concepts),
                    "auto_tags": _json.dumps(auto_tags),
                })

            logger.info(
                "entity_extraction_completed",
                memory_id=data.get("memory_id"),
                entity_count=len(entities),
            )
            return True

        except Exception as e:
            logger.error("entity_extraction_error", memory_id=data.get("memory_id"), error=str(e))
            return False

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
    api_url = os.getenv("API_URL", "http://api:8000")

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
    o2_user = os.getenv("O2_USER", "admin@mnemolite.local")
    o2_password = os.getenv("O2_PASSWORD", "Complexpass#123")
    auth_string = f"{o2_user}:{o2_password}"
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
