"""
Tests for MCP base classes and models.
"""

import pytest
from mnemo_mcp.base import BaseMCPComponent, MCPBaseResponse


class TestMCPBaseResponse:
    """Tests for MCPBaseResponse model."""

    def test_default_success(self):
        """Test default response is success."""
        response = MCPBaseResponse()
        assert response.success is True
        assert response.message is None
        assert response.metadata == {}

    def test_with_message(self):
        """Test response with custom message."""
        response = MCPBaseResponse(
            success=True,
            message="Operation completed",
            metadata={"duration_ms": 123}
        )
        assert response.success is True
        assert response.message == "Operation completed"
        assert response.metadata["duration_ms"] == 123

    def test_failure_response(self):
        """Test failure response."""
        response = MCPBaseResponse(
            success=False,
            message="Operation failed"
        )
        assert response.success is False
        assert response.message == "Operation failed"


class TestBaseMCPComponent:
    """Tests for BaseMCPComponent."""

    class MockComponent(BaseMCPComponent):
        """Mock MCP component for testing."""

        def get_name(self) -> str:
            return "mock_component"

    def test_init_no_services(self):
        """Test component initializes with no services."""
        component = self.MockComponent()
        assert component._services is None

    def test_inject_services(self):
        """Test service injection."""
        component = self.MockComponent()
        services = {
            "db": "mock_db",
            "redis": "mock_redis"
        }

        component.inject_services(services)

        assert component._services == services
        assert component._services["db"] == "mock_db"
        assert component._services["redis"] == "mock_redis"

    def test_get_service_success(self):
        """Test getting service successfully."""
        component = self.MockComponent()
        services = {"test_service": "test_value"}
        component.inject_services(services)

        result = component._get_service("test_service")
        assert result == "test_value"

    def test_get_service_not_injected(self):
        """Test getting service when not injected raises error."""
        component = self.MockComponent()

        with pytest.raises(RuntimeError, match="Services not injected"):
            component._get_service("test_service")

    def test_get_service_not_found(self):
        """Test getting non-existent service raises error."""
        component = self.MockComponent()
        component.inject_services({"other_service": "value"})

        with pytest.raises(KeyError, match="Service 'test_service' not found"):
            component._get_service("test_service")

    def test_get_name(self):
        """Test get_name returns correct name."""
        component = self.MockComponent()
        assert component.get_name() == "mock_component"
