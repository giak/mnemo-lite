# MnemoLite Test Suite

This directory contains all automated tests for the MnemoLite project, ensuring the reliability and correctness of its components.

## Overview

The test suite is designed to cover various aspects of the application, including:

*   API Endpoints (Routes) - Agent Memory + Code Intelligence
*   Service Layer Logic - Events, Search, Code Intelligence
*   Database Repository Interactions - EventRepository, CodeChunkRepository, GraphRepository
*   Core Utilities and Protocols
*   Dependency Injection Mechanisms
*   Performance Testing - Load testing with Locust
*   End-to-End Testing - UI testing with Playwright

We use `pytest` as the test runner, `pytest-cov` for coverage reports, and have integrated CI/CD with GitHub Actions (EPIC-08).

## Test Categories

The tests are organized to reflect the project's structure:

*   **Route Tests:** (`test_*_routes.py`)
    *   `test_event_routes.py`: Tests for `/v1/events` endpoints.
    *   `test_health_routes.py`: Tests for `/v1/health` endpoint.
    *   `test_memory_routes.py`: Tests for `/v1/memories` endpoints (if applicable, or general memory operations).
    *   `test_search_routes.py`: Tests for `/v1/search` endpoints.
*   **Service Tests:** (`test_*_service.py`)
    *   `test_embedding_service.py`: Tests for the embedding generation/handling service.
    *   `test_memory_search_service.py`: Tests for the memory and search orchestration logic.
    *   `test_notification_service.py`: Tests for any notification mechanisms.
*   **Repository & Database Tests:** (`db/` and `test_*_repository.py`)
    *   `tests/db/repositories/test_event_repository.py`: Tests for `EventRepository` interactions with the database.
    *   `tests/db/repositories/test_memory_repository.py`: Tests for `MemoryRepository` interactions.
    *   (Other files in `tests/db/` would be listed here)
*   **Protocol Conformance Tests:** (`test_*_protocols.py`)
    *   `test_memory_protocols.py`: Ensures memory-related components adhere to defined interfaces.
    *   `test_repository_protocols.py`: Ensures repository components adhere to defined interfaces.
*   **Core Logic Tests:**
    *   `test_dependency_injection.py`: Validates the dependency injection setup.
    *   `test_event_processor.py`: Tests for any central event processing logic.

## Running Tests

Tests are typically executed using `make` targets or dedicated scripts.

### Quick Testing (EPIC-08)
*   **Quick test suite:**
    ```bash
    ./test_application.sh quick
    ```
*   **Full test suite:**
    ```bash
    ./test_application.sh full
    ```
*   **Load testing:**
    ```bash
    ./test_application.sh load
    ```

### Standard Testing
*   **Run all tests:**
    ```bash
    make api-test
    ```
*   **Run tests with coverage report:**
    ```bash
    make api-coverage
    ```
    This command will output a summary to the console and often generate a detailed HTML report (e.g., in an `htmlcov/` directory).

### Performance Testing (EPIC-08)
*   **Benchmark performance:**
    ```bash
    ./apply_optimizations.sh benchmark
    ```
*   **Load testing with Locust:**
    ```bash
    locust -f locust_load_test.py
    ```

### CI/CD Testing
*   Tests run automatically on push/PR via GitHub Actions
*   See `.github/workflows/test.yml` for CI/CD configuration

## Test Coverage Status (v2.0.0 - EPIC-08)

**Overall Coverage:** `~87%` (Agent Memory) + `100%` (Code Intelligence Services)

**Total Tests:** 245 passing
*   Agent Memory: 102 tests (40/42 passing optimized routes = 95.2%)
*   Code Intelligence: 126 tests (100% passing)
*   Integration Tests: 17 tests

### Agent Memory Coverage

**Key Areas & Coverage Details:**

*   `api/routes/` (`event_routes.py`, `health_routes.py`, `search_routes.py`): ~`74%`
    *   `routes/event_routes.py`: `72%` (95.2% with optimized cache routes)
    *   `routes/health_routes.py`: `58%`
    *   `routes/search_routes.py`: `65%`
*   `api/services/` (`embedding_service.py`, `event_processor.py`, `memory_search_service.py`): ~`83%`
    *   `services/embedding_service.py`: `78%`
    *   `services/event_processor.py`: `90%`
    *   `services/memory_search_service.py`: `76%`
    *   `services/simple_memory_cache.py`: `100%` (EPIC-08)
*   `api/db/repositories/`:
    *   `db/repositories/event_repository.py`: `76%`
*   `api/models/`:
    *   `models/event_models.py`: `76%`
*   `main.py`: `72%`

### Code Intelligence Coverage (EPIC-06)

**Services Coverage:** `100%`
*   `services/code_chunking_service.py`: `100%` (9/10 tests, 1 xfail)
*   `services/metadata_extractor_service.py`: `100%` (34/34 tests)
*   `services/graph_construction_service.py`: `100%` (11/11 tests)
*   `services/graph_traversal_service.py`: `100%` (9/9 tests)
*   `services/hybrid_code_search_service.py`: `100%` (43/43 tests)
*   `services/code_indexing_service.py`: `100%` (19/19 tests)

**Repositories Coverage:** `100%`
*   `db/repositories/code_chunk_repository.py`: `100%` (10/10 tests)
*   `db/repositories/node_repository.py`: Integrated tests
*   `db/repositories/edge_repository.py`: Integrated tests

### Performance Testing Coverage (EPIC-08)

**Infrastructure:**
*   CI/CD Pipeline: GitHub Actions (`.github/workflows/test.yml`)
*   E2E Testing: Playwright (`tests/e2e/playwright_tests.js`)
*   Load Testing: Locust (`locust_load_test.py`)
*   Quick Testing: `test_application.sh` (quick/full/load modes)

**Performance Metrics:**
*   40/42 agent memory tests passing (95.2%)
*   126/126 code intelligence tests passing (100%)
*   Load testing: 100 req/s sustained, 0 errors
*   Cache hit rate: 80%+ after warm-up

**To update coverage information:**

1.  Run `make api-coverage` from the project root.
2.  Run `./test_application.sh full` for comprehensive testing.
3.  Note the overall coverage percentage and any relevant per-module/file percentages.
4.  Update the placeholders in this README accordingly. 