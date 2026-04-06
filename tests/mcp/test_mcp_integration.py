"""
Integration tests for MCP server against live HTTP endpoint.

These tests make real HTTP calls to the running MCP container to verify:
- End-to-end tool execution with real DB
- Performance under load
- Stateful operations across requests
- Error handling with real infrastructure
"""

import asyncio
import httpx
import json
import os
import time
import pytest

MCP_URL = os.getenv("MCP_URL", "http://localhost:8002/mcp")

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"
}


def _parse_sse_response(text: str) -> dict:
    """Parse SSE response from MCP server."""
    for line in text.strip().split("\n"):
        if line.startswith("data: "):
            return json.loads(line[6:])
    raise ValueError(f"No SSE data found in response: {text[:200]}")


async def call_mcp_tool(client: httpx.AsyncClient, tool_name: str, args: dict) -> dict:
    """Call an MCP tool and return parsed result."""
    response = await client.post(
        MCP_URL,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": args,
            }
        },
        headers=HEADERS,
        timeout=30.0,
    )
    assert response.status_code == 200, f"HTTP {response.status_code}: {response.text[:500]}"
    return _parse_sse_response(response.text)


@pytest.mark.asyncio
async def test_ping_responds_fast():
    """Ping tool responds in < 100ms."""
    async with httpx.AsyncClient() as client:
        start = time.time()
        result = await call_mcp_tool(client, "ping", {})
        elapsed = time.time() - start

        assert result["result"]["content"][0]["text"]
        data = json.loads(result["result"]["content"][0]["text"])
        assert data["success"] is True
        assert data["message"] == "pong"
        assert elapsed < 0.1, f"Ping too slow: {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_write_memory_creates_and_returns_id():
    """write_memory creates a memory and returns a valid UUID."""
    async with httpx.AsyncClient() as client:
        result = await call_mcp_tool(client, "write_memory", {
            "title": "Integration test: write",
            "content": "Created by integration test suite",
            "memory_type": "note",
            "tags": ["integration-test", "write-test"],
        })

        text = result["result"]["content"][0]["text"]
        data = json.loads(text)

        assert "id" in data
        assert data["title"] == "Integration test: write"
        assert data["memory_type"] == "note"
        assert "integration-test" in data["tags"]
        assert "write-test" in data["tags"]
        assert result["result"]["isError"] is False


@pytest.mark.asyncio
async def test_write_memory_responds_fast():
    """write_memory responds in < 500ms."""
    async with httpx.AsyncClient() as client:
        start = time.time()
        result = await call_mcp_tool(client, "write_memory", {
            "title": "Integration test: speed",
            "content": "Testing write performance",
            "memory_type": "note",
            "tags": ["integration-test", "speed-test"],
        })
        elapsed = time.time() - start

        assert elapsed < 0.5, f"write_memory too slow: {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_write_memory_validation_errors():
    """write_memory returns proper error for invalid input."""
    async with httpx.AsyncClient() as client:
        result = await call_mcp_tool(client, "write_memory", {
            "title": "",
            "content": "Should fail",
        })

        assert result["result"]["isError"] is True


@pytest.mark.asyncio
async def test_search_memory_returns_results():
    """search_memory finds memories by tags."""
    async with httpx.AsyncClient() as client:
        result = await call_mcp_tool(client, "search_memory", {
            "tags": ["integration-test"],
            "limit": 5,
        })

        text = result["result"]["content"][0]["text"]
        data = json.loads(text)

        assert "memories" in data
        assert "total" in data
        assert data["total"] >= 1
        assert result["result"]["isError"] is False


@pytest.mark.asyncio
async def test_search_memory_responds_fast():
    """search_memory responds in < 500ms."""
    async with httpx.AsyncClient() as client:
        start = time.time()
        await call_mcp_tool(client, "search_memory", {
            "query": "test",
            "limit": 5,
        })
        elapsed = time.time() - start

        assert elapsed < 0.5, f"search_memory too slow: {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_search_memory_validation_errors():
    """search_memory returns error for empty query without tags."""
    async with httpx.AsyncClient() as client:
        result = await call_mcp_tool(client, "search_memory", {
            "query": "",
        })

        assert result["result"]["isError"] is True


@pytest.mark.asyncio
async def test_write_then_search_finds_new_memory():
    """Write a memory, then search and find it."""
    async with httpx.AsyncClient() as client:
        # Write unique memory
        unique_tag = f"integration-unique-{int(time.time())}"
        write_result = await call_mcp_tool(client, "write_memory", {
            "title": f"Unique memory {unique_tag}",
            "content": "This memory has a unique tag for this test run",
            "memory_type": "note",
            "tags": [unique_tag],
        })

        write_data = json.loads(write_result["result"]["content"][0]["text"])
        memory_id = write_data["id"]

        # Search for it
        search_result = await call_mcp_tool(client, "search_memory", {
            "tags": [unique_tag],
            "limit": 5,
        })

        search_data = json.loads(search_result["result"]["content"][0]["text"])

        # Verify found
        assert search_data["total"] >= 1
        found_ids = [m["id"] for m in search_data["memories"]]
        assert memory_id in found_ids


@pytest.mark.asyncio
async def test_concurrent_write_requests():
    """Multiple concurrent write requests all succeed."""
    async with httpx.AsyncClient() as client:
        async def write_one(i: int):
            return await call_mcp_tool(client, "write_memory", {
                "title": f"Concurrent test {i}",
                "content": f"Concurrent write number {i}",
                "memory_type": "note",
                "tags": ["concurrent-test"],
            })

        tasks = [write_one(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        for r in results:
            assert r["result"]["isError"] is False
            data = json.loads(r["result"]["content"][0]["text"])
            assert "id" in data


@pytest.mark.asyncio
async def test_concurrent_search_requests():
    """Multiple concurrent search requests all succeed."""
    async with httpx.AsyncClient() as client:
        async def search_one(i: int):
            return await call_mcp_tool(client, "search_memory", {
                "query": "test",
                "limit": 3,
            })

        tasks = [search_one(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        for r in results:
            assert r["result"]["isError"] is False


@pytest.mark.asyncio
async def test_mcp_server_survives_rapid_requests():
    """Server stays responsive after 50 rapid sequential requests."""
    async with httpx.AsyncClient() as client:
        start = time.time()

        for i in range(50):
            result = await call_mcp_tool(client, "ping", {})
            data = json.loads(result["result"]["content"][0]["text"])
            assert data["success"] is True

        elapsed = time.time() - start
        avg_ms = (elapsed / 50) * 1000

        # Average should be well under 100ms
        assert avg_ms < 100, f"Average ping too slow: {avg_ms:.1f}ms"


@pytest.mark.asyncio
async def test_write_memory_special_characters():
    """write_memory handles special characters correctly."""
    async with httpx.AsyncClient() as client:
        result = await call_mcp_tool(client, "write_memory", {
            "title": "Test: émojis 🎉 et accents éàç",
            "content": "User: 你好 مرحبا\nClaude: Çà fonctionne! 🚀",
            "memory_type": "note",
            "tags": ["unicode-test", "special-chars"],
        })

        data = json.loads(result["result"]["content"][0]["text"])
        assert "id" in data
        assert result["result"]["isError"] is False


@pytest.mark.asyncio
async def test_search_memory_by_lifecycle_state():
    """search_memory accepts lifecycle_state parameter."""
    async with httpx.AsyncClient() as client:
        result = await call_mcp_tool(client, "search_memory", {
            "tags": ["sys:core"],
            "lifecycle_state": "sealed",
            "limit": 5,
        })

        assert result["result"]["isError"] is False
        data = json.loads(result["result"]["content"][0]["text"])
        assert "memories" in data


@pytest.mark.asyncio
async def test_write_and_read_memory_full_cycle():
    """Full CRUD cycle: write → search → verify exists."""
    async with httpx.AsyncClient() as client:
        # 1. Write
        write_result = await call_mcp_tool(client, "write_memory", {
            "title": "Full cycle test memory",
            "content": "This tests the full write-search cycle",
            "memory_type": "decision",
            "tags": ["full-cycle-test"],
            "author": "integration-test-suite",
        })

        write_data = json.loads(write_result["result"]["content"][0]["text"])
        assert write_data["memory_type"] == "decision"

        # 2. Search and find
        search_result = await call_mcp_tool(client, "search_memory", {
            "tags": ["full-cycle-test"],
            "limit": 5,
        })

        search_data = json.loads(search_result["result"]["content"][0]["text"])
        assert search_data["total"] >= 1

        # 3. Verify the memory has correct type
        found = [m for m in search_data["memories"] if m["title"] == "Full cycle test memory"]
        assert len(found) >= 1
        assert found[0]["memory_type"] == "decision"
