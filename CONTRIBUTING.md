# Contributing to MnemoLite

First off, thank you for considering contributing to MnemoLite! 🎉

MnemoLite is a PostgreSQL-native cognitive memory system, and we welcome contributions of all kinds: bug fixes, features, documentation improvements, and more.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Commit Conventions](#commit-conventions)
- [Pull Request Process](#pull-request-process)
- [Project Structure](#project-structure)

---

## Code of Conduct

This project adheres to a simple code of conduct:

- **Be respectful** and considerate in your communication
- **Be collaborative** and help others learn and grow
- **Be professional** in all interactions
- **Be patient** with questions and different skill levels

We aim to create a welcoming environment for contributors of all experience levels.

---

## How Can I Contribute?

### 🐛 Reporting Bugs

Before creating a bug report, please check existing issues to avoid duplicates.

**Good bug reports** include:

- **Clear title** (e.g., "Vector search returns 0 results with threshold=0.8")
- **Environment details** (OS, Docker version, MnemoLite version)
- **Steps to reproduce** the issue
- **Expected vs. actual behavior**
- **Relevant logs or error messages**
- **Code snippets** if applicable

**Template:**
```markdown
**Environment:**
- MnemoLite version: 1.3.0
- OS: Ubuntu 22.04
- Docker version: 24.0.6

**Bug Description:**
Vector search with threshold=0.8 returns 0 results despite having matching events.

**Steps to Reproduce:**
1. Create event with content "test message"
2. Search with vector_query="test message" and distance_threshold=0.8
3. Observe 0 results

**Expected:** At least 1 result (the created event)
**Actual:** 0 results

**Logs:**
```
[2025-10-14 10:00:00] WARNING: Vector search with threshold 0.8 returned 0 results
```
```

### 💡 Suggesting Features

We love feature suggestions! Before proposing a feature:

1. **Search existing issues** to avoid duplicates
2. **Explain the use case** - why is this feature needed?
3. **Describe the proposed solution** - how should it work?
4. **Consider alternatives** - are there other approaches?

Label your issue with `enhancement` or `feature-request`.

### 📖 Improving Documentation

Documentation improvements are highly valued! This includes:

- Fixing typos or clarifying explanations
- Adding examples or tutorials
- Improving API documentation
- Translating documentation
- Creating diagrams or visualizations

### 🔧 Contributing Code

We welcome code contributions! See the sections below for our development workflow and standards.

---

## Development Setup

MnemoLite uses **Docker** for development to ensure environment consistency. You don't need to install Python or PostgreSQL locally.

### Prerequisites

- Docker & Docker Compose v2+
- Git
- Make (optional but recommended)

### Initial Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/MnemoLite.git
cd MnemoLite

# 2. Copy environment file
cp .env.example .env
# Review .env and adjust if needed (defaults work for development)

# 3. Start services
make up
# Or: docker compose up -d

# 4. Verify installation
make health
# Expected: {"status":"healthy","services":{"postgres":{"status":"ok"}}}

# 5. Run tests to ensure everything works
make api-test
# Expected: 102 passed, 11 skipped
```

### Development Commands

```bash
# Services
make up          # Start all services
make down        # Stop all services
make restart     # Restart services
make ps          # Show service status
make logs        # Show all logs
make api-logs    # Show API logs only
make db-logs     # Show database logs

# Development
make api-shell   # Open shell in API container
make db-shell    # Open psql shell in database

# Testing
make api-test                    # Run all unit tests
make api-test-file file=X        # Run specific test file
make api-test-one test=X         # Run specific test
make coverage                    # Generate coverage report

# Code Quality
make lint        # Run linters (black, isort, flake8)
make lint-fix    # Auto-fix linting issues
```

---

## Development Workflow

### 1. Create a Branch

```bash
# Create a feature branch from main
git checkout main
git pull origin main
git checkout -b feature/my-awesome-feature

# Branch naming conventions:
# - feature/description    (new features)
# - fix/description        (bug fixes)
# - docs/description       (documentation)
# - refactor/description   (code refactoring)
# - test/description       (test improvements)
```

### 2. Make Changes

- **Keep changes focused** - one feature/fix per branch
- **Write tests** for new functionality
- **Update documentation** if needed
- **Follow coding standards** (see below)

### 3. Test Locally

```bash
# Run tests
make api-test

# Check linting
make lint

# Test manually
curl http://localhost:8001/health
```

### 4. Commit Changes

Follow our [commit conventions](#commit-conventions) (see below).

```bash
git add .
git commit -m "feat(search): Add distance_threshold validation"
```

### 5. Push and Create PR

```bash
git push origin feature/my-awesome-feature
```

Then create a Pull Request on GitHub (see [PR Process](#pull-request-process)).

---

## Coding Standards

### Python Style

We follow **PEP 8** with some adaptations:

- **Line length**: 100 characters (soft limit, 120 hard limit)
- **Indentation**: 4 spaces (no tabs)
- **Quotes**: Double quotes `"` for strings (consistent with existing code)
- **Imports**: Grouped (stdlib, third-party, local) and sorted (isort)

### Code Formatting

We use automated formatters:

```bash
# Auto-format code
make lint-fix

# Tools used:
# - black: Code formatting
# - isort: Import sorting
# - flake8: Style checking
```

### Type Hints

Use type hints for all function signatures:

```python
# Good ✅
async def search_vector(
    self,
    vector: Optional[List[float]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    limit: int = 10
) -> Tuple[List[EventModel], int]:
    ...

# Bad ❌
async def search_vector(self, vector=None, metadata=None, limit=10):
    ...
```

### Docstrings

Use **Google-style docstrings** for all public functions/classes:

```python
def my_function(param1: str, param2: int) -> bool:
    """
    Brief description of the function (one line).

    Longer description if needed. Explain the purpose, behavior,
    and any important details.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When and why this exception is raised

    Example:
        >>> result = my_function("test", 42)
        >>> print(result)
        True
    """
    ...
```

### Error Handling

- Use **specific exceptions** (ValueError, KeyError, etc.)
- **Log errors** with context (structlog)
- **Don't catch generic Exception** unless necessary
- **Clean up resources** in finally blocks

```python
# Good ✅
try:
    result = await repository.get_by_id(event_id)
    if result is None:
        raise ValueError(f"Event not found: {event_id}")
except asyncpg.PostgresError as e:
    logger.error("Database error", extra={"event_id": str(event_id), "error": str(e)})
    raise
finally:
    await cleanup_resources()

# Bad ❌
try:
    result = await repository.get_by_id(event_id)
except:
    pass
```

---

## Testing Guidelines

### Test Organization

```
tests/
├── conftest.py                      # Shared fixtures
├── test_*.py                        # Unit tests
├── db/repositories/test_*.py        # Repository tests
├── integration/test_*.py            # Integration tests
└── performance/test_*.py            # Performance tests
```

### Writing Tests

- **Use pytest** with async support (`@pytest.mark.anyio`)
- **Test one thing** per test function
- **Use descriptive names** (`test_search_vector_returns_empty_with_strict_threshold`)
- **Arrange-Act-Assert** pattern
- **Use fixtures** for common setup

```python
@pytest.mark.anyio
async def test_search_vector_with_metadata_filter(mock_engine, sample_event):
    """
    Test vector search combined with metadata filtering.

    Verifies that search_vector correctly combines vector similarity
    with metadata filters in a single query.
    """
    # Arrange
    repository = EventRepository(engine=mock_engine)
    vector = [0.1] * 768
    metadata = {"type": "test"}

    # Act
    results, total = await repository.search_vector(
        vector=vector,
        metadata=metadata,
        limit=10
    )

    # Assert
    assert len(results) >= 0
    assert total >= 0
    assert all(r.metadata.get("type") == "test" for r in results)
```

### Test Coverage

- **Aim for 90%+ coverage** for new code
- **Test happy paths** and **error cases**
- **Test edge cases** (empty input, null values, boundary conditions)

```bash
# Generate coverage report
make coverage

# View HTML report
open htmlcov/index.html
```

### Running Tests

```bash
# All unit tests
make api-test

# Specific test file
make api-test-file file=tests/test_search_routes.py

# Specific test
make api-test-one test=test_search_vector_with_metadata

# With coverage
make coverage
```

---

## Commit Conventions

We follow **Conventional Commits** for clear, structured commit history.

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring (no functional change)
- `test`: Adding or updating tests
- `chore`: Maintenance tasks (dependencies, build config)
- `perf`: Performance improvements
- `style`: Code style changes (formatting, no logic change)

### Scopes (examples)

- `search`: Search functionality
- `embedding`: Embedding generation
- `api`: API routes
- `db`: Database layer
- `tests`: Test suite
- `docs`: Documentation

### Examples

```bash
# Good commits ✅
feat(search): Add distance_threshold parameter to vector search
fix(embedding): Handle empty text input gracefully
docs(api): Update search endpoint examples in README
refactor(db): Simplify connection pool initialization
test(search): Add tests for fallback mechanism
perf(embedding): Cache embeddings with LRU strategy

# Bad commits ❌
fixed bug
update code
changes
WIP
```

### Breaking Changes

If your change breaks backward compatibility, add `BREAKING CHANGE:` in the footer:

```
feat(api): Change search response format

BREAKING CHANGE: Search endpoint now returns {results, total_hits}
instead of flat array. Update client code accordingly.
```

---

## Pull Request Process

### Before Submitting

1. ✅ **Tests pass** (`make api-test`)
2. ✅ **Linting passes** (`make lint`)
3. ✅ **Coverage maintained** (>= 87%)
4. ✅ **Documentation updated** (if needed)
5. ✅ **Commits follow conventions**
6. ✅ **Branch is up-to-date** with main

### PR Title

Use the same format as commit messages:

```
feat(search): Add distance_threshold validation
fix(db): Resolve connection pool leak
docs: Update contribution guidelines
```

### PR Description Template

```markdown
## Summary
Brief description of changes (1-2 sentences).

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Changes Made
- Bullet list of specific changes
- Be concise but descriptive

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated (if applicable)
- [ ] Manual testing performed

**Test Coverage:** 92% (+5%)

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally

## Related Issues
Closes #123
Relates to #456
```

### Review Process

1. **Automated checks** run (tests, linting, coverage)
2. **Maintainer review** (usually within 48 hours)
3. **Address feedback** if requested
4. **Approval** and **merge** by maintainer

### After Merge

Your contribution will be included in the next release! 🎉

- Check the [CHANGELOG](docs/CHANGELOG.md) (if exists)
- Your name will be added to contributors
- Feel free to share your contribution!

---

## Project Structure

Understanding the codebase structure:

```
MnemoLite/
├── api/                          # FastAPI application
│   ├── main.py                   # Entry point, lifespan, app setup
│   ├── dependencies.py           # Dependency injection
│   ├── db/
│   │   ├── database.py           # Connection pool manager
│   │   └── repositories/         # Data access layer
│   │       ├── base.py           # Base repository
│   │       └── event_repository.py  # Event CRUD + search
│   ├── interfaces/               # Protocol definitions (DI contracts)
│   │   ├── repositories.py       # Repository protocols
│   │   └── services.py           # Service protocols
│   ├── models/                   # Pydantic models
│   │   ├── event_models.py       # Event schemas
│   │   └── memory_models.py      # Memory view models
│   ├── routes/                   # API endpoints
│   │   ├── event_routes.py       # /v1/events
│   │   ├── search_routes.py      # /v1/search
│   │   └── health_routes.py      # /health, /readiness, /metrics
│   └── services/                 # Business logic
│       ├── embedding_service.py      # Embedding generation (Sentence-Transformers)
│       ├── memory_search_service.py  # Search orchestration
│       └── event_processor.py        # Event processing
├── db/                           # PostgreSQL Docker setup
│   ├── Dockerfile                # PostgreSQL 17 + pgvector
│   └── init/                     # Initialization SQL scripts
├── tests/                        # Test suite
│   ├── conftest.py               # Shared fixtures
│   ├── test_*.py                 # Unit tests
│   ├── db/repositories/          # Repository tests
│   ├── integration/              # Integration tests
│   └── performance/              # Performance tests
├── docs/                         # Documentation
│   ├── Document Architecture.md  # Architecture overview
│   ├── Specification_API.md      # API specification
│   ├── bdd_schema.md             # Database schema
│   └── docker_setup.md           # Docker setup guide
├── scripts/                      # Utility scripts
├── docker-compose.yml            # Service orchestration
├── .env.example                  # Environment template
├── Makefile                      # Development commands
├── README.md                     # Project overview
├── GUIDE_DEMARRAGE.md            # Quick start (French)
└── CONTRIBUTING.md               # This file

```

### Key Architectural Concepts

**Architecture Principles (v1.3.0):**
- ✅ **Single Repository Pattern** - EventRepository as sole data access layer
- ✅ **Protocol-based DI** - Clean interfaces with dependency inversion
- ✅ **CQRS-inspired** - Logical separation of commands and queries
- ✅ **100% Async** - All database operations use `asyncio`

**Data Flow:**
```
HTTP Request
    → FastAPI Route (routes/)
    → Service Layer (services/) - Business logic
    → Repository (db/repositories/) - Data access
    → PostgreSQL 17 (with pgvector)
```

**Testing Strategy:**
- **Unit tests**: Mock dependencies, test logic in isolation
- **Integration tests**: Real database, test full workflows
- **Performance tests**: Benchmark critical operations

---

## Questions?

- **Documentation**: Check [docs/](docs/) folder
- **Issues**: Search [existing issues](https://github.com/giak/MnemoLite/issues)
- **Discussions**: Open a [discussion](https://github.com/giak/MnemoLite/discussions)
- **Contact**: Open an issue or discussion on GitHub

---

**Thank you for contributing to MnemoLite!** 🧠✨

Every contribution, no matter how small, helps make MnemoLite better for everyone.
