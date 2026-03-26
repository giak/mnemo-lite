"""
MCP Transport Layers

MnemoLite supports two transport mechanisms:

1. stdio (default)
   - JSON-RPC over stdin/stdout
   - Used by Claude Desktop, local integrations
   - Zero-config, single client
   - Run: python -m api.mcp.server

2. Streamable HTTP (production)
   - MCP spec 2025-06-18, replaces legacy SSE
   - Clients connect via POST to /mcp endpoint
   - Supports bidirectional communication + SSE streaming
   - Multi-client, stateful or stateless sessions
   - Run: MCP_TRANSPORT=http python -m api.mcp.server
   - Or mount in FastAPI: app.mount("/mcp", mcp.streamable_http_app())

Authentication (HTTP transport only):
- OAuth 2.0 + PKCE: Production authentication (config.auth_mode = "oauth")
- API Key: Development/testing (config.auth_mode = "api_key")
- None: No auth (config.auth_mode = "none", default)

Configuration (env vars with MCP_ prefix):
- MCP_TRANSPORT=stdio|http
- MCP_HTTP_HOST=0.0.0.0
- MCP_HTTP_PORT=8002
- MCP_AUTH_MODE=none|api_key|oauth
- MCP_CORS_ORIGINS=http://localhost:3000
"""
