"""
Tests for MCP graph tools.

Tests: get_graph_stats, traverse_graph, find_path, get_module_data
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, patch
from dataclasses import dataclass
from typing import List, Optional

from mnemo_mcp.tools.graph_tools import (
    GetGraphStatsTool,
    TraverseGraphTool,
    FindPathTool,
    GetModuleDataTool,
)


@dataclass
class MockRow:
    """Mock database row."""
    def __init__(self, *values):
        self._values = values

    def __getitem__(self, idx):
        return self._values[idx]


class TestGetGraphStatsTool:
    """Tests for get_graph_stats tool."""

    def test_get_name(self):
        tool = GetGraphStatsTool()
        assert tool.get_name() == "get_graph_stats"

    @pytest.mark.asyncio
    async def test_success(self):
        """Test successful graph stats retrieval."""
        tool = GetGraphStatsTool()

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect.return_value = mock_cm

        # Mock query results
        node_row = MockRow(100, 15, 3)  # total_nodes, modules, languages
        edge_row = MockRow(250, 4)  # total_edges, edge_types
        hub_rows = [
            MockRow("main", "src", "python", 10),
            MockRow("utils", "src", "python", 5),
        ]

        mock_conn.execute = AsyncMock(side_effect=[
            MagicMock(fetchone=MagicMock(return_value=node_row)),
            MagicMock(fetchone=MagicMock(return_value=edge_row)),
            MagicMock(fetchall=MagicMock(return_value=hub_rows)),
        ])

        tool.inject_services({"engine": mock_engine})

        result = await tool.execute(repository="test-repo")

        assert result["success"] is True
        assert result["total_nodes"] == 100
        assert result["total_edges"] == 250
        assert result["modules"] == 15
        assert result["languages"] == 3
        assert len(result["top_hubs"]) == 2
        assert result["top_hubs"][0]["name"] == "main"

    @pytest.mark.asyncio
    async def test_no_engine(self):
        """Test failure when engine not available."""
        tool = GetGraphStatsTool()
        tool.inject_services({})

        result = await tool.execute()
        assert result["success"] is False
        assert "not available" in result["message"]


class TestTraverseGraphTool:
    """Tests for traverse_graph tool."""

    def test_get_name(self):
        tool = TraverseGraphTool()
        assert tool.get_name() == "traverse_graph"

    @pytest.mark.asyncio
    async def test_outgoing_traversal(self):
        """Test outgoing edge traversal."""
        tool = TraverseGraphTool()

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect.return_value = mock_cm

        node_row = MockRow("node-1", "func_a", "src.main", "python", "src/main.py")
        connected_rows = [
            MockRow("node-2", "func_b", "src.utils", "python", "calls", "node-1", "node-2"),
            MockRow("node-3", "func_c", "src.helpers", "python", "imports", "node-1", "node-3"),
        ]

        mock_conn.execute = AsyncMock(side_effect=[
            MagicMock(fetchone=MagicMock(return_value=node_row)),
            MagicMock(fetchall=MagicMock(return_value=connected_rows)),
        ])

        tool.inject_services({"engine": mock_engine})

        result = await tool.execute(
            node_id="node-1",
            direction="outgoing",
            repository="test-repo",
        )

        assert result["success"] is True
        assert result["source_node"]["id"] == "node-1"
        assert result["source_node"]["name"] == "func_a"
        assert len(result["connected_nodes"]) == 2
        assert result["connected_nodes"][0]["direction"] == "outgoing"
        assert result["total_connections"] == 2

    @pytest.mark.asyncio
    async def test_node_not_found(self):
        """Test traversal when node doesn't exist."""
        tool = TraverseGraphTool()

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect.return_value = mock_cm

        mock_conn.execute = AsyncMock(
            return_value=MagicMock(fetchone=MagicMock(return_value=None))
        )

        tool.inject_services({"engine": mock_engine})

        result = await tool.execute(node_id="nonexistent")
        assert result["success"] is False
        assert "not found" in result["message"]

    @pytest.mark.asyncio
    async def test_no_engine(self):
        """Test failure when engine not available."""
        tool = TraverseGraphTool()
        tool.inject_services({})

        result = await tool.execute(node_id="test")
        assert result["success"] is False


class TestFindPathTool:
    """Tests for find_path tool."""

    def test_get_name(self):
        tool = FindPathTool()
        assert tool.get_name() == "find_path"

    @pytest.mark.asyncio
    async def test_path_found(self):
        """Test finding a path between two nodes."""
        tool = FindPathTool()

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect.return_value = mock_cm

        # Mock node lookups
        node_a = MockRow("func_a", "src.main")
        node_b = MockRow("func_b", "src.utils")
        # Mock edges: A -> C -> B
        edges = [
            MockRow("node-a", "node-c", "calls"),
            MockRow("node-c", "node-b", "calls"),
            MockRow("node-a", "node-b", "imports"),
        ]
        # Mock node details for path
        path_node_a = MockRow("func_a", "src.main", "python")
        path_node_c = MockRow("func_c", "src.core", "python")
        path_node_b = MockRow("func_b", "src.utils", "python")

        execute_calls = [
            MagicMock(fetchone=MagicMock(return_value=node_a)),
            MagicMock(fetchone=MagicMock(return_value=node_b)),
            MagicMock(fetchall=MagicMock(return_value=edges)),
            MagicMock(fetchone=MagicMock(return_value=path_node_a)),
            MagicMock(fetchone=MagicMock(return_value=path_node_c)),
            MagicMock(fetchone=MagicMock(return_value=path_node_b)),
        ]
        mock_conn.execute = AsyncMock(side_effect=execute_calls)

        tool.inject_services({"engine": mock_engine})

        result = await tool.execute(
            source_id="node-a",
            target_id="node-b",
            repository="test-repo",
        )

        assert result["success"] is True
        # When path found, result has nodes/edges (no path_found key)
        assert "nodes" in result
        assert len(result["nodes"]) >= 2

    @pytest.mark.asyncio
    async def test_no_path(self):
        """Test when no path exists between nodes."""
        tool = FindPathTool()

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect.return_value = mock_cm

        node_a = MockRow("func_a", "src.main")
        node_b = MockRow("func_b", "src.utils")

        mock_conn.execute = AsyncMock(side_effect=[
            MagicMock(fetchone=MagicMock(return_value=node_a)),
            MagicMock(fetchone=MagicMock(return_value=node_b)),
            MagicMock(fetchall=MagicMock(return_value=[])),  # No edges
        ])

        tool.inject_services({"engine": mock_engine})

        result = await tool.execute(
            source_id="node-a",
            target_id="node-b",
            repository="test-repo",
        )

        assert result["success"] is True
        assert result["path_found"] is False

    @pytest.mark.asyncio
    async def test_source_not_found(self):
        """Test when source node doesn't exist."""
        tool = FindPathTool()

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect.return_value = mock_cm

        mock_conn.execute = AsyncMock(
            return_value=MagicMock(fetchone=MagicMock(return_value=None))
        )

        tool.inject_services({"engine": mock_engine})

        result = await tool.execute(source_id="nonexistent", target_id="node-b")
        assert result["success"] is False
        assert "not found" in result["message"]


class TestGetModuleDataTool:
    """Tests for get_module_data tool."""

    def test_get_name(self):
        tool = GetModuleDataTool()
        assert tool.get_name() == "get_module_data"

    @pytest.mark.asyncio
    async def test_module_found(self):
        """Test successful module data retrieval."""
        tool = GetModuleDataTool()

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect.return_value = mock_cm

        nodes = [
            MockRow("n1", "func_a", "python", "src/main.py", "function"),
            MockRow("n2", "class_b", "python", "src/main.py", "class"),
        ]
        internal = [MockRow("calls", 3)]
        external = [MockRow("imports", 2)]

        mock_conn.execute = AsyncMock(side_effect=[
            MagicMock(fetchall=MagicMock(return_value=nodes)),
            MagicMock(fetchall=MagicMock(return_value=internal)),
            MagicMock(fetchall=MagicMock(return_value=external)),
        ])

        tool.inject_services({"engine": mock_engine})

        result = await tool.execute(
            module_path="src/main.py",
            repository="test-repo",
        )

        assert result["success"] is True
        assert result["total_nodes"] == 2
        assert len(result["nodes"]) == 2
        assert result["nodes"][0]["name"] == "func_a"

    @pytest.mark.asyncio
    async def test_module_not_found(self):
        """Test when module doesn't exist."""
        tool = GetModuleDataTool()

        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_engine.connect.return_value = mock_cm

        mock_conn.execute = AsyncMock(
            return_value=MagicMock(fetchall=MagicMock(return_value=[]))
        )

        tool.inject_services({"engine": mock_engine})

        result = await tool.execute(module_path="nonexistent.py")
        assert result["success"] is False
        assert "not found" in result["message"]

    @pytest.mark.asyncio
    async def test_no_engine(self):
        """Test failure when engine not available."""
        tool = GetModuleDataTool()
        tool.inject_services({})

        result = await tool.execute(module_path="test.py")
        assert result["success"] is False
