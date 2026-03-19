"""
LMAS Design Intelligence — CLI Search Interface

Command-line tool for searching design knowledge base CSVs using BM25.

Usage:
    python search.py "modern blue dashboard" --domain colors --top 5
    python search.py "accessible typography" --format json
    python search.py --list-domains

Requirements: Python 3.8+ (standard library only)
"""

import argparse
import json
import sys
from typing import Any, Dict, List

from core import DesignKnowledgeBase


# ---------------------------------------------------------------------------
# Table formatter
# ---------------------------------------------------------------------------


def format_table(
    results: List[Dict[str, Any]],
    max_col_width: int = 40,
    terminal_width: int = 120,
) -> str:
    """Format search results as a compact terminal-friendly table.

    Each result is displayed as a block with domain, score, and truncated
    field values.
    """
    if not results:
        return "(no results found)"

    lines: List[str] = []
    separator = "-" * min(terminal_width, 80)

    lines.append(separator)
    lines.append(f" {'#':>3}  {'Score':>8}  {'Domain':<20}  Data Preview")
    lines.append(separator)

    for i, r in enumerate(results, 1):
        domain = r["domain"]
        score = r["score"]
        data = r["data"]

        # Build a compact preview of the data fields
        preview_parts: List[str] = []
        remaining_width = terminal_width - 40  # space used by #, score, domain
        for key, val in data.items():
            val_str = str(val).strip()
            if not val_str:
                continue
            field = f"{key}={val_str}"
            if len(field) > max_col_width:
                field = field[: max_col_width - 3] + "..."
            preview_parts.append(field)

        preview = " | ".join(preview_parts)
        if len(preview) > remaining_width:
            preview = preview[: remaining_width - 3] + "..."

        lines.append(f" {i:>3}  {score:>8.4f}  {domain:<20}  {preview}")

    lines.append(separator)
    lines.append(f" {len(results)} result(s) returned")
    lines.append("")

    return "\n".join(lines)


def format_detailed(
    results: List[Dict[str, Any]],
    max_col_width: int = 60,
) -> str:
    """Format results with full field details (one field per line)."""
    if not results:
        return "(no results found)"

    lines: List[str] = []

    for i, r in enumerate(results, 1):
        lines.append(f"=== Result {i} ===")
        lines.append(f"  Domain : {r['domain']}")
        lines.append(f"  Score  : {r['score']}")
        lines.append(f"  Fields :")
        for key, val in r["data"].items():
            display = str(val).strip()
            if len(display) > max_col_width:
                display = display[: max_col_width - 3] + "..."
            lines.append(f"    {key}: {display}")
        lines.append("")

    lines.append(f"Total: {len(results)} result(s)")
    return "\n".join(lines)


def format_json(results: List[Dict[str, Any]], indent: int = 2) -> str:
    """Format results as JSON."""
    return json.dumps(results, indent=indent, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Domain listing
# ---------------------------------------------------------------------------


def print_domains(kb: DesignKnowledgeBase) -> None:
    """Print all available domains with record counts."""
    stats = kb.domain_stats()
    if not stats:
        print("No domains found. Ensure CSV files exist in the data directory.")
        return

    print(f"\nAvailable domains ({len(stats)}):")
    print("-" * 40)
    for domain, count in stats.items():
        # Show column headers from first record
        data = kb.get_domain_data(domain)
        cols = list(data[0].keys()) if data else []
        col_preview = ", ".join(cols[:5])
        if len(cols) > 5:
            col_preview += f" (+{len(cols) - 5} more)"
        print(f"  {domain:<25} {count:>5} records  [{col_preview}]")
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="search",
        description="LMAS Design Intelligence — Search design knowledge base",
        epilog="Examples:\n"
        '  python search.py "blue dashboard" --domain colors\n'
        '  python search.py "accessible" --format json --top 20\n'
        "  python search.py --list-domains\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Search query (free text)",
    )
    parser.add_argument(
        "--domain", "-d",
        type=str,
        default=None,
        help="Restrict search to a specific domain (CSV filename without extension)",
    )
    parser.add_argument(
        "--top", "-k",
        type=int,
        default=10,
        help="Number of results to return (default: 10)",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["table", "detailed", "json"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--list-domains", "-l",
        action="store_true",
        help="List all available domains and exit",
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=40,
        help="Maximum column width for table display (default: 40)",
    )

    return parser


def main() -> int:
    """Main entry point. Returns exit code."""
    parser = build_parser()
    args = parser.parse_args()

    # Load knowledge base
    kb = DesignKnowledgeBase()

    # Handle --list-domains
    if args.list_domains:
        print_domains(kb)
        return 0

    # Require query if not listing domains
    if not args.query:
        parser.print_help()
        print("\nError: A search query is required (or use --list-domains).")
        return 1

    # Validate domain if specified
    if args.domain and args.domain not in kb.get_domains():
        available = ", ".join(kb.get_domains())
        print(f"Error: Unknown domain '{args.domain}'.")
        print(f"Available domains: {available}")
        return 1

    # Execute search
    results = kb.search(args.query, domain=args.domain, top_k=args.top)

    # Format output
    if args.format == "json":
        print(format_json(results))
    elif args.format == "detailed":
        print(format_detailed(results, max_col_width=args.max_width))
    else:
        print(format_table(results, max_col_width=args.max_width))

    return 0


if __name__ == "__main__":
    sys.exit(main())
