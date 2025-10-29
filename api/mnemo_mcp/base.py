"""
MCP Base Classes and Models

Provides base classes and Pydantic models for all MCP components.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
from urllib.parse import urlparse, parse_qs
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()


class MCPBaseResponse(BaseModel):
    """
    Base response model for all MCP interactions.

    All Tools and Resources should return models that inherit from this.
    Provides consistent success/failure reporting and metadata support.
    """
    success: bool = True
    message: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "metadata": {"duration_ms": 123}
            }
        }


class BaseMCPComponent(ABC):
    """
    Base class for all MCP components (Tools, Resources, Prompts).

    Provides dependency injection pattern for MnemoLite services.
    All MCP components should inherit from this class.

    Example:
        ```python
        class SearchCodeResource(BaseMCPComponent):
            def get_name(self) -> str:
                return "code://search"

            async def get(self, ctx: Context, query: str):
                search_service = self._services["search_service"]
                results = await search_service.hybrid_search(query)
                return results
        ```
    """

    def __init__(self):
        """Initialize component with no services (will be injected later)."""
        self._services: Optional[dict[str, Any]] = None

    def inject_services(self, services: dict[str, Any]) -> None:
        """
        Inject MnemoLite services (dependency injection pattern).

        This method is called during MCP server lifespan initialization.
        Services are shared across all MCP components for efficiency.

        Args:
            services: Dictionary of service instances:
                - search_service: HybridCodeSearchService (code search)
                - graph_service: CodeGraphService (code graph navigation)
                - indexing_service: CodeIndexingService (project indexing)
                - db: Database connection pool (asyncpg)
                - redis: Redis client (L2 cache)
                - metrics: MetricsCollectorService (EPIC-22 observability)

        Example:
            ```python
            services = {
                "search_service": HybridCodeSearchService(db, redis),
                "db": db_pool,
                "redis": redis_client
            }
            component.inject_services(services)
            ```
        """
        self._services = services
        service_names = list(services.keys()) if services else []
        logger.info(
            "mcp.component.services_injected",
            component=self.get_name(),
            services=service_names
        )

    @abstractmethod
    def get_name(self) -> str:
        """
        Return the component name.

        - For Tools: tool name (e.g., "ping", "write_memory")
        - For Resources: URI template (e.g., "code://search", "graph://nodes/{id}")
        - For Prompts: prompt name (e.g., "analyze_codebase")

        Returns:
            Component name string
        """
        pass

    def _get_service(self, service_name: str) -> Any:
        """
        Helper to safely get a service with error handling.

        Args:
            service_name: Name of the service to retrieve

        Returns:
            The requested service instance

        Raises:
            RuntimeError: If services not injected
            KeyError: If service not found
        """
        if self._services is None:
            raise RuntimeError(
                f"{self.get_name()}: Services not injected. "
                "Call inject_services() first."
            )

        if service_name not in self._services:
            raise KeyError(
                f"{self.get_name()}: Service '{service_name}' not found. "
                f"Available: {list(self._services.keys())}"
            )

        return self._services[service_name]

    # Service property accessors for common services
    @property
    def memory_repository(self):
        """Access memory repository service (EPIC-23)."""
        return self._services.get("memory_repository") if self._services else None

    @property
    def embedding_service(self):
        """Access embedding service (EPIC-18)."""
        return self._services.get("embedding_service") if self._services else None

    @property
    def redis_client(self):
        """Access Redis L2 cache client."""
        return self._services.get("redis") if self._services else None

    def _parse_query_params(self, uri: str) -> Dict[str, str]:
        """
        Parse query parameters from URI.

        Args:
            uri: Full URI with query string

        Returns:
            Dict of parameter name -> value
        """
        parsed = urlparse(uri)
        query_params = parse_qs(parsed.query)

        # Flatten single-value params (parse_qs returns lists)
        params = {}
        for key, values in query_params.items():
            params[key] = values[0] if values else ""

        return params
