"""
MCP Transport Layers

Supports multiple transport mechanisms:
- stdio: Default transport for Claude Desktop (JSON-RPC over stdin/stdout)
- HTTP/SSE: Web transport for HTTP clients with Server-Sent Events streaming

Authentication:
- OAuth 2.0 + PKCE: Production authentication
- API Key: Development/testing authentication
"""
