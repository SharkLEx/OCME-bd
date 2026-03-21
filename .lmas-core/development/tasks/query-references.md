# query-references

## Metadata

- **Task ID:** query-references
- **Version:** 1.0.0
- **Owner:** lmas-master (Morpheus)
- **Consumers:** All agents
- **elicit:** false
- **Category:** reference-management

---

## Purpose

Query the project's Reference Store for previously absorbed references. Supports listing, searching, viewing details, deleting, and exporting references across all domains.

This is the read-side counterpart to `absorb-reference.md`. While `*absorb` writes references into the store, `*refs` reads and manages them.

---

## Inputs

| Input | Required | Type | Description |
|-------|----------|------|-------------|
| domain | NO | enum | Filter by domain: `design` \| `architecture` \| `content` \| `competitive` |
| --search | NO | string | Search query — BM25 fuzzy search across all `search_text` fields |
| --tags | NO | string | Filter by tags (comma-separated, AND logic — all tags must match) |
| --list | NO | flag | List all references in domain (or all domains if domain omitted) |
| --detail | NO | string | Show full reference detail for a specific reference by name |
| --delete | NO | string | Delete a reference by name (requires user confirmation) |
| --export | NO | string | Export references as JSON. Value: `"all"` or a domain name |
| --since | NO | string | Filter by absorption date (ISO 8601 date, e.g., `"2026-03-01"`) |
| --expired | NO | flag | Show only references past their TTL expiry date |

---

## Pre-conditions

1. The `project-refs/` directory exists with at least one domain subdirectory
2. At least one `_index.yaml` file exists in a domain subdirectory
3. For `--delete`: the user must confirm the deletion

---

## Execution Flow

### Overview Mode (`*refs` with no arguments)

When invoked with no arguments, show a summary of the entire Reference Store.

1. **Scan** `project-refs/` for domain subdirectories
2. **Count** entries in each `_index.yaml`
3. **Display overview:**

```
📚 Reference Store — Overview

| Domínio       | Referências | Última absorção    |
|---------------|-------------|--------------------|
| design        | 12          | 2026-03-17         |
| architecture  | 5           | 2026-03-15         |
| content       | 3           | 2026-03-10         |
| competitive   | 7           | 2026-03-16         |
| **Total**     | **27**      |                    |

Comandos:
  *refs design --list          — Listar referências de design
  *refs --search "dark mode"   — Buscar em todos os domínios
  *refs --detail "Linear App"  — Ver detalhes de uma referência
```

### List Mode (`*refs {domain} --list`)

List all references in a specific domain, or all domains if domain is omitted.

1. **Read** `project-refs/{domain}/_index.yaml`
   - If no domain specified, read all `_index.yaml` files
2. **Apply filters:**
   - If `--tags` provided: filter entries where ALL specified tags are present
   - If `--since` provided: filter entries where `absorbed_at >= since`
   - If `--expired` provided: filter entries where `ttl_days` is set AND current date > `absorbed_at + ttl_days`
3. **Sort** by `absorbed_at` (newest first)
4. **Display table:**

```
📋 Referências — Design (12 total)

| # | Nome                          | Tags                        | Absorvido em  | Fonte (resumo)           |
|---|-------------------------------|-----------------------------|---------------|--------------------------|
| 1 | Linear App                    | saas, minimal, dark-mode    | 2026-03-17    | linear.app               |
| 2 | Stripe Dashboard              | saas, dashboard, clean      | 2026-03-16    | dashboard.stripe.com     |
| 3 | Vercel Design System          | design-system, react        | 2026-03-15    | github.com/vercel/geist  |
| ...                                                                                                      |

Filtros ativos: nenhum
Use *refs design --list --tags "saas" para filtrar por tags.
```

**When listing all domains:**
- Group by domain with a header for each
- Show domain totals
- Limit to 10 entries per domain in summary view

### Search Mode (`*refs --search {query}`)

Full-text fuzzy search across all (or filtered) references.

1. **Load indices:**
   - If domain specified: load only `project-refs/{domain}/_index.yaml`
   - If no domain: load ALL `_index.yaml` files across all domains
2. **BM25 search:**
   - Tokenize query into terms
   - Search each entry's `search_text` field
   - Score using BM25 ranking:
     - Term frequency (TF): how often query terms appear in `search_text`
     - Inverse document frequency (IDF): rarer terms score higher
     - Document length normalization: shorter entries aren't penalized
3. **Apply additional filters:**
   - `--tags`: intersect BM25 results with tag filter
   - `--since`: intersect with date filter
4. **Rank and display** (top 10 results):

```
🔍 Busca: "dark mode saas" (27 referências pesquisadas)

| # | Score | Domínio      | Nome                    | Tags                     |
|---|-------|--------------|-------------------------|--------------------------|
| 1 | 0.92  | design       | Linear App              | saas, minimal, dark-mode |
| 2 | 0.78  | design       | Notion Dark Theme       | saas, dark-mode, notes   |
| 3 | 0.65  | competitive  | Dark Mode SaaS Trends   | dark-mode, market, 2026  |

Use *refs --detail "Linear App" para ver detalhes completos.
```

**BM25 implementation notes:**
- Since the Reference Store is typically small (< 1000 entries), a simple in-memory BM25 is sufficient
- Parameters: k1=1.5, b=0.75 (standard BM25 tuning)
- Pre-tokenize search_text at index time (split on spaces, lowercase, remove punctuation)
- Query is tokenized the same way

### Detail Mode (`*refs --detail {name}`)

Show the complete reference for a specific entry.

1. **Find reference** by name:
   - Search all `_index.yaml` files for exact name match (case-insensitive)
   - If no exact match: try fuzzy match (Levenshtein distance <= 3)
   - If fuzzy match found: ask user to confirm
2. **Read** the full YAML reference file
3. **Display formatted output:**

```
📄 Referência: Linear App

┌─────────────────────────────────────────────────┐
│ Domínio:     design                             │
│ Fonte:       https://linear.app                 │
│ Absorvido:   2026-03-17 14:30 por @lmas-master  │
│ Confiança:   90%                                │
│ Tags:        saas, minimal, dark-mode           │
│ Arquivo:     project-refs/design/linear-app.yaml│
└─────────────────────────────────────────────────┘

🎨 Tokens — Cores
  primary:    #5E6AD2  ██
  secondary:  #26273B  ██
  accent:     #8A8F98  ██
  background: #111111  ██
  surface:    #1A1A2E  ██
  text.primary:   #F2F2F2
  text.secondary: #8A8F98
  text.muted:     #505050

🔤 Tokens — Tipografia
  heading: Inter
  body:    Inter
  code:    JetBrains Mono
  scale:   13px → 14px → 16px → 20px → 24px

📐 Tokens — Espaçamento
  scale: 4px → 8px → 12px → 16px → 24px → 32px → 48px

🧩 Padrões (2)
  1. Command palette — Cmd+K modal for keyboard-driven navigation
  2. Sidebar navigation — Collapsible sidebar with hierarchy

📸 Screenshots (1)
  project-refs/design/screenshots/linear-app.png

🔗 Referências similares
  - Stripe Dashboard (similarity: 0.72)
  - Notion Dark Theme (similarity: 0.65)
```

**For non-design domains, adapt the display:**
- Architecture: show patterns, technologies, service diagrams
- Content: show brand voice attributes, content patterns
- Competitive: show pricing, features, market positioning

### Delete Mode (`*refs --delete {name}`)

Remove a reference from the store.

1. **Find reference** by name (same logic as Detail Mode)
2. **Show reference summary** and ask for confirmation:
   ```
   ⚠️ Deletar referência?

   Nome:     {name}
   Domínio:  {domain}
   Arquivo:  project-refs/{domain}/{slug}.yaml
   Tags:     {tags}

   Esta ação não pode ser desfeita. Confirmar? (s/n)
   ```
3. **On confirmation:**
   - Delete the YAML reference file
   - Delete associated screenshots (if any)
   - Remove entry from `_index.yaml`
   - Rewrite `_index.yaml` without the deleted entry
4. **Report:**
   ```
   ✅ Referência "{name}" deletada do domínio {domain}.
   ```

### Export Mode (`*refs --export {scope}`)

Export references to a portable JSON format.

1. **Determine scope:**
   - `--export all`: export all references from all domains
   - `--export {domain}`: export all references from a specific domain
2. **Load references:**
   - Read all YAML reference files in scope
   - Parse into structured objects
3. **Build export JSON:**
   ```json
   {
     "exported_at": "2026-03-17T16:00:00Z",
     "store_version": "1.0.0",
     "total_references": 27,
     "domains": {
       "design": {
         "count": 12,
         "references": [
           {
             "name": "Linear App",
             "source": "https://linear.app",
             "domain": "design",
             "absorbed_at": "2026-03-17T14:30:00Z",
             "tags": ["saas", "minimal", "dark-mode"],
             "tokens": { "..." },
             "patterns": ["..."]
           }
         ]
       }
     }
   }
   ```
4. **Write export file:**
   - Path: `project-refs/exports/export-{scope}-{date}.json`
   - Create `project-refs/exports/` if it doesn't exist
5. **Report:**
   ```
   ✅ Exportação concluída!

   📁 Arquivo: project-refs/exports/export-all-2026-03-17.json
   📊 Referências: 27 em 4 domínios
   📦 Tamanho: 45 KB
   ```

---

## Output Formats

### Table Format (List and Search modes)

Used for multi-result displays. Columns auto-adjust width based on content. Maximum 10 results per page in search mode, unlimited in list mode.

### Detail Format (Detail mode)

Full structured display with sections for each data category (tokens, patterns, metadata). Uses box-drawing characters for visual structure.

### JSON Format (Export mode)

Standard JSON with 2-space indentation. All datetime values in ISO 8601. References nested by domain.

---

## Error Handling

| Error | Handling | User Message |
|-------|----------|-------------|
| No `project-refs/` directory | Suggest running `*absorb` first | "Nenhuma referência encontrada. Use `*absorb {source}` para começar." |
| Domain not found | List available domains | "Domínio '{domain}' não existe. Domínios disponíveis: {list}" |
| Reference not found (exact) | Try fuzzy match | "Referência '{name}' não encontrada. Você quis dizer '{fuzzy_match}'?" |
| Reference not found (no fuzzy match) | Suggest search | "Referência '{name}' não encontrada. Use `*refs --search \"{query}\"` para buscar." |
| Empty search results | Suggest broader query | "Nenhum resultado para '{query}'. Tente termos mais genéricos ou remova filtros." |
| Corrupted index file | Rebuild index | "Índice corrompido. Reconstruindo a partir dos arquivos existentes..." |
| Empty domain (no references) | Inform user | "Domínio '{domain}' existe mas está vazio. Use `*absorb` para adicionar referências." |
| Export write failure | Error with path | "Falha ao escrever exportação. Verifique permissões em project-refs/exports/." |

---

## Cross-Agent Usage

Any agent can query the Reference Store. Common use cases:

| Agent | Typical Query | Purpose |
|-------|--------------|---------|
| @dev | `*refs design --detail "{name}"` | Get design tokens for implementation |
| @architect | `*refs architecture --search "microservice"` | Find architecture patterns |
| @ux-design-expert | `*refs design --list --tags "saas"` | Browse design references for inspiration |
| @analyst | `*refs competitive --list` | Review competitor analysis |
| @po | `*refs --search "{feature}"` | Check if similar patterns exist |
| @qa | `*refs design --detail "{name}"` | Validate implementation against reference tokens |

**Agent delegation rule:** Any agent can READ references directly. Only @lmas-master can WRITE (absorb/delete) references. Other agents must delegate writes via `@lmas-master *absorb`.

---

## Constitutional Compliance

- **Article I (CLI First):** All query operations are CLI-native. No UI dependency.
- **Article II (Agent Authority):** Read access is open to all agents. Write/delete restricted to @lmas-master.
- **Article IV (No Invention):** Query results display only stored data. Never fabricate or interpolate missing fields.

---

## Related Tasks

- `absorb-reference.md` — Absorb new references into the store (`*absorb` command)
- `extract-tokens.md` — Standalone design token extraction
- `learn-patterns.md` — Pattern learning and recognition pipeline
- `shard-doc.md` — Document sharding (can shard large references)
