# AGENTS.md — MnemoLite Memory Rules

Deploy this file in any project root to enable automatic memory capture via MnemoLite MCP tools.
Works with Codebuff, OpenCode, KiloCode, and any MCP-compatible agent.

## Project ID ($P)
`$P` = **lowercase** root folder name of the current project. MnemoLite auto-resolves it.
Example: in `/home/user/projects/MnemoLite` → `$P` = `mnemolite` (just lowercase, no hyphen insertion).
⚠ Tags are case-sensitive in PostgreSQL. Always use lowercase `$P` in `sys:project:$P` and `repository="$P"`.
**Always** pass `project_id="$P"` and include `"sys:project:$P"` in tags on every `write_memory` call.

## MCP Tools
- Memory: `write_memory`, `read_memory`, `search_memory`, `update_memory`, `delete_memory`, `export_memories`, `get_system_snapshot`, `mark_consumed`, `rate_memory`, `consolidate_memory`, `suggest_consolidation`, `configure_decay`
- Code: `search_code` (hybrid lexical+vector w/ RRF)
- Indexing: `index_project`, `reindex_file`, `get_indexing_status`
- Graph: `get_graph_stats`, `traverse_graph`, `find_path`
- `ping`

## Memory Rules
Automatic memory capture across all AI environments.

| Trigger | Tool Call | Notes |
|---|---|---|
| Session start | `get_system_snapshot(repository="$P")` | Load context |
| Context drift | `get_system_snapshot(repository="$P")` | Re-anchor if conversation is long |
| Before complex work | `search_memory(query, tags=["sys:project:$P"], limit=3)` | Scope to project |
| Signif. decision/observation | `write_memory(title, content, memory_type, tags=["sys:project:$P"], project_id="$P")` | Types: `decision`, `note`, `task`, `reference`, `investigation`, `conversation`¹ |
| Major file change | `write_memory(title, content, memory_type="note", tags=["file-change", "sys:project:$P"], project_id="$P")` | Record what & why |
| Session end | `write_memory(title, content, memory_type="conversation", tags=["session", "summary", "sys:project:$P"], project_id="$P")` | Done / Next steps |
| Before major changes | `export_memories(project_id="$P")` | Backup memories |
| write_memory returns duplicate_warning | `update_memory(id, ...)` instead | Update existing memory |
| After using memory | `mark_consumed(memory_ids, consumed_by)` | Avoid re-processing |
| Memory useful/useless | `rate_memory(id, helpful=True/False)` | Adjusts decay |
| 3+ related memories | `suggest_consolidation(tags=["sys:project:$P"])` → `consolidate_memory(title, summary, source_ids, tags=["sys:project:$P"])` | Same-project only |

¹ Tag hints: `decision`→arch, `note`→obs, `task`→todo, `reference`→docs, `investigation`→debug, `conversation`→session

**Do NOT save:** Trivial edits, duplicates, secrets, debug logs, large code blocks (use `search_code`), codebase-reconstructable facts.
