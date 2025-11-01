#!/usr/bin/env python3
"""
Script to index the CV Generator project into MnemoLite for graph visualization testing.
"""
import json
import requests
from pathlib import Path
from typing import List, Dict, Any

# Configuration
CODE_TEST_ROOT = Path("/home/giak/Work/MnemoLite/code_test")
API_BASE_URL = "http://localhost:8001"
REPOSITORY_NAME = "CVGenerator"

# Directories to scan for TypeScript files
SCAN_DIRS = [
    CODE_TEST_ROOT / "packages" / "core" / "src",
    CODE_TEST_ROOT / "packages" / "infrastructure" / "src",
    CODE_TEST_ROOT / "packages" / "ui" / "src",
]

# File extensions to index
EXTENSIONS = [".ts", ".tsx"]


def find_typescript_files(base_dirs: List[Path], limit: int = 50) -> List[Path]:
    """Find TypeScript files in the given directories."""
    files = []

    for base_dir in base_dirs:
        if not base_dir.exists():
            print(f"⚠️  Directory not found: {base_dir}")
            continue

        for ext in EXTENSIONS:
            for file_path in base_dir.rglob(f"*{ext}"):
                # Skip test files, node_modules, dist
                if any(skip in str(file_path) for skip in ["__tests__", "node_modules", "dist", ".test.", ".spec."]):
                    continue

                files.append(file_path)

                if len(files) >= limit:
                    return files

    return files


def read_file_content(file_path: Path) -> str:
    """Read file content safely."""
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"⚠️  Failed to read {file_path}: {e}")
        return ""


def create_index_request(files: List[Path], repository_root: Path) -> Dict[str, Any]:
    """Create the index request payload."""
    file_inputs = []

    for file_path in files:
        content = read_file_content(file_path)
        if not content:
            continue

        # Get relative path from repository root
        try:
            relative_path = file_path.relative_to(repository_root)
        except ValueError:
            # File is outside repository root, use absolute path
            relative_path = file_path

        file_inputs.append({
            "path": str(relative_path),
            "content": content,
            "language": "typescript"
        })

    return {
        "repository": REPOSITORY_NAME,
        "repository_root": str(repository_root),
        "files": file_inputs,
        "extract_metadata": True,
        "generate_embeddings": False,  # Skip embeddings for speed
        "build_graph": True  # Build graph immediately
    }


def index_repository(request_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send index request to MnemoLite API."""
    url = f"{API_BASE_URL}/v1/code/index"

    print(f"\n🚀 Indexing {len(request_payload['files'])} files...")
    print(f"   Repository: {request_payload['repository']}")
    print(f"   Repository root: {request_payload['repository_root']}")

    response = requests.post(url, json=request_payload, timeout=300)

    if response.status_code == 201:
        return response.json()
    else:
        print(f"❌ Index request failed: {response.status_code}")
        print(f"   Response: {response.text}")
        raise Exception(f"Index request failed: {response.status_code}")


def get_graph_stats(repository: str) -> Dict[str, Any]:
    """Get graph statistics for the repository."""
    url = f"{API_BASE_URL}/v1/code/graph/stats/{repository}"
    response = requests.get(url, timeout=30)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"⚠️  Failed to get graph stats: {response.status_code}")
        return {}


def main():
    """Main execution."""
    print("=" * 80)
    print("📚 MnemoLite CV Project Indexer")
    print("=" * 80)

    # Find TypeScript files
    print("\n🔍 Scanning for TypeScript files...")
    typescript_files = find_typescript_files(SCAN_DIRS, limit=50)

    if not typescript_files:
        print("❌ No TypeScript files found!")
        return

    print(f"✅ Found {len(typescript_files)} TypeScript files")
    print("\nSample files:")
    for i, f in enumerate(typescript_files[:5]):
        print(f"   {i+1}. {f.name} ({f.stat().st_size} bytes)")

    # Create index request
    print("\n📦 Creating index request...")
    request_payload = create_index_request(typescript_files, CODE_TEST_ROOT)

    # Index files
    try:
        result = index_repository(request_payload)

        print("\n✅ Indexing complete!")
        print(f"   📁 Indexed files: {result.get('indexed_files', 0)}")
        print(f"   🧩 Indexed chunks: {result.get('indexed_chunks', 0)}")
        print(f"   🔵 Indexed nodes: {result.get('indexed_nodes', 0)}")
        print(f"   🔗 Indexed edges: {result.get('indexed_edges', 0)}")
        print(f"   ⏱️  Processing time: {result.get('processing_time_ms', 0):.0f}ms")

        if result.get('failed_files', 0) > 0:
            print(f"   ⚠️  Failed files: {result['failed_files']}")
            if result.get('errors'):
                print("   Errors:")
                for error in result.get('errors', [])[:3]:
                    print(f"      - {error}")

        # Get graph stats
        print("\n📊 Fetching graph statistics...")
        stats = get_graph_stats(REPOSITORY_NAME)

        if stats:
            print(f"\n📈 Graph Statistics for {REPOSITORY_NAME}:")
            print(f"   Total nodes: {stats.get('total_nodes', 0)}")
            print(f"   Total edges: {stats.get('total_edges', 0)}")
            print(f"   Nodes by type: {stats.get('nodes_by_type', {})}")
            print(f"   Edges by type: {stats.get('edges_by_type', {})}")

        print("\n" + "=" * 80)
        print("✅ SUCCESS! CV project indexed into MnemoLite")
        print("🌐 Visit http://localhost:3002/graph to see the visualization")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
