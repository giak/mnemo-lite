---
description: Generate an HTML diagram for any technical topic
agent: build
---

Generate a self-contained HTML page that visually explains: $ARGUMENTS

Use the visual-explainer skill. Read the relevant template first:
- For architecture/system diagrams: read @.opencode/skills/visual-explainer/templates/architecture.html
- For flowcharts/sequence/ER/state diagrams: read @.opencode/skills/visual-explainer/templates/mermaid-flowchart.html

Follow these rules:
1. Pick a constrained aesthetic (Blueprint, Editorial, Paper/ink, or Monochrome terminal) — NOT neon dashboard or gradient mesh
2. Use a distinctive font pairing from the skill's list (NOT Inter/Roboto/Arial)
3. For Mermaid diagrams: use theme 'base', add zoom controls, center the diagram
4. For CSS Grid architectures: use cards with colored left borders and monospace labels
5. Write to ~/.agent/diagrams/ with a descriptive filename
6. Open with: xdg-open ~/.agent/diagrams/filename.html
7. Tell me the file path
