"""
LMAS Design Intelligence — BM25 Search Engine for Design Data

Provides BM25-based full-text search over design knowledge base CSVs.
Adapted from ui-ux-pro-max-skill (MIT License).

Usage:
    from core import DesignKnowledgeBase
    kb = DesignKnowledgeBase()
    results = kb.search("modern blue dashboard", domain="colors", top_k=5)

Requirements: Python 3.8+ (standard library only)
"""

import csv
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------

# DATA_DIR = parent of scripts/ → .lmas-core/development/data/ux/
DATA_DIR: Path = Path(__file__).resolve().parent.parent
SUB_SKILLS_DIR: Path = DATA_DIR / "sub-skills"

# ---------------------------------------------------------------------------
# Stopwords (English — minimal set to keep file self-contained)
# ---------------------------------------------------------------------------

STOPWORDS: set = {
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall", "can",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "because", "if", "about", "up", "it", "its", "this", "that",
    "these", "those", "i", "me", "my", "we", "our", "you", "your", "he",
    "him", "his", "she", "her", "they", "them", "their", "what", "which",
    "who", "whom",
}

# ---------------------------------------------------------------------------
# BM25 Implementation
# ---------------------------------------------------------------------------


class BM25Index:
    """Okapi BM25 ranking implementation (from scratch, no external deps).

    Parameters
    ----------
    k1 : float
        Term-frequency saturation parameter (default 1.5).
    b : float
        Length-normalization parameter (default 0.75).
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b

        # Corpus statistics
        self.corpus_size: int = 0
        self.avg_dl: float = 0.0
        self.doc_lengths: List[int] = []

        # term -> list of (doc_index, term_frequency)
        self.inverted_index: Dict[str, List[Tuple[int, int]]] = {}

        # term -> document frequency (number of docs containing term)
        self.df: Dict[str, int] = {}

        # Original documents (list of token lists)
        self.corpus: List[List[str]] = []

    def index(self, tokenized_docs: List[List[str]]) -> None:
        """Build the BM25 index from a list of tokenized documents."""
        self.corpus = tokenized_docs
        self.corpus_size = len(tokenized_docs)
        if self.corpus_size == 0:
            self.avg_dl = 0.0
            return

        total_length = 0
        self.doc_lengths = []
        self.inverted_index = {}
        self.df = {}

        for doc_idx, tokens in enumerate(tokenized_docs):
            doc_len = len(tokens)
            self.doc_lengths.append(doc_len)
            total_length += doc_len

            # Count term frequencies within this document
            tf_map: Dict[str, int] = {}
            for token in tokens:
                tf_map[token] = tf_map.get(token, 0) + 1

            # Update inverted index and document frequencies
            for term, freq in tf_map.items():
                if term not in self.inverted_index:
                    self.inverted_index[term] = []
                    self.df[term] = 0
                self.inverted_index[term].append((doc_idx, freq))
                self.df[term] += 1

        self.avg_dl = total_length / self.corpus_size

    def _idf(self, term: str) -> float:
        """Compute IDF for a term using the standard BM25 formula."""
        if term not in self.df:
            return 0.0
        n = self.df[term]
        # Robertson-Sparck-Jones IDF variant
        return math.log(
            (self.corpus_size - n + 0.5) / (n + 0.5) + 1.0
        )

    def score(self, query_tokens: List[str]) -> List[float]:
        """Score every document against the query. Returns list of scores."""
        scores = [0.0] * self.corpus_size

        for term in query_tokens:
            if term not in self.inverted_index:
                continue

            idf = self._idf(term)
            for doc_idx, tf in self.inverted_index[term]:
                dl = self.doc_lengths[doc_idx]
                # BM25 term-frequency component
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * (dl / self.avg_dl) if self.avg_dl > 0 else 1
                )
                scores[doc_idx] += idf * (numerator / denominator)

        return scores

    def search(
        self, query_tokens: List[str], top_k: int = 10
    ) -> List[Tuple[int, float]]:
        """Return top-k (doc_index, score) pairs sorted by descending score."""
        scores = self.score(query_tokens)
        # Build (index, score) pairs, filter zero scores
        indexed = [
            (idx, s) for idx, s in enumerate(scores) if s > 0.0
        ]
        indexed.sort(key=lambda x: x[1], reverse=True)
        return indexed[:top_k]


# ---------------------------------------------------------------------------
# Design Knowledge Base
# ---------------------------------------------------------------------------


class DesignKnowledgeBase:
    """Loads CSV design data and provides BM25 search across domains.

    A *domain* corresponds to a CSV file (without extension). For example,
    ``colors.csv`` becomes the domain ``"colors"``.

    Attributes
    ----------
    documents : dict
        Mapping ``{domain_name: [list of row dicts]}``.
    """

    def __init__(self, auto_load: bool = True) -> None:
        self.documents: Dict[str, List[Dict[str, str]]] = {}
        self._indices: Dict[str, BM25Index] = {}
        self._flat_docs: Dict[str, List[Tuple[str, int]]] = {}
        if auto_load:
            self.load_all()

    # ------------------------------------------------------------------
    # CSV loading
    # ------------------------------------------------------------------

    @staticmethod
    def load_csv(path: Path) -> List[Dict[str, str]]:
        """Read a CSV file and return a list of dicts (one per row).

        Handles common encodings and normalizes empty values to ``""``.
        """
        rows: List[Dict[str, str]] = []
        encodings = ["utf-8", "utf-8-sig", "latin-1"]

        for enc in encodings:
            try:
                with open(path, "r", encoding=enc, newline="") as fh:
                    reader = csv.DictReader(fh)
                    for row in reader:
                        # Normalize None → ""
                        cleaned = {
                            k.strip(): (v.strip() if v else "")
                            for k, v in row.items()
                            if k is not None
                        }
                        rows.append(cleaned)
                return rows
            except UnicodeDecodeError:
                continue
            except Exception as exc:
                print(f"[DesignKB] Warning: failed to load {path}: {exc}")
                return []

        print(f"[DesignKB] Warning: could not decode {path} with any encoding")
        return []

    def load_all(self) -> None:
        """Scan DATA_DIR and SUB_SKILLS_DIR for CSVs and load them all."""
        self.documents.clear()
        self._indices.clear()
        self._flat_docs.clear()

        dirs_to_scan = [DATA_DIR]
        if SUB_SKILLS_DIR.is_dir():
            dirs_to_scan.append(SUB_SKILLS_DIR)

        for scan_dir in dirs_to_scan:
            if not scan_dir.is_dir():
                continue
            for csv_path in sorted(scan_dir.glob("*.csv")):
                domain = csv_path.stem  # filename without .csv
                rows = self.load_csv(csv_path)
                if rows:
                    self.documents[domain] = rows

        total = sum(len(v) for v in self.documents.values())
        print(
            f"[DesignKB] Loaded {len(self.documents)} domain(s), "
            f"{total} total record(s)"
        )

    # ------------------------------------------------------------------
    # Tokenization
    # ------------------------------------------------------------------

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tokenize text: lowercase, split on non-alphanumeric, remove stopwords."""
        if not text:
            return []
        # Split on anything that is not a letter or digit
        tokens = re.split(r"[^a-zA-Z0-9]+", text.lower())
        return [t for t in tokens if t and t not in STOPWORDS]

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def _doc_to_text(self, record: Dict[str, str]) -> str:
        """Concatenate all values of a record dict into a single string."""
        return " ".join(str(v) for v in record.values() if v)

    def _ensure_index(self, domain: Optional[str] = None) -> str:
        """Build (or retrieve cached) BM25 index. Returns the cache key."""
        cache_key = domain if domain else "__ALL__"

        if cache_key in self._indices:
            return cache_key

        # Collect relevant records
        flat: List[Tuple[str, int]] = []  # (domain, row_index)
        tokenized: List[List[str]] = []

        if domain and domain in self.documents:
            for idx, rec in enumerate(self.documents[domain]):
                flat.append((domain, idx))
                tokenized.append(self.tokenize(self._doc_to_text(rec)))
        elif domain and domain not in self.documents:
            # Unknown domain — fallback to all
            return self._ensure_index(None)
        else:
            for dom, records in self.documents.items():
                for idx, rec in enumerate(records):
                    flat.append((dom, idx))
                    tokenized.append(self.tokenize(self._doc_to_text(rec)))

        index = BM25Index(k1=1.5, b=0.75)
        index.index(tokenized)

        self._indices[cache_key] = index
        self._flat_docs[cache_key] = flat
        return cache_key

    def build_index(self, domain: Optional[str] = None) -> None:
        """Explicitly build (or rebuild) a BM25 index.

        Parameters
        ----------
        domain : str or None
            If given, index only that domain's CSV. If None, index all.
        """
        cache_key = domain if domain else "__ALL__"
        # Remove existing cache so _ensure_index rebuilds
        self._indices.pop(cache_key, None)
        self._flat_docs.pop(cache_key, None)
        self._ensure_index(domain)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        domain: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search the knowledge base using BM25.

        Parameters
        ----------
        query : str
            Free-text search query.
        domain : str or None
            Restrict search to a specific CSV domain.
        top_k : int
            Maximum number of results to return.

        Returns
        -------
        list of dict
            Each result dict contains:
            - ``"domain"``: the CSV domain name
            - ``"score"``: BM25 relevance score
            - ``"data"``: the original CSV row dict
        """
        if not query or not self.documents:
            return []

        cache_key = self._ensure_index(domain)
        index = self._indices[cache_key]
        flat = self._flat_docs[cache_key]

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        hits = index.search(query_tokens, top_k=top_k)

        results: List[Dict[str, Any]] = []
        for doc_idx, score in hits:
            dom, row_idx = flat[doc_idx]
            results.append(
                {
                    "domain": dom,
                    "score": round(score, 4),
                    "data": self.documents[dom][row_idx],
                }
            )
        return results

    # ------------------------------------------------------------------
    # Domain utilities
    # ------------------------------------------------------------------

    def get_domains(self) -> List[str]:
        """Return sorted list of available CSV domain names."""
        return sorted(self.documents.keys())

    def get_domain_data(self, domain: str) -> List[Dict[str, str]]:
        """Return all records from a specific domain.

        Returns an empty list if the domain does not exist.
        """
        return self.documents.get(domain, [])

    def domain_stats(self) -> Dict[str, int]:
        """Return ``{domain: record_count}`` for every loaded domain."""
        return {d: len(rows) for d, rows in sorted(self.documents.items())}

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def results_to_json(
        self, results: List[Dict[str, Any]], indent: int = 2
    ) -> str:
        """Serialize search results to a JSON string."""
        return json.dumps(results, indent=indent, ensure_ascii=False)

    def results_to_table(
        self,
        results: List[Dict[str, Any]],
        max_col_width: int = 30,
    ) -> str:
        """Format search results as a human-readable text table."""
        if not results:
            return "(no results)"

        lines: List[str] = []
        for i, r in enumerate(results, 1):
            lines.append(f"--- Result {i} (score: {r['score']}) [{r['domain']}] ---")
            for key, val in r["data"].items():
                display = str(val)
                if len(display) > max_col_width:
                    display = display[: max_col_width - 3] + "..."
                lines.append(f"  {key}: {display}")
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("LMAS Design Intelligence — BM25 Core Test")
    print("=" * 60)
    print()

    kb = DesignKnowledgeBase()
    print()

    # Show available domains
    domains = kb.get_domains()
    print(f"Available domains ({len(domains)}):")
    for d in domains:
        count = len(kb.get_domain_data(d))
        print(f"  - {d} ({count} records)")
    print()

    # Run a sample search if any data exists
    if domains:
        test_queries = [
            "modern blue dashboard",
            "dark theme high contrast",
            "accessibility WCAG",
            "typography heading font",
        ]

        for q in test_queries:
            print(f'Search: "{q}"')
            results = kb.search(q, top_k=3)
            if results:
                for r in results:
                    # Show first 2 fields of data for brevity
                    preview = dict(list(r["data"].items())[:2])
                    print(
                        f"  [{r['domain']}] score={r['score']} | {preview}"
                    )
            else:
                print("  (no results)")
            print()
    else:
        print("No CSV data found. Place .csv files in:")
        print(f"  {DATA_DIR}")
        print(f"  {SUB_SKILLS_DIR}")

    print("Test complete.")
