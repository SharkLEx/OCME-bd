# SEO Full Audit — Orchestrator Task

> **Owner:** @seo (Cypher)
> **Trigger:** `*audit {url}`
> **Type:** Orchestrator — spawns 5 parallel workers, aggregates into SEO Health Score

---

## Purpose

Execute a comprehensive SEO audit of a website by orchestrating 5 specialized workers in parallel, then aggregating results into a unified SEO Health Score (0-100) with a prioritized action plan.

## Prerequisites

- Target URL provided by user
- WebFetch tool available for page fetching
- Reference data: `.lmas-core/development/data/seo-references.md` (load on-demand)

## Execution Flow

### Phase 1: Discovery (Sequential)

1. **Fetch homepage** — Use WebFetch to get the target URL
2. **Detect industry** — Analyze page content for business type signals:
   - SaaS: /pricing, /features, "free trial", "sign up"
   - E-commerce: /products, /cart, "add to cart", product schema
   - Local: phone, address, service area, Maps embed
   - Publisher: /blog, article schema, author pages
   - Agency: /case-studies, /portfolio, client logos
3. **Check robots.txt** — Fetch `{domain}/robots.txt` to understand crawl rules
4. **Check sitemap** — Fetch `{domain}/sitemap.xml` to understand site structure
5. **Load references** — Load `seo-references.md` for thresholds and scoring weights

### Phase 2: Parallel Analysis (5 Workers via Agent tool)

Spawn 5 agents in PARALLEL using the Agent tool. Each agent receives:
- The fetched page HTML content
- The industry type detected
- Relevant sections from seo-references.md

| Worker | Task File | Agent Prompt Focus |
|--------|-----------|-------------------|
| Technical Eye | `seo-technical.md` | Crawlability, indexability, security, URLs, rendering |
| Content Judge | `seo-content.md` | E-E-A-T scoring, content quality, thin content |
| Schema Validator | `seo-schema.md` | JSON-LD detection, validation, recommendations |
| Performance Gauge | `seo-performance.md` | Core Web Vitals analysis, LCP/INP/CLS |
| GEO Sentinel | `seo-geo.md` | AI search readiness, citability, llms.txt |

**Agent spawn pattern:**
```
Agent tool (subagent_type: general-purpose) × 5 in parallel
Each receives: URL, HTML content, industry type, reference thresholds
Each returns: Structured findings with scores per dimension
```

### Phase 3: Aggregation (Sequential)

1. **Collect worker results** — Gather all 5 worker outputs
2. **Calculate SEO Health Score** using weights from seo-references.md:
   - Technical SEO: 22%
   - Content Quality (E-E-A-T): 23%
   - On-Page SEO: 20%
   - Schema/Structured Data: 10%
   - Performance (CWV): 10%
   - AI Search Readiness (GEO): 10%
   - Images: 5%
3. **Classify findings** by priority: Critical > High > Medium > Low
4. **Generate report**

### Phase 4: Report Output

Present the audit report in this structure:

```markdown
# 🔍 SEO Audit Report — {domain}

**Industry:** {detected type}
**Date:** {current date}
**SEO Health Score: {score}/100** {color emoji}

## Score Breakdown

| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Technical SEO | X/100 | 22% | X |
| Content Quality | X/100 | 23% | X |
| On-Page SEO | X/100 | 20% | X |
| Schema | X/100 | 10% | X |
| Performance | X/100 | 10% | X |
| AI Search | X/100 | 10% | X |
| Images | X/100 | 5% | X |

## 🔴 Critical Findings (Immediate Action)
{findings}

## 🟠 High Priority (This Week)
{findings}

## 🟡 Medium Priority (This Month)
{findings}

## 🟢 Low Priority (Backlog)
{findings}

## Action Plan
| # | Action | Priority | Impact | Effort |
|---|--------|----------|--------|--------|
| 1 | ... | Critical | High | Low |

## Next Steps
- Recommended follow-up commands for deeper analysis
- Delegation suggestions to other agents (@copywriter, @content-strategist)
```

## Error Handling

- If WebFetch fails: Report the error, suggest checking URL accessibility
- If a worker fails: Continue with remaining workers, note gap in report
- If site blocks crawling: Report robots.txt restrictions, analyze what's accessible
- If no sitemap found: Note as finding, proceed with homepage analysis only

## Elicitation

- `elicit: false` — This task runs autonomously after receiving the URL
- If industry detection confidence is LOW (<60%), ask user to confirm before proceeding
