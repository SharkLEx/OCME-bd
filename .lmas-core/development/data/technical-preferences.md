# Technical Preferences — UX Design Expert (@ux-design-expert / Switch)

> **Usage:** Loaded on-demand to establish default technical choices for the UX Design Expert agent.
> These are defaults — they can be overridden by project-specific configuration in `core-config.yaml`.
> **Last Updated:** 2026-03 (review quarterly)

---

## 1. Preferred Frameworks

| Category | Default | Alternatives |
|----------|---------|-------------|
| **UI Framework** | React 18+ | Next.js (for SSR), Vue 3 (if project uses it) |
| **CSS Strategy** | Tailwind CSS 3+ | CSS Modules (for scoped styles), CSS custom properties (for token-only) |
| **Component Pattern** | Compound components + forwardRef | Render props (for advanced composition) |
| **State Management** | Zustand | React Context (simple cases), Redux Toolkit (large apps) |
| **Build Tool** | Vite | Next.js built-in (for Next projects), Turbopack |
| **Package Manager** | pnpm | npm (if project standard) |

---

## 2. Token Format

| Setting | Default |
|---------|---------|
| **Source format** | W3C DTCG (YAML) |
| **Naming convention** | CTI (Category-Type-Item), kebab-case |
| **Build tool** | Style Dictionary (when pipeline needed) |
| **CSS output** | CSS custom properties (`:root`) |
| **JS output** | Tailwind config extension (CommonJS) |
| **Tier structure** | 3-tier: Global (primitive) → Semantic (alias) → Component |

---

## 3. Accessibility Defaults

| Setting | Default |
|---------|---------|
| **Target level** | WCAG 2.1 AA |
| **Contrast minimum** | 4.5:1 (normal text), 3:1 (large text, UI components) |
| **Keyboard navigation** | Required for all interactive elements |
| **Screen reader testing** | NVDA (Windows), VoiceOver (macOS) |
| **Automated scanning** | axe-core in CI pipeline |
| **Focus indicators** | Visible focus ring on all focusable elements (never `outline: none` alone) |
| **Reduced motion** | `prefers-reduced-motion: reduce` support required |
| **Color independence** | Never rely on color alone for information |

---

## 4. Component Patterns

### Default Component Structure

```tsx
// ComponentName.tsx
export interface ComponentNameProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'primary' | 'secondary'
  size?: 'sm' | 'md' | 'lg'
  children: React.ReactNode
}

const ComponentName = React.forwardRef<HTMLDivElement, ComponentNameProps>(
  ({ variant = 'default', size = 'md', children, className, ...rest }, ref) => {
    return (
      <div ref={ref} data-variant={variant} data-size={size} className={className} {...rest}>
        {children}
      </div>
    )
  }
)

ComponentName.displayName = 'ComponentName'
export default ComponentName
```

### Pattern Rules
- Always use `forwardRef` for components that render DOM elements
- Always set `displayName` for DevTools debugging
- Extend native HTML attributes for the root element type
- Use `data-*` attributes for variant/state styling hooks
- Spread remaining props (`...rest`) onto the root element
- Default export for the component, named exports for sub-components

---

## 5. Testing Tools

| Tool | Purpose | Integration |
|------|---------|-------------|
| **Jest** | Unit testing | Default test runner |
| **React Testing Library** | Component interaction testing | `@testing-library/react` |
| **axe-core** | Automated accessibility testing | `jest-axe` for unit, `@axe-core/playwright` for E2E |
| **Storybook** | Component documentation and visual development | `@storybook/react-vite` |
| **Chromatic** | Visual regression testing (cloud) | Storybook integration |
| **Playwright** | End-to-end browser testing | Cross-browser validation |

### Test File Convention
```
ComponentName/
  ComponentName.tsx
  ComponentName.test.tsx
  ComponentName.stories.tsx
```

---

## 6. Color Space Preferences

| Setting | Default | Notes |
|---------|---------|-------|
| **Primary format** | Hex (#RRGGBB) | For token definitions and CSS |
| **Working space** | sRGB | Standard for web |
| **Advanced format** | OKLCH | For perceptually uniform color manipulation |
| **Gradient space** | OKLAB | Smoother gradients than sRGB |
| **Opacity** | rgba() or hex with alpha (#RRGGBBAA) | CSS Level 4 syntax preferred |

### Color Usage Rules
- Define primitive tokens in hex
- Use CSS custom properties for runtime values
- Use `oklch()` only when doing programmatic color generation (scales, palettes)
- Always check contrast in sRGB (WCAG formulas use sRGB)

---

## 7. File Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Components | PascalCase | `Button.tsx`, `SearchBar.tsx` |
| Component directories | PascalCase | `Button/Button.tsx` |
| Styles (CSS Modules) | PascalCase + `.module.css` | `Button.module.css` |
| Tokens | kebab-case | `colors.yaml`, `typography.yaml` |
| Templates | kebab-case + `-tmpl` suffix | `component-react-tmpl.tsx` |
| Tests | PascalCase + `.test.tsx` | `Button.test.tsx` |
| Stories | PascalCase + `.stories.tsx` | `Button.stories.tsx` |
| Utilities | kebab-case | `use-tokens.ts`, `format-color.ts` |

---

## 8. Responsive Design Defaults

| Breakpoint | Name | Width | Typical Layout |
|------------|------|-------|----------------|
| Mobile | `sm` | < 640px | Single column, stacked |
| Tablet | `md` | 640-1023px | 2-column, collapsible sidebar |
| Desktop | `lg` | 1024-1279px | Full layout, persistent sidebar |
| Wide | `xl` | >= 1280px | Full layout, wider content area |

### Approach
- **Mobile-first** — Base styles target mobile, breakpoints add complexity
- **Fluid typography** — Use `clamp()` for responsive font sizes
- **Container queries** — Prefer over media queries for component-level responsiveness (when browser support allows)
- **Touch targets** — Minimum 44x44px on mobile, 32x32px on desktop

---

## 9. Performance Budgets

| Metric | Budget |
|--------|--------|
| Component bundle size (gzipped) | < 5KB per component |
| Design system total CSS | < 30KB gzipped |
| First Contentful Paint (FCP) | < 1.8s |
| Largest Contentful Paint (LCP) | < 2.5s |
| Cumulative Layout Shift (CLS) | < 0.1 |
| Interaction to Next Paint (INP) | < 200ms |
