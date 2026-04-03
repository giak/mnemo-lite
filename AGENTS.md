# AGENTS.md — MnemoLite

Project rules and conventions for AI agents working on this codebase.

## Project Overview

MnemoLite is a code intelligence MCP server with hybrid lexical + vector search, code graph traversal, and semantic memory management. Built with Python (FastAPI + SQLAlchemy), it provides tools for searching, indexing, and understanding codebases.

## Key Directories

- `api/` — MCP server implementation (FastAPI, tools, schemas)
- `db/` — Database models and migrations
- `frontend/` — Web UI
- `scripts/` — Utility scripts including MCP server launcher
- `tests/` — Test suite
- `docs/` — Documentation and superpowers (plans, specs)
- `workers/` — Background workers
- `configs/` — Configuration files

## Code Conventions

- Python with type hints throughout
- Pydantic models for all request/response schemas
- SQLAlchemy for database models
- structlog for logging
- MCP SDK for tool definitions
- Follow existing patterns in `api/mnemo_mcp/tools/` when adding new tools

## Visual Explainer

This project includes the **visual-explainer** skill for generating HTML diagrams, tables, and visual explanations.

- Skill: `.opencode/skills/visual-explainer/SKILL.md`
- Commands: `/diagram`, `/diff-review`, `/plan-review`, `/project-recap`
- Templates: `.opencode/skills/visual-explainer/templates/`
- Agent: `@visualizer` (subagent for visual tasks)

When asked to create diagrams, architecture overviews, or complex tables, use the visual-explainer skill instead of ASCII art. Output goes to `~/.agent/diagrams/` and opens with `xdg-open`.

## MCP Tools

The server exposes these tool categories via MCP:
- `search_code` — Hybrid lexical + vector search with RRF fusion
- `write_memory` / `search_memory` / `update_memory` / `delete_memory` — Semantic memory management
- `index_project` / `reindex_file` / `get_indexing_status` — Code indexing
- `get_graph_stats` / `traverse_graph` / `find_path` — Code graph operations
- `ping` — Health check

## Testing

- Run tests with: `make test` or `pytest`
- Test files mirror source structure under `tests/`
- Use pytest fixtures for database and MCP context
