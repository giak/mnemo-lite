# MnemoLite CSS Architecture v4.0

Modular CSS structure for the MnemoLite UI - SCADA Industrial Design System.

## 📁 Structure

```
css/
├── style.css              # Main entry point with @import statements
├── base/                  # Foundational styles
│   ├── variables.css      # CSS custom properties (--color-*, --space-*, etc.)
│   └── reset.css          # CSS reset and base body styles
├── layout/                # Page layout components
│   ├── container.css      # Container and main content area
│   ├── navbar.css         # Navigation bar (responsive)
│   └── footer.css         # Footer
├── components/            # Reusable UI components
│   ├── buttons.css        # Button styles (.btn, .btn-primary, .btn-clear)
│   ├── cards.css          # Event cards and stat cards
│   ├── page-header.css    # Page titles and subtitles
│   ├── stats.css          # Statistics bar
│   ├── search.css         # Search box and input controls
│   ├── filters.css        # Filter controls and period buttons
│   ├── modal.css          # Modal dialogs
│   ├── event-detail.css   # Event detail modal content
│   ├── messages.css       # Info messages, errors, empty states
│   └── loading.css        # Loading spinners and indicators
└── utils/                 # Utilities and overrides
    └── responsive.css     # Mobile/tablet breakpoints

Total: 17 files (16 modules + 1 main)
Old monolithic: style.css.old (843 lines → backup)
```

## 🎨 Design System

### SCADA Industrial Principles
- **Zero Border Radius**: `--radius-sm: 0` (strict industrial aesthetic)
- **Ultra Dark Palette**: `#0d1117` to `#2d333b` (minimal eye strain)
- **Compact Spacing**: 2px to 20px scale (information density)
- **Vivid Status Colors**: Critical (#ff4757), OK (#26de81), Warning (#ffa502)
- **Border-left Accents**: 2px colored borders for state indication
- **Fast Transitions**: 80ms (immediate feedback)

### CSS Variables

All design tokens are in `base/variables.css`:

```css
/* Spacing */
--space-xs: 2px;
--space-sm: 4px;
--space-lg: 8px;
--space-xl: 12px;

/* Colors */
--color-bg-primary: #0d1117;
--color-text-primary: #ffffff;
--color-accent-blue: #4a90e2;
--color-critical: #ff4757;
--color-ok: #26de81;

/* Typography */
--font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
--font-mono: 'SF Mono', Consolas, 'Courier New', monospace;
--text-tiny: 0.625rem;
--text-sm: 0.75rem;
```

## 🚀 Usage

### Loading CSS

The main `style.css` is loaded in `templates/base.html`:

```html
<link rel="stylesheet" href="/static/css/style.css?v=4.0">
```

### Adding New Styles

**Option 1: Extend Existing Module**

Edit the relevant module file:
```css
/* components/buttons.css */
.btn-danger {
    background-color: var(--color-critical);
    border-color: var(--color-critical);
}
```

**Option 2: Create New Module**

1. Create file: `components/new-component.css`
2. Write styles using CSS variables
3. Add import to `style.css`:
   ```css
   @import url('components/new-component.css');
   ```

### CSS Variables Usage

Always prefer CSS variables over hardcoded values:

```css
/* ❌ Bad */
.my-component {
    color: #4a90e2;
    padding: 8px;
}

/* ✅ Good */
.my-component {
    color: var(--color-accent-blue);
    padding: var(--space-lg);
}
```

## 📊 Metrics

### Before (v3.7)
- **Files**: 1 monolithic file
- **Lines**: 843 lines
- **Maintainability**: Low (find/edit difficult)
- **Caching**: Poor (entire file invalidated on any change)
- **Duplication**: High (~30%)

### After (v4.0)
- **Files**: 16 modular files + 1 main
- **Average**: ~50 lines per module
- **Maintainability**: High (organized by purpose)
- **Caching**: Better (only changed modules invalidate)
- **Duplication**: <5%

## 🎯 Benefits

1. **Separation of Concerns**: Each file has a single responsibility
2. **Easier Navigation**: Find styles by component name
3. **Better Collaboration**: Multiple developers can work simultaneously
4. **Reduced Conflicts**: Git diffs are cleaner
5. **Scalability**: Add new modules without modifying existing files
6. **Performance**: Browser can cache individual modules

## 🔧 Development Workflow

### Modifying Styles

1. Identify the component you need to style
2. Open the corresponding CSS module:
   ```bash
   # Example: Editing button styles
   vi static/css/components/buttons.css
   ```
3. Make changes using CSS variables
4. Test in browser (no build step required)
5. Commit only the changed module

### Cache Busting

When deploying, update version in `base.html`:
```html
<link rel="stylesheet" href="/static/css/style.css?v=4.1">
```

## 📝 Conventions

### File Naming
- **Lowercase**: All filenames are lowercase
- **Hyphens**: Use hyphens for multi-word names (`event-detail.css`)
- **Singular**: Use singular form (`button.css` not `buttons.css` - except when plural makes semantic sense)

### Class Naming (BEM-inspired)
- **Block**: `.event-card`, `.search-box`
- **Element**: `.event-card-header`, `.search-box-input`
- **Modifier**: `.btn-primary`, `.period-btn.active`

### Ordering in CSS
1. Layout properties (display, position, etc.)
2. Box model (margin, padding, border)
3. Typography (font-*, text-*, line-height)
4. Visual (color, background, etc.)
5. Misc (cursor, transition, etc.)

## 🧪 Testing

After CSS changes, test all pages:

```bash
# Dashboard
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/ui/

# Search
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/ui/search

# Graph
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/ui/graph

# Monitoring
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/ui/monitoring
```

All should return `200`.

## 🔄 Migration Notes

### From v3.7 to v4.0

**Breaking Changes**: None - CSS classes remain identical

**Backup**: Original monolithic CSS saved as `style.css.old`

**Rollback**: If issues occur, revert `base.html`:
```html
<link rel="stylesheet" href="/static/css/style.css.old?v=3.7">
```

## 🎓 SCADA Design Reference

MnemoLite follows industrial SCADA (Supervisory Control and Data Acquisition) design principles:

- **High Information Density**: Compact spacing, small fonts
- **Maximum Contrast**: Dark backgrounds, bright text
- **Clear Visual Hierarchy**: Borders, spacing, typography
- **Status Indication**: Border-left accents, vivid colors
- **Minimal Decoration**: No shadows, gradients, or effects
- **Ultra-Fast Feedback**: 80ms transitions

**Inspiration**: GitHub Dark Dimmed + Grafana + Industrial HMI systems

---

**Version**: 4.0
**Date**: 2025-10-14
**Maintained by**: MnemoLite Project
**License**: Follows MnemoLite project license
