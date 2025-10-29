"""
MnemoLite MCP Server - Model Context Protocol Integration

This module provides MCP (Model Context Protocol) server capabilities,
exposing MnemoLite's code intelligence features to LLMs like Claude.

Architecture:
    - Tools: Write operations with side effects (index, write memory, etc.)
    - Resources: Read-only operations (search, graph navigation, etc.)
    - Prompts: User-facing templates for common workflows

MCP Spec Version: 2025-06-18
SDK: FastMCP (mcp==1.12.3)
"""

__version__ = "1.0.0"
__mcp_spec__ = "2025-06-18"
