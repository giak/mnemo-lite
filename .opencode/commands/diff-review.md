---
description: Visual diff review with architecture comparison and code review
agent: build
---

Perform a visual diff review of the current changes.

1. Run: !`git diff --stat`
2. Run: !`git diff HEAD~1` (or compare with a specific branch if provided: $ARGUMENTS)
3. Use the visual-explainer skill to generate an HTML page showing:
   - Summary of changed files (KPI cards: files changed, lines added/removed)
   - Architecture impact analysis (what components are affected)
   - Key code changes with before/after panels
   - Risk assessment table

Read @.opencode/skills/visual-explainer/templates/data-table.html for table patterns.
Read @.opencode/skills/visual-explainer/templates/architecture.html for card patterns.

Write to ~/.agent/diagrams/diff-review.html and open with xdg-open.
Tell me the file path.
