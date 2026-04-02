"""
Load Testing for MnemoLite API
Usage: locust -f locust_load_test.py --host http://localhost:8001
"""

from locust import HttpUser, task, between, TaskSet
from locust.contrib.fasthttp import FastHttpUser
import random
import json
import uuid
from datetime import datetime, timedelta

# Sample data for testing
SAMPLE_REPOSITORIES = [
    "numpy", "pandas", "django", "flask", "fastapi",
    "pytorch", "tensorflow", "scikit-learn", "requests", "pytest"
]

SAMPLE_CODE_QUERIES = [
    "def calculate", "import numpy", "class Model", "async def",
    "SELECT * FROM", "raise Exception", "return result", "@property",
    "for item in", "while True", "if __name__", "try except"
]

SAMPLE_PYTHON_CODE = '''
def {func_name}(param1, param2):
    """Sample function for load testing."""
    result = param1 + param2
    return result * random.random()

class {class_name}:
    def __init__(self):
        self.value = random.randint(1, 100)

    def process(self):
        return self.value ** 2
'''

class CodeSearchTasks(TaskSet):
    """Tasks for code search functionality."""

    @task(3)
    def search_code(self):
        """Search for code with random queries."""
        query = random.choice(SAMPLE_CODE_QUERIES)
        with self.client.post(
            "/v1/search/",
            json={
                "query": query,
                "limit": random.choice([10, 20, 50]),
                "offset": 0
            },
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "events" in data:
                    response.success()
                else:
                    response.failure(f"Invalid response format: {data}")
            else:
                response.failure(f"Search failed: {response.status_code}")

    @task(2)
    def filter_by_repository(self):
        """Search within specific repository."""
        repo = random.choice(SAMPLE_REPOSITORIES)
        with self.client.post(
            "/v1/search/",
            json={
                "metadata": {"repository": repo},
                "limit": 20
            },
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()

    @task(1)
    def get_code_stats(self):
        """Get repository statistics."""
        repo = random.choice(SAMPLE_REPOSITORIES)
        self.client.get(f"/v1/code/repos/{repo}/stats")

class CodeIndexingTasks(TaskSet):
    """Tasks for code indexing functionality."""

    @task(5)
    def index_single_file(self):
        """Index a single Python file."""
        func_name = f"function_{uuid.uuid4().hex[:8]}"
        class_name = f"Class_{uuid.uuid4().hex[:8]}"
        code = SAMPLE_PYTHON_CODE.format(
            func_name=func_name,
            class_name=class_name
        )

        response = self.client.post(
            "/v1/code/index",
            json={
                "repository": random.choice(SAMPLE_REPOSITORIES),
                "files": [{
                    "path": f"src/{func_name}.py",
                    "content": code,
                    "language": "python"
                }]
            }
        )

        if response.status_code == 200:
            self.user.indexed_files.append(func_name)

    @task(2)
    def batch_index_files(self):
        """Index multiple files at once."""
        files = []
        for i in range(random.randint(5, 20)):
            func_name = f"batch_func_{uuid.uuid4().hex[:8]}"
            files.append({
                "path": f"batch/{func_name}.py",
                "content": SAMPLE_PYTHON_CODE.format(
                    func_name=func_name,
                    class_name=f"BatchClass{i}"
                ),
                "language": "python"
            })

        self.client.post(
            "/v1/code/index",
            json={
                "repository": random.choice(SAMPLE_REPOSITORIES),
                "files": files
            }
        )

class GraphVisualizationTasks(TaskSet):
    """Tasks for dependency graph operations."""

    @task(3)
    def get_dependency_graph(self):
        """Fetch dependency graph for a repository."""
        repo = random.choice(SAMPLE_REPOSITORIES)
        self.client.get(f"/v1/code/graph/build?repository={repo}")

    @task(2)
    def traverse_graph(self):
        """Traverse graph from random node."""
        if self.user.indexed_files:
            node = random.choice(self.user.indexed_files)
            self.client.post(
                "/v1/code/graph/traverse",
                json={
                    "start_node": node,
                    "max_depth": random.randint(1, 3),
                    "direction": random.choice(["forward", "backward", "both"])
                }
            )

    @task(1)
    def get_node_details(self):
        """Get details for specific node."""
        if self.user.indexed_files:
            node = random.choice(self.user.indexed_files)
            self.client.get(f"/v1/code/graph/node/{node}")

class EventOperationsTasks(TaskSet):
    """Basic CRUD operations on events."""

    def on_start(self):
        """Initialize user session."""
        self.created_events = []

    @task(10)
    def create_event(self):
        """Create a new event."""
        response = self.client.post(
            "/v1/events/",
            json={
                "content": {
                    "text": f"Load test event {uuid.uuid4()}",
                    "type": "code_analysis",
                    "timestamp": datetime.utcnow().isoformat()
                },
                "metadata": {
                    "source": "load_test",
                    "user": f"user_{self.user.user_id}",
                    "repository": random.choice(SAMPLE_REPOSITORIES)
                }
            }
        )
        if response.status_code == 201:
            event_id = response.json().get("id")
            if event_id:
                self.created_events.append(event_id)

    @task(5)
    def read_event(self):
        """Read an existing event."""
        if self.created_events:
            event_id = random.choice(self.created_events)
            self.client.get(f"/v1/events/{event_id}")

    @task(2)
    def update_event(self):
        """Update event metadata."""
        if self.created_events:
            event_id = random.choice(self.created_events)
            self.client.patch(
                f"/v1/events/{event_id}/metadata",
                json={
                    "updated_at": datetime.utcnow().isoformat(),
                    "status": "processed"
                }
            )

    @task(1)
    def delete_event(self):
        """Delete an event."""
        if len(self.created_events) > 10:  # Keep some events
            event_id = self.created_events.pop(0)
            self.client.delete(f"/v1/events/{event_id}")

class HealthCheckTasks(TaskSet):
    """System health and monitoring tasks."""

    @task(10)
    def health_check(self):
        """Check system health."""
        self.client.get("/health")

    @task(2)
    def metrics_check(self):
        """Get system metrics."""
        self.client.get("/performance/metrics")

    @task(1)
    def cache_stats(self):
        """Get cache statistics."""
        self.client.get("/performance/cache/stats")

class MnemoLiteUser(FastHttpUser):
    """Main user class for load testing."""

    # Wait between 1-3 seconds between tasks
    wait_time = between(1, 3)

    # Task distribution (weights)
    tasks = {
        CodeSearchTasks: 40,      # 40% search operations
        CodeIndexingTasks: 20,    # 20% indexing
        EventOperationsTasks: 20, # 20% CRUD
        GraphVisualizationTasks: 15, # 15% graph
        HealthCheckTasks: 5       # 5% health checks
    }

    def on_start(self):
        """Initialize user session."""
        self.user_id = uuid.uuid4().hex[:8]
        self.indexed_files = []
        print(f"User {self.user_id} starting...")

    def on_stop(self):
        """Clean up user session."""
        print(f"User {self.user_id} stopping...")

class AdminUser(FastHttpUser):
    """Admin user for heavy operations."""

    wait_time = between(5, 10)
    weight = 1  # Only 1 admin per 10 regular users

    @task
    def reindex_repository(self):
        """Trigger full repository reindex."""
        repo = random.choice(SAMPLE_REPOSITORIES)
        self.client.post(f"/v1/code/repos/{repo}/reindex")

    @task
    def cleanup_old_data(self):
        """Clean up old test data."""
        cutoff_date = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        self.client.delete(f"/v1/events/cleanup?before={cutoff_date}")

    @task
    def optimize_database(self):
        """Trigger database optimization."""
        self.client.post("/v1/admin/optimize")

# Custom load test scenarios
class StressTestScenario(FastHttpUser):
    """Stress test with rapid requests."""

    wait_time = between(0.1, 0.5)  # Very fast requests

    @task
    def rapid_search(self):
        """Rapid fire search requests."""
        for _ in range(10):
            query = random.choice(SAMPLE_CODE_QUERIES)
            self.client.post(
                "/v1/search/",
                json={"query": query, "limit": 5},
                catch_response=True
            )

class SpikeTestScenario(FastHttpUser):
    """Spike test to simulate traffic surge."""

    wait_time = between(0.5, 1)

    @task
    def surge_traffic(self):
        """Simulate sudden traffic spike."""
        # Burst of 50 requests
        for _ in range(50):
            endpoint = random.choice([
                "/v1/search/",
                "/v1/events/",
                "/health",
                "/v1/code/graph/build"
            ])

            if "search" in endpoint:
                self.client.post(endpoint, json={"query": "test"})
            elif "events" in endpoint:
                self.client.post(endpoint, json={
                    "content": {"text": "spike test"}
                })
            else:
                self.client.get(endpoint)

# Configuration for different test scenarios
if __name__ == "__main__":
    import sys

    scenario = sys.argv[1] if len(sys.argv) > 1 else "normal"

    print(f"""
    ╔══════════════════════════════════════════╗
    ║     MnemoLite Load Test - {scenario:^10}    ║
    ╠══════════════════════════════════════════╣
    ║ Scenarios:                               ║
    ║ - normal: Mixed realistic traffic        ║
    ║ - stress: High frequency requests        ║
    ║ - spike: Sudden traffic surges           ║
    ║ - endurance: Long running test           ║
    ╚══════════════════════════════════════════╝

    Usage: locust -f {__file__} --host http://localhost:8001
    Web UI: http://localhost:8089
    """)