# SEO Schema Markup Analysis — Worker Task

> **Owner:** @seo (Cypher) → Worker: Schema Validator
> **Trigger:** `*schema {url}` or spawned by `*audit`
> **Type:** Worker — standalone or parallel execution

---

## Purpose

Detect, validate, and recommend schema markup (structured data) for a web page. Covers JSON-LD, Microdata, and RDFa with awareness of Google's current support and deprecations.

## Prerequisites

- Page HTML content (provided by orchestrator or fetched directly)
- Reference: Schema types and deprecations from `seo-references.md`

## Analysis Steps

### 1. Detection

Scan page HTML for structured data:

| Format | Detection Method | Priority |
|--------|-----------------|----------|
| **JSON-LD** | `<script type="application/ld+json">` blocks | Preferred |
| **Microdata** | `itemscope`, `itemtype`, `itemprop` attributes | Acceptable |
| **RDFa** | `typeof`, `property`, `vocab` attributes | Acceptable |

Extract all found schema blocks for analysis.

### 2. Validation

For each schema block found:

| Check | Rule | Severity |
|-------|------|----------|
| Valid JSON | Parse without errors | Critical |
| @context | Must be `https://schema.org` (not http) | High |
| @type | Must be a valid schema.org type | Critical |
| Required fields | All required properties populated | High |
| No placeholders | No "Lorem ipsum", "TODO", "example" values | Critical |
| URL format | All URLs must be absolute (not relative) | Medium |
| Date format | ISO 8601 for datePublished, dateModified | Medium |
| Image URLs | Must resolve to actual images | Medium |
| Nesting | Properly nested types (e.g., Organization > Address) | Low |

### 3. Deprecation Check

Flag any deprecated or restricted types:

| Type | Status | Action |
|------|--------|--------|
| **HowTo** | ❌ DEPRECATED (Sep 2023) | Remove — Google no longer shows rich results |
| **SpecialAnnouncement** | ❌ DEPRECATED (Jul 2025) | Remove — COVID-era type |
| **FAQPage** | ⚠️ RESTRICTED (Aug 2023) | Keep for structure, but rich results only for gov/health sites |

### 4. Coverage Analysis

Compare detected schema against recommended types for the page:

| Page Type | Expected Schema | Present? |
|-----------|----------------|----------|
| Homepage | Organization, WebSite, SearchAction | ✅/❌ |
| Product | Product, Offer, AggregateRating | ✅/❌ |
| Article | Article/BlogPosting, Author, BreadcrumbList | ✅/❌ |
| Local | LocalBusiness, PostalAddress, GeoCoordinates | ✅/❌ |
| Service | Service, Offer, AreaServed | ✅/❌ |

### 5. Generation Recommendations

For missing but recommended schema types, provide:
- Complete JSON-LD template with placeholder values
- Instructions for populating real data
- Priority level (Critical/High/Medium/Low)

## Output Format

```markdown
## Schema Markup Analysis — {url}

**Schema Score: {score}/100**
**Formats Found:** {JSON-LD, Microdata, RDFa, or None}
**Total Blocks:** {count}

### Detected Schema

| # | Type | Format | Valid | Issues |
|---|------|--------|-------|--------|
| 1 | Organization | JSON-LD | ✅ | None |
| 2 | Article | JSON-LD | ⚠️ | Missing author |

### Validation Issues

| # | Type | Issue | Severity | Fix |
|---|------|-------|----------|-----|

### Deprecation Warnings

| Type | Status | Action Required |
|------|--------|----------------|

### Missing Recommended Schema

| Type | Priority | Why |
|------|----------|-----|

### Generated Templates

{JSON-LD templates for missing recommended schema, ready to implement}

### Implementation Notes
- Where to place JSON-LD (head vs body)
- Testing tool: Google Rich Results Test
- Monitoring: Google Search Console Enhancements report
```

## Scoring Logic

- 100: All recommended types present, valid, no issues
- -20: Missing critical schema type for page type
- -15: Deprecated type found
- -10: Validation errors in existing schema
- -5: Missing optional but recommended schema
- Minimum: 0
