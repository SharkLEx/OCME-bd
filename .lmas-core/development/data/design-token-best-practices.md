# Design Token Best Practices — On-Demand Knowledge Base

> **Usage:** Loaded on-demand by @ux-design-expert (Switch) during token extraction and design system setup.
> Do NOT pre-load during agent activation. Load when working with design tokens.
> **Last Updated:** 2026-03 (review quarterly)

---

## 1. Naming Conventions

### CTI Format (Category-Type-Item)

The CTI naming convention creates predictable, scalable token names.

```
{category}-{type}-{item}-{sub-item}-{state}
```

**Examples:**
| Token | Category | Type | Item | State |
|-------|----------|------|------|-------|
| `color-text-primary` | color | text | primary | — |
| `color-bg-surface-hover` | color | bg | surface | hover |
| `font-size-base` | font | size | base | — |
| `spacing-4` | spacing | — | 4 | — |
| `shadow-elevation-md` | shadow | elevation | md | — |
| `border-radius-lg` | border | radius | lg | — |
| `motion-duration-normal` | motion | duration | normal | — |

### Rules
- Use kebab-case exclusively (no camelCase, no snake_case)
- Category first, specificity increases left to right
- States go last (hover, active, disabled, focus)
- Avoid abbreviations except widely known ones (bg, sm, md, lg, xl)
- Never include platform in token names (no `-css`, no `-ios`)

---

## 2. Token Tiers

### Tier 1: Global (Primitive) Tokens

Raw values with no semantic meaning. The source of truth for all values.

```yaml
color-blue-500: "#3B82F6"
color-gray-900: "#111827"
font-size-16: "1rem"
spacing-16: "16px"
```

**Rules:**
- Never use global tokens directly in components
- Name describes the value, not the usage
- Complete scale coverage (e.g., gray-50 through gray-900)

### Tier 2: Alias (Semantic) Tokens

Reference global tokens and add meaning. This is what components consume.

```yaml
color-primary: "{color-blue-600}"
color-text-primary: "{color-gray-900}"
color-error: "{color-red-500}"
font-size-body: "{font-size-16}"
```

**Rules:**
- Always reference a global token, never a raw value
- Name describes the purpose, not the appearance
- Enables theming by remapping aliases to different globals

### Tier 3: Component Tokens

Scoped to a specific component. Override alias tokens for edge cases.

```yaml
button-color-bg: "{color-primary}"
button-color-bg-hover: "{color-primary-hover}"
button-border-radius: "{border-radius-md}"
input-color-border-focus: "{color-primary}"
```

**Rules:**
- Only create when a component genuinely differs from the alias
- Prefix with component name
- Keep the count minimal — overuse defeats the purpose of shared tokens

---

## 3. Multi-Theme Support

### Architecture

```
tokens/
  global/           # Tier 1 — same for all themes
    colors.yaml
    typography.yaml
    spacing.yaml
  themes/
    light.yaml      # Tier 2 aliases for light theme
    dark.yaml       # Tier 2 aliases for dark theme
    brand-a.yaml    # Multi-brand support
  components/       # Tier 3 — component-specific overrides
    button.yaml
```

### Dark Mode Strategy

Map semantic tokens to different primitive values:

```yaml
# light.yaml
color-surface: "{color-white}"
color-text-primary: "{color-gray-900}"
color-border: "{color-gray-200}"

# dark.yaml
color-surface: "{color-gray-900}"
color-text-primary: "{color-gray-50}"
color-border: "{color-gray-700}"
```

**Key principle:** Component code NEVER changes between themes. Only token values change.

---

## 4. W3C DTCG Format

The W3C Design Tokens Community Group defines a standard JSON format.

```json
{
  "color": {
    "primary": {
      "$value": "#2563EB",
      "$type": "color",
      "$description": "Primary brand color"
    }
  }
}
```

**Required fields:** `$value`, `$type`
**Optional fields:** `$description`, `$extensions`

**Supported types:** `color`, `dimension`, `fontFamily`, `fontWeight`, `duration`, `cubicBezier`, `number`, `shadow`, `strokeStyle`, `border`, `transition`, `gradient`, `typography`

---

## 5. Migration from Hardcoded Values

### Step-by-step process:

1. **Scan** — Extract all unique hardcoded values (colors, sizes, spacing) from the codebase
2. **Cluster** — Group similar values (e.g., `#2563EB` and `#2555DD` are likely the same intent)
3. **Name** — Assign CTI token names to each cluster
4. **Tier** — Decide global vs semantic vs component scope
5. **Export** — Generate token files in target format (CSS vars, Tailwind, JSON)
6. **Replace** — Swap hardcoded values with token references (codemod when possible)
7. **Validate** — Visual regression tests confirm no visual change

### Common pitfalls:
- Creating too many tokens (aim for < 100 semantic tokens for most projects)
- Skipping the clustering step (results in near-duplicate tokens)
- Not involving designers in naming (tokens should match design tool names)
- Forgetting state tokens (hover, focus, disabled need separate tokens)

---

## 6. Token Documentation

Every token should be documented with:

| Field | Purpose |
|-------|---------|
| Name | CTI token name |
| Value | Resolved value (e.g., `#2563EB`) |
| Type | DTCG type (color, dimension, etc.) |
| Tier | Global / Semantic / Component |
| Usage | Where and how to use this token |
| Do/Don't | Correct and incorrect usage examples |
| Theme variants | Values in light, dark, brand themes |

---

## 7. Tool Recommendations

| Tool | Purpose |
|------|---------|
| Style Dictionary | Build tokens into any platform format |
| Tokens Studio (Figma) | Manage tokens in Figma, sync to code |
| Token CSS | Lightweight CSS custom property generator |
| Chromatic | Visual regression testing with token themes |
