# UI Gotchas

**Purpose**: UI patterns, HTMX, templates, and frontend gotchas

**When to reference**: Building UI features, debugging HTMX, or working with templates

---

## 🟡 UI-01: Template Inheritance Pattern

**Rule**: Follow `base.html` → `page.html` → `partials/*.html` hierarchy

```html
<!-- ✅ CORRECT -->
<!-- templates/code_search.html -->
{% extends "base.html" %}
{% block content %}
  {% include "partials/code_results.html" %}
{% endblock %}

<!-- ❌ WRONG - Skips base -->
<!-- templates/code_search.html -->
<!DOCTYPE html>
<html>
  <!-- Rebuilds everything! -->
</html>
```

**Why**: Consistent layout, shared navbar/footer, DRY principle

---

## 🟡 UI-02: HTMX Partial Targets

**Rule**: HTMX partials must have target IDs matching hx-target

```html
<!-- ✅ CORRECT -->
<div hx-get="/api/search" hx-target="#results">Search</div>
<div id="results"><!-- Partial loaded here --></div>

<!-- ❌ WRONG - Target mismatch -->
<div hx-get="/api/search" hx-target="#results">Search</div>
<div id="search-results"><!-- Won't update! --></div>
```

**Detection**: HTMX request succeeds but UI doesn't update

---

## 🟡 UI-03: Cytoscape.js Initialization

**Rule**: Wait for DOM ready before initializing Cytoscape

```javascript
// ✅ CORRECT
document.addEventListener('DOMContentLoaded', function() {
    const cy = cytoscape({ container: document.getElementById('cy'), ... });
});

// ❌ WRONG - Container not ready
const cy = cytoscape({ container: document.getElementById('cy'), ... });
// Runs before DOM loads!
```

**Detection**: "Container not found" error, graph doesn't render

---

**Total UI Gotchas**: 3
