---
name: visual-explainer
description: Generate beautiful, self-contained HTML pages for diagrams, code reviews, plans, data tables, and visual explanations. Use when asked for a diagram, architecture overview, diff review, plan audit, comparison table, or any visual explanation of technical concepts. Also use proactively when about to render a complex ASCII table (4+ rows or 3+ columns) — generate HTML instead.
license: MIT
compatibility: Requires a browser to view generated HTML files. Linux: uses xdg-open.
metadata:
  author: adapted from nicobailon/visual-explainer
  version: "1.0.0"
---

# Visual Explainer

Generate self-contained HTML files for technical diagrams, visualizations, and data tables. Always open the result in the browser with `xdg-open`. Never fall back to ASCII art when this skill is loaded.

**Proactive table rendering.** If the table has 4+ rows or 3+ columns, generate an HTML page instead. Don't wait for the user to ask.

## Workflow

### 1. Think (5 seconds)

**Visual is always default.** Even essays get visual treatment — extract structure into cards, diagrams, grids, tables.

**Who is looking?** Developer? PM? Team reviewing? Shape information density accordingly.

**What aesthetic?** Pick one and commit. Constrained aesthetics are safer:
- **Blueprint** — technical drawing, subtle grid bg, deep slate/blue, monospace labels
- **Editorial** — serif headlines (Instrument Serif/Crimson Pro), generous whitespace, muted earth tones
- **Paper/ink** — warm cream `#faf7f5`, terracotta/sage accents, informal
- **Monochrome terminal** — green/amber on near-black, monospace, CRT glow

**Forbidden:**
- Neon dashboard (cyan + magenta + purple on dark)
- Gradient mesh (pink/purple/cyan blobs)
- Inter font + violet/indigo accents + gradient text

### 2. Choose rendering approach

| Content type | Approach |
|---|---|
| Architecture (text-heavy) | CSS Grid cards + flow arrows |
| Architecture (topology) | **Mermaid** `graph TD` |
| Flowchart / pipeline | **Mermaid** |
| Sequence diagram | **Mermaid** `sequenceDiagram` |
| ER / schema | **Mermaid** `erDiagram` |
| State machine | **Mermaid** `stateDiagram-v2` or `graph TD` |
| Mind map | **Mermaid** `mindmap` |
| Class diagram | **Mermaid** `classDiagram` |
| C4 architecture | **Mermaid** `graph TD` + `subgraph` (NOT native C4Context) |
| Data table | HTML `<table>` |
| Timeline | CSS (central line + cards) |
| Dashboard | CSS Grid + Chart.js |

### 3. Read templates before generating

Before writing HTML, read the relevant template for patterns:
- Architecture cards: `@templates/architecture.html`
- Mermaid diagrams: `@templates/mermaid-flowchart.html`
- Data tables: `@templates/data-table.html`

### 4. Style rules

**Typography:** Pick a distinctive font pairing. Load via `<link>` in `<head>`.

Good pairings:
- DM Sans + Fira Code
- Instrument Serif + JetBrains Mono
- IBM Plex Sans + IBM Plex Mono
- Bricolage Grotesque + Fragment Mono
- Plus Jakarta Sans + Azeret Mono

**Forbidden as `--font-body`:** Inter, Roboto, Arial, Helvetica, system-ui alone.

**Color:** Use CSS custom properties. Define `--bg`, `--surface`, `--border`, `--text`, `--text-dim`, and 3-5 accents. Support both themes via `prefers-color-scheme`.

**Forbidden accents:** `#8b5cf6`, `#7c3aed`, `#a78bfa` (indigo/violet), `#d946ef` (fuchsia).

**Good palettes:**
- Terracotta + sage (`#c2410c`, `#65a30d`)
- Teal + slate (`#0891b2`, `#0369a1`)
- Rose + cranberry (`#be123c`, `#881337`)
- Amber + emerald (`#d97706`, `#059669`)
- Deep blue + gold (`#1e3a5f`, `#d4a73a`)

**Card depth:** Vary to signal importance. Hero sections get elevated shadows. Body content stays flat. Code blocks feel recessed. Use `<details>` for lower-priority content.

**Animations:** Staggered fade-ins on load are almost always worth it. Never use animated glowing box-shadows or pulsing effects on static content.

### 5. Mermaid rules

- Always use `theme: 'base'` with custom `themeVariables`
- Always center with `display: flex; justify-content: center;`
- Always add zoom controls (+/−/reset/expand) — see `@templates/mermaid-flowchart.html`
- **Never use bare `<pre class="mermaid">`** — no zoom/pan controls
- Prefer `graph TD` over `graph LR` (LR spreads horizontally, makes labels unreadable)
- Use `<br/>` for line breaks in labels, NOT `\n`
- Quote labels with special characters: `A["handleRequest(ctx)"]`
- Max 10-12 nodes per diagram. For 15+ elements, use hybrid: simple Mermaid overview + CSS Grid cards
- **Never set `color:` in classDef** — hardcodes text color that breaks in opposite theme
- Use semi-transparent fills (8-digit hex) for node backgrounds

### 6. Deliver

**Output:** Write to `~/.agent/diagrams/filename.html`
**Open:** `xdg-open ~/.agent/diagrams/filename.html`
**Tell the user** the file path.

## Anti-Patterns (AI Slop)

**Forbidden:**
- Inter/Roboto as primary font
- Indigo-500/violet-500 accents (`#8b5cf6`, `#7c3aed`)
- Cyan + magenta + pink neon gradients
- Gradient text on headings (`background-clip: text`)
- Animated glowing box-shadows
- Emoji icons in section headers (🏗️, ⚙️, 📁, 💻, etc.)
- Three-dot window chrome on code blocks
- Perfectly centered everything with uniform padding
- All cards styled identically

**The Slop Test:** Would a developer immediately think "AI generated this"? If 2+ of these signs are present, regenerate with a different aesthetic.
