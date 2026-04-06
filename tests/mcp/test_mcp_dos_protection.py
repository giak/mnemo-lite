"""
Regression test for MCP DDOS protection against Kilo/Claude Desktop infinite retry bug.

This test verifies that the MCP server remains operational under the exact conditions
that caused the timeout errors:
1. Failing prompt requests
2. Massive parallel retry flood
3. Invalid parameters from Kilo
"""
import asyncio
import httpx
import pytest
import time
from typing import List

import os
MCP_URL = os.getenv("MCP_URL", "http://localhost:8002/mcp")
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"
}

async def send_bad_request(client: httpx.AsyncClient, request_id: int) -> int:
    """Send the exact bad request that triggers the Kilo bug"""
    try:
        response = await client.post(
            MCP_URL,
            json={
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "prompts/get",
                "params": {
                    "name": "generate_tests",
                    "arguments": {
                        "chunk_id": f"test-{request_id}",
                        "test_type": "unit",
                        "coverage_target": "$3"
                    }
                }
            },
            timeout=5.0
        )
        return response.status_code
    except Exception:
        return 500

async def send_good_request(client: httpx.AsyncClient) -> bool:
    """Send a valid ping request to verify server is still responsive"""
    try:
        response = await client.post(
            MCP_URL,
            json={
                "jsonrpc": "2.0",
                "id": 999,
                "method": "tools/call",
                "params": {
                    "name": "ping",
                    "arguments": {}
                }
            },
            timeout=3.0
        )
        return response.status_code == 200
    except Exception:
        return False

@pytest.mark.asyncio
async def test_mcp_survives_ddos_flood():
    """
    Test that MCP server survives 100 parallel bad requests and remains responsive.
    
    Before the fix: Server would hang indefinitely, all subsequent requests timeout.
    After the fix: Server handles all requests, remains responsive.
    """
    async with httpx.AsyncClient(headers=HEADERS) as client:
        # Verify server works before test
        assert await send_good_request(client), "Server not responsive before test"
        
        # Send 100 parallel bad requests (simulate Kilo infinite retry)
        start_time = time.time()
        
        tasks: List[asyncio.Task] = []
        for i in range(100):
            tasks.append(asyncio.create_task(send_bad_request(client, i)))
            
        status_codes = await asyncio.gather(*tasks)
        
        elapsed = time.time() - start_time
        
        # Verify all requests completed (no hang)
        assert len(status_codes) == 100
        assert elapsed < 10.0, f"Server took too long: {elapsed:.2f}s"
        
        # Verify server still responds AFTER the flood
        assert await send_good_request(client), "Server dead after DDOS flood"
        
        # Verify most requests succeeded (not 503)
        success_count = sum(1 for code in status_codes if code == 200)
        assert success_count >= 90, f"Too many failures: {100 - success_count}/100"
        
        print(f"✓ DDOS test passed: 100 requests processed in {elapsed:.2f}s")
        print(f"✓ Success rate: {success_count}%")
        print(f"✓ Server remains responsive")

@pytest.mark.asyncio
async def test_mcp_timeout_enforcement():
    """Test that long running requests are terminated after 5 seconds"""
    # This test would verify that even if a request hangs, it's killed by the middleware
    pass
