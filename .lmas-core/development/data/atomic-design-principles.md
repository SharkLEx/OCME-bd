# Atomic Design Principles — On-Demand Knowledge Base

> **Usage:** Loaded on-demand by @ux-design-expert (Switch) during design system work.
> Do NOT pre-load during agent activation. Load when classifying or auditing components.
> **Last Updated:** 2026-03 (review quarterly)

---

## Overview

Atomic Design is a methodology by Brad Frost for creating design systems with five hierarchical levels. Each level builds upon the previous one, creating a clear mental model for component classification and composition.

---

## The Five Levels

### 1. Atoms

**Definition:** The smallest, indivisible UI elements that cannot be broken down further without losing meaning.

**Examples:**
- Button, Input, Label, Icon, Badge, Avatar, Checkbox, Radio, Toggle, Tooltip trigger
- Typography elements: Heading, Text, Caption, Link

**Decision Criteria:**
- Can this element function independently? Yes = Atom
- Does it contain other meaningful components inside? If yes, it is NOT an atom
- Is it a native HTML element with styling? Likely an atom

**Anti-patterns:**
- Putting layout logic inside atoms (atoms should not know about their container)
- Creating atoms that are too specific (e.g., `RedErrorButton` instead of `Button` with variant)
- Atoms with business logic — they should be purely presentational

---

### 2. Molecules

**Definition:** Simple groups of atoms functioning together as a unit. They have a single responsibility.

**Examples:**
- SearchBar (Input + Button + Icon)
- FormField (Label + Input + HelperText)
- Card (Image + Heading + Text + Button)
- NavItem (Icon + Link + Badge)
- Chip (Text + CloseButton)

**Decision Criteria:**
- Is it a combination of 2-4 atoms working together? Likely a molecule
- Does it have a single, clear purpose? Yes = Molecule
- Could you explain its function in one sentence? Yes = Molecule

**Anti-patterns:**
- Molecules that do too many things (if it has 3+ responsibilities, it may be an organism)
- Molecules with deeply nested internal state — keep state minimal
- Naming molecules after their visual appearance instead of their function

---

### 3. Organisms

**Definition:** Complex UI sections composed of molecules and/or atoms. They form distinct sections of an interface.

**Examples:**
- Header (Logo + Navigation + SearchBar + UserMenu)
- Sidebar (NavGroup + NavItems + Footer)
- Modal/Dialog (Header + Body + Footer + Overlay)
- DataTable (TableHeader + TableRows + Pagination + Filters)
- CommentSection (CommentForm + CommentList + LoadMore)

**Decision Criteria:**
- Does it represent a distinct section of the page? Yes = Organism
- Does it contain multiple molecules? Likely an organism
- Would removing it leave a visible gap in the page? Yes = Organism

**Anti-patterns:**
- God organisms that contain the entire page (that is a template)
- Organisms tightly coupled to specific data — use props/slots for content injection
- Organisms that manage global state — keep state local or lifted to templates

---

### 4. Templates

**Definition:** Page-level layouts that place organisms in a structure. They define the content skeleton without real data.

**Examples:**
- DashboardLayout (Sidebar + Header + MainContent area + Footer)
- ArticleLayout (Header + HeroImage + Content + RelatedArticles)
- SettingsLayout (TabNavigation + ContentPanel)
- AuthLayout (CenteredCard + Logo + Footer)

**Decision Criteria:**
- Does it define WHERE organisms go on a page? Yes = Template
- Does it use placeholder content? Yes = Template
- Is it reusable across multiple pages with different data? Yes = Template

**Anti-patterns:**
- Templates with real data hardcoded — templates are structural, pages fill in data
- One template per page — templates should be reusable across similar pages
- Business logic in templates — keep them as layout-only

---

### 5. Pages

**Definition:** Specific instances of templates filled with real content and data. They represent what the user actually sees.

**Examples:**
- UserDashboardPage (DashboardLayout filled with user-specific data)
- ProductDetailPage (ArticleLayout filled with product data)
- LoginPage (AuthLayout filled with login form)

**Decision Criteria:**
- Is it a template with real data? Yes = Page
- Is it a unique route in the application? Likely a page
- Does it connect to APIs or state management? Yes = Page

**Anti-patterns:**
- Pages that redefine layout (that should be in the template)
- Pages without a corresponding template — every page should use a template
- Pages that directly import atoms (they should compose through organisms)

---

## Classification Decision Tree

```
Is it a single HTML element with styling?
  YES → ATOM
  NO ↓

Is it a small group (2-4 elements) with one purpose?
  YES → MOLECULE
  NO ↓

Is it a distinct page section with multiple sub-components?
  YES → ORGANISM
  NO ↓

Does it define page structure without real data?
  YES → TEMPLATE
  NO ↓

Is it a template instance with real data and API connections?
  YES → PAGE
```

---

## Composition Rules

1. **Atoms** → used by Molecules, Organisms (never by Templates/Pages directly)
2. **Molecules** → used by Organisms (occasionally by Templates for simple cases)
3. **Organisms** → used by Templates
4. **Templates** → used by Pages
5. **Pages** → top-level, not composed into anything else

---

## Naming Conventions

| Level | Prefix Convention | File Location |
|-------|-------------------|---------------|
| Atom | No prefix | `components/atoms/` |
| Molecule | No prefix | `components/molecules/` |
| Organism | No prefix | `components/organisms/` |
| Template | `*Layout` suffix | `components/layouts/` or `templates/` |
| Page | `*Page` suffix | `pages/` or `app/` (Next.js) |
