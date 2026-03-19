# absorb-reference

## Metadata

- **Task ID:** absorb-reference
- **Version:** 1.0.0
- **Owner:** lmas-master (Morpheus)
- **Consumers:** All agents (via Morpheus delegation)
- **elicit:** true
- **Category:** reference-management

---

## Purpose

Absorb external references into the project's Reference Store for future consultation by any agent. This task handles the full pipeline: source analysis, content extraction, reference assembly, storage, and optional enrichment.

The Reference Store lives at `project-refs/` in the project root, organized by domain. Each absorbed reference becomes a YAML file following the schema defined in `.lmas-core/data/reference-store-schema.yaml`.

---

## Inputs

| Input | Required | Type | Description |
|-------|----------|------|-------------|
| source | YES | string | URL, file path, or free-text description of the reference |
| --domain | NO | enum | Target domain: `design` \| `architecture` \| `content` \| `competitive`. Auto-detected if omitted |
| --name | NO | string | Human-readable reference name. Auto-generated from source if omitted |
| --tags | NO | string | Comma-separated tags for searchability (e.g., `"dark-mode,saas,dashboard"`) |
| --update | NO | string | Name of existing reference to update (re-absorb with fresh data) |
| --ttl | NO | int | Auto-expire after N days. References with TTL are flagged after expiry but not auto-deleted |

---

## Pre-conditions

1. The `.lmas-core/data/reference-store-schema.yaml` file exists and is valid
2. The executing agent has write access to `project-refs/` (L4 — Project Runtime)
3. If source is a URL, network access is available
4. If source is a file path, the file exists and is readable

---

## Execution Flow

### Step 1: Source Analysis

Determine the source type and plan the extraction strategy.

**URL sources:**

| URL Pattern | Source Type | Extraction Strategy |
|-------------|-----------|---------------------|
| `*.figma.com/*` | Figma design | Browser MCP → visual extraction + metadata |
| `github.com/*` | GitHub repository | `gh` CLI → repo metadata + config files |
| `*.netlify.app`, `*.vercel.app`, `*.io` | Live website | Browser MCP → full page extraction |
| `dribbble.com/*`, `behance.net/*` | Design showcase | Browser MCP → visual extraction |
| `medium.com/*`, `dev.to/*` | Article/blog | Browser MCP → text content extraction |
| Any other URL | Generic website | Browser MCP → best-effort extraction |

**File path sources:**

| File Extension | Source Type | Extraction Strategy |
|----------------|-----------|---------------------|
| `.png`, `.jpg`, `.jpeg`, `.webp`, `.svg` | Image | Claude vision analysis |
| `.pdf` | Document | Read tool (PDF mode) → content extraction |
| `.css`, `.scss`, `.less` | Stylesheet | Read tool → token extraction |
| `.ts`, `.tsx`, `.js`, `.jsx` | Component code | Read tool → pattern extraction |
| `.json`, `.yaml`, `.yml` | Config/data | Read tool → structured data extraction |
| `tailwind.config.*` | Tailwind config | Read tool → full token extraction |
| `package.json` | Package metadata | Read tool → dependency analysis |

**Description sources:**
- Treat as manual reference entry
- Structure the description into the reference schema
- Mark `confidence: 1.0` (user-provided data)

### Step 2: Domain Detection

If `--domain` is not provided, auto-detect from source content.

**Detection heuristics:**

| Signal | Domain | Weight |
|--------|--------|--------|
| CSS custom properties, color values, font declarations | design | HIGH |
| Figma URL, Dribbble URL, Behance URL | design | HIGH |
| `tailwind.config`, `theme`, `tokens` in path | design | HIGH |
| Words: colors, typography, spacing, components, UI | design | MEDIUM |
| Words: API, database, microservice, infrastructure | architecture | HIGH |
| `docker-compose`, `terraform`, `.github/workflows` | architecture | HIGH |
| Words: scalability, distributed, event-driven, CQRS | architecture | MEDIUM |
| Words: blog, copy, brand, editorial, tone-of-voice | content | HIGH |
| Words: SEO, keywords, content-strategy, audience | content | MEDIUM |
| Words: competitor, market, pricing, comparison | competitive | HIGH |
| Words: market-share, SWOT, positioning, benchmark | competitive | MEDIUM |

**Confidence thresholds:**
- >= 80%: Auto-assign domain, inform user of choice
- 50-79%: Suggest domain, ask user to confirm
- < 50%: Ask user to specify domain explicitly

**Elicitation prompt (when confidence < 80%):**
```
Não consegui determinar o domínio com certeza. O conteúdo parece ser sobre {detected_signals}.

Qual domínio você quer usar?
1. design — Design systems, UI patterns, cores, tipografia
2. architecture — Padrões de arquitetura, system design
3. content — Estratégias de conteúdo, copy, brand voice
4. competitive — Análise competitiva, posicionamento
```

### Step 3: Content Extraction

Execute the extraction strategy determined in Step 1.

#### 3A: URL → Website

1. **Navigate** to URL using Browser MCP (`mcp__claude-in-chrome__navigate`)
2. **Extract page metadata:**
   - Title (`<title>` tag)
   - Meta description (`<meta name="description">`)
   - OpenGraph data (`og:title`, `og:description`, `og:image`)
   - Canonical URL
3. **Extract CSS custom properties** (design tokens):
   - Use `mcp__claude-in-chrome__javascript_tool` to run:
     ```javascript
     // Extract all CSS custom properties from :root
     const root = getComputedStyle(document.documentElement);
     const props = {};
     for (const sheet of document.styleSheets) {
       try {
         for (const rule of sheet.cssRules) {
           if (rule.selectorText === ':root') {
             for (const prop of rule.style) {
               if (prop.startsWith('--')) {
                 props[prop] = rule.style.getPropertyValue(prop).trim();
               }
             }
           }
         }
       } catch(e) { /* cross-origin stylesheet, skip */ }
     }
     return JSON.stringify(props);
     ```
4. **Extract color palette** from computed styles:
   - Scan key elements (body, headers, buttons, links) for `color`, `background-color`, `border-color`
   - Deduplicate and categorize: primary, secondary, accent, neutral, semantic (success/warning/error)
5. **Extract typography:**
   - Font families used (body, headings, code)
   - Font sizes (scale)
   - Font weights
   - Line heights
6. **Take screenshot** for visual reference:
   - Use `mcp__claude-in-chrome__upload_image` or page capture
   - Save to `project-refs/{domain}/screenshots/{slug}.png`
7. **Design enrichment** (if domain=design):
   - Search existing design intelligence data for similar patterns
   - Cross-reference with learned patterns in `.lmas-core/data/learned-patterns.yaml`

#### 3B: URL → GitHub Repository

1. **Fetch repo metadata** using `gh` CLI:
   ```bash
   gh repo view {owner/repo} --json name,description,languages,topics
   ```
2. **Scan for design-relevant files:**
   - `package.json` → extract dependencies (UI libraries, CSS frameworks)
   - `tailwind.config.*` → extract full theme configuration
   - `*.css` / `*.scss` in `src/styles/` or `src/theme/` → extract tokens
   - `design-system/` or `tokens/` directories → extract token definitions
   - `.storybook/` → note Storybook presence
3. **Scan for architecture-relevant files:**
   - `docker-compose.yml` → extract service architecture
   - `.github/workflows/` → extract CI/CD patterns
   - `terraform/` or `infrastructure/` → extract infra patterns
   - `README.md` → extract architecture decisions and diagrams
4. **Extract tokens from config files:**
   - Parse Tailwind theme → colors, spacing, typography, breakpoints
   - Parse CSS variables → design token map
   - Parse SCSS variables → token map

#### 3C: File Path → Image/PDF

1. **Read file** using Read tool (supports images and PDFs natively)
2. **Visual analysis** (Claude vision):
   - **Colors:** Identify dominant color palette (hex values)
   - **Typography:** Identify font families if visible, note sizes and weights
   - **Layout:** Describe grid structure, spacing patterns, alignment
   - **Components:** Identify UI components visible (cards, buttons, nav, forms)
   - **Style:** Describe overall aesthetic (minimal, corporate, playful, dark, etc.)
3. **Confidence:** Set to `0.7` (vision-based extraction is approximate)
4. **Note in reference:** Mark extracted values as `extraction_method: "vision-approximate"`

#### 3D: File Path → Code/Config

1. **Read file(s)** using Read tool
2. **CSS/SCSS extraction:**
   - Parse CSS custom properties (`--color-primary: #xxx`)
   - Parse SCSS variables (`$color-primary: #xxx`)
   - Categorize into: colors, spacing, typography, shadows, borders, transitions
3. **Tailwind config extraction:**
   - Parse `theme.extend` for custom tokens
   - Parse `colors`, `spacing`, `fontFamily`, `fontSize`, `screens`
   - Map to standardized token format
4. **Component pattern extraction:**
   - Identify component structure (functional vs class)
   - Extract prop interfaces
   - Note composition patterns (compound components, render props, hooks)
   - Identify styling approach (CSS modules, Tailwind, styled-components, CSS-in-JS)
5. **Package.json analysis:**
   - Extract UI framework (React, Vue, Angular, Svelte)
   - Extract CSS framework (Tailwind, Bootstrap, Material UI)
   - Extract relevant dev dependencies

#### 3E: Description → Manual Entry

1. **Structure the description** into reference fields:
   - Parse for any URLs mentioned → store as `source`
   - Parse for color values (hex, rgb, hsl) → store as `tokens.colors`
   - Parse for font names → store as `tokens.typography`
   - Parse for technology names → store as `tags`
2. **Ask for additional context** (elicitation):
   ```
   Referência manual registrada. Quer adicionar mais detalhes?
   - Tags para busca futura
   - Links relacionados
   - Notas adicionais
   ```
3. **Confidence:** Set to `1.0` (user-provided data is authoritative)

### Step 4: Reference Assembly

Assemble the extracted data into a YAML file following the schema.

**Reference YAML structure:**

```yaml
# Reference: {name}
# Absorbed: {ISO 8601 timestamp}
# Source: {source}

name: "{name}"
source: "{source}"
domain: "{domain}"
absorbed_at: "{ISO 8601}"
absorbed_by: "{agent_id}"
description: "{auto-generated or user-provided description}"
confidence: {0.0-1.0}
tags:
  - "{tag1}"
  - "{tag2}"

tokens:
  colors:
    primary: "{hex}"
    secondary: "{hex}"
    accent: "{hex}"
    background: "{hex}"
    surface: "{hex}"
    text:
      primary: "{hex}"
      secondary: "{hex}"
      muted: "{hex}"
    semantic:
      success: "{hex}"
      warning: "{hex}"
      error: "{hex}"
      info: "{hex}"
  typography:
    font_families:
      heading: "{font-family}"
      body: "{font-family}"
      code: "{font-family}"
    font_sizes:
      xs: "{value}"
      sm: "{value}"
      base: "{value}"
      lg: "{value}"
      xl: "{value}"
      2xl: "{value}"
      3xl: "{value}"
    font_weights:
      normal: "{value}"
      medium: "{value}"
      semibold: "{value}"
      bold: "{value}"
    line_heights:
      tight: "{value}"
      normal: "{value}"
      relaxed: "{value}"
  spacing:
    scale: ["{values}"]
  border_radius:
    sm: "{value}"
    md: "{value}"
    lg: "{value}"
    full: "{value}"
  shadows:
    sm: "{value}"
    md: "{value}"
    lg: "{value}"

patterns:
  - name: "{pattern name}"
    type: "{component|layout|interaction|architecture}"
    description: "{what it does and when to use it}"
    implementation_notes: "{how it's built}"

screenshots:
  - "project-refs/{domain}/screenshots/{slug}.png"

metadata:
  extraction_method: "{browser|gh-cli|vision|file-read|manual}"
  source_type: "{website|github|image|pdf|code|config|description}"
  technologies_detected:
    - "{tech1}"
    - "{tech2}"
  enrichment_applied: {true|false}
```

**Generate search_text:**
Concatenate: name + description + all tags + all token names + all pattern names + source URL. This field is used for BM25 fuzzy search in `_index.yaml`.

**Calculate confidence:**

| Extraction Method | Base Confidence |
|------------------|----------------|
| Browser MCP (full extraction) | 0.9 |
| `gh` CLI (config file parsing) | 0.85 |
| File read (code/config) | 0.95 |
| Vision (image/PDF) | 0.7 |
| Manual entry | 1.0 |
| URL metadata only (degraded) | 0.3 |

Reduce confidence by 0.1 if cross-origin stylesheets blocked CSS extraction.
Reduce confidence by 0.05 for each major extraction category that returned empty.

### Step 5: Storage

1. **Ensure directory exists:**
   ```bash
   mkdir -p project-refs/{domain}/screenshots
   ```

2. **Generate slug** from name:
   - Lowercase
   - Replace spaces and special characters with hyphens
   - Remove consecutive hyphens
   - Max 60 characters
   - Example: "Stripe Dashboard Design System" → `stripe-dashboard-design-system`

3. **Handle --update flag:**
   - If `--update {name}` is provided:
     - Find existing reference by name in `project-refs/{domain}/_index.yaml`
     - Read existing file to preserve `absorbed_at` (original date)
     - Add `updated_at: {current ISO 8601}` field
     - Overwrite the YAML file with new extraction
     - Update `_index.yaml` entry
   - If reference not found: error with suggestion to use `*absorb` without `--update`

4. **Write reference YAML:**
   ```
   project-refs/{domain}/{slug}.yaml
   ```

5. **Update domain index** (`project-refs/{domain}/_index.yaml`):
   - Read existing index (or create new if first reference in domain)
   - Add/update entry:
     ```yaml
     - name: "{name}"
       file: "{slug}.yaml"
       source: "{source}"
       tags: ["{tag1}", "{tag2}"]
       absorbed_at: "{ISO 8601}"
       search_text: "{concatenated searchable text}"
     ```
   - Sort entries alphabetically by name
   - Write updated index

6. **Handle TTL:**
   - If `--ttl` provided, add `ttl_days: {value}` to reference YAML
   - Add `expires_at: "{computed ISO 8601}"` for easy checking
   - TTL references are flagged by `*refs` queries but NOT auto-deleted

7. **Report to user:**
   ```
   ✅ Referência absorvida com sucesso!

   📋 Nome: {name}
   🏷️ Domínio: {domain}
   📁 Arquivo: project-refs/{domain}/{slug}.yaml
   🎯 Confiança: {confidence}%
   🔖 Tags: {tags}

   Tokens extraídos:
   - Cores: {count} tokens
   - Tipografia: {count} tokens
   - Espaçamento: {count} tokens
   - Padrões: {count} identificados

   Use `*refs {domain} --detail "{name}"` para ver detalhes completos.
   ```

### Step 6: Enrichment (optional)

Enrichment runs automatically when ALL of these conditions are true:
- Domain is `design`
- At least 3 color tokens were extracted
- Learned patterns exist in `.lmas-core/data/learned-patterns.yaml`

**Enrichment steps:**

1. **Search learned patterns** for similar color palettes:
   - Compare extracted primary/secondary/accent against known patterns
   - If similarity > 70%, add to `recommendations` section

2. **Search existing Reference Store** for similar references:
   - Load all design domain references from `project-refs/design/_index.yaml`
   - BM25 search using extracted tags and technology names
   - Top 3 matches added to `similar_references` section

3. **Add enrichment data to reference:**
   ```yaml
   enrichment:
     applied: true
     similar_references:
       - name: "{ref name}"
         similarity: {0.0-1.0}
         file: "{ref file path}"
     recommendations:
       - pattern: "{pattern name}"
         reason: "{why this pattern is relevant}"
         source: "learned-patterns"
   ```

---

## Post-conditions

1. A valid YAML file exists at `project-refs/{domain}/{slug}.yaml`
2. The domain `_index.yaml` contains an entry for this reference
3. If screenshots were taken, they exist at `project-refs/{domain}/screenshots/`
4. The user received a confirmation summary

---

## Error Handling

| Error | Handling | User Message |
|-------|----------|-------------|
| URL unreachable (timeout/404) | Save partial reference with source URL, `confidence: 0.0` | "URL inacessível. Referência salva apenas com URL — reabsorva quando disponível." |
| Browser MCP unavailable | Degrade to URL metadata only (title from HEAD request) | "Browser MCP indisponível. Extração limitada a metadados da URL." |
| File not found | Abort with suggestion | "Arquivo não encontrado: {path}. Verifique o caminho e tente novamente." |
| Domain ambiguous (< 50%) | Ask user to specify | Elicitation prompt (see Step 2) |
| Cross-origin CSS blocked | Continue with partial extraction, reduce confidence | "Alguns estilos CSS bloqueados por cross-origin. Extração parcial." |
| Index file corrupted | Rebuild index from existing YAML files in domain directory | "Índice reconstruído a partir dos arquivos existentes." |
| Duplicate name (without --update) | Error with suggestion | "Referência '{name}' já existe. Use `--update` para atualizar ou escolha outro nome." |
| Empty extraction (no tokens/patterns) | Save reference with metadata only | "Nenhum token/padrão extraído. Referência salva com metadados básicos." |

---

## Graceful Degradation

The extraction pipeline degrades gracefully when tools are unavailable:

| Tool | Available | Degraded |
|------|-----------|----------|
| Browser MCP | Full page extraction (tokens, screenshots, computed styles) | URL metadata only via HEAD request |
| `gh` CLI | Full repo scan (configs, dependencies, README) | Manual description of repo |
| Claude Vision | Image/PDF color and layout analysis | File metadata only (dimensions, format) |
| Read tool | Full file content parsing | Always available (Tier 1) |

---

## Examples

### Example 1: Absorb a Website (Design Reference)

**Command:**
```
@lmas-master *absorb https://linear.app --domain design --tags "saas,project-management,minimal"
```

**Result:**
```yaml
name: "Linear App"
source: "https://linear.app"
domain: "design"
absorbed_at: "2026-03-17T14:30:00Z"
absorbed_by: "lmas-master"
description: "Linear — project management tool with minimal, keyboard-first design"
confidence: 0.9
tags: ["saas", "project-management", "minimal", "dark-mode", "keyboard-first"]

tokens:
  colors:
    primary: "#5E6AD2"
    secondary: "#26273B"
    accent: "#8A8F98"
    background: "#111111"
    surface: "#1A1A2E"
    text:
      primary: "#F2F2F2"
      secondary: "#8A8F98"
      muted: "#505050"
    semantic:
      success: "#3FB950"
      warning: "#D29922"
      error: "#F85149"
      info: "#58A6FF"
  typography:
    font_families:
      heading: "Inter"
      body: "Inter"
      code: "JetBrains Mono"
    font_sizes:
      sm: "13px"
      base: "14px"
      lg: "16px"
      xl: "20px"
      2xl: "24px"
  spacing:
    scale: ["4px", "8px", "12px", "16px", "24px", "32px", "48px"]
  border_radius:
    sm: "4px"
    md: "6px"
    lg: "8px"

patterns:
  - name: "Command palette"
    type: "interaction"
    description: "Cmd+K modal for keyboard-driven navigation and actions"
    implementation_notes: "Full-screen overlay with search input and categorized results"
  - name: "Sidebar navigation"
    type: "layout"
    description: "Collapsible sidebar with workspace, team, and project hierarchy"

screenshots:
  - "project-refs/design/screenshots/linear-app.png"

metadata:
  extraction_method: "browser"
  source_type: "website"
  technologies_detected: ["react", "next.js", "tailwind"]
```

### Example 2: Absorb a GitHub Repository (Architecture Reference)

**Command:**
```
@lmas-master *absorb https://github.com/supabase/supabase --domain architecture --tags "baas,postgres,realtime"
```

**Result:**
```yaml
name: "Supabase"
source: "https://github.com/supabase/supabase"
domain: "architecture"
absorbed_at: "2026-03-17T15:00:00Z"
absorbed_by: "lmas-master"
description: "Open source Firebase alternative — Postgres, Auth, Realtime, Storage, Edge Functions"
confidence: 0.85
tags: ["baas", "postgres", "realtime", "open-source", "docker", "typescript"]

patterns:
  - name: "Monorepo with Turborepo"
    type: "architecture"
    description: "Multi-package monorepo using Turborepo for build orchestration"
    implementation_notes: "packages/ for shared libs, apps/ for deployable services"
  - name: "Docker Compose local dev"
    type: "architecture"
    description: "Full local development stack via docker-compose"
    implementation_notes: "20+ services orchestrated with health checks and dependency ordering"
  - name: "Edge Functions"
    type: "architecture"
    description: "Deno-based serverless functions at the edge"
    implementation_notes: "Custom Deno runtime with Postgres connection pooling"

metadata:
  extraction_method: "gh-cli"
  source_type: "github"
  technologies_detected: ["typescript", "go", "elixir", "docker", "postgres", "deno"]
  repo_stats:
    stars: 75000
    language: "TypeScript"
    topics: ["database", "firebase-alternative", "postgres", "supabase"]
```

### Example 3: Absorb a Manual Description (Competitive Reference)

**Command:**
```
@lmas-master *absorb "Vercel v0 — AI-powered UI generation tool. Generates React+Tailwind components from text prompts. Free tier with 10 generations/day, Pro at $20/mo." --domain competitive --tags "ai,ui-generation,competitor"
```

**Result:**
```yaml
name: "Vercel v0"
source: "Vercel v0 — AI-powered UI generation tool. Generates React+Tailwind components from text prompts."
domain: "competitive"
absorbed_at: "2026-03-17T15:30:00Z"
absorbed_by: "lmas-master"
description: "AI-powered UI generation tool by Vercel. Generates React+Tailwind components from text prompts."
confidence: 1.0
tags: ["ai", "ui-generation", "competitor", "react", "tailwind", "freemium"]

metadata:
  extraction_method: "manual"
  source_type: "description"
  pricing:
    free_tier: "10 generations/day"
    pro_tier: "$20/month"
  technologies_detected: ["react", "tailwind"]
```

---

## Constitutional Compliance

- **Article I (CLI First):** This task is fully CLI-driven. No UI required.
- **Article II (Agent Authority):** Only @lmas-master owns this task. Other agents consume via delegation.
- **Article IV (No Invention):** Extracted data must come from the source. Never fabricate tokens or patterns.
- **Article V (Quality First):** Confidence levels ensure extraction quality is transparent.

---

## Related Tasks

- `query-references.md` — Query the Reference Store (`*refs` command)
- `extract-tokens.md` — Standalone token extraction (design domain)
- `learn-patterns.md` — Pattern learning pipeline
- `analyze-project-structure.md` — Project structure analysis
