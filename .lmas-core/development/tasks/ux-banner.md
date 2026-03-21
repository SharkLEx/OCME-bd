# Banner — Ad Creative Design Guidelines

> **Task ID:** ux-banner
> **Agent:** UX-Design Expert (Sati)
> **Version:** 1.0.0
> **Owner:** ux-design-expert
> **Consumers:** ux-design-expert, pm, analyst
> **Elicit:** true
> **Category:** creative-design

---

## Purpose

Generate banner and ad creative design guidelines for a specific platform. Returns size specifications, layout grid, typography hierarchy, color usage rules, CTA placement, and platform-specific best practices. Data sourced from core `colors.csv` and `typography.csv` combined with built-in platform specs.

---

## Inputs

| Field | Type | Required | Source | Validation |
|-------|------|----------|--------|------------|
| `platform` | string | yes | User Input | Target platform: "instagram", "facebook", "linkedin", "google-ads", "web", "twitter", "youtube", "tiktok", "email" |
| `mode` | string | no | User Input | `yolo` \| `interactive`. Default: `interactive` |

### Elicited Inputs (gathered during interactive mode)

| Field | Type | Required | Prompt |
|-------|------|----------|--------|
| `message` | string | yes | "What is the primary message/headline?" |
| `cta` | string | yes | "What is the call-to-action? (e.g., 'Sign Up Free', 'Learn More', 'Shop Now')" |
| `brand_colors` | string | no | "Brand colors? (hex values)" |
| `format` | string | no | "Format: static, carousel, video-cover, story?" Default: varies by platform |
| `tone` | string | no | "Visual tone: bold, minimal, playful, corporate, premium?" Default: bold |

---

## Execution Flow

### 1. Load Design Data
1.1. Read `.lmas-core/development/data/ux/colors.csv` — for color recommendations
1.2. Read `.lmas-core/development/data/ux/typography.csv` — for font recommendations
1.3. Load built-in platform specifications database
1.4. Validation: Core CSVs loaded

### 2. Resolve Platform Specifications
2.1. Look up platform in built-in specs:

**Instagram:**
| Format | Size (px) | Aspect Ratio |
|--------|----------|--------------|
| Feed Post | 1080x1080 | 1:1 |
| Feed Portrait | 1080x1350 | 4:5 |
| Story/Reel | 1080x1920 | 9:16 |
| Carousel | 1080x1080 (each) | 1:1 |

**Facebook:**
| Format | Size (px) | Aspect Ratio |
|--------|----------|--------------|
| Feed Image | 1200x628 | 1.91:1 |
| Feed Square | 1080x1080 | 1:1 |
| Story | 1080x1920 | 9:16 |
| Cover | 820x312 | 2.63:1 |

**LinkedIn:**
| Format | Size (px) | Aspect Ratio |
|--------|----------|--------------|
| Feed Image | 1200x627 | 1.91:1 |
| Feed Square | 1080x1080 | 1:1 |
| Banner | 1584x396 | 4:1 |
| Article Cover | 1200x644 | 1.86:1 |

**Google Ads:**
| Format | Size (px) | Type |
|--------|----------|------|
| Leaderboard | 728x90 | Display |
| Medium Rectangle | 300x250 | Display |
| Large Rectangle | 336x280 | Display |
| Skyscraper | 160x600 | Display |
| Mobile Banner | 320x50 | Mobile |
| Responsive | varies | Responsive |

**Web (generic):**
| Format | Size (px) | Usage |
|--------|----------|-------|
| Hero Banner | 1920x600 | Homepage |
| CTA Banner | 1200x400 | In-page |
| Sidebar | 300x600 | Sidebar |
| Notification | 1200x100 | Top bar |

2.2. Select sizes based on `format` parameter
2.3. If format not specified → return all sizes for platform
2.4. Validation: At least 1 size spec resolved

### 3. Build Layout Grid
3.1. For each banner size, define:
   - **Safe zone:** 10% inset from all edges (critical content area)
   - **Logo zone:** top-left or bottom-right, max 15% of banner area
   - **Headline zone:** center or center-left, 30-40% of banner area
   - **CTA zone:** bottom-center or bottom-right, prominent placement
   - **Image zone:** background or side panel, remainder of space
3.2. Specify grid columns and rows for each size
3.3. Include text-safe overlays (ensure text readability over images)
3.4. Validation: Layout grid covers all content elements

### 4. Define Typography Hierarchy
4.1. Cross-reference `typography.csv` for fonts matching `tone`
4.2. Define hierarchy for each banner size:
   - **Headline:** largest, boldest (e.g., 36-60px for large, 18-24px for small)
   - **Subheadline:** 60-70% of headline size
   - **CTA text:** 80% of headline size, bold/uppercase
   - **Legal/fine print:** 10-12px minimum
4.3. Rules:
   - Max 2 font families per banner
   - Max 3 text size levels per banner
   - All text must be readable at actual display size
4.4. Validation: Text sizes appropriate for each banner dimension

### 5. Define Color Usage
5.1. If `brand_colors` provided → build palette from brand colors
5.2. If not → recommend from `colors.csv` based on `tone`:
   - Bold: high saturation primaries, high contrast
   - Minimal: neutrals + single accent
   - Playful: multi-color, warm palette
   - Corporate: navy/gray + single accent
   - Premium: dark backgrounds, gold/silver accents
5.3. Rules:
   - Background: 1 color or gradient (max 2 colors)
   - Text: high contrast against background (4.5:1 minimum)
   - CTA button: highest contrast element on banner
   - Max 3 colors total (background, text, accent/CTA)
5.4. Validation: All text passes WCAG AA contrast against background

### 6. CTA Placement & Design
6.1. CTA button specifications:
   - Size: minimum 44px height (touch-friendly)
   - Shape: rounded rectangle (4-8px radius)
   - Color: highest contrast, most saturated color
   - Text: uppercase or sentence case, bold, 14-18px
6.2. Placement rules by platform:
   - Instagram: bottom-third, centered
   - Facebook: right-side or bottom-center
   - LinkedIn: bottom-right
   - Google Ads: bottom-right, large relative to banner
   - Web: center or right-aligned
6.3. Validation: CTA clearly visible and clickable

### 7. Platform-Specific Best Practices
7.1. Generate platform-specific tips:
   - **Instagram:** Minimal text (20% rule relaxed but still relevant), visual-first, hashtag hints
   - **Facebook:** Text overlay < 20% of image for better reach, emotional imagery
   - **LinkedIn:** Professional tone, data/stats perform well, faces increase engagement
   - **Google Ads:** Clear CTA, brand visible, avoid clutter, fast-loading images
   - **Web:** Responsive sizing, lazy loading, animation considerations
7.2. Include file format requirements (JPEG, PNG, WebP, GIF)
7.3. Include file size limits per platform
7.4. Validation: Tips match selected platform

---

## Output Format

```markdown
## 🖼️ Banner Guidelines: {platform}

**Message:** {headline}
**CTA:** {cta}
**Tone:** {tone}

### Size Specifications
| Format | Size (px) | Aspect Ratio | File Format | Max File Size |
|--------|----------|--------------|-------------|---------------|
| {format} | {WxH} | {ratio} | {format} | {size} |

### Layout Grid
```
┌────────────────────────────────┐
│ [Logo]              [safe zone]│
│                                │
│      HEADLINE TEXT             │
│      Subheadline               │
│                                │
│           [CTA BUTTON]         │
│                   [fine print] │
└────────────────────────────────┘
```

### Typography
| Element | Font | Size | Weight | Color |
|---------|------|------|--------|-------|
| Headline | {font} | {size}px | Bold | {hex} |
| Subheadline | {font} | {size}px | Regular | {hex} |
| CTA | {font} | {size}px | Bold | {hex} |

### Color Usage
| Role | Hex | Usage |
|------|-----|-------|
| Background | {hex} | Banner background |
| Text | {hex} | Headlines, body |
| CTA | {hex} | Button background |

### CTA Design
- Shape: Rounded rectangle ({X}px radius)
- Size: {W}x{H}px minimum
- Placement: {position}
- Text: "{cta}" — {weight}, {size}px

### Platform Best Practices
1. {tip 1}
2. {tip 2}
3. {tip 3}
4. {tip 4}
5. {tip 5}
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| Unknown platform | Platform not in supported list | List supported platforms, suggest closest match |
| CSV missing | colors.csv or typography.csv not found | Use built-in defaults for tone-based recommendations |
| Invalid brand colors | Hex format incorrect | Ignore, use tone-based palette |
| Invalid format | Format doesn't exist for platform | List available formats for the platform |

---

## Examples

### Example 1: Instagram Ad

```
*banner instagram
> Message: "Launch your AI agent in 60 seconds"
> CTA: "Start Free"
> Tone: bold
```

Returns: 4 size specs (feed, portrait, story, carousel), bold purple/blue palette, Inter Bold headlines, centered CTA, Instagram-specific tips.

### Example 2: Google Ads

```
*banner google-ads
> Message: "50% Off First Month"
> CTA: "Claim Offer"
> Brand colors: #2563EB, #F59E0B
```

Returns: 5 display sizes, brand-color palette, compact typography, prominent CTA, Google Ads text-to-image ratio tips.

### Example 3: LinkedIn

```
*banner linkedin --format=static
> Message: "The future of development is multi-agent"
> CTA: "Read the Report"
> Tone: corporate
```

Returns: Feed + banner sizes, corporate navy palette, professional typography, data-friendly layout, LinkedIn engagement tips.

---

## Metadata

```yaml
story: N/A
version: 1.0.0
dependencies:
  - .lmas-core/development/data/ux/colors.csv
  - .lmas-core/development/data/ux/typography.csv
tags:
  - ux
  - banner
  - advertising
  - creative-design
  - data-driven
updated_at: 2026-03-17
```
