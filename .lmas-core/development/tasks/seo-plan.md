# SEO Strategic Plan — Worker Task

> **Owner:** @seo (Cypher) → Worker: Strategy Architect
> **Trigger:** `*plan {industry}`
> **Type:** Worker — standalone execution with elicitation

---

## Purpose

Create a comprehensive SEO strategic plan tailored to a specific industry vertical. Includes site architecture, content strategy, technical foundation, and a phased implementation roadmap.

## Prerequisites

- Industry vertical: `saas | ecommerce | local | publisher | agency | generic`
- Optional: Target URL for current-state analysis
- Reference: Industry defaults from `seo-references.md`

## Elicitation (Required)

`elicit: true`

Before generating the plan, gather:

```
1. **Industry:** {saas|ecommerce|local|publisher|agency}
2. **Business Name:** {name}
3. **Target Audience:** {who are the customers}
4. **Current Website:** {URL or "new site"}
5. **Top 3 Competitors:** {URLs}
6. **Primary Goal:** {traffic|leads|sales|authority|local visibility}
7. **Geographic Focus:** {global|national|regional|local + cities}
8. **Budget Level:** {bootstrap|moderate|aggressive}
9. **Timeline:** {3 months|6 months|12 months}
```

## Plan Structure

### Phase 1: Foundation (Month 1-2)

#### Technical Setup
| Task | Priority | Details |
|------|----------|---------|
| SSL/HTTPS | Critical | Full site HTTPS with proper redirects |
| robots.txt | Critical | Proper allow/disallow rules, AI crawlers allowed |
| XML Sitemap | Critical | Auto-generated, submitted to GSC |
| Google Search Console | Critical | Verified, sitemap submitted |
| Core Web Vitals | High | Meet all "Good" thresholds |
| Schema markup | High | Organization + industry-specific types |
| llms.txt | Medium | AI search readiness |

#### Site Architecture
Provide industry-specific URL hierarchy:

**SaaS:**
```
/                     → Homepage (Organization, WebSite)
├── /features/        → Feature pages (SoftwareApplication)
├── /pricing/         → Pricing page
├── /integrations/    → Integration pages
├── /blog/            → Content hub (Article, BlogPosting)
├── /docs/            → Documentation
├── /case-studies/    → Social proof
└── /about/           → Company info
```

**E-commerce:**
```
/                     → Homepage
├── /products/        → Category pages (ItemList)
│   └── /products/x/  → Product pages (Product, Offer)
├── /collections/     → Curated collections
├── /blog/            → Content marketing
├── /reviews/         → Customer reviews (Review)
└── /about/           → Brand story
```

**Local Business:**
```
/                     → Homepage (LocalBusiness)
├── /services/        → Service pages (Service)
├── /areas/           → Service area pages (⚠️ max 30-50)
├── /blog/            → Local content
├── /reviews/         → Testimonials
├── /contact/         → Contact + map
└── /about/           → Team, history
```

**Publisher:**
```
/                     → Homepage (WebSite, Organization)
├── /category/        → Topic categories
│   └── /category/x/  → Articles (Article, BlogPosting)
├── /author/          → Author pages (Person, ProfilePage)
├── /topic/           → Pillar pages
└── /about/           → Editorial standards
```

**Agency:**
```
/                     → Homepage (Organization)
├── /services/        → Service pages (Service)
├── /case-studies/    → Portfolio
├── /blog/            → Thought leadership
├── /team/            → Team profiles
└── /contact/         → Lead generation
```

### Phase 2: Content Expansion (Month 2-4)

| Activity | Details |
|----------|---------|
| **Keyword research** | Pillar + cluster strategy via `*keywords` |
| **Content calendar** | Monthly publishing plan (delegate to @content-strategist) |
| **Pillar content** | 4-6 comprehensive guides (2000+ words, E-E-A-T optimized) |
| **Cluster content** | 3-5 supporting articles per pillar (1500+ words) |
| **Internal linking** | Hub & spoke model, no orphan pages |
| **Schema expansion** | Article schema, FAQ schema (where applicable), BreadcrumbList |

### Phase 3: Scale & Authority (Month 4-8)

| Activity | Details |
|----------|---------|
| **Link building** | Guest posts, HARO, industry partnerships |
| **Content refresh** | Update existing content with new data, expand thin pages |
| **Technical audit** | Monthly `*audit` to catch regressions |
| **GEO optimization** | `*geo` analysis, llms.txt, citability improvements |
| **Competitor monitoring** | Monthly `*competitor` analysis |

### Phase 4: Dominate & Maintain (Month 8+)

| Activity | Details |
|----------|---------|
| **Content velocity** | Increase publishing frequency based on what works |
| **Advanced schema** | Industry-specific advanced types |
| **International** | hreflang if applicable |
| **Performance tuning** | CWV optimization for edge cases |
| **Reporting** | Monthly SEO Health Score tracking |

## Output Format

```markdown
# 🔍 SEO Strategic Plan — {business_name}

**Industry:** {type}
**Goal:** {primary goal}
**Timeline:** {X months}
**Geographic Focus:** {scope}

## Executive Summary
{2-3 paragraph overview of the strategy}

## Site Architecture
{Industry-specific URL tree with schema types}

## Phase 1: Foundation (Month 1-2)
### Technical Checklist
{prioritized technical tasks}
### Schema Implementation
{recommended schema types with templates}

## Phase 2: Content Expansion (Month 2-4)
### Keyword Strategy
{pillar/cluster overview — delegate to *keywords for deep research}
### Content Calendar Framework
{monthly publishing targets and content types}

## Phase 3: Scale & Authority (Month 4-8)
{link building, content refresh, competitor monitoring}

## Phase 4: Dominate & Maintain (Month 8+)
{velocity, advanced optimization, reporting}

## KPIs to Track
| Metric | Baseline | 3-Month Target | 6-Month Target | 12-Month Target |
|--------|----------|---------------|----------------|-----------------|

## Delegation Map
| Task | Agent | When |
|------|-------|------|
| Keyword research | @seo `*keywords` | Phase 2 |
| Content creation | @copywriter `*write-copy` | Phase 2+ |
| Content calendar | @content-strategist | Phase 2 |
| Technical monitoring | @seo `*audit` | Monthly |
| Content review | @content-reviewer | Per piece |
| Campaign approval | @marketing-chief | Per campaign |
```

## Integration Points

| Phase | Agent | Action |
|-------|-------|--------|
| Phase 1 | @devops | Technical implementation (SSL, server config) |
| Phase 2 | @content-strategist | Editorial calendar from keyword data |
| Phase 2 | @copywriter | Content creation from keyword briefs |
| Phase 3 | @content-reviewer | Quality gate for all content |
| Phase 3 | @marketing-chief | Strategy approval for scaling |
| Ongoing | @traffic-manager | Paid search to complement organic |
