# MnemoLite Test Suite

This directory contains all automated tests for the MnemoLite project, ensuring the reliability and correctness of its components.

## Overview

The test suite is designed to cover various aspects of the application, including:

*   API Endpoints (Routes)
*   Service Layer Logic
*   Database Repository Interactions
*   Core Utilities and Protocols
*   Dependency Injection Mechanisms

We use `pytest` as the test runner and `pytest-cov` for generating coverage reports.

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

Tests are typically executed using `make` targets defined in the project's `Makefile`.

*   **Run all tests:**
    ```bash
    make api-test
    ```
*   **Run tests with coverage report:**
    ```bash
    make api-coverage
    ```
    This command will output a summary to the console and often generate a detailed HTML report (e.g., in an `htmlcov/` directory).

## Test Coverage Status

**Overall Coverage:** `87%`

**Key Areas & Coverage Details (approximate based on output):**

*   `api/routes/` (`event_routes.py`, `health_routes.py`, `memory_routes.py`, `search_routes.py`): ~`74%`
    *   `routes/event_routes.py`: `72%`
    *   `routes/health_routes.py`: `58%`
    *   `routes/memory_routes.py`: `100%`
    *   `routes/search_routes.py`: `65%`
*   `api/services/` (`embedding_service.py`, `event_processor.py`, `memory_search_service.py`, `notification_service.py`): ~`83%`
    *   `services/embedding_service.py`: `78%`
    *   `services/event_processor.py`: `90%`
    *   `services/memory_search_service.py`: `76%`
    *   `services/notification_service.py`: `95%`
*   `api/db/repositories/` (`event_repository.py`, `memory_repository.py`):
    *   `db/repositories/event_repository.py`: `76%`
    *   `db/repositories/memory_repository.py`: `79%`
*   `api/models/`: 
    *   `models/embedding_models.py`: `88%`
    *   `models/event_models.py`: `76%`
    *   `models/memory_models.py`: `79%`
*   `main.py`: `72%`
*   `dependencies.py`: `76%`

*(This section has been updated with the results from `make api-coverage` run on the latest commit. Individual file percentages are taken directly from the report.)*

**To update coverage information:**

1.  Run `make api-coverage` from the project root.
2.  Note the overall coverage percentage and any relevant per-module/file percentages.
3.  Update the placeholders in this README accordingly. 