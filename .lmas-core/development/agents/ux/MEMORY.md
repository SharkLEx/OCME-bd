# UX Design Expert Agent Memory (Uma)

## Active Patterns
<!-- Current, verified patterns used by this agent -->

### Key Patterns
- CommonJS (`require`/`module.exports`), NOT ES Modules
- ES2022, Node.js 18+, 2-space indent, single quotes
- kebab-case for files, PascalCase for components

### Project Structure
- `.lmas-core/core/` — Core modules
- `docs/` — Documentation and design specs
- `packages/` — Shared packages

### Git Rules
- NEVER push — delegate to @devops
- Conventional commits: `docs:` for design specs, `feat:` for components

### Design Conventions
- Atomic Design principles (atoms → molecules → organisms → templates → pages)
- Design tokens for consistent theming
- WCAG 2.1 AA compliance target

## Promotion Candidates
<!-- Patterns seen across 3+ agents — candidates for CLAUDE.md or .claude/rules/ -->
<!-- Format: - **{pattern}** | Source: {agent} | Detected: {YYYY-MM-DD} -->

## Design Intelligence System (v2.0 — 2026-03-17)

### Data-Driven Capabilities
- 23 design intelligence CSVs (11 core + 12 sub-skills) at `.lmas-core/development/data/ux/`
- BM25 search engine for fuzzy matching across all design data
- Domains: colors, typography, spacing, components, layouts, animations, icons, patterns, responsive, shadows, borders
- Sub-skills: logo design, CIP, icon design, slides, charts, landing pages

### New Commands (Phase 6 + 7)
- Phase 6: *style, *palette, *font-pair, *landing, *chart, *validate-pattern, *mobile-check, *logo-brief, *cip-brief, *pitch-deck, *banner, *brand-audit
- Phase 7: *extract-design-system (flagship — reverse-engineers design systems from URL/code/image)

### Reference Store Integration
- *extract-design-system can save to project-refs/design/ via --save-ref flag
- Cross-agent: any agent can query design references via @lmas-master *refs design

### Key Files
- Intelligence data: `.lmas-core/development/data/ux/*.csv`
- BM25 engine: `.lmas-core/development/data/ux/scripts/core.py`
- Flagship task: `.lmas-core/development/tasks/extract-design-system.md`

## Archived
<!-- Patterns no longer relevant — kept for history -->
<!-- Format: - ~~{pattern}~~ | Archived: {YYYY-MM-DD} | Reason: {reason} -->
