# CIP Brief — Corporate Identity Program Brief Generator

> **Task ID:** ux-cip-brief
> **Agent:** UX-Design Expert (Sati)
> **Version:** 1.0.0
> **Owner:** ux-design-expert
> **Consumers:** ux-design-expert, pm, architect
> **Elicit:** true
> **Category:** branding

---

## Purpose

Generate a Corporate Identity Program (CIP) brief that defines the scope, required elements, specifications, and deliverable list for a brand's visual identity system. Covers digital, physical, or both media scopes. Data sourced from `cip-elements.csv` and `cip-guidelines.csv`.

---

## Inputs

| Field | Type | Required | Source | Validation |
|-------|------|----------|--------|------------|
| `brand` | string | yes | User Input | Brand or company name |
| `mode` | string | no | User Input | `yolo` \| `interactive` \| `pre-flight`. Default: `interactive` |

### Elicited Inputs (gathered during interactive mode)

| Field | Type | Required | Prompt |
|-------|------|----------|--------|
| `scope` | string | yes | "CIP scope: digital only, physical only, or both?" |
| `industry` | string | yes | "What industry/sector?" |
| `company_size` | string | no | "Company size: startup, SMB, enterprise?" Default: SMB |
| `existing_brand` | boolean | no | "Does the brand already have identity elements? (refresh vs. new)" |
| `budget_level` | string | no | "Budget level: lean, standard, premium?" Default: standard |
| `priority_touchpoints` | string[] | no | "Which touchpoints are most important? (website, social, print, packaging, signage)" |

---

## Execution Flow

### 1. Load CIP Data
1.1. Read `.lmas-core/development/data/ux/sub-skills/cip-elements.csv`
1.2. Read `.lmas-core/development/data/ux/sub-skills/cip-guidelines.csv`
1.3. Parse cip-elements columns: element_name, category, scope_digital, scope_physical, priority, description, deliverable_format, dependencies
1.4. Parse cip-guidelines columns: guideline, category, description, mandatory, examples
1.5. Validation: Both CSVs loaded. If missing, use built-in CIP structure.

### 2. Elicit Brand Scope
2.1. If `mode=interactive` → ask each elicited input sequentially
2.2. If `mode=yolo` → default scope=both, company_size=SMB, budget_level=standard
2.3. If `mode=pre-flight` → gather ALL inputs, then validate as a batch
2.4. Validation: Scope and industry collected

### 3. Filter CIP Elements
3.1. From `cip-elements.csv`, filter elements by scope:
   - `scope=digital` → only rows where `scope_digital=true`
   - `scope=physical` → only rows where `scope_physical=true`
   - `scope=both` → all rows
3.2. Sort by priority (1 = highest)
3.3. If `budget_level=lean` → keep only priority 1-2 elements
3.4. If `budget_level=standard` → keep priority 1-3 elements
3.5. If `budget_level=premium` → keep all elements
3.6. If `priority_touchpoints` provided → boost priority of matching elements
3.7. Validation: At least 5 elements selected

### 4. Build Element Specifications
4.1. For each selected element, compile:
   - **Element name** (e.g., "Logo Usage Guidelines", "Business Card", "Social Media Templates")
   - **Category** (Logo, Color, Typography, Stationery, Digital, Environmental)
   - **Description** — what this element covers
   - **Deliverable format** — file formats and dimensions
   - **Dependencies** — which elements must be completed first
4.2. Resolve dependency chains (logo before stationery, colors before templates)
4.3. Assign phase numbers based on dependency order
4.4. Validation: All dependencies resolvable

### 5. Load Guidelines
5.1. From `cip-guidelines.csv`, select guidelines matching:
   - The selected element categories
   - The brand's industry
   - Mandatory guidelines (always included)
5.2. Organize guidelines by category
5.3. Include specification details (min sizes, spacing rules, color formulas)
5.4. Validation: At least 1 guideline per category

### 6. Generate Timeline Estimate
6.1. Estimate timeline based on scope and budget:
   - **Lean digital:** 2-3 weeks
   - **Standard both:** 4-6 weeks
   - **Premium both:** 8-12 weeks
6.2. Break down by phase:
   - Phase 1: Core (logo, colors, typography) — 30% of timeline
   - Phase 2: Applications (stationery, digital templates) — 40%
   - Phase 3: Guidelines document + delivery — 30%
6.3. Adjust for company_size (enterprise adds review cycles)
6.4. Validation: Timeline is realistic

### 7. Compile CIP Brief Document
7.1. Assemble all sections into structured deliverable
7.2. Include executive summary
7.3. Include scope definition table
7.4. Include prioritized element list with phases
7.5. Include timeline and milestones
7.6. Include deliverables checklist

---

## Output Format

```markdown
## 📋 CIP Brief: {brand}

### Executive Summary
{1-2 paragraph overview of the CIP scope, objectives, and expected outcomes}

### Scope Definition
| Attribute | Value |
|-----------|-------|
| Brand | {name} |
| Industry | {industry} |
| Scope | {digital/physical/both} |
| Budget Level | {lean/standard/premium} |
| Company Size | {startup/SMB/enterprise} |

### Identity Elements (Priority Order)

#### Phase 1 — Core Identity
| # | Element | Category | Format | Dependency |
|---|---------|----------|--------|------------|
| 1 | Logo System | Logo | SVG, PNG, EPS | — |
| 2 | Color Palette | Color | ASE, CSS, Pantone | Logo |
| 3 | Typography Scale | Typography | WOFF2, OTF | — |

#### Phase 2 — Applications
| # | Element | Category | Format | Dependency |
|---|---------|----------|--------|------------|
| 4 | Business Card | Stationery | PDF, AI | Logo, Color, Type |
| 5 | Email Signature | Digital | HTML | Logo, Color, Type |
| ... | ... | ... | ... | ... |

#### Phase 3 — Guidelines
| # | Element | Category | Format |
|---|---------|----------|--------|
| N | Brand Guidelines PDF | Documentation | PDF, Figma |

### Guidelines Summary
| Category | Key Rules |
|----------|-----------|
| Logo | {min size, clear space, forbidden modifications} |
| Color | {primary, secondary, usage ratios, contrast requirements} |
| Typography | {heading/body fonts, hierarchy, web vs print} |

### Timeline & Milestones
| Phase | Duration | Milestone |
|-------|----------|-----------|
| Phase 1 | {X} weeks | Core identity approved |
| Phase 2 | {X} weeks | Applications complete |
| Phase 3 | {X} weeks | Guidelines delivered |
| **Total** | **{X} weeks** | **CIP complete** |

### Deliverables Checklist
- [ ] Logo system (primary, secondary, icon, monochrome)
- [ ] Color specifications (hex, RGB, CMYK, Pantone)
- [ ] Typography kit (web fonts, print fonts, scale)
- [ ] {Additional elements based on scope}
- [ ] Brand guidelines document (PDF + editable)
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| CSV not found | CIP data CSVs missing from `sub-skills/` | Use built-in CIP structure (logo, color, type, stationery, digital, guidelines) |
| Invalid scope | Scope is not digital/physical/both | Default to "both", inform user |
| Circular dependencies | Elements reference each other | Flag circular chain, suggest breaking point |
| Empty budget | Lean budget + both scope = too few elements | Warn user, suggest digital-first approach |

---

## Examples

### Example 1: Startup Digital-First

```
*cip-brief MyStartup
> Scope: digital
> Industry: SaaS
> Company size: startup
> Budget: lean
```

Returns: Lean 8-element CIP — logo, colors, typography, social templates, email signature, favicon, OG images, brand guidelines. 2-3 week timeline.

### Example 2: Enterprise Full CIP

```
*cip-brief "Banco Nacional"
> Scope: both
> Industry: banking/finance
> Company size: enterprise
> Budget: premium
```

Returns: 25+ element CIP — full logo system, color specs (Pantone+CMYK), stationery suite, signage, vehicle wraps, digital templates, brand guidelines book. 10-12 week timeline.

### Example 3: Brand Refresh

```
*cip-brief "CafeExpress"
> Existing brand: yes
> Scope: both
> Priority touchpoints: packaging, social
```

Returns: Refresh-focused CIP — audit existing elements, modernize logo, update packaging templates, social media kit. Preserves brand equity.

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - .lmas-core/development/data/ux/sub-skills/cip-elements.csv
  - .lmas-core/development/data/ux/sub-skills/cip-guidelines.csv
tags:
  - ux
  - branding
  - corporate-identity
  - design-brief
  - data-driven
updated_at: 2026-03-17
```
