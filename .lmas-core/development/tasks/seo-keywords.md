# SEO Keyword Research — Worker Task

> **Owner:** @seo (Cypher) → Worker: Keyword Miner
> **Trigger:** `*keywords {topic|url}`
> **Type:** Worker — standalone execution

---

## Purpose

Perform keyword research for a given topic or URL. Identifies keyword opportunities, search intent, clusters, and provides actionable recommendations for content strategy. Works with or without MCP data tools.

## Prerequisites

- Topic or URL provided by user
- Optional: MCP tools (DataForSEO, Ahrefs, Semrush) for live volume/difficulty data
- Reference: Industry verticals from `seo-references.md`

## Execution Modes

### Mode A: With MCP Data Tools (Rich Data)
If DataForSEO, Ahrefs, or Semrush MCP is available:
1. Query live keyword data (volume, difficulty, CPC, trends)
2. Pull competitor keyword gaps
3. Get SERP feature data
4. Enrich with real metrics

### Mode B: Without MCP Tools (Analysis-Based)
If no data MCP available:
1. Analyze existing page content for keyword signals
2. Use semantic analysis to identify related topics
3. Infer search intent from content structure
4. Provide qualitative recommendations based on SEO knowledge
5. Suggest keywords based on industry patterns and best practices

**Note:** Always inform user which mode is active and recommend MCP setup for richer data.

## Research Framework

### 1. Seed Keyword Expansion

From the input topic/URL, generate:

| Type | Description | Example |
|------|-------------|---------|
| **Head terms** | 1-2 words, high volume, high competition | "SEO tools" |
| **Body terms** | 2-3 words, medium volume, moderate competition | "best SEO audit tools" |
| **Long-tail** | 4+ words, lower volume, lower competition | "best free SEO audit tools for small business" |
| **Questions** | How/what/why/when queries | "how to do an SEO audit" |
| **Comparison** | X vs Y, alternatives, reviews | "Ahrefs vs Semrush" |
| **Commercial** | Buy/pricing/coupon/review intent | "SEO tool pricing 2026" |

### 2. Search Intent Classification

Classify each keyword:

| Intent | Description | Content Type |
|--------|-------------|-------------|
| **Informational** | Learning, researching | Blog post, guide, how-to |
| **Navigational** | Finding specific site/page | Brand page, product page |
| **Commercial** | Comparing, evaluating | Comparison, review, listicle |
| **Transactional** | Ready to buy/act | Product page, pricing, sign-up |

### 3. Keyword Clustering

Group keywords into topical clusters:

```
Pillar Topic: {main topic}
├── Cluster 1: {subtopic}
│   ├── Keyword A (volume, difficulty, intent)
│   ├── Keyword B
│   └── Keyword C
├── Cluster 2: {subtopic}
│   ├── Keyword D
│   └── Keyword E
└── Cluster 3: {subtopic}
    ├── Keyword F
    └── Keyword G
```

### 4. Content Gap Analysis (if URL provided)

Compare current content against keyword opportunities:
- **Covered:** Keywords the page already targets well
- **Partially covered:** Keywords mentioned but not optimized
- **Missing:** High-opportunity keywords not addressed
- **Cannibalization risk:** Multiple pages targeting same keyword

### 5. SERP Feature Opportunities

Identify opportunities for:
- Featured snippets (paragraph, list, table)
- People Also Ask (PAA) questions
- Video results
- Image pack
- Knowledge panel
- AI Overviews (GEO relevance)

## Output Format

```markdown
## 🔍 Keyword Research — {topic}

**Mode:** {With MCP Data | Analysis-Based}
**Industry:** {detected or inferred}
**Total Keywords Identified:** {count}

### Top Keyword Opportunities

| # | Keyword | Volume | Difficulty | Intent | Priority |
|---|---------|--------|------------|--------|----------|
| 1 | ... | ... | ... | ... | High |

### Keyword Clusters

#### Cluster 1: {subtopic}
| Keyword | Volume | Difficulty | Intent | Content Type |
|---------|--------|------------|--------|-------------|

#### Cluster 2: {subtopic}
...

### Search Intent Distribution
| Intent | % of Keywords | Strategy |
|--------|--------------|----------|
| Informational | X% | Blog posts, guides |
| Commercial | X% | Comparison pages, reviews |
| Transactional | X% | Product/pricing pages |

### Content Recommendations
| # | Action | Target Keyword | Content Type | Priority |
|---|--------|---------------|-------------|----------|

### SERP Feature Opportunities
| Keyword | Feature | Strategy |
|---------|---------|----------|

### Next Steps
- Delegate to @content-strategist for editorial calendar
- Delegate to @copywriter for content creation
- Delegate to @traffic-manager for paid search opportunities
```

## Integration Points

| Agent | What to Send | Command |
|-------|-------------|---------|
| @content-strategist | Keyword clusters + content recommendations | Input for editorial calendar |
| @copywriter | Target keywords + intent + content type | Input for `*write-copy` |
| @traffic-manager | Commercial/transactional keywords with CPC | Input for paid campaigns |
| @seo (self) | URLs of created content | `*content` for E-E-A-T validation |
