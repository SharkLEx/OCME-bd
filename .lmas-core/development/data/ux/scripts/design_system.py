"""
LMAS Design Intelligence — Design System Extraction Utilities

Extracts design tokens from CSS / Tailwind configs, analyzes color palettes
for WCAG compliance, and generates design system documents.

Usage:
    python design_system.py extract --css styles.css
    python design_system.py extract --tailwind tailwind.config.js
    python design_system.py analyze-colors "#2563EB,#F59E0B,#1E293B,#F8FAFC"
    python design_system.py suggest --domain colors

Requirements: Python 3.8+ (standard library only)
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import DesignKnowledgeBase


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert a hex color string to an (R, G, B) tuple.

    Supports ``#RGB``, ``#RRGGBB``, and variants without ``#``.
    """
    h = hex_color.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _relative_luminance(r: int, g: int, b: int) -> float:
    """Compute relative luminance per WCAG 2.1 definition."""

    def _linearize(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def contrast_ratio(color1: str, color2: str) -> float:
    """Calculate WCAG contrast ratio between two hex colors.

    Returns a float >= 1.0.  Higher is better contrast.
    """
    l1 = _relative_luminance(*hex_to_rgb(color1))
    l2 = _relative_luminance(*hex_to_rgb(color2))
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def wcag_level(ratio: float) -> str:
    """Determine WCAG conformance level from a contrast ratio.

    Returns one of ``"AAA"``, ``"AA"``, ``"AA-large"``, or ``"Fail"``.
    """
    if ratio >= 7.0:
        return "AAA"
    if ratio >= 4.5:
        return "AA"
    if ratio >= 3.0:
        return "AA-large"
    return "Fail"


def _hue_from_rgb(r: int, g: int, b: int) -> float:
    """Return hue in degrees [0, 360) from RGB."""
    r_, g_, b_ = r / 255.0, g / 255.0, b / 255.0
    mx = max(r_, g_, b_)
    mn = min(r_, g_, b_)
    diff = mx - mn
    if diff == 0:
        return 0.0
    if mx == r_:
        hue = (60 * ((g_ - b_) / diff) + 360) % 360
    elif mx == g_:
        hue = (60 * ((b_ - r_) / diff) + 120) % 360
    else:
        hue = (60 * ((r_ - g_) / diff) + 240) % 360
    return hue


def _classify_harmony(hues: List[float]) -> str:
    """Classify color harmony type from a list of hue values."""
    if len(hues) < 2:
        return "monochromatic"

    # Sort hues and compute gaps
    sorted_hues = sorted(hues)
    gaps = []
    for i in range(len(sorted_hues)):
        next_i = (i + 1) % len(sorted_hues)
        gap = (sorted_hues[next_i] - sorted_hues[i]) % 360
        gaps.append(gap)

    max_gap = max(gaps)
    min_gap = min(gaps) if gaps else 0

    # Heuristic classification
    hue_range = (sorted_hues[-1] - sorted_hues[0]) % 360
    if hue_range < 30:
        return "analogous"

    if len(hues) == 2:
        diff = abs(hues[0] - hues[1])
        diff = min(diff, 360 - diff)
        if 150 <= diff <= 210:
            return "complementary"
        if 60 <= diff <= 150:
            return "split-complementary"
        return "analogous"

    if len(hues) >= 3:
        # Check triadic (roughly 120 degree spacing)
        even_spread = all(abs(g - 120) < 30 for g in gaps if g > 10)
        if even_spread and len(hues) == 3:
            return "triadic"
        # Check if there are near-complementary pairs
        for i in range(len(hues)):
            for j in range(i + 1, len(hues)):
                diff = abs(hues[i] - hues[j])
                diff = min(diff, 360 - diff)
                if 150 <= diff <= 210:
                    return "complementary-based"

    return "custom"


# ---------------------------------------------------------------------------
# Token extraction
# ---------------------------------------------------------------------------


def extract_tokens_from_css(css_content: str) -> Dict[str, Dict[str, str]]:
    """Parse CSS custom properties (``--var-name: value``) into structured tokens.

    Returns a dict grouped by inferred category::

        {
            "colors": {"--color-primary": "#2563EB", ...},
            "spacing": {"--spacing-sm": "0.5rem", ...},
            "typography": {"--font-heading": "Inter", ...},
            "other": {"--border-radius": "8px", ...},
        }
    """
    tokens: Dict[str, Dict[str, str]] = {
        "colors": {},
        "spacing": {},
        "typography": {},
        "borders": {},
        "shadows": {},
        "other": {},
    }

    # Match CSS custom properties
    pattern = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")
    for match in pattern.finditer(css_content):
        name = match.group(1).strip()
        value = match.group(2).strip()
        category = _categorize_token(name, value)
        tokens[category][name] = value

    # Remove empty categories
    return {k: v for k, v in tokens.items() if v}


def extract_tokens_from_tailwind(config_content: str) -> Dict[str, Dict[str, str]]:
    """Parse a Tailwind config file and extract theme tokens.

    This is a best-effort parser for common Tailwind config patterns.
    It extracts key-value pairs from the ``theme.extend`` section.
    """
    tokens: Dict[str, Dict[str, str]] = {
        "colors": {},
        "spacing": {},
        "typography": {},
        "borders": {},
        "other": {},
    }

    # Extract colors object
    colors_match = re.search(
        r"colors\s*:\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}", config_content
    )
    if colors_match:
        color_block = colors_match.group(1)
        # Match simple key: 'value' or key: "value" patterns
        for m in re.finditer(
            r"""['"]?([\w-]+)['"]?\s*:\s*['"]([^'"]+)['"]""", color_block
        ):
            tokens["colors"][f"--color-{m.group(1)}"] = m.group(2)

    # Extract fontFamily
    font_match = re.search(
        r"fontFamily\s*:\s*\{([^}]+)\}", config_content
    )
    if font_match:
        for m in re.finditer(
            r"""['"]?([\w-]+)['"]?\s*:\s*\[['"]([^'"]+)['"]""",
            font_match.group(1),
        ):
            tokens["typography"][f"--font-{m.group(1)}"] = m.group(2)

    # Extract fontSize
    fontsize_match = re.search(
        r"fontSize\s*:\s*\{([^}]+)\}", config_content
    )
    if fontsize_match:
        for m in re.finditer(
            r"""['"]?([\w-]+)['"]?\s*:\s*['"]([^'"]+)['"]""",
            fontsize_match.group(1),
        ):
            tokens["typography"][f"--text-{m.group(1)}"] = m.group(2)

    # Extract spacing
    spacing_match = re.search(
        r"spacing\s*:\s*\{([^}]+)\}", config_content
    )
    if spacing_match:
        for m in re.finditer(
            r"""['"]?([\w-]+)['"]?\s*:\s*['"]([^'"]+)['"]""",
            spacing_match.group(1),
        ):
            tokens["spacing"][f"--spacing-{m.group(1)}"] = m.group(2)

    # Extract borderRadius
    radius_match = re.search(
        r"borderRadius\s*:\s*\{([^}]+)\}", config_content
    )
    if radius_match:
        for m in re.finditer(
            r"""['"]?([\w-]+)['"]?\s*:\s*['"]([^'"]+)['"]""",
            radius_match.group(1),
        ):
            tokens["borders"][f"--radius-{m.group(1)}"] = m.group(2)

    return {k: v for k, v in tokens.items() if v}


def _categorize_token(name: str, value: str) -> str:
    """Infer a token category from its name and value."""
    name_lower = name.lower()
    value_lower = value.lower()

    if any(kw in name_lower for kw in ("color", "bg", "text", "border-color", "fill", "stroke")):
        return "colors"
    if re.match(r"^#[0-9a-fA-F]{3,8}$", value.strip()):
        return "colors"
    if any(kw in value_lower for kw in ("rgb", "hsl", "oklch")):
        return "colors"
    if any(kw in name_lower for kw in ("font", "text", "line-height", "letter-spacing")):
        return "typography"
    if any(kw in name_lower for kw in ("spacing", "gap", "margin", "padding")):
        return "spacing"
    if any(kw in name_lower for kw in ("border", "radius", "outline")):
        return "borders"
    if "shadow" in name_lower:
        return "shadows"
    return "other"


# ---------------------------------------------------------------------------
# Color palette analysis
# ---------------------------------------------------------------------------


def analyze_color_palette(colors: List[str]) -> Dict[str, Any]:
    """Analyze a list of hex colors for contrast, WCAG compliance, and harmony.

    Parameters
    ----------
    colors : list of str
        Hex color strings (e.g., ``["#2563EB", "#F59E0B"]``).

    Returns
    -------
    dict with keys:
        - ``colors``: input colors with RGB and hue
        - ``contrast_matrix``: pairwise contrast ratios
        - ``wcag_pairs``: WCAG levels for all pairs
        - ``harmony``: detected harmony type
        - ``issues``: list of accessibility warnings
    """
    analysis: Dict[str, Any] = {
        "colors": [],
        "contrast_matrix": [],
        "wcag_pairs": [],
        "harmony": "unknown",
        "issues": [],
    }

    if not colors:
        return analysis

    # Parse colors
    hues: List[float] = []
    for c in colors:
        try:
            r, g, b = hex_to_rgb(c)
            hue = _hue_from_rgb(r, g, b)
            hues.append(hue)
            analysis["colors"].append({
                "hex": c,
                "rgb": f"rgb({r}, {g}, {b})",
                "hue": round(hue, 1),
            })
        except ValueError:
            analysis["issues"].append(f"Invalid color: {c}")

    # Contrast matrix (pairwise)
    n = len(colors)
    matrix: List[List[Optional[float]]] = [[None] * n for _ in range(n)]
    wcag_pairs: List[Dict[str, str]] = []

    for i in range(n):
        for j in range(i + 1, n):
            try:
                ratio = contrast_ratio(colors[i], colors[j])
                ratio = round(ratio, 2)
                matrix[i][j] = ratio
                matrix[j][i] = ratio
                level = wcag_level(ratio)
                wcag_pairs.append({
                    "pair": f"{colors[i]} / {colors[j]}",
                    "ratio": ratio,
                    "level": level,
                })
                if level == "Fail":
                    analysis["issues"].append(
                        f"Low contrast ({ratio}:1) between {colors[i]} and {colors[j]} — WCAG Fail"
                    )
            except ValueError:
                pass

    analysis["contrast_matrix"] = matrix
    analysis["wcag_pairs"] = wcag_pairs

    # Harmony
    if hues:
        analysis["harmony"] = _classify_harmony(hues)

    return analysis


# ---------------------------------------------------------------------------
# Suggestions from knowledge base
# ---------------------------------------------------------------------------


def suggest_improvements(
    tokens: Dict[str, Dict[str, str]],
    domain: Optional[str] = None,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Use BM25 to find similar patterns in the knowledge base.

    Builds a query from the token names and values, then searches the
    design knowledge base for relevant suggestions.
    """
    kb = DesignKnowledgeBase()

    # Build query from token content
    query_parts: List[str] = []
    for category, pairs in tokens.items():
        query_parts.append(category)
        for name, value in list(pairs.items())[:5]:  # limit to avoid overly long queries
            query_parts.append(name.replace("--", "").replace("-", " "))

    query = " ".join(query_parts)
    results = kb.search(query, domain=domain, top_k=top_k)
    return results


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def generate_tokens_css(tokens: Dict[str, Dict[str, str]]) -> str:
    """Generate a CSS custom properties file from extracted tokens."""
    lines: List[str] = [
        "/* ==========================================================",
        "   Design Tokens — Generated by LMAS Design Intelligence",
        "   ========================================================== */",
        "",
        ":root {",
    ]

    for category, pairs in sorted(tokens.items()):
        if not pairs:
            continue
        lines.append(f"  /* --- {category} --- */")
        for name, value in sorted(pairs.items()):
            lines.append(f"  {name}: {value};")
        lines.append("")

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def generate_tailwind_config(tokens: Dict[str, Dict[str, str]]) -> str:
    """Generate a Tailwind theme extend config from extracted tokens."""
    config: Dict[str, Dict[str, str]] = {}

    for category, pairs in tokens.items():
        tw_section = {
            "colors": "colors",
            "spacing": "spacing",
            "typography": "fontFamily",
            "borders": "borderRadius",
        }.get(category, category)

        section: Dict[str, str] = {}
        for name, value in pairs.items():
            # Convert --color-primary to primary
            clean = re.sub(r"^--(color|font|text|spacing|radius|shadow)-?", "", name)
            clean = clean.strip("-") or name.lstrip("-")
            section[clean] = value

        if section:
            config[tw_section] = section

    # Build JS config string
    lines: List[str] = [
        "// Tailwind Theme — Generated by LMAS Design Intelligence",
        "/** @type {import('tailwindcss').Config} */",
        "module.exports = {",
        "  theme: {",
        "    extend: {",
    ]

    for section_name, section_data in sorted(config.items()):
        lines.append(f"      {section_name}: {{")
        for key, val in sorted(section_data.items()):
            lines.append(f"        '{key}': '{val}',")
        lines.append("      },")

    lines.extend([
        "    },",
        "  },",
        "};",
        "",
    ])

    return "\n".join(lines)


def generate_master_md(
    tokens: Dict[str, Dict[str, str]],
    analysis: Optional[Dict[str, Any]] = None,
    suggestions: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Generate a MASTER.md design system document.

    Parameters
    ----------
    tokens : dict
        Extracted design tokens by category.
    analysis : dict or None
        Color palette analysis from ``analyze_color_palette()``.
    suggestions : list or None
        Knowledge base suggestions from ``suggest_improvements()``.
    """
    lines: List[str] = [
        "# Design System — MASTER",
        "",
        "> Generated by LMAS Design Intelligence",
        "",
    ]

    # Tokens section
    lines.append("## Design Tokens")
    lines.append("")
    for category, pairs in sorted(tokens.items()):
        if not pairs:
            continue
        lines.append(f"### {category.title()}")
        lines.append("")
        lines.append("| Token | Value |")
        lines.append("|-------|-------|")
        for name, value in sorted(pairs.items()):
            lines.append(f"| `{name}` | `{value}` |")
        lines.append("")

    # Color analysis section
    if analysis:
        lines.append("## Color Analysis")
        lines.append("")
        lines.append(f"**Harmony type:** {analysis.get('harmony', 'N/A')}")
        lines.append("")

        wcag_pairs = analysis.get("wcag_pairs", [])
        if wcag_pairs:
            lines.append("### Contrast Ratios (WCAG)")
            lines.append("")
            lines.append("| Pair | Ratio | Level |")
            lines.append("|------|-------|-------|")
            for p in wcag_pairs:
                lines.append(f"| {p['pair']} | {p['ratio']}:1 | {p['level']} |")
            lines.append("")

        issues = analysis.get("issues", [])
        if issues:
            lines.append("### Accessibility Issues")
            lines.append("")
            for issue in issues:
                lines.append(f"- {issue}")
            lines.append("")

    # Suggestions section
    if suggestions:
        lines.append("## Suggestions from Knowledge Base")
        lines.append("")
        for i, s in enumerate(suggestions, 1):
            data_preview = ", ".join(
                f"{k}={v}" for k, v in list(s["data"].items())[:3]
            )
            lines.append(
                f"{i}. **[{s['domain']}]** (score: {s['score']}) — {data_preview}"
            )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*LMAS Design Intelligence | CLI First*")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="design_system",
        description="LMAS Design Intelligence — Design System Utilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # extract
    extract_p = sub.add_parser("extract", help="Extract tokens from CSS or Tailwind config")
    extract_p.add_argument("--css", type=str, help="Path to CSS file")
    extract_p.add_argument("--tailwind", type=str, help="Path to Tailwind config file")
    extract_p.add_argument(
        "--output", "-o",
        choices=["json", "css", "tailwind", "master"],
        default="json",
        help="Output format (default: json)",
    )

    # analyze-colors
    colors_p = sub.add_parser("analyze-colors", help="Analyze a color palette")
    colors_p.add_argument(
        "colors",
        type=str,
        help="Comma-separated hex colors (e.g., '#2563EB,#F59E0B,#1E293B')",
    )
    colors_p.add_argument(
        "--format", "-f",
        choices=["json", "table"],
        default="table",
    )

    # suggest
    suggest_p = sub.add_parser("suggest", help="Get suggestions from knowledge base")
    suggest_p.add_argument("--css", type=str, help="Path to CSS file with tokens")
    suggest_p.add_argument("--domain", "-d", type=str, help="Restrict to domain")
    suggest_p.add_argument("--top", "-k", type=int, default=5, help="Number of results")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "extract":
        tokens: Dict[str, Dict[str, str]] = {}
        if args.css:
            content = Path(args.css).read_text(encoding="utf-8")
            tokens = extract_tokens_from_css(content)
        elif args.tailwind:
            content = Path(args.tailwind).read_text(encoding="utf-8")
            tokens = extract_tokens_from_tailwind(content)
        else:
            print("Error: Provide --css or --tailwind file path.")
            return 1

        if args.output == "json":
            print(json.dumps(tokens, indent=2, ensure_ascii=False))
        elif args.output == "css":
            print(generate_tokens_css(tokens))
        elif args.output == "tailwind":
            print(generate_tailwind_config(tokens))
        elif args.output == "master":
            print(generate_master_md(tokens))

    elif args.command == "analyze-colors":
        color_list = [c.strip() for c in args.colors.split(",") if c.strip()]
        result = analyze_color_palette(color_list)

        if args.format == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"\nPalette Analysis ({len(color_list)} colors)")
            print("=" * 50)
            print(f"Harmony: {result['harmony']}")
            print()
            if result["wcag_pairs"]:
                print("Contrast Pairs:")
                for p in result["wcag_pairs"]:
                    status = "PASS" if p["level"] != "Fail" else "FAIL"
                    print(f"  {p['pair']}  {p['ratio']}:1  [{p['level']}] {status}")
            if result["issues"]:
                print("\nIssues:")
                for issue in result["issues"]:
                    print(f"  - {issue}")
            print()

    elif args.command == "suggest":
        tokens = {}
        if args.css:
            content = Path(args.css).read_text(encoding="utf-8")
            tokens = extract_tokens_from_css(content)
        if not tokens:
            print("No tokens found. Provide a --css file with custom properties.")
            return 1
        results = suggest_improvements(tokens, domain=args.domain, top_k=args.top)
        if results:
            for i, r in enumerate(results, 1):
                preview = ", ".join(f"{k}={v}" for k, v in list(r["data"].items())[:3])
                print(f"  {i}. [{r['domain']}] score={r['score']} — {preview}")
        else:
            print("No suggestions found.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
