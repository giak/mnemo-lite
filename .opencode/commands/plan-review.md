---
description: Compare a plan against the codebase with risk assessment
agent: build
---

Compare the implementation plan against the actual codebase and generate a visual risk assessment.

If $ARGUMENTS is provided, treat it as a path to a plan document or feature description.
Otherwise, ask me what plan to review.

Generate an HTML page showing:
1. Plan summary (what was proposed)
2. Implementation status table (planned vs actual, with status indicators)
3. Risk assessment (what's missing, what's risky, what needs attention)
4. Gap analysis with severity levels

Use the visual-explainer skill. Read @.opencode/skills/visual-explainer/templates/data-table.html for table patterns.

Write to ~/.agent/diagrams/plan-review.html and open with xdg-open.
Tell me the file path.
