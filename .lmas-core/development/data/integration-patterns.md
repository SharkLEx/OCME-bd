# Design System Integration Patterns — On-Demand Knowledge Base

> **Usage:** Loaded on-demand by @ux-design-expert (Switch) during design system implementation and migration.
> Do NOT pre-load during agent activation. Load when integrating tokens or components with a project.
> **Last Updated:** 2026-03 (review quarterly)

---

## 1. CSS Custom Properties (Native)

The simplest and most portable integration pattern. Works with any framework.

### Setup
```css
/* tokens.css — generated from design token source */
:root {
  --color-primary: #2563EB;
  --spacing-4: 16px;
  --font-size-base: 1rem;
}
```

### Consumption
```css
.button {
  background-color: var(--color-primary);
  padding: var(--spacing-2) var(--spacing-4);
  font-size: var(--font-size-base);
}
```

### Theming (dark mode)
```css
[data-theme="dark"] {
  --color-primary: #60A5FA;
  --color-surface: #1F2937;
  --color-text-primary: #F9FAFB;
}
```

**Pros:** Zero runtime cost, works everywhere, native browser support, easy theming
**Cons:** No type safety, no autocomplete without tooling, values are always strings

---

## 2. Tailwind CSS Integration

### Token-powered Tailwind config

```js
// tailwind.config.js
const tokens = require('./tokens/tailwind-tokens')

module.exports = {
  theme: {
    extend: {
      colors: tokens.colors,
      spacing: tokens.spacing,
      fontFamily: tokens.fontFamily,
      fontSize: tokens.fontSize,
      borderRadius: tokens.borderRadius,
      boxShadow: tokens.boxShadow,
    },
  },
}
```

### Usage in components
```html
<button class="bg-primary text-text-inverse px-4 py-2 rounded-md shadow-sm">
  Click me
</button>
```

### Dark mode with Tailwind
```js
// tailwind.config.js
module.exports = {
  darkMode: 'class', // or 'media' for system preference
}
```

```html
<div class="bg-surface text-text-primary dark:bg-gray-900 dark:text-gray-50">
  Content adapts to theme
</div>
```

**Recommendation:** Use CSS custom properties inside Tailwind config values for runtime theming:
```js
colors: {
  primary: 'var(--color-primary)',
}
```

**Pros:** Fast development, consistent spacing, purges unused CSS
**Cons:** Class name verbosity, requires build step, team must learn utility conventions

---

## 3. CSS Modules Integration

### Token consumption via CSS custom properties
```css
/* Button.module.css */
.button {
  background: var(--color-primary);
  border-radius: var(--border-radius-md);
  padding: var(--spacing-2) var(--spacing-4);
  font-size: var(--font-size-base);
  transition: background var(--motion-duration-normal) var(--motion-easing-default);
}

.button:hover {
  background: var(--color-primary-hover);
}
```

### Usage in React
```tsx
import styles from './Button.module.css'

export function Button({ children }: { children: React.ReactNode }) {
  return <button className={styles.button}>{children}</button>
}
```

**Pros:** Scoped styles, no naming collisions, works with any token format via CSS vars
**Cons:** Cannot use JS token values directly, no dynamic styles without inline styles

---

## 4. CSS-in-JS Integration (styled-components / Emotion)

### Theme provider setup
```tsx
import { ThemeProvider } from 'styled-components'

const theme = {
  colors: {
    primary: 'var(--color-primary)',
    textPrimary: 'var(--color-text-primary)',
    surface: 'var(--color-surface)',
  },
  spacing: {
    sm: 'var(--spacing-2)',
    md: 'var(--spacing-4)',
    lg: 'var(--spacing-8)',
  },
  radii: {
    md: 'var(--border-radius-md)',
  },
}

export default function App() {
  return <ThemeProvider theme={theme}>{children}</ThemeProvider>
}
```

### Consumption
```tsx
import styled from 'styled-components'

const Button = styled.button`
  background: ${({ theme }) => theme.colors.primary};
  padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
  border-radius: ${({ theme }) => theme.radii.md};
  color: white;
`
```

**Pros:** Dynamic styling, type-safe themes, co-located styles
**Cons:** Runtime CSS generation, larger bundle, SSR complexity

**Recommendation:** Use CSS custom properties as values within the theme object. This gives you the best of both worlds: CSS-in-JS ergonomics with CSS variable runtime theming.

---

## 5. Design Token Consumption Patterns

### Pattern A: Direct Token Reference
```css
color: var(--color-primary);
```
Best for: Simple, stable values that rarely change per-component.

### Pattern B: Component Token Override
```css
.card {
  --card-bg: var(--color-surface);
  --card-padding: var(--spacing-4);
  background: var(--card-bg);
  padding: var(--card-padding);
}
.card--highlighted {
  --card-bg: var(--color-primary);
}
```
Best for: Components that need theme-able sub-properties.

### Pattern C: Utility Class Mapping
```css
.text-primary { color: var(--color-text-primary); }
.bg-surface { background: var(--color-surface); }
.p-4 { padding: var(--spacing-4); }
```
Best for: Tailwind-like utility systems built on tokens.

---

## 6. Multi-Framework Support

### Strategy: Token Layer Separation

```
tokens/                     ← Framework-agnostic (source of truth)
  colors.yaml
  typography.yaml
  spacing.yaml
build/                      ← Generated per-framework
  css/tokens.css            ← For any framework
  tailwind/tokens.js        ← For Tailwind projects
  scss/tokens.scss          ← For SCSS projects
  js/tokens.ts              ← For CSS-in-JS projects
  ios/tokens.swift          ← For iOS (if needed)
  android/tokens.xml        ← For Android (if needed)
```

### Build Pipeline (Style Dictionary)

```js
// style-dictionary.config.js
module.exports = {
  source: ['tokens/**/*.yaml'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'build/css/',
      files: [{ destination: 'tokens.css', format: 'css/variables' }],
    },
    tailwind: {
      transformGroup: 'js',
      buildPath: 'build/tailwind/',
      files: [{ destination: 'tokens.js', format: 'javascript/module' }],
    },
  },
}
```

---

## 7. Mono-Repo Strategies

### Package Structure

```
packages/
  design-tokens/           ← Source tokens + build pipeline
    src/
      colors.yaml
      typography.yaml
    dist/
      css/tokens.css
      js/tokens.ts
    package.json           ← @org/design-tokens
  design-system/           ← React components consuming tokens
    src/
      Button/
      Card/
    package.json           ← @org/design-system (depends on @org/design-tokens)
  app-web/                 ← Web application
    package.json           ← depends on @org/design-system
  app-admin/               ← Admin panel
    package.json           ← depends on @org/design-system
```

### Dependency Rules
1. `design-tokens` has zero dependencies — purely a build artifact
2. `design-system` depends on `design-tokens` — imports CSS or JS tokens
3. Applications depend on `design-system` — never on `design-tokens` directly
4. Token changes propagate: tokens build -> design-system rebuild -> apps rebuild

### Versioning
- Token breaking changes (rename, removal) = major version bump
- New tokens = minor version bump
- Value changes within existing tokens = patch version bump
