# MnemoLite UI Design System v2.0

**Version**: 2.0
**Date**: 2025-10-14
**Status**: Production

## 📐 Design Philosophy

### Core Principles
1. **Élégance**: Minimaliste avec détails soignés
2. **Compacité**: Densité d'information optimale sans surcharge
3. **Sobriété**: Palette réduite, contraste élevé
4. **Professionnalisme**: Cohérence visuelle totale

### Influenced By
- **Material Design 3**: Elevation, states
- **Tailwind**: Utility-first tokens
- **Apple HIG**: Typography scale
- **Modern SaaS**: Clean, data-focused

---

## 🎨 Color Palette

### Primary Colors
```css
--color-primary: #2563eb      /* Blue 600 - Actions, links */
--color-primary-hover: #1d4ed8 /* Blue 700 - Hover states */
--color-primary-light: #dbeafe /* Blue 100 - Backgrounds */
--color-primary-dark: #1e40af  /* Blue 800 - Text on light */
```

### Semantic Colors
```css
--color-accent: #0ea5e9    /* Cyan 500 - Highlights */
--color-success: #10b981   /* Green 500 - Success states */
--color-warning: #f59e0b   /* Amber 500 - Warnings */
--color-error: #ef4444     /* Red 500 - Errors */
```

### Neutral Scale (9 shades)
```css
--color-neutral-50: #fafafa   /* Lightest background */
--color-neutral-100: #f5f5f5  /* Cards, badges */
--color-neutral-200: #e5e5e5  /* Borders */
--color-neutral-300: #d4d4d4  /* Border hover */
--color-neutral-400: #a3a3a3  /* Disabled */
--color-neutral-500: #737373  /* Tertiary text */
--color-neutral-600: #525252  /* Secondary text */
--color-neutral-700: #404040  /* Body text */
--color-neutral-800: #262626  /* Headings */
--color-neutral-900: #171717  /* Primary text */
```

### Usage Guidelines
- **Maximum 3 colors per screen**: Primary + 1-2 accents
- **High contrast**: Text on background ≥ 4.5:1 (WCAG AA)
- **Colorblocking**: Neutral backgrounds + bright accents

---

## 📏 Spacing System (8-point grid)

### Scale
```css
--space-xs: 4px     /* Tight spacing */
--space-sm: 8px     /* Compact */
--space-md: 16px    /* Default */
--space-lg: 24px    /* Comfortable */
--space-xl: 32px    /* Generous */
--space-2xl: 40px   /* Section spacing */
--space-3xl: 48px   /* Large sections */
--space-4xl: 64px   /* Hero sections */
```

### Rules
1. **Internal < External**: Padding inside elements < margin between elements
2. **Consistent rhythm**: Use scale consistently (no arbitrary values)
3. **Vertical spacing**: Prefer `margin-bottom` for stacking
4. **Horizontal spacing**: Use `gap` for flex/grid layouts

### Common Patterns
```css
/* Card padding */
padding: var(--space-lg);  /* 24px */

/* Section margins */
margin-bottom: var(--space-3xl);  /* 48px */

/* Flex gaps */
gap: var(--space-md);  /* 16px */
```

---

## 🔤 Typography

### Font Stacks
```css
--font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', ...
--font-mono: ui-monospace, 'SF Mono', 'Cascadia Code', 'Roboto Mono', ...
```

### Type Scale
```css
--text-xs: 0.75rem    /* 12px - Labels, badges */
--text-sm: 0.875rem   /* 14px - Body, captions */
--text-base: 1rem     /* 16px - Default body */
--text-lg: 1.125rem   /* 18px - Large body */
--text-xl: 1.25rem    /* 20px - Small headings */
--text-2xl: 1.5rem    /* 24px - Headings */
--text-3xl: 1.875rem  /* 30px - Page titles */
--text-4xl: 2.25rem   /* 36px - Hero */
```

### Line Heights
```css
--leading-none: 1         /* Headings, tight */
--leading-tight: 1.25     /* Subheadings */
--leading-snug: 1.375     /* Compact text */
--leading-normal: 1.5     /* Default body */
--leading-relaxed: 1.625  /* Comfortable reading */
--leading-loose: 2        /* Loose, airy */
```

### Usage Guidelines
- **Body text**: 16px, line-height 1.5
- **Headings**: -2.5% letter-spacing for large sizes
- **Labels**: Uppercase, +5% letter-spacing, weight 600
- **Monospace**: IDs, code, technical data

### Hierarchy Example
```
h1: 30px/1.25, weight 700, -0.025em     (Page titles)
h2: 24px/1.25, weight 700               (Section titles)
h3: 12px/1.5, weight 700, uppercase     (Labels)
p:  16px/1.5, weight 400                (Body)
small: 14px/1.625, weight 400           (Captions)
```

---

## 🌑 Shadows

### Scale
```css
--shadow-sm: 0 1px 2px rgba(0,0,0,0.05)
--shadow-md: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1)
--shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1)
--shadow-xl: 0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)
```

### Usage
- **Cards**: `shadow-sm` (default) → `shadow-lg` (hover)
- **Modals**: `shadow-xl`
- **Navigation**: `shadow-sm` + `backdrop-filter: blur(8px)`
- **Floating elements**: `shadow-md`

---

## 🔘 Border Radius

```css
--radius-sm: 4px      /* Small elements, badges */
--radius-md: 6px      /* Inputs, buttons */
--radius-lg: 8px      /* Cards */
--radius-xl: 12px     /* Modals, large containers */
--radius-full: 9999px /* Pills, circular */
```

---

## ⏱️ Transitions

### Timing Functions
```css
--transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1)
--transition-base: 200ms cubic-bezier(0.4, 0, 0.2, 1)
--transition-slow: 300ms cubic-bezier(0.4, 0, 0.2, 1)
```

### Usage
- **Micro-interactions**: `transition-fast` (hover, focus)
- **Standard**: `transition-base` (default)
- **Large movements**: `transition-slow` (modals, slides)

### Easing Curve
`cubic-bezier(0.4, 0, 0.2, 1)` - Material Design's "standard easing"
- Smooth acceleration/deceleration
- Natural feeling

---

## 🎭 Component Patterns

### Cards
```css
.card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: var(--space-lg);
  transition: all var(--transition-base);
}

.card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}
```

### Buttons
```css
.btn {
  padding: var(--space-md) var(--space-xl);
  font-size: var(--text-sm);
  font-weight: 600;
  border-radius: var(--radius-md);
  transition: all var(--transition-base);
}

.btn:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.btn:active {
  transform: translateY(0);
}
```

### Inputs
```css
.input {
  padding: var(--space-md) var(--space-lg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  transition: all var(--transition-base);
}

.input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-light);
  outline: none;
}
```

### Badges
```css
.badge {
  font-size: var(--text-xs);
  font-weight: 500;
  padding: var(--space-xs) var(--space-md);
  background: var(--color-neutral-100);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
}
```

---

## 📱 Responsive Breakpoints

```css
/* Mobile-first approach */
@media (max-width: 480px)  { /* Small mobile */ }
@media (max-width: 768px)  { /* Tablet */ }
@media (max-width: 1024px) { /* Small desktop */ }
@media (min-width: 1280px) { /* Large desktop */ }
```

### Responsive Typography
At breakpoints, reduce type scale:
```css
@media (max-width: 768px) {
  --text-3xl: 1.5rem;   /* 30px → 24px */
  --text-2xl: 1.25rem;  /* 24px → 20px */
  --text-xl: 1.125rem;  /* 20px → 18px */
}
```

---

## ♿ Accessibility

### Focus States
All interactive elements have visible focus rings:
```css
element:focus {
  outline: none;
  box-shadow: 0 0 0 3px var(--color-primary-light);
}
```

### Color Contrast
- Body text: ≥ 4.5:1 (WCAG AA)
- Large text: ≥ 3:1
- UI components: ≥ 3:1

### Motion
```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 🎬 Animations

### Keyframes
```css
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

### Usage
- **Modal entry**: `slideUp 300ms`
- **Backdrop**: `fadeIn 200ms`
- **Loaders**: `spin 600ms linear infinite`

---

## 📊 Layout

### Container
```css
.container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 var(--space-lg);
}
```

### Grid Patterns
```css
/* Auto-fit responsive grid */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--space-lg);
}

/* Fixed columns */
.grid-3 {
  grid-template-columns: repeat(3, 1fr);
}
```

---

## 🧪 Usage Examples

### Dashboard Card
```html
<div class="stat-card">
  <div class="stat-label">Total Events</div>
  <div class="stat-value">1,234</div>
</div>
```

### Event Card
```html
<div class="event-card">
  <div class="event-header">
    <span class="event-id">a3f9b...</span>
    <span class="event-timestamp">2025-10-14 10:30</span>
  </div>
  <div class="event-content">
    <p>Event description...</p>
  </div>
  <div class="event-metadata">
    <span class="badge">source: api</span>
    <span class="badge">priority: high</span>
  </div>
</div>
```

### Search Form
```html
<div class="search-box">
  <form>
    <div class="search-input-group">
      <input type="text" class="search-input" placeholder="Search...">
      <button type="submit" class="btn btn-primary">Search</button>
    </div>
  </form>
</div>
```

---

## 📋 Checklist de Qualité

### Avant de Merger
- [ ] Tous les espacements utilisent le système 8-point
- [ ] Pas de couleurs en dur (utiliser CSS variables)
- [ ] Focus states visibles sur tous les éléments interactifs
- [ ] Transitions sur hover/focus
- [ ] Responsive testé sur mobile/tablet/desktop
- [ ] Contraste de couleur vérifié (WCAG AA minimum)
- [ ] Pas de valeurs magiques (expliquer les calculs)

### Performance
- [ ] Polices système (pas de web fonts inutiles)
- [ ] Shadows raisonnables (pas de blur > 15px)
- [ ] Animations performantes (transform/opacity uniquement)
- [ ] Media queries optimisées

---

## 🔄 Évolutions Futures

### v2.1 (Court terme)
- [ ] Dark mode
- [ ] Thème personnalisable (via CSS vars)
- [ ] Composants avancés (charts, tables)

### v3.0 (Long terme)
- [ ] Animation library (Framer Motion / GSAP)
- [ ] Advanced data visualization
- [ ] Component library documentation
- [ ] Storybook integration

---

## 📚 Références

### Inspirations
- **Tailwind CSS**: Design tokens approach
- **Material Design 3**: Elevation system
- **Radix UI**: Accessible components
- **Vercel**: Professional SaaS aesthetic

### Outils
- **Color**: https://coolors.co/, https://uicolors.app/
- **Typography**: https://type-scale.com/
- **Spacing**: https://8ptgrid.com/
- **Shadows**: https://shadows.brumm.af/

---

**Maintenu par**: MnemoLite Team
**Dernière mise à jour**: 2025-10-14
**Version**: 2.0.0
