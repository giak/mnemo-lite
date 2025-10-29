#!/usr/bin/env python3
"""
Test if write_memory tool has services properly injected.
"""

import asyncio
import sys
import os

os.chdir('/app')
sys.path.insert(0, '/app')


async def test_service_injection():
    """Test if services are properly injected into write_memory_tool."""
    try:
        from mnemo_mcp.tools.memory_tools import write_memory_tool

        print("=" * 60)
        print("TEST: write_memory_tool service injection")
        print("=" * 60)

        # Check if services are injected
        if write_memory_tool._services is None:
            print("❌ FAILED: _services is None")
            return False

        print(f"✅ _services exists: {type(write_memory_tool._services)}")
        print(f"   Services available: {list(write_memory_tool._services.keys())}")

        # Check memory_repository
        if "memory_repository" in write_memory_tool._services:
            memory_repo = write_memory_tool._services["memory_repository"]
            print(f"✅ memory_repository exists: {type(memory_repo)}")
        else:
            print("❌ FAILED: memory_repository not in services")
            return False

        # Check embedding_service
        if "embedding_service" in write_memory_tool._services:
            embedding_svc = write_memory_tool._services["embedding_service"]
            print(f"✅ embedding_service exists: {type(embedding_svc)}")
        else:
            print("❌ FAILED: embedding_service not in services")
            return False

        # Check using properties
        print(f"\n--- Testing properties ---")
        print(f"write_memory_tool.memory_repository: {type(write_memory_tool.memory_repository)}")
        print(f"write_memory_tool.embedding_service: {type(write_memory_tool.embedding_service)}")

        if write_memory_tool.memory_repository is None:
            print("❌ FAILED: memory_repository property returns None")
            return False

        if write_memory_tool.embedding_service is None:
            print("❌ FAILED: embedding_service property returns None")
            return False

        print("\n✅ ALL CHECKS PASSED")
        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_service_injection())
    sys.exit(0 if result else 1)
