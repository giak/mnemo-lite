---
description: Mental model snapshot for context-switching back to a project
agent: build
---

Generate a visual project recap page to help me quickly reorient to this codebase.

If $ARGUMENTS is provided, use it as a time range (e.g., "1w", "2d") to focus on recent changes.
Otherwise, give a full project overview.

Generate an HTML page showing:
1. Project purpose and architecture (Mermaid diagram or CSS cards)
2. Directory structure (key folders with descriptions)
3. Recent activity (last commits, changed files)
4. Open tasks / TODOs found in code
5. Key decisions and patterns

Use the visual-explainer skill. Read the relevant templates from @.opencode/skills/visual-explainer/templates/

Write to ~/.agent/diagrams/project-recap.html and open with xdg-open.
Tell me the file path.
