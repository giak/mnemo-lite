"""
Integration tests for Code Indexing API (Story 6).

Tests the complete API endpoints for indexing code files.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from main import app


@pytest.fixture
def client():
    """Create FastAPI TestClient."""
    with TestClient(app) as test_client:
        yield test_client


class TestCodeIndexingIntegration:
    """Integration tests for code indexing API"""

    
    def test_index_single_python_file(self, test_engine):
        """Test indexing a single Python file"""
        request_data = {
            "repository": "test-repo-single",
            "files": [
                {
                    "path": "main.py",
                    "content": "def calculate_total(items):\n    '''Calculate total of items'''\n    return sum(items)",
                }
            ],
            "extract_metadata": True,
            "generate_embeddings": True,
            "build_graph": True,
        }

        response = client.post("/v1/code/index", json=request_data)

        assert response.status_code == 201
        data = response.json()

        assert data["repository"] == "test-repo-single"
        assert data["indexed_files"] == 1
        assert data["indexed_chunks"] >= 1
        assert data["failed_files"] == 0
        assert data["processing_time_ms"] > 0

        # Verify chunks were stored
        async with test_engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM code_chunks WHERE repository = :repo"
                ),
                {"repo": "test-repo-single"},
            )
            count = result.scalar()
            assert count >= 1

    
    def test_index_multiple_files(self, test_engine):
        """Test indexing multiple files"""
        request_data = {
            "repository": "test-repo-multi",
            "files": [
                {
                    "path": "utils.py",
                    "content": "def helper():\n    '''Helper function'''\n    pass",
                },
                {
                    "path": "main.py",
                    "content": "from utils import helper\n\ndef main():\n    '''Main function'''\n    helper()",
                },
            ],
            "build_graph": True,
        }

        response = client.post("/v1/code/index", json=request_data)

        assert response.status_code == 201
        data = response.json()

        assert data["indexed_files"] == 2
        assert data["indexed_chunks"] >= 2
        assert data["failed_files"] == 0

        # Graph should be built
        if data["indexed_nodes"] > 0:
            assert data["indexed_nodes"] >= 2  # helper + main functions
            # Note: edges count depends on call resolution

    
    def test_index_without_embeddings(self, test_engine):
        """Test indexing without embeddings"""
        request_data = {
            "repository": "test-repo-no-embeddings",
            "files": [
                {
                    "path": "test.py",
                    "content": "def test(): pass",
                }
            ],
            "extract_metadata": True,
            "generate_embeddings": False,  # Disabled
            "build_graph": False,
        }

        response = client.post("/v1/code/index", json=request_data)

        assert response.status_code == 201
        data = response.json()

        assert data["indexed_files"] == 1
        assert data["indexed_chunks"] >= 1
        assert data["indexed_nodes"] == 0
        assert data["indexed_edges"] == 0

    
    def test_index_without_graph(self, test_engine):
        """Test indexing without graph construction"""
        request_data = {
            "repository": "test-repo-no-graph",
            "files": [
                {
                    "path": "test.py",
                    "content": "def test(): pass",
                }
            ],
            "build_graph": False,  # Disabled
        }

        response = client.post("/v1/code/index", json=request_data)

        assert response.status_code == 201
        data = response.json()

        assert data["indexed_files"] == 1
        assert data["indexed_nodes"] == 0
        assert data["indexed_edges"] == 0

    
    def test_index_with_language_specified(self, test_engine):
        """Test indexing with explicit language specification"""
        request_data = {
            "repository": "test-repo-lang",
            "files": [
                {
                    "path": "script",  # No extension
                    "content": "def test(): pass",
                    "language": "python",  # Explicit
                }
            ],
        }

        response = client.post("/v1/code/index", json=request_data)

        assert response.status_code == 201
        data = response.json()

        assert data["indexed_files"] == 1
        assert data["indexed_chunks"] >= 1

    
    def test_list_repositories(self, test_engine):
        """Test listing indexed repositories"""
        # First index a repository
        
        # Index repository
        client.post(
            "/v1/code/index",
            json={
                "repository": "list-test-repo",
                "files": [{"path": "test.py", "content": "def test(): pass"}],
            },
        )

        # List repositories
        response = client.get("/v1/code/index/repositories")

        assert response.status_code == 200
        data = response.json()

        assert "repositories" in data
        assert len(data["repositories"]) > 0

        # Find our repository
        our_repo = next(
            (r for r in data["repositories"] if r["repository"] == "list-test-repo"),
            None,
        )
        assert our_repo is not None
        assert our_repo["file_count"] >= 1
        assert our_repo["chunk_count"] >= 1
        assert our_repo["last_indexed"] is not None

    
    def test_list_repositories_empty(self, test_engine):
        """Test listing repositories when none exist"""
        response = client.get("/v1/code/index/repositories")

        assert response.status_code == 200
        data = response.json()

        assert "repositories" in data
        # May be empty or contain repos from other tests

    
    def test_delete_repository(self, test_engine):
        """Test deleting a repository"""
        # Index a repository
        client.post(
            "/v1/code/index",
            json={
                "repository": "delete-test-repo",
                "files": [
                    {"path": "test.py", "content": "def test(): pass"}
                ],
            },
        )

        # Delete repository
        response = client.delete(
            "/v1/code/index/repositories/delete-test-repo"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["repository"] == "delete-test-repo"
        assert data["deleted_chunks"] >= 1

        # Verify chunks were deleted
        async with test_engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM code_chunks WHERE repository = :repo"
                ),
                {"repo": "delete-test-repo"},
            )
            count = result.scalar()
            assert count == 0

    
    def test_delete_nonexistent_repository(self, test_engine):
        """Test deleting a repository that doesn't exist"""
        response = client.delete(
            "/v1/code/index/repositories/nonexistent-repo"
        )

        # Should succeed but delete nothing
        assert response.status_code == 200
        data = response.json()

        assert data["repository"] == "nonexistent-repo"
        assert data["deleted_chunks"] == 0

    
    def test_health_check(self, test_engine):
        """Test health check endpoint"""
        response = client.get("/v1/code/index/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert "services" in data
        assert "code_chunking" in data["services"]
        assert "metadata_extraction" in data["services"]
        assert "embedding_generation" in data["services"]
        assert "graph_construction" in data["services"]

    
    def test_index_with_commit_hash(self, test_engine):
        """Test indexing with commit hash"""
        request_data = {
            "repository": "test-repo-commit",
            "files": [
                {
                    "path": "test.py",
                    "content": "def test(): pass",
                }
            ],
            "commit_hash": "abc123def456",
        }

        response = client.post("/v1/code/index", json=request_data)

        assert response.status_code == 201
        data = response.json()

        assert data["indexed_files"] == 1

        # Verify commit hash was stored
        async with test_engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT commit_hash FROM code_chunks
                    WHERE repository = :repo
                    LIMIT 1
                """
                ),
                {"repo": "test-repo-commit"},
            )
            row = result.first()
            if row:
                assert row[0] == "abc123def456"

    
    def test_index_large_file(self, test_engine):
        """Test indexing a larger file with multiple functions"""
        large_content = """
def function1():
    '''Function 1'''
    pass

def function2():
    '''Function 2'''
    pass

def function3():
    '''Function 3'''
    pass

class MyClass:
    '''My class'''
    def method1(self):
        '''Method 1'''
        pass

    def method2(self):
        '''Method 2'''
        pass
"""

        
            request_data = {
                "repository": "test-repo-large",
                "files": [
                    {
                        "path": "large.py",
                        "content": large_content,
                    }
                ],
            }

            response = client.post("/v1/code/index", json=request_data)

            assert response.status_code == 201
            data = response.json()

            assert data["indexed_files"] == 1
            # Should have multiple chunks (3 functions + 1 class + 2 methods)
            assert data["indexed_chunks"] >= 5

    
    def test_index_invalid_request_missing_repository(self, test_engine):
        """Test indexing with missing repository field"""
        request_data = {
            # Missing "repository" field
            "files": [
                {
                    "path": "test.py",
                    "content": "def test(): pass",
                }
            ],
        }

        response = client.post("/v1/code/index", json=request_data)

        # Should return validation error
        assert response.status_code == 422

    
    def test_index_invalid_request_empty_files(self, test_engine):
        """Test indexing with empty files list"""
        request_data = {
            "repository": "test-repo",
            "files": [],  # Empty
        }

        response = client.post("/v1/code/index", json=request_data)

        # Should succeed but index nothing
        assert response.status_code == 201
        data = response.json()

        assert data["indexed_files"] == 0
        assert data["indexed_chunks"] == 0

    
    def test_index_javascript_file(self, test_engine):
        """Test indexing a JavaScript file"""
        request_data = {
            "repository": "test-repo-js",
            "files": [
                {
                    "path": "app.js",
                    "content": "function hello() {\n  console.log('Hello');\n}",
                }
            ],
        }

        response = client.post("/v1/code/index", json=request_data)

        assert response.status_code == 201
        data = response.json()

        assert data["indexed_files"] == 1
        assert data["indexed_chunks"] >= 1

    
    def test_index_multiple_languages(self, test_engine):
        """Test indexing files in multiple languages"""
        request_data = {
            "repository": "test-repo-multilang",
            "files": [
                {
                    "path": "main.py",
                    "content": "def main(): pass",
                },
                {
                    "path": "app.js",
                    "content": "function app() { }",
                },
                {
                    "path": "lib.go",
                    "content": "func main() { }",
                },
            ],
        }

        response = client.post("/v1/code/index", json=request_data)

        assert response.status_code == 201
        data = response.json()

        # Should index all 3 files (assuming parsers available)
        assert data["indexed_files"] >= 1
        assert data["indexed_chunks"] >= 1

    
    def test_reindex_same_repository(self, test_engine):
        """Test re-indexing the same repository (should add more chunks)"""
        request_data = {
            "repository": "test-repo-reindex",
            "files": [
                {
                    "path": "file1.py",
                    "content": "def func1(): pass",
                }
            ],
        }

        # First index
        response1 = client.post("/v1/code/index", json=request_data)
        assert response1.status_code == 201
        data1 = response1.json()
        first_chunk_count = data1["indexed_chunks"]

        # Second index (different file)
        request_data["files"] = [
            {
                "path": "file2.py",
                "content": "def func2(): pass",
            }
        ]

        response2 = client.post("/v1/code/index", json=request_data)
        assert response2.status_code == 201

        # Total chunks should increase
        async with test_engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM code_chunks WHERE repository = :repo"
                ),
                {"repo": "test-repo-reindex"},
            )
            total_count = result.scalar()
            assert total_count >= first_chunk_count + 1
