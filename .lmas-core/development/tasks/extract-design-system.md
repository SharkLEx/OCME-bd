# extract-design-system

## Metadata

```yaml
task_id: extract-design-system
version: 1.0.0
owner: ux-design-expert (Sati)
consumers:
  - ux-design-expert
  - architect
  - dev
elicit: true
category: design-system-extraction
complexity: HIGH
estimated_tokens: ~2000 per execution
```

## Purpose

Reverse-engineer a complete design system from any source: live URL, source code repository, local codebase, or visual assets. Produces a comprehensive MASTER.md, tokens.css, tailwind.config.ts, and optionally saves to the Reference Store.

This is the flagship extraction task in the LMAS design pipeline. It supports three input families (code, visual, hybrid) and auto-detects the optimal extraction strategy based on source type. The output is a production-ready design system package that can be consumed directly by `@dev` for implementation or by `@architect` for system-level decisions.

---

## Inputs

| Input | Required | Type | Description |
|-------|----------|------|-------------|
| `source` | YES | string | URL, file/directory path, or image path to extract from |
| `--mode` | NO | string | `source` \| `visual` \| `hybrid` (default: auto-detect) |
| `--output` | NO | string | Output directory (default: `design-system/`) |
| `--save-ref` | NO | boolean | Also save to Reference Store (`project-refs/design/`) |
| `--name` | NO | string | Design system name (auto-detected if omitted) |
| `--depth` | NO | string | Analysis depth: `quick` \| `standard` \| `deep` (default: `standard`) |
| `--format` | NO | string | Output formats: `all` \| `css` \| `tailwind` \| `master` (default: `all`) |
| `--dark-mode` | NO | boolean | Include dark mode token layer (default: `true`) |

---

## Execution Modes

**Choose your execution mode:**

### 1. YOLO Mode - Fast, Autonomous (0-1 prompts)
- Auto-detect everything, extract with defaults
- Minimal user interaction
- **Best for:** Quick extractions, known sources, CI pipelines

### 2. Interactive Mode - Balanced, Educational (5-10 prompts) **[DEFAULT]**
- Confirm source detection and mode selection
- Review extracted tokens before output generation
- **Best for:** First extraction from a new source, learning the tool

### 3. Pre-Flight Planning - Comprehensive Upfront Planning
- Full source audit before extraction begins
- All naming conventions and output preferences decided upfront
- **Best for:** Enterprise design systems, multi-brand extraction

**Parameter:** `mode` (optional, default: `interactive`)

**Usage:**
```
*extract-design-system {source}                         # Interactive (default)
*extract-design-system {source} yolo                    # YOLO mode
*extract-design-system {source} preflight               # Pre-flight planning
*extract-design-system {source} --depth deep --save-ref # Deep + reference store
```

---

## Task Definition (LMAS Task Format V1.0)

```yaml
task: extractDesignSystem()
responsavel: Sati (Empathizer)
responsavel_type: Agente
atomic_layer: Organism

inputs:
- campo: source
  tipo: string
  origem: User Input
  obrigatorio: true
  validacao: URL, file path, directory path, or image path — must be accessible

- campo: mode
  tipo: string
  origem: User Input
  obrigatorio: false
  validacao: source|visual|hybrid (auto-detect if omitted)

- campo: output
  tipo: string
  origem: User Input
  obrigatorio: false
  validacao: Valid directory path, will be created if missing

- campo: save_ref
  tipo: boolean
  origem: User Input
  obrigatorio: false
  validacao: true|false

- campo: name
  tipo: string
  origem: User Input / Auto-detected
  obrigatorio: false
  validacao: Alphanumeric + hyphens, kebab-case

- campo: depth
  tipo: string
  origem: User Input
  obrigatorio: false
  validacao: quick|standard|deep

- campo: format
  tipo: string
  origem: User Input
  obrigatorio: false
  validacao: all|css|tailwind|master

- campo: dark_mode
  tipo: boolean
  origem: User Input
  obrigatorio: false
  validacao: true|false

saidas:
- campo: master_document
  tipo: file
  destino: {output}/MASTER.md
  persistido: true

- campo: css_tokens
  tipo: file
  destino: {output}/tokens.css
  persistido: true

- campo: tailwind_config
  tipo: file
  destino: {output}/tailwind.config.ts
  persistido: true

- campo: extraction_summary
  tipo: object
  destino: Console
  persistido: false

- campo: reference_entry
  tipo: file
  destino: project-refs/design/{name}.yaml
  persistido: conditional (--save-ref)
```

---

## Mode Selection (Auto-Detection)

When `--mode` is not provided, auto-detect based on source type:

| Source Type | Detection Pattern | Selected Mode | Rationale |
|-------------|------------------|--------------|-----------|
| Live URL | `https?://` (not GitHub) | `hybrid` | Source code extraction + visual analysis |
| GitHub URL | `github.com/{owner}/{repo}` | `source` | Clone and analyze code directly |
| GitLab URL | `gitlab.com/{owner}/{repo}` | `source` | Clone and analyze code directly |
| Local directory | Path exists and `isDirectory()` | `source` | Direct file analysis |
| Single CSS/SCSS file | `.css`, `.scss`, `.less` extension | `source` | Parse single stylesheet |
| Single TS/JS file | `.ts`, `.js` with theme/token exports | `source` | Parse single config |
| Single JSON/YAML file | `.json`, `.yaml`, `.yml` | `source` | Parse structured tokens |
| Image file | `.png`, `.jpg`, `.jpeg`, `.webp`, `.svg` | `visual` | Claude vision analysis |
| PDF file | `.pdf` | `visual` | Claude vision analysis |
| Figma URL | `figma.com/` | `visual` | Screenshot + extraction |
| Unknown | Anything else | `hybrid` | Try both, merge results |

### Depth Defaults by Source Type

| Source Type | Default Depth | Pages Analyzed | Token Categories |
|-------------|--------------|----------------|-----------------|
| Live URL | `standard` | 1 (homepage) | All |
| Live URL + `--depth deep` | `deep` | 3-5 key pages | All + component variants |
| GitHub repo | `standard` | N/A | All found in config |
| Local directory | `standard` | N/A | All found in files |
| Image | `quick` | 1 | Colors, typography, spacing |
| Image + `--depth deep` | `deep` | 1 | All + component identification |

---

## Constitutional Gates

> **Reference:** Constitution Article IV (No Invention)
> **Enforcement:** Automatic validation during extraction

### Gate 1: No Invention (Article IV)

```yaml
constitutional_gate:
  article: IV
  name: No Invention
  severity: WARN

  validation:
    - Extracted tokens MUST come from actual source analysis
    - Visual-mode tokens MUST be marked as confidence: approximate
    - NEVER invent tokens that were not found in the source
    - Recommendations section clearly separated from extracted data

  on_violation:
    action: WARN
    message: |
      CONSTITUTIONAL WARNING: Article IV - No Invention
      All design tokens must trace to actual source data.
      Do not invent tokens or values not found in the source.
```

---

## Pre-Conditions

**Purpose:** Validate prerequisites BEFORE task execution (blocking)

```yaml
pre-conditions:
  - [ ] Source is accessible (URL reachable, file/directory exists, image readable)
    tipo: pre-condition
    blocker: true
    validacao: |
      URL: HTTP HEAD returns 2xx or 3xx
      File: fs.existsSync(source) returns true
      Directory: fs.statSync(source).isDirectory() returns true
    error_message: "Source not accessible: {source}. Verify path/URL and try again."

  - [ ] Output directory is writable (or can be created)
    tipo: pre-condition
    blocker: true
    validacao: |
      Directory exists and is writable, or parent directory allows creation
    error_message: "Cannot write to output directory: {output}"

  - [ ] At least one extraction tool available (Browser MCP, Read tool, or gh CLI)
    tipo: pre-condition
    blocker: true
    validacao: |
      For URL sources: Browser MCP or fetch available
      For GitHub: gh CLI available
      For local: Read/Glob tools available (always true in Claude Code)
    error_message: "No extraction tools available for source type: {sourceType}"
```

---

## Post-Conditions

**Purpose:** Validate execution success AFTER task completes

```yaml
post-conditions:
  - [ ] MASTER.md generated with at least colors and typography sections
    tipo: post-condition
    blocker: true
    validacao: |
      File exists at {output}/MASTER.md
      Contains ## Color Palette section with at least 1 token
      Contains ## Typography section with at least 1 font family
    error_message: "MASTER.md incomplete: missing core sections"

  - [ ] tokens.css generated with valid CSS custom properties
    tipo: post-condition
    blocker: true
    validacao: |
      File exists at {output}/tokens.css
      Contains :root { block
      Contains at least 1 --token-name: value; declaration
    error_message: "tokens.css invalid or empty"

  - [ ] tailwind.config.ts generated with valid TypeScript
    tipo: post-condition
    blocker: true
    validacao: |
      File exists at {output}/tailwind.config.ts
      Contains export default { block
      Contains theme.extend with at least colors key
    error_message: "tailwind.config.ts invalid or empty"

  - [ ] Extraction summary displayed with token counts
    tipo: post-condition
    blocker: false
    validacao: |
      Summary includes: source, mode, token counts by category, confidence level
    error_message: "Extraction summary incomplete"
```

---

## Acceptance Criteria

**Purpose:** Definitive pass/fail criteria for task completion

```yaml
acceptance-criteria:
  - [ ] Design system extracted with tokens in at least 3 categories (colors, typography, spacing)
    tipo: acceptance-criterion
    blocker: true
    validacao: |
      Token count > 0 for colors AND typography AND spacing
    error_message: "Extraction too shallow: need tokens in at least 3 categories"

  - [ ] All output files are syntactically valid
    tipo: acceptance-criterion
    blocker: true
    validacao: |
      MASTER.md: valid markdown (headers, tables render)
      tokens.css: parseable CSS (no syntax errors)
      tailwind.config.ts: valid TypeScript syntax
    error_message: "Output files contain syntax errors"

  - [ ] Visual-mode tokens marked with approximate confidence
    tipo: acceptance-criterion
    blocker: true
    validacao: |
      If mode == visual or hybrid:
        All vision-derived values have confidence: approximate annotation
    error_message: "Visual tokens missing confidence annotations (Article IV)"

  - [ ] Reference store entry valid if --save-ref used
    tipo: acceptance-criterion
    blocker: false
    validacao: |
      If --save-ref: file exists at project-refs/design/{name}.yaml
      YAML is valid and follows reference-store-schema
    error_message: "Reference store entry invalid"
```

---

## Execution Flow

### Step 1: Source Detection & Validation

**Goal:** Determine source type, select extraction mode, validate accessibility.

1. **Parse source argument:**
   - If starts with `http://` or `https://` → URL type
   - If matches `github.com/{owner}/{repo}` → GitHub type
   - If matches `gitlab.com/{owner}/{repo}` → GitLab type
   - If matches `figma.com/` → Figma type
   - If path ends with image extension → Image type
   - If path ends with `.pdf` → PDF type
   - If path ends with `.css`, `.scss`, `.less` → Single stylesheet type
   - If path ends with `.ts`, `.js`, `.json`, `.yaml`, `.yml` → Single config type
   - If path is directory → Local directory type
   - Else → Unknown (try hybrid)

2. **Auto-select mode** (if `--mode` not provided):
   - Apply mapping from Mode Selection table above
   - Log: `Auto-detected mode: {mode} for source type: {sourceType}`

3. **Validate source accessibility:**

   ```javascript
   // URL validation
   async function validateURL(url) {
     try {
       // Try Browser MCP first
       const response = await navigateToURL(url);
       return { accessible: true, method: 'browser' };
     } catch {
       // Fallback: try fetch/curl
       try {
         const result = await bash(`curl -sI -o /dev/null -w "%{http_code}" "${url}"`);
         const statusCode = parseInt(result.trim());
         return { accessible: statusCode >= 200 && statusCode < 400, method: 'curl' };
       } catch {
         return { accessible: false, method: null };
       }
     }
   }

   // GitHub validation
   async function validateGitHub(url) {
     const match = url.match(/github\.com\/([^/]+)\/([^/]+)/);
     if (!match) return { accessible: false };
     const [_, owner, repo] = match;
     try {
       await bash(`gh repo view ${owner}/${repo} --json name`);
       return { accessible: true, owner, repo };
     } catch {
       return { accessible: false };
     }
   }

   // Local path validation
   async function validateLocal(path) {
     // Use Glob/Read tools — always available in Claude Code
     const exists = await fileExists(path);
     const isDir = exists && await isDirectory(path);
     return { accessible: exists, isDirectory: isDir };
   }
   ```

4. **Set analysis depth** based on source type defaults (override with `--depth`)

5. **Auto-detect name** (if `--name` not provided):
   - URL: extract domain name (e.g., `stripe.com` → `stripe`)
   - GitHub: use repo name
   - Local dir: use directory name
   - File: use filename without extension
   - Image: use `visual-extraction-{timestamp}`

---

### Step 2: Extraction — Source Code Mode

**Goal:** Extract design tokens from source code, config files, and stylesheets.

#### 2a. Live Website (URL → Source Code)

1. **Navigate to URL** using Browser MCP (`mcp__claude-in-chrome__navigate`):
   ```
   Navigate to: {source}
   Wait for: page fully loaded (DOMContentLoaded + 2s for dynamic content)
   ```

2. **Extract CSS custom properties** from `:root` and all stylesheets:
   ```javascript
   // Execute in browser context via mcp__claude-in-chrome__javascript_tool
   (function extractDesignTokens() {
     const tokens = {
       customProperties: {},
       colors: new Set(),
       fonts: new Set(),
       fontSizes: new Set(),
       fontWeights: new Set(),
       lineHeights: new Set(),
       spacings: new Set(),
       borderRadii: new Set(),
       shadows: [],
       transitions: new Set(),
       zIndices: new Set(),
       breakpoints: {}
     };

     // 1. Extract CSS custom properties from all stylesheets
     try {
       for (const sheet of document.styleSheets) {
         try {
           for (const rule of sheet.cssRules) {
             if (rule.selectorText === ':root' || rule.selectorText === ':host') {
               for (const prop of rule.style) {
                 if (prop.startsWith('--')) {
                   tokens.customProperties[prop] = rule.style.getPropertyValue(prop).trim();
                 }
               }
             }
           }
         } catch (e) {
           // Cross-origin stylesheet — skip silently
         }
       }
     } catch (e) {
       // Stylesheets not accessible
     }

     // 2. Extract computed styles from all visible elements
     const elements = document.querySelectorAll('body *:not(script):not(style):not(link)');
     const sampleSize = Math.min(elements.length, 500); // Cap at 500 elements

     for (let i = 0; i < sampleSize; i++) {
       const el = elements[i];
       const computed = getComputedStyle(el);

       // Colors
       tokens.colors.add(computed.color);
       tokens.colors.add(computed.backgroundColor);
       tokens.colors.add(computed.borderColor);

       // Typography
       tokens.fonts.add(computed.fontFamily);
       tokens.fontSizes.add(computed.fontSize);
       tokens.fontWeights.add(computed.fontWeight);
       tokens.lineHeights.add(computed.lineHeight);

       // Spacing (collect unique padding/margin/gap values)
       ['padding', 'margin', 'gap', 'rowGap', 'columnGap'].forEach(prop => {
         const val = computed[prop];
         if (val && val !== '0px' && val !== 'normal') tokens.spacings.add(val);
       });

       // Border radius
       const radius = computed.borderRadius;
       if (radius && radius !== '0px') tokens.borderRadii.add(radius);

       // Box shadow
       const shadow = computed.boxShadow;
       if (shadow && shadow !== 'none') tokens.shadows.push(shadow);

       // Transitions
       const transition = computed.transition;
       if (transition && transition !== 'all 0s ease 0s') tokens.transitions.add(transition);

       // Z-index
       const zIndex = computed.zIndex;
       if (zIndex !== 'auto') tokens.zIndices.add(zIndex);
     }

     // 3. Detect media query breakpoints from stylesheets
     try {
       for (const sheet of document.styleSheets) {
         try {
           for (const rule of sheet.cssRules) {
             if (rule instanceof CSSMediaRule) {
               const match = rule.conditionText.match(/min-width:\s*(\d+)px/);
               if (match) tokens.breakpoints[match[1] + 'px'] = true;
             }
           }
         } catch (e) { /* cross-origin */ }
       }
     } catch (e) { /* no access */ }

     // Convert Sets to sorted Arrays
     return {
       customProperties: tokens.customProperties,
       colors: [...tokens.colors].filter(c => c !== 'rgba(0, 0, 0, 0)'),
       fonts: [...tokens.fonts],
       fontSizes: [...tokens.fontSizes].sort((a, b) => parseFloat(a) - parseFloat(b)),
       fontWeights: [...tokens.fontWeights].sort(),
       lineHeights: [...tokens.lineHeights],
       spacings: [...tokens.spacings].sort((a, b) => parseFloat(a) - parseFloat(b)),
       borderRadii: [...tokens.borderRadii],
       shadows: [...new Set(tokens.shadows)],
       transitions: [...tokens.transitions],
       zIndices: [...tokens.zIndices].sort((a, b) => Number(a) - Number(b)),
       breakpoints: Object.keys(tokens.breakpoints).sort((a, b) => parseInt(a) - parseInt(b)),
       elementCount: elements.length,
       sampledCount: sampleSize
     };
   })();
   ```

3. **Take full-page screenshot** for visual cross-reference:
   ```
   mcp__claude-in-chrome__get_page_text → capture page structure
   mcp__claude-in-chrome__computer → screenshot for visual analysis
   ```

4. **Deep mode (--depth deep):** Navigate to additional pages:
   - Parse `<nav>` links for key pages (about, pricing, features, contact)
   - Limit to 3-5 additional pages
   - Run extraction script on each page
   - Merge token sets (union, deduplicate)

#### 2b. GitHub / GitLab Repository

1. **Parse repository URL:**
   ```javascript
   function parseRepoURL(url) {
     const ghMatch = url.match(/github\.com\/([^/]+)\/([^/]+)/);
     const glMatch = url.match(/gitlab\.com\/([^/]+)\/([^/]+)/);
     if (ghMatch) return { platform: 'github', owner: ghMatch[1], repo: ghMatch[2].replace('.git', '') };
     if (glMatch) return { platform: 'gitlab', owner: glMatch[1], repo: glMatch[2].replace('.git', '') };
     return null;
   }
   ```

2. **Clone repository** (shallow, to temp directory):
   ```bash
   # Create temp directory
   TEMP_DIR=$(mktemp -d)
   gh repo clone {owner}/{repo} "$TEMP_DIR" -- --depth 1
   ```

3. **Scan for design system indicators:**

   | File Pattern | Indicator | Priority |
   |-------------|-----------|----------|
   | `tailwind.config.*` | Tailwind theme tokens | HIGH |
   | `**/tokens.*`, `**/theme.*` | Design token files | HIGH |
   | `**/design-system/**` | DS directory structure | HIGH |
   | `package.json` → dependencies | CSS framework detection | MEDIUM |
   | `**/*.css` with `:root` | CSS custom properties | MEDIUM |
   | `**/*.scss` with `$variables` | SCSS variables | MEDIUM |
   | `**/styles/variables.*` | Variable files | MEDIUM |
   | `**/constants/colors.*` | Hardcoded color constants | LOW |
   | `src/components/` | Component inventory | LOW |

4. **Extract tokens from each found source:**
   - Tailwind config: parse `theme.extend` object
   - CSS files: regex for `--{name}: {value}` in `:root` blocks
   - SCSS files: regex for `\${name}: {value}`
   - JS/TS theme files: parse exported objects
   - JSON token files: parse structured data
   - package.json: detect CSS framework (tailwind, chakra, mantine, etc.)

5. **Build component inventory** from file structure:
   - Scan `src/components/` or equivalent
   - Classify by atomic design level (atom, molecule, organism)
   - Count unique components

6. **Clean up** temp clone:
   ```bash
   rm -rf "$TEMP_DIR"
   ```

#### 2c. Local Directory

1. **Glob for design-related files:**
   ```
   Glob: **/*.css                    → CSS custom properties
   Glob: **/tailwind.config.*        → Tailwind tokens
   Glob: **/theme.{ts,js,json,yaml}  → Theme files
   Glob: **/tokens.{ts,js,json,yaml,css} → Token files
   Glob: **/design-system/**         → DS directory
   Glob: **/*.scss                   → SCSS variables
   Glob: **/*.less                   → LESS variables
   Glob: **/variables.{css,scss,less} → Variable files
   Glob: **/colors.{ts,js,json}      → Color constants
   Glob: **/typography.{ts,js,json}   → Typography constants
   ```

2. **Read and parse each found file:**
   - Apply same extraction logic as 2b step 4
   - For large directories: prioritize files closer to root
   - Skip `node_modules/`, `dist/`, `.next/`, `build/`

3. **Detect framework from package.json** (if exists):
   ```javascript
   function detectFramework(packageJson) {
     const deps = {
       ...packageJson.dependencies,
       ...packageJson.devDependencies
     };
     const frameworks = [];
     if (deps['tailwindcss']) frameworks.push('tailwind');
     if (deps['@chakra-ui/react']) frameworks.push('chakra');
     if (deps['@mantine/core']) frameworks.push('mantine');
     if (deps['@mui/material']) frameworks.push('material-ui');
     if (deps['styled-components']) frameworks.push('styled-components');
     if (deps['@emotion/react']) frameworks.push('emotion');
     if (deps['antd']) frameworks.push('ant-design');
     if (deps['bootstrap']) frameworks.push('bootstrap');
     return frameworks;
   }
   ```

4. **Build component inventory** from directory structure

#### 2d. Single File

1. **Read file content** using Read tool

2. **Parse based on extension:**

   | Extension | Parser | Token Extraction |
   |-----------|--------|-----------------|
   | `.css` | CSS parser | `--{name}: {value}` in `:root` |
   | `.scss` | SCSS parser | `\${name}: {value}` declarations |
   | `.less` | LESS parser | `@{name}: {value}` declarations |
   | `.ts`, `.js` | AST/regex | Exported theme/config objects |
   | `.json` | JSON.parse | Structured token data |
   | `.yaml`, `.yml` | YAML parse | Structured token data |

3. **Map to standardized token format** (see Step 5)

---

### Step 3: Extraction — Visual Mode

**Goal:** Extract design tokens from images/PDFs/screenshots using Claude vision.

1. **Read image/PDF** with Read tool (Claude vision handles this natively):
   ```
   Read: {source}
   For PDF: Read with pages parameter if > 10 pages
   ```

2. **Structured visual analysis prompt:**
   ```
   Analyze this design/screenshot and extract:

   COLORS:
   - List every distinct color visible (primary, secondary, accent, neutrals, states)
   - Provide approximate hex values
   - Note where each color is used (backgrounds, text, buttons, borders)

   TYPOGRAPHY:
   - Identify font families (approximate — note system fonts vs custom)
   - List all distinct font sizes (approximate px values)
   - Note font weights visible (light, regular, medium, semibold, bold)
   - Estimate line heights for body and heading text

   SPACING:
   - Identify the base spacing unit (4px, 8px grid?)
   - Note section padding
   - Note component internal padding
   - Note gap between elements

   LAYOUT:
   - Grid system (columns, max-width, gutters)
   - Responsive hints (if multiple sizes shown)

   COMPONENTS:
   - Button styles (sizes, variants, states)
   - Card patterns (shadow, radius, padding)
   - Input field styles
   - Navigation patterns

   BORDERS:
   - Border radius values (approximate px)
   - Border widths and colors

   SHADOWS:
   - Number of distinct elevation levels
   - Approximate shadow values (offset, blur, color)

   Mark ALL values as APPROXIMATE (vision-based extraction).
   ```

3. **Parse structured response** into token categories

4. **Mark confidence level:**
   - All values get `confidence: approximate`
   - Color hex values: +/- 10% accuracy
   - Size values: +/- 2px accuracy
   - Font identification: may be incorrect for custom fonts

---

### Step 4: Extraction — Hybrid Mode (default for URLs)

**Goal:** Combine source code and visual extraction for maximum coverage.

1. **Execute Source Code extraction** (Step 2a):
   - Extract CSS custom properties, computed styles
   - Confidence: `exact` for all values

2. **Execute Visual extraction** (Step 3):
   - Screenshot of the page
   - Confidence: `approximate` for all values

3. **Merge results with conflict resolution:**

   ```
   MERGE RULES:
   ┌─────────────────────────────────────────────────────────────┐
   │ Source code value exists?                                    │
   │   YES → Use source code value (confidence: exact)           │
   │   NO  → Use visual value (confidence: approximate)          │
   ├─────────────────────────────────────────────────────────────┤
   │ Both exist but different?                                    │
   │   → Use source code value                                   │
   │   → Note visual discrepancy in MASTER.md                    │
   │   → Common cause: CSS overrides, dynamic themes, JS styles  │
   ├─────────────────────────────────────────────────────────────┤
   │ Visual found tokens source missed?                          │
   │   → Add visual token (confidence: approximate)              │
   │   → Flag for manual verification                            │
   └─────────────────────────────────────────────────────────────┘
   ```

4. **Compute overall confidence:**
   - `high` if > 80% tokens from source code
   - `medium` if 50-80% from source code
   - `low` if < 50% from source code (mostly visual)

---

### Step 5: Token Normalization

**Goal:** Deduplicate, normalize, and categorize all extracted tokens.

1. **Deduplicate extracted values:**
   - Remove exact duplicates
   - Merge near-duplicates (colors within deltaE < 3, sizes within 1px)

2. **Normalize color formats** to hex:
   ```javascript
   function normalizeColor(value) {
     // rgb(r, g, b) → #hex
     // rgba(r, g, b, a) → #hex + opacity note
     // hsl(h, s%, l%) → #hex
     // hsla(h, s%, l%, a) → #hex + opacity note
     // oklch(l c h) → #hex (using conversion)
     // named colors (red, blue) → #hex
     // Already hex → validate and return
     return { hex, original: value, format: detectedFormat };
   }
   ```

3. **Normalize spacing** to px:
   ```javascript
   function normalizeSpacing(value, baseFontSize = 16) {
     // rem → px (value * baseFontSize)
     // em → px (value * baseFontSize, note context-dependent)
     // px → as-is
     // % → note as percentage, keep original
     return { px: normalizedValue, original: value };
   }
   ```

4. **Group tokens by category:**
   ```yaml
   colors:
     primitive:    # Raw color values (#hex)
     semantic:     # Named roles (primary, secondary, error, success, warning, info)
     state:        # Interactive states (hover, active, disabled, focus)

   typography:
     families:     # Font family stacks
     sizes:        # Font size scale
     weights:      # Font weight scale
     lineHeights:  # Line height values
     letterSpacing: # Letter spacing values

   spacing:
     scale:        # Spacing scale values (4, 8, 12, 16, 24, 32, 48, 64...)

   borders:
     radii:        # Border radius scale
     widths:       # Border width values
     colors:       # Border colors (if distinct from palette)

   shadows:
     levels:       # Elevation levels (sm, md, lg, xl)

   motion:
     durations:    # Transition/animation durations
     easings:      # Easing functions

   layout:
     breakpoints:  # Responsive breakpoints
     maxWidth:     # Container max-widths
     grid:         # Grid column counts, gutters

   zIndex:
     scale:        # Z-index layers
   ```

5. **Generate semantic token names** using CTI format (Category-Type-Item):
   ```
   color-primary-default    → #635BFF
   color-primary-hover      → #5851DB
   color-background-default → #FFFFFF
   color-text-primary       → #0A2540
   font-family-heading      → "Sohne", system-ui, sans-serif
   font-size-h1             → 48px
   spacing-md               → 16px
   radius-lg                → 12px
   shadow-md                → 0 4px 6px rgba(0,0,0,0.1)
   ```

---

### Step 6: Design Intelligence Enrichment

**Goal:** Enrich extraction with design best-practice recommendations.

1. **Color analysis:**
   - Calculate WCAG contrast ratios for text/background pairs
   - Flag pairs below AA (4.5:1 for normal text, 3:1 for large text)
   - Identify missing semantic colors (success, warning, error, info)
   - Detect if palette follows a system (Material, Tailwind scale, custom)

2. **Typography analysis:**
   - Check type scale ratio (is it consistent? e.g., 1.25 major third)
   - Verify heading hierarchy (h1 > h2 > h3 in size and weight)
   - Flag missing weights for common use cases
   - Check line-height ratios (1.4-1.6 for body is ideal)

3. **Spacing analysis:**
   - Detect grid system (4px, 8px base unit)
   - Check if spacing follows a scale (linear, geometric)
   - Flag inconsistent spacing values

4. **Component coverage:**
   - List expected components for the detected framework
   - Check which are present vs missing
   - Provide recommendations for missing essentials

5. **Accessibility check:**
   - Color contrast compliance summary
   - Font size minimums (16px base recommended)
   - Touch target sizes (44x44px minimum)

6. **Generate recommendations section:**
   ```markdown
   ## Recommendations

   ### Accessibility
   - color-text-primary (#0A2540) on color-background (#F6F9FC): contrast 12.4:1 (AAA)
   - color-primary (#635BFF) on white: contrast 4.2:1 (AA Large only — consider darkening)

   ### Missing Tokens
   - No explicit `error` color found — consider adding for form validation
   - No `disabled` state tokens — add opacity-based disabled variants
   - No `focus-ring` token — add for keyboard navigation accessibility

   ### Scale Consistency
   - Spacing scale follows 4px grid (good)
   - Font size scale approximate ratio: 1.25 (Major Third — consistent)
   - 2 spacing outliers detected: 18px and 22px (consider rounding to 16px and 24px)

   ### Domain Match
   - Palette profile: "fintech" (93% similarity — blues, clean whites, minimal accents)
   ```

---

### Step 7: Output Generation

**Goal:** Generate all output files from normalized tokens.

#### 7a. MASTER.md (Comprehensive Design System Document)

```markdown
# {Name} Design System

> Extracted from `{source}` on {date}
> Extraction mode: {mode} | Confidence: {confidence_level}
> Agent: @ux-design-expert (Sati) | Task: extract-design-system v1.0.0

---

## Overview

| Metric | Value |
|--------|-------|
| Source | {source} |
| Mode | {mode} |
| Depth | {depth} |
| Total tokens | {total_count} |
| Confidence | {confidence_level} |
| Date | {extraction_date} |
| Dark mode | {dark_mode_status} |

---

## Color Palette

### Primitive Colors

| Token | Value | Preview | Source |
|-------|-------|---------|--------|
| `color-blue-500` | `#635BFF` | ![#635BFF](https://via.placeholder.com/20/635BFF/635BFF) | {exact\|approximate} |
| `color-dark-900` | `#0A2540` | ![#0A2540](https://via.placeholder.com/20/0A2540/0A2540) | {exact\|approximate} |
| ... | ... | ... | ... |

### Semantic Colors

| Token | Value | Maps To | Usage |
|-------|-------|---------|-------|
| `color-primary` | `#635BFF` | `color-blue-500` | Primary actions, links |
| `color-secondary` | `#0A2540` | `color-dark-900` | Headings, emphasis |
| `color-background` | `#F6F9FC` | `color-gray-50` | Page background |
| `color-surface` | `#FFFFFF` | `color-white` | Card backgrounds |
| `color-success` | `#28A745` | — | Success states |
| `color-warning` | `#FFC107` | — | Warning states |
| `color-error` | `#DC3545` | — | Error states |
| `color-info` | `#17A2B8` | — | Info states |

### Dark Mode Colors (if detected/generated)

| Token | Light | Dark |
|-------|-------|------|
| `color-background` | `#F6F9FC` | `#0A2540` |
| `color-surface` | `#FFFFFF` | `#1A3A5C` |
| `color-text-primary` | `#0A2540` | `#F6F9FC` |
| ... | ... | ... |

---

## Typography

### Font Families

| Token | Value | Fallback Stack | Usage |
|-------|-------|---------------|-------|
| `font-family-primary` | `"Sohne"` | `system-ui, sans-serif` | Body text |
| `font-family-heading` | `"Sohne"` | `system-ui, sans-serif` | Headings |
| `font-family-mono` | `"Sohne Mono"` | `monospace` | Code blocks |

### Type Scale

| Token | Size | Weight | Line Height | Usage |
|-------|------|--------|-------------|-------|
| `font-size-xs` | `12px` | 400 | 1.5 | Captions, labels |
| `font-size-sm` | `14px` | 400 | 1.5 | Secondary text |
| `font-size-base` | `16px` | 400 | 1.6 | Body text |
| `font-size-lg` | `18px` | 500 | 1.5 | Lead paragraphs |
| `font-size-xl` | `24px` | 600 | 1.3 | H3 headings |
| `font-size-2xl` | `32px` | 600 | 1.2 | H2 headings |
| `font-size-3xl` | `48px` | 700 | 1.1 | H1 headings |

### Font Weights

| Token | Value | Usage |
|-------|-------|-------|
| `font-weight-light` | `300` | De-emphasis |
| `font-weight-normal` | `400` | Body text |
| `font-weight-medium` | `500` | Emphasis, labels |
| `font-weight-semibold` | `600` | Subheadings |
| `font-weight-bold` | `700` | Headings, CTAs |

---

## Spacing

| Token | Value | Usage |
|-------|-------|-------|
| `spacing-0` | `0` | Reset |
| `spacing-1` | `4px` | Tight gaps |
| `spacing-2` | `8px` | Inline elements |
| `spacing-3` | `12px` | Form gaps |
| `spacing-4` | `16px` | Component padding |
| `spacing-5` | `20px` | — |
| `spacing-6` | `24px` | Card padding |
| `spacing-8` | `32px` | Section gap |
| `spacing-10` | `40px` | — |
| `spacing-12` | `48px` | Page sections |
| `spacing-16` | `64px` | Large sections |

**Grid system:** {detected_base}px base unit

---

## Borders & Radii

### Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `radius-none` | `0` | Sharp corners |
| `radius-sm` | `4px` | Subtle rounding |
| `radius-md` | `8px` | Buttons, inputs |
| `radius-lg` | `12px` | Cards |
| `radius-xl` | `16px` | Modals |
| `radius-full` | `9999px` | Pills, avatars |

### Border Widths

| Token | Value |
|-------|-------|
| `border-width-thin` | `1px` |
| `border-width-medium` | `2px` |
| `border-width-thick` | `4px` |

---

## Shadows & Elevation

| Token | Value | Usage |
|-------|-------|-------|
| `shadow-xs` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `shadow-sm` | `0 1px 3px rgba(0,0,0,0.1)` | Cards at rest |
| `shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Dropdowns |
| `shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals |
| `shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Popovers |

---

## Motion

### Durations

| Token | Value | Usage |
|-------|-------|-------|
| `duration-fast` | `100ms` | Micro-interactions |
| `duration-normal` | `200ms` | Default transitions |
| `duration-slow` | `300ms` | Page transitions |
| `duration-slower` | `500ms` | Complex animations |

### Easings

| Token | Value | Usage |
|-------|-------|-------|
| `easing-default` | `cubic-bezier(0.4, 0, 0.2, 1)` | General purpose |
| `easing-in` | `cubic-bezier(0.4, 0, 1, 1)` | Enter animations |
| `easing-out` | `cubic-bezier(0, 0, 0.2, 1)` | Exit animations |
| `easing-bounce` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Playful interactions |

---

## Layout

### Breakpoints

| Token | Value | Usage |
|-------|-------|-------|
| `breakpoint-sm` | `640px` | Mobile landscape |
| `breakpoint-md` | `768px` | Tablet |
| `breakpoint-lg` | `1024px` | Desktop |
| `breakpoint-xl` | `1280px` | Wide desktop |
| `breakpoint-2xl` | `1536px` | Ultra-wide |

### Container

| Token | Value |
|-------|-------|
| `container-max-width` | `{detected}px` |
| `container-padding` | `{detected}px` |

---

## Component Inventory

| Component | Atomic Level | Variants | Status |
|-----------|-------------|----------|--------|
| Button | Atom | {count} | Extracted |
| Input | Atom | {count} | Extracted |
| Card | Molecule | {count} | Extracted |
| ... | ... | ... | ... |

**Total components identified:** {count}

---

## Recommendations

{Generated by Step 6 — Design Intelligence Enrichment}

---

## Extraction Metadata

| Field | Value |
|-------|-------|
| Source | `{source}` |
| Mode | {mode} |
| Depth | {depth} |
| Date | {date} |
| Agent | @ux-design-expert (Sati) |
| Task | extract-design-system v1.0.0 |
| Confidence | {level} |
| Files analyzed | {count} |
| Tokens extracted | {count} |
| Duration | {duration} |
```

#### 7b. tokens.css

```css
/* ==========================================================================
   {Name} Design System — CSS Custom Properties
   Extracted from: {source}
   Date: {date}
   Agent: @ux-design-expert (Sati)
   ========================================================================== */

:root {
  /* ========== Colors — Primitive ========== */
  --color-white: #FFFFFF;
  --color-black: #000000;
  /* {dynamic: all primitive colors} */

  /* ========== Colors — Semantic ========== */
  --color-primary: var(--color-blue-500);
  --color-secondary: var(--color-dark-900);
  --color-background: var(--color-gray-50);
  --color-surface: var(--color-white);
  --color-text-primary: var(--color-dark-900);
  --color-text-secondary: var(--color-gray-600);
  --color-success: #28A745;
  --color-warning: #FFC107;
  --color-error: #DC3545;
  --color-info: #17A2B8;

  /* ========== Colors — State ========== */
  --color-primary-hover: var(--color-blue-600);
  --color-primary-active: var(--color-blue-700);
  --color-primary-disabled: var(--color-blue-300);

  /* ========== Typography ========== */
  --font-family-primary: {value};
  --font-family-heading: {value};
  --font-family-mono: {value};

  --font-size-xs: 12px;
  --font-size-sm: 14px;
  --font-size-base: 16px;
  --font-size-lg: 18px;
  --font-size-xl: 24px;
  --font-size-2xl: 32px;
  --font-size-3xl: 48px;

  --font-weight-light: 300;
  --font-weight-normal: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;

  --line-height-tight: 1.1;
  --line-height-snug: 1.3;
  --line-height-normal: 1.5;
  --line-height-relaxed: 1.6;

  /* ========== Spacing ========== */
  --spacing-0: 0;
  --spacing-1: 4px;
  --spacing-2: 8px;
  --spacing-3: 12px;
  --spacing-4: 16px;
  --spacing-5: 20px;
  --spacing-6: 24px;
  --spacing-8: 32px;
  --spacing-10: 40px;
  --spacing-12: 48px;
  --spacing-16: 64px;

  /* ========== Borders ========== */
  --radius-none: 0;
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-full: 9999px;

  --border-width-thin: 1px;
  --border-width-medium: 2px;
  --border-width-thick: 4px;

  /* ========== Shadows ========== */
  --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.1);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1);
  --shadow-xl: 0 20px 25px rgba(0, 0, 0, 0.15);

  /* ========== Motion ========== */
  --duration-fast: 100ms;
  --duration-normal: 200ms;
  --duration-slow: 300ms;
  --duration-slower: 500ms;

  --easing-default: cubic-bezier(0.4, 0, 0.2, 1);
  --easing-in: cubic-bezier(0.4, 0, 1, 1);
  --easing-out: cubic-bezier(0, 0, 0.2, 1);

  /* ========== Layout ========== */
  --breakpoint-sm: 640px;
  --breakpoint-md: 768px;
  --breakpoint-lg: 1024px;
  --breakpoint-xl: 1280px;

  /* ========== Z-Index ========== */
  --z-index-dropdown: 1000;
  --z-index-sticky: 1020;
  --z-index-fixed: 1030;
  --z-index-modal-backdrop: 1040;
  --z-index-modal: 1050;
  --z-index-popover: 1060;
  --z-index-tooltip: 1070;
}

/* ========== Dark Mode ========== */
[data-theme="dark"],
.dark {
  --color-background: var(--color-dark-900);
  --color-surface: var(--color-dark-800);
  --color-text-primary: var(--color-gray-50);
  --color-text-secondary: var(--color-gray-400);
  /* {dynamic: all dark mode overrides} */
}

/* ========== Prefers Dark ========== */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --color-background: var(--color-dark-900);
    --color-surface: var(--color-dark-800);
    --color-text-primary: var(--color-gray-50);
    --color-text-secondary: var(--color-gray-400);
  }
}
```

#### 7c. tailwind.config.ts

```typescript
import type { Config } from 'tailwindcss'

/**
 * {Name} Design System — Tailwind Configuration
 * Extracted from: {source}
 * Date: {date}
 * Agent: @ux-design-expert (Sati)
 */
export default {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '{value}',
          hover: '{value}',
          active: '{value}',
          disabled: '{value}',
        },
        secondary: { /* mapped */ },
        background: '{value}',
        surface: '{value}',
        success: '{value}',
        warning: '{value}',
        error: '{value}',
        info: '{value}',
        /* {dynamic: all extracted colors} */
      },
      fontFamily: {
        primary: ['{font}', 'system-ui', 'sans-serif'],
        heading: ['{font}', 'system-ui', 'sans-serif'],
        mono: ['{font}', 'monospace'],
      },
      fontSize: {
        xs: ['12px', { lineHeight: '1.5' }],
        sm: ['14px', { lineHeight: '1.5' }],
        base: ['16px', { lineHeight: '1.6' }],
        lg: ['18px', { lineHeight: '1.5' }],
        xl: ['24px', { lineHeight: '1.3' }],
        '2xl': ['32px', { lineHeight: '1.2' }],
        '3xl': ['48px', { lineHeight: '1.1' }],
      },
      spacing: {
        /* {dynamic: extracted spacing scale} */
      },
      borderRadius: {
        sm: '4px',
        md: '8px',
        lg: '12px',
        xl: '16px',
      },
      boxShadow: {
        xs: '0 1px 2px rgba(0, 0, 0, 0.05)',
        sm: '0 1px 3px rgba(0, 0, 0, 0.1)',
        md: '0 4px 6px rgba(0, 0, 0, 0.1)',
        lg: '0 10px 15px rgba(0, 0, 0, 0.1)',
        xl: '0 20px 25px rgba(0, 0, 0, 0.15)',
      },
      transitionDuration: {
        fast: '100ms',
        normal: '200ms',
        slow: '300ms',
      },
      transitionTimingFunction: {
        DEFAULT: 'cubic-bezier(0.4, 0, 0.2, 1)',
        in: 'cubic-bezier(0.4, 0, 1, 1)',
        out: 'cubic-bezier(0, 0, 0.2, 1)',
      },
      zIndex: {
        dropdown: '1000',
        sticky: '1020',
        fixed: '1030',
        'modal-backdrop': '1040',
        modal: '1050',
        popover: '1060',
        tooltip: '1070',
      },
    },
  },
  plugins: [],
} satisfies Config
```

#### 7d. Reference Store Entry (if --save-ref)

Save to `project-refs/design/{name}.yaml`:

```yaml
# Reference Store Entry — {Name} Design System
ref_id: design-{name}
type: design-system
source: "{source}"
extracted_at: "{date}"
agent: ux-design-expert
task: extract-design-system
version: 1.0.0
confidence: "{level}"

tokens:
  colors: {count}
  typography: {count}
  spacing: {count}
  borders: {count}
  shadows: {count}
  motion: {count}

files:
  master: "{output}/MASTER.md"
  css: "{output}/tokens.css"
  tailwind: "{output}/tailwind.config.ts"

metadata:
  mode: "{mode}"
  depth: "{depth}"
  dark_mode: {boolean}
  components_found: {count}
  recommendations: {count}
```

---

### Step 8: Summary Report

**Goal:** Display extraction summary in console.

```
============================================================
  DESIGN SYSTEM EXTRACTION COMPLETE
============================================================

  Source:      {source}
  Mode:        {mode} ({auto-detected | user-specified})
  Depth:       {depth}
  Confidence:  {confidence_level}

  TOKENS EXTRACTED:
  ├── Colors:       {count} ({primitive} primitive + {semantic} semantic)
  ├── Typography:   {count} ({families} families, {sizes} sizes, {weights} weights)
  ├── Spacing:      {count} (base unit: {base}px)
  ├── Borders:      {count} ({radii} radii + {widths} widths)
  ├── Shadows:      {count} levels
  ├── Motion:       {count} ({durations} durations + {easings} easings)
  ├── Layout:       {count} ({breakpoints} breakpoints)
  └── Z-Index:      {count} layers
  ─────────────────────────
  Total:            {total_count} tokens

  COMPONENTS IDENTIFIED: {count}

  OUTPUT FILES:
  ├── {output}/MASTER.md              (comprehensive design system)
  ├── {output}/tokens.css             ({css_vars} CSS custom properties)
  ├── {output}/tailwind.config.ts     (theme configuration)
  {if save_ref}
  └── project-refs/design/{name}.yaml (reference store entry)
  {end}

  RECOMMENDATIONS: {count}
  {top 3 recommendations as bullets}

  Duration: {duration}
============================================================
```

---

## Graceful Degradation

| Tool Unavailable | Impact | Fallback Strategy |
|-----------------|--------|-------------------|
| Browser MCP (`mcp__claude-in-chrome__*`) | Cannot extract from live URLs via DOM | Offer user to provide screenshot → visual mode. Or suggest `--mode source` with manual HTML save |
| `gh` CLI | Cannot clone GitHub repos | Ask user to clone manually, then use local directory mode |
| Claude vision (Read tool for images) | Cannot do visual extraction | Source-code-only mode. Flag: "Visual analysis unavailable" |
| BM25 / design intelligence CSVs | Cannot enrich recommendations | Skip enrichment step, still produce MASTER.md + tokens. Add note: "Recommendations unavailable — run with design intelligence data for enriched output" |
| Write tool | Cannot write output files | Display all output content inline in chat. User can copy-paste |
| Curl / fetch | Cannot validate URL reachability | Attempt Browser MCP directly. If that fails too, ask user to verify URL |
| Temp directory creation | Cannot clone repos | Ask user for local clone path |

**Degradation priority:** Always produce at least MASTER.md with whatever data was extractable. Never fail silently — always report what was skipped and why.

---

## Error Handling

**Strategy:** graceful-degradation

### Common Errors

1. **Error:** URL Unreachable
   - **Cause:** Invalid URL, site down, DNS failure, firewall
   - **Detection:** HTTP status >= 400 or connection timeout
   - **Resolution:** Suggest checking URL, offer manual screenshot upload
   - **Recovery:**
     ```
     Source URL unreachable: {url}
     Options:
     1. Verify URL is correct and try again
     2. Provide a screenshot: *extract-design-system ./screenshot.png
     3. Save page HTML locally and extract: *extract-design-system ./saved-page/
     ```

2. **Error:** No Tokens Found
   - **Cause:** Source has no CSS custom properties, no theme config, minimal styling
   - **Detection:** Total extracted tokens = 0 after all extraction steps
   - **Resolution:** Suggest deeper scan or different mode
   - **Recovery:**
     ```
     No design tokens found in source.
     Suggestions:
     1. Try --depth deep for more thorough analysis
     2. Try --mode visual for screenshot-based extraction
     3. Check if the source uses inline styles or CSS-in-JS (harder to extract)
     ```

3. **Error:** Empty Repository
   - **Cause:** Repo is empty, private, or has no design-related files
   - **Detection:** No design indicator files found after clone
   - **Resolution:** Report findings, suggest alternatives
   - **Recovery:** Return minimal analysis with note about empty source

4. **Error:** Mixed Format Tokens
   - **Cause:** Source uses multiple color formats (hex, rgb, hsl, oklch mixed)
   - **Detection:** Multiple formats detected during normalization
   - **Resolution:** Normalize all to hex, preserve originals in metadata
   - **Recovery:** Warn about inconsistencies in MASTER.md recommendations

5. **Error:** CORS Blocking JavaScript Extraction
   - **Cause:** Cross-origin stylesheets cannot be read via JavaScript
   - **Detection:** `SecurityError` when iterating `sheet.cssRules`
   - **Resolution:** Degrade to visual mode for blocked stylesheets
   - **Recovery:** Note in summary: "X stylesheets blocked by CORS — visual fallback used"

6. **Error:** Large Repository Timeout
   - **Cause:** Repository too large for shallow clone in reasonable time
   - **Detection:** Clone exceeds 60 seconds
   - **Resolution:** Suggest sparse checkout or specific directory
   - **Recovery:**
     ```
     Repository is very large. Options:
     1. Provide path to specific design directory
     2. Clone locally and use: *extract-design-system ./local-clone/src/styles/
     ```

7. **Error:** Image Too Low Resolution
   - **Cause:** Screenshot/image too small for accurate extraction
   - **Detection:** Image dimensions < 800x600
   - **Resolution:** Request higher resolution image
   - **Recovery:** Extract what is possible, mark all values as `confidence: very-low`

8. **Error:** Output Directory Conflict
   - **Cause:** Output directory already contains design system files
   - **Detection:** Files exist at output path
   - **Resolution:** In Interactive mode: ask to overwrite. In YOLO mode: backup and overwrite
   - **Recovery:** Create backup at `{output}.backup-{timestamp}/`

---

## Interactive Elicitation Flow

When `mode=interactive` (default), the task uses structured elicitation:

### Checkpoint 1: Source Confirmation

```
Sati: I detected the following source:

  Type:  {sourceType}
  Source: {source}
  Mode:  {detectedMode} (auto-detected)
  Name:  {detectedName}

  Shall I proceed with these settings?
  [1] Yes, proceed with defaults
  [2] Change mode to: source | visual | hybrid
  [3] Change name to: ___
  [4] Change depth to: quick | standard | deep
```

### Checkpoint 2: Extraction Preview

```
Sati: Extraction complete. Here is a preview:

  Colors found:     {count}
  Fonts found:      {count}
  Spacing values:   {count}
  Components found: {count}

  Top 5 colors:
    #635BFF (used 47 times) — likely primary
    #0A2540 (used 32 times) — likely text/heading
    #F6F9FC (used 28 times) — likely background
    ...

  Proceed to output generation?
  [1] Yes, generate all outputs
  [2] Show more details before proceeding
  [3] Re-extract with different depth
```

### Checkpoint 3: Output Confirmation

```
Sati: Output files ready:

  design-system/MASTER.md          — 245 lines
  design-system/tokens.css         — 89 custom properties
  design-system/tailwind.config.ts — theme with 6 categories

  Write files?
  [1] Yes, write all files
  [2] Preview file contents first
  [3] Change output directory
  [4] Also save to Reference Store (--save-ref)
```

---

## Security Considerations

1. **URL Validation:**
   - Only allow `http://` and `https://` protocols
   - Block `file://`, `javascript:`, `data:` URLs
   - Sanitize URL before passing to Browser MCP

2. **Token Name Sanitization:**
   - Only allow: `a-z`, `A-Z`, `0-9`, `-`, `_`
   - Strip any other characters from generated token names
   - Prevent CSS injection via token values

3. **File Path Validation:**
   - Validate output directory is within project scope
   - Prevent path traversal (`../` sequences)
   - Do not write to system directories

4. **Repository Clone Safety:**
   - Always use `--depth 1` for shallow clones
   - Clone to temp directory, not project root
   - Clean up temp files after extraction
   - Do not execute any code from cloned repos

5. **Extracted Value Validation:**
   - Validate color hex format (3, 4, 6, or 8 hex digits)
   - Validate numeric values (spacing, sizes) are positive numbers
   - Sanitize font-family values (no executable content)
   - Strip HTML/script tags from any extracted text

---

## Tools

**External/shared resources used by this task:**

| Tool | Purpose | Tier | Required |
|------|---------|------|----------|
| Read | Read local files, images, PDFs | Tier 1 | YES |
| Write | Write output files | Tier 1 | YES |
| Glob | Find design-related files in directories | Tier 1 | YES |
| Grep | Search for patterns in CSS/config files | Tier 1 | YES |
| Bash | Run git clone, curl, file operations | Tier 1 | YES |
| Browser MCP | Navigate URLs, execute JS, take screenshots | Tier 2 | NO (graceful degradation) |
| `gh` CLI | Clone GitHub repositories | Tier 2 | NO (graceful degradation) |

---

## Scripts

**Agent-specific code for this task:**

- **Script:** execute-task.js
  - **Purpose:** Generic task execution wrapper
  - **Language:** JavaScript
  - **Location:** .lmas-core/scripts/execute-task.js

---

## Performance

**Expected Metrics:**

```yaml
duration_expected:
  quick: 30s-1min
  standard: 1-3 min
  deep: 3-8 min (multiple pages / large repos)
cost_estimated: $0.005-0.020
token_usage: ~1,500-3,000 tokens (standard), ~4,000-6,000 (deep)
```

**Optimization Notes:**
- Parallel extraction: run CSS custom property scan and computed style scan simultaneously
- Cap element sampling at 500 elements for live URL extraction
- Use shallow clone (`--depth 1`) for repository extraction
- Skip `node_modules/`, `dist/`, `.next/`, `build/`, `vendor/` directories
- Cache normalized color values to avoid redundant conversions
- For deep mode: limit additional pages to 5 maximum

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - extract-tokens (related task — token extraction from consolidated patterns)
  - absorb-reference (downstream — save to Reference Store)
tags:
  - design-system
  - extraction
  - reverse-engineering
  - tokens
  - css
  - tailwind
  - visual-analysis
updated_at: 2025-11-17
```

---

## Examples

### Example 1: Extract from Live URL (Hybrid Mode)

```bash
*extract-design-system https://stripe.com
```

**Output:**
```
Sati: Analyzing stripe.com in hybrid mode...

[Source Extraction — Browser MCP]
  Navigating to https://stripe.com...
  Executing CSS extraction script on 1 page...
  CSS custom properties: 47 tokens found
  Computed styles sampled from 412/2,847 elements
  Color palette: 12 unique colors
  Typography: 3 font families, 7 sizes, 5 weights
  Spacing: 8-point grid system detected (18 values)
  Shadows: 4 elevation levels
  Border radii: 5 values

[Visual Analysis — Screenshot]
  Taking full-page screenshot...
  Analyzing visual design...
  Dominant palette: #635BFF (primary), #0A2540 (dark), #F6F9FC (light)
  Font identified: system fonts (-apple-system, system-ui)
  Layout: 12-column grid, max-width 1080px

[Merge — Hybrid Results]
  Source code tokens: 47 (confidence: exact)
  Visual-only tokens: 3 (confidence: approximate)
  Conflicts resolved: 0

[Output Generated]
  design-system/MASTER.md              (comprehensive design system — 312 lines)
  design-system/tokens.css             (50 CSS custom properties)
  design-system/tailwind.config.ts     (theme configuration)

[Recommendations]
  - Your palette matches a "fintech" domain style (93% similarity)
  - Consider adding semantic error/warning/info colors (not found in source)
  - Font contrast ratio: heading weight 600 vs body 400 — good hierarchy
  - Spacing follows 8px grid — 2 outliers detected (18px, 22px)
  - WCAG: primary (#635BFF) on white = 4.2:1 (AA Large only)

  Duration: 1m 42s
```

### Example 2: Extract from Local Codebase (Source Mode, Deep)

```bash
*extract-design-system ./src --depth deep --save-ref --name my-app
```

**Output:**
```
Sati: Deep scanning local codebase at ./src...

[File Discovery]
  Scanning 1,247 files across 89 directories...
  Found: tailwind.config.ts, src/styles/globals.css, src/lib/theme.ts
  Framework detected: Tailwind CSS v3.4, Next.js 14
  Skipped: node_modules/ (23,456 files), .next/ (891 files)

[Source Extraction]
  tailwind.config.ts: 34 theme tokens extracted
  globals.css: 12 CSS custom properties extracted
  theme.ts: 8 color constants extracted
  Component inventory: 47 components in src/components/

[Normalization]
  Merged 54 tokens (6 near-duplicates removed)
  All colors normalized to hex
  Spacing normalized to px (base: 16px from tailwind)

[Output Generated]
  design-system/MASTER.md
  design-system/tokens.css
  design-system/tailwind.config.ts
  project-refs/design/my-app.yaml (Reference Store)

  Duration: 2m 15s
```

### Example 3: Extract from Screenshot (Visual Mode)

```bash
*extract-design-system ./designs/homepage.png --mode visual
```

**Output:**
```
Sati: Visual analysis mode — reading image...

  Note: All values are APPROXIMATE (vision-based extraction).
  For exact values, provide source code or a live URL.

[Visual Analysis]
  Image: 1920x1080px, homepage design mockup
  Colors identified: 8 (confidence: approximate)
  Typography: 2 font families detected (approximate identification)
  Spacing: 8px grid likely (confidence: medium)
  Components: 6 patterns identified (buttons, cards, nav, hero, footer, form)

[Output Generated]
  design-system/MASTER.md              (all values marked approximate)
  design-system/tokens.css             (23 CSS custom properties)
  design-system/tailwind.config.ts     (theme configuration)

[Recommendations]
  - Font appears to be Inter or similar geometric sans-serif
  - Primary color approximately #3B82F6 (blue-500 range)
  - For exact values, extract from source code or Figma

  Duration: 45s
```

### Example 4: Extract from GitHub Repository

```bash
*extract-design-system https://github.com/shadcn/ui --depth standard
```

**Output:**
```
Sati: Cloning shadcn/ui (shallow)...

[Repository Analysis]
  Framework: Tailwind CSS, Radix UI, TypeScript
  Design tokens in: tailwind.config.ts, src/styles/globals.css
  Component count: 40+ (button, card, dialog, dropdown, input, ...)
  Token format: CSS custom properties + Tailwind theme

[Source Extraction]
  tailwind.config.ts: 52 theme tokens
  globals.css: 38 CSS custom properties (light + dark mode)
  Total unique tokens: 78

[Output Generated]
  design-system/MASTER.md
  design-system/tokens.css
  design-system/tailwind.config.ts

  Duration: 1m 08s
```

---

## Integration with Other Tasks

This task integrates with the LMAS design pipeline:

| Task | Relationship | Direction |
|------|-------------|-----------|
| `extract-tokens` | Downstream — can feed extracted tokens into token refinement | This task → extract-tokens |
| `absorb-reference` | Downstream — save extraction to Reference Store | This task → absorb-reference |
| `audit-tailwind-config` | Downstream — audit generated tailwind config | This task → audit-tailwind-config |
| `build-component` | Downstream — build components using extracted tokens | This task → build-component |
| `generate-ai-frontend-prompt` | Downstream — generate prompts using extracted design system | This task → generate-ai-frontend-prompt |
| `analyze-brownfield` | Upstream — understand codebase before extracting | analyze-brownfield → This task |
| `consolidate-patterns` | Related — extract from already consolidated data | Parallel |

---

## Notes

- **Constitutional compliance:** All extracted tokens trace to source data (Article IV — No Invention). Visual-mode values are always marked as approximate.
- **Idempotent:** Running the same extraction twice with the same source and settings produces identical output. Timestamps in metadata will differ.
- **Non-destructive:** This task only reads from sources and writes to the output directory. It never modifies source files.
- **Framework-agnostic:** Works with any CSS framework (Tailwind, Bootstrap, Material, Chakra, custom) or no framework at all.
- **Backward compatible:** Output tokens.css and tailwind.config.ts are standard formats consumable by any toolchain.
- **Dark mode:** When `--dark-mode true` (default), attempts to extract dark mode tokens. For live URLs, checks for `prefers-color-scheme` media queries and `[data-theme]` attributes. For source code, looks for dark mode config in Tailwind or CSS.

---

## Handoff

```yaml
next_agent: "@dev"
next_command: "*build-component {component-name}"
condition: Design system extracted and tokens available
alternatives:
  - agent: "@architect"
    command: "*review-design-system"
    condition: Need architectural review of extracted system
  - agent: "@ux-design-expert"
    command: "*extract-tokens"
    condition: Need further token refinement from consolidated patterns
  - agent: "@qa"
    command: "*review"
    condition: Quality gate for design system accuracy
```
