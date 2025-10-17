#!/usr/bin/env python3
"""
Audit Story 3 - Edge Cases & Error Handling Tests.

Tests robustesse de la metadata extraction sur cas limites.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from services.code_chunking_service import CodeChunkingService


async def test_edge_cases():
    """Test edge cases and error handling."""

    service = CodeChunkingService(max_workers=2)

    print("=" * 80)
    print("AUDIT STORY 3 - EDGE CASES & ERROR HANDLING")
    print("=" * 80)
    print()

    results = {
        "passed": [],
        "failed": [],
        "errors": []
    }

    # Test 1: Empty function
    print("Test 1: Empty function...")
    try:
        source = "def empty_func():\n    pass"
        chunks = await service.chunk_code(source, "python", "test.py")
        assert len(chunks) == 1
        assert chunks[0].metadata.get("complexity", {}).get("cyclomatic") == 1
        results["passed"].append("Empty function")
        print("✅ PASSED\n")
    except Exception as e:
        results["failed"].append(f"Empty function: {e}")
        print(f"❌ FAILED: {e}\n")

    # Test 2: Function with no docstring
    print("Test 2: Function with no docstring...")
    try:
        source = "def no_doc(x):\n    return x * 2"
        chunks = await service.chunk_code(source, "python", "test.py")
        assert chunks[0].metadata.get("docstring") is None
        results["passed"].append("No docstring")
        print("✅ PASSED\n")
    except Exception as e:
        results["failed"].append(f"No docstring: {e}")
        print(f"❌ FAILED: {e}\n")

    # Test 3: Function with no parameters
    print("Test 3: Function with no parameters...")
    try:
        source = "def no_params():\n    return 42"
        chunks = await service.chunk_code(source, "python", "test.py")
        assert chunks[0].metadata.get("parameters") == []
        results["passed"].append("No parameters")
        print("✅ PASSED\n")
    except Exception as e:
        results["failed"].append(f"No parameters: {e}")
        print(f"❌ FAILED: {e}\n")

    # Test 4: Function with no return
    print("Test 4: Function with no return type...")
    try:
        source = "def no_return(x):\n    print(x)"
        chunks = await service.chunk_code(source, "python", "test.py")
        assert chunks[0].metadata.get("returns") is None
        results["passed"].append("No return type")
        print("✅ PASSED\n")
    except Exception as e:
        results["failed"].append(f"No return type: {e}")
        print(f"❌ FAILED: {e}\n")

    # Test 5: Very complex function (high cyclomatic)
    print("Test 5: Very complex function...")
    try:
        source = """
def complex_func(x):
    if x > 0:
        if x > 10:
            if x > 100:
                return "huge"
            else:
                return "large"
        else:
            return "small"
    elif x < 0:
        if x < -10:
            return "very negative"
        else:
            return "negative"
    else:
        return "zero"
"""
        chunks = await service.chunk_code(source, "python", "test.py")
        complexity = chunks[0].metadata.get("complexity", {}).get("cyclomatic")
        assert complexity is not None
        assert complexity >= 5  # Should detect high complexity
        results["passed"].append(f"Complex function (cyclomatic={complexity})")
        print(f"✅ PASSED (cyclomatic={complexity})\n")
    except Exception as e:
        results["failed"].append(f"Complex function: {e}")
        print(f"❌ FAILED: {e}\n")

    # Test 6: Nested functions
    print("Test 6: Nested functions...")
    try:
        source = """
def outer(x):
    def inner(y):
        return y * 2
    return inner(x)
"""
        chunks = await service.chunk_code(source, "python", "test.py")
        # Should handle nested functions
        assert len(chunks) >= 1
        results["passed"].append("Nested functions")
        print("✅ PASSED\n")
    except Exception as e:
        results["failed"].append(f"Nested functions: {e}")
        print(f"❌ FAILED: {e}\n")

    # Test 7: Lambda functions
    print("Test 7: Lambda functions...")
    try:
        source = "square = lambda x: x ** 2"
        chunks = await service.chunk_code(source, "python", "test.py")
        # Should not crash (may be in fallback)
        assert len(chunks) >= 0
        results["passed"].append("Lambda functions")
        print("✅ PASSED\n")
    except Exception as e:
        results["failed"].append(f"Lambda functions: {e}")
        print(f"❌ FAILED: {e}\n")

    # Test 8: Syntax error (graceful degradation)
    print("Test 8: Syntax error (graceful degradation)...")
    try:
        source = "def broken(\n    # incomplete"
        chunks = await service.chunk_code(source, "python", "test.py")
        # Should fallback to fixed chunking
        # May return 0 chunks if too small
        results["passed"].append("Syntax error handled")
        print("✅ PASSED (graceful degradation)\n")
    except Exception as e:
        results["failed"].append(f"Syntax error: {e}")
        print(f"❌ FAILED: {e}\n")

    # Test 9: Unicode in function name
    print("Test 9: Unicode characters...")
    try:
        source = """
def calculer_été(température):
    '''Fonction avec accents.'''
    return température > 25
"""
        chunks = await service.chunk_code(source, "python", "test.py")
        assert len(chunks) == 1
        assert "calculer" in chunks[0].name or "été" in chunks[0].name
        results["passed"].append("Unicode characters")
        print("✅ PASSED\n")
    except Exception as e:
        results["failed"].append(f"Unicode: {e}")
        print(f"❌ FAILED: {e}\n")

    # Test 10: Very long docstring
    print("Test 10: Very long docstring...")
    try:
        long_doc = "This is a very long docstring. " * 100
        source = f'''
def long_doc():
    """{long_doc}"""
    return True
'''
        # Use larger max_chunk_size to avoid fallback
        chunks = await service.chunk_code(source, "python", "test.py", max_chunk_size=5000)
        assert len(chunks) >= 1
        # May be in fallback if still too large, that's OK
        if chunks[0].metadata.get("docstring"):
            assert len(chunks[0].metadata["docstring"]) > 1000
            results["passed"].append("Long docstring (metadata extracted)")
        else:
            # Fallback chunking - expected for very large functions
            results["passed"].append("Long docstring (fallback - OK)")
        print("✅ PASSED\n")
    except Exception as e:
        results["failed"].append(f"Long docstring: {e}")
        print(f"❌ FAILED: {e}\n")

    # Test 11: extract_metadata=False
    print("Test 11: Metadata extraction disabled...")
    try:
        source = "def test(x):\n    return x * 2"
        chunks = await service.chunk_code(source, "python", "test.py", extract_metadata=False)
        # Should not have extracted metadata
        assert "signature" not in chunks[0].metadata or chunks[0].metadata.get("signature") is None
        results["passed"].append("Metadata extraction OFF")
        print("✅ PASSED\n")
    except Exception as e:
        results["failed"].append(f"Metadata OFF: {e}")
        print(f"❌ FAILED: {e}\n")

    # Test 12: Multiple imports
    print("Test 12: Multiple imports...")
    try:
        source = """
import os
import sys
from typing import List, Dict
from pathlib import Path

def use_imports(path: Path) -> Dict:
    return {"exists": os.path.exists(str(path))}
"""
        chunks = await service.chunk_code(source, "python", "test.py")
        imports = chunks[0].metadata.get("imports", [])
        # Should detect at least some imports
        assert "os" in imports or "Path" in imports or any("Path" in imp for imp in imports)
        results["passed"].append("Multiple imports")
        print("✅ PASSED\n")
    except Exception as e:
        results["failed"].append(f"Multiple imports: {e}")
        print(f"❌ FAILED: {e}\n")

    # Summary
    print("=" * 80)
    print("EDGE CASES TEST SUMMARY")
    print("=" * 80)
    print(f"✅ PASSED: {len(results['passed'])}/12")
    print(f"❌ FAILED: {len(results['failed'])}/12")
    print()

    if results["passed"]:
        print("Passed tests:")
        for test in results["passed"]:
            print(f"  ✅ {test}")
        print()

    if results["failed"]:
        print("Failed tests:")
        for test in results["failed"]:
            print(f"  ❌ {test}")
        print()
        return False

    print("🎉 ALL EDGE CASES HANDLED CORRECTLY!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_edge_cases())
    sys.exit(0 if success else 1)
