"""
webdex_ai_digest.py — Digest diário do protocolo WEbdEX.

Salva resumo estruturado + análise IA após cada ciclo 21h.
Expõe funções para:
  - save_digest()       : persiste no SQLite
  - get_recent_digests(): lê últimos N dias
  - generate_analysis() : chama Haiku via OpenRouter (fail-open)

Story C.1 — bdZinho Intelligence v4 (Memória Histórica)
"""
from __future__ import annotations

import json
import logging
import time
import urllib.request
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("webdex_ai_digest")

# ── Schema ────────────────────────────────────────────────────────────────────

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS ai_digests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT    NOT NULL UNIQUE,   -- YYYY-MM-DD (ciclo BRT)
    traders     INTEGER NOT NULL DEFAULT 0,
    trades      INTEGER NOT NULL DEFAULT 0,
    wins        INTEGER NOT NULL DEFAULT 0,
    wr_pct      REAL    NOT NULL DEFAULT 0.0,
    pnl_usd     REAL    NOT NULL DEFAULT 0.0,
    fee_bd      REAL    NOT NULL DEFAULT 0.0,
    tvl_usd     REAL    NOT NULL DEFAULT 0.0,
    lag_blocks  INTEGER NOT NULL DEFAULT 0,
    analysis    TEXT,                      -- linguagem natural (IA), pode ser NULL
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

def _ensure_table(conn):
    conn.execute(_CREATE_TABLE)
    conn.commit()


# ── Análise IA ────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "Você é o analista do protocolo WEbdEX DeFi na Polygon. "
    "Analise os dados do ciclo de 24h e gere um resumo conciso em português (3-5 frases). "
    "Inclua: performance geral, comparação de tendência quando disponível, anomalias ou destaques. "
    "Seja direto e factual. Não use markdown."
)


def generate_analysis(
    date: str,
    traders: int,
    trades: int,
    wr_pct: float,
    pnl_usd: float,
    fee_bd: float,
    tvl_usd: float,
    lag_blocks: int,
    prev_digests: list,
    api_key: str,
    model: str = "anthropic/claude-haiku-4-5",
    base_url: str = "https://openrouter.ai/api/v1",
    timeout: int = 15,
) -> Optional[str]:
    """Gera análise em linguagem natural via Haiku. Fail-open: retorna None se falhar."""
    if not api_key:
        logger.warning("[ai_digest] API key não configurada — análise IA pulada")
        return None

    # Contexto histórico (últimos 3 ciclos)
    hist_lines = []
    for d in prev_digests[-3:]:
        hist_lines.append(
            f"  {d['date']}: {d['traders']} traders, {d['trades']} trades, "
            f"WR {d['wr_pct']:.1f}%, P&L ${d['pnl_usd']:+.2f}, TVL ${d['tvl_usd']:,.0f}"
        )
    hist_ctx = "\n".join(hist_lines) if hist_lines else "  (primeiro ciclo registrado)"

    user_msg = (
        f"Ciclo {date}:\n"
        f"  Traders ativos: {traders}\n"
        f"  Total de trades: {trades:,}\n"
        f"  Wins: {int(wr_pct * trades / 100) if trades else 0} | WinRate: {wr_pct:.1f}%\n"
        f"  P&L bruto: ${pnl_usd:+.4f}\n"
        f"  Fee BD coletado: {fee_bd:.6f} BD\n"
        f"  TVL total: ${tvl_usd:,.0f}\n"
        f"  Lag da chain: {lag_blocks} blocos\n\n"
        f"Histórico recente:\n{hist_ctx}"
    )

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 300,
        "temperature": 0.4,
    }).encode()

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://webdex.fyi",
            "X-Title": "WEbdEX Monitor",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning("[ai_digest] Análise IA falhou (fail-open): %s", e)
        return None


# ── Persistência ──────────────────────────────────────────────────────────────

def save_digest(
    conn,
    db_lock,
    date: str,
    traders: int,
    trades: int,
    wins: int,
    wr_pct: float,
    pnl_usd: float,
    fee_bd: float,
    tvl_usd: float,
    lag_blocks: int,
    analysis: Optional[str] = None,
) -> bool:
    """Salva digest no SQLite. Upsert por date. Retorna True se sucesso."""
    try:
        with db_lock:
            _ensure_table(conn)
            conn.execute("""
                INSERT INTO ai_digests
                    (date, traders, trades, wins, wr_pct, pnl_usd, fee_bd, tvl_usd, lag_blocks, analysis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    traders=excluded.traders, trades=excluded.trades, wins=excluded.wins,
                    wr_pct=excluded.wr_pct, pnl_usd=excluded.pnl_usd, fee_bd=excluded.fee_bd,
                    tvl_usd=excluded.tvl_usd, lag_blocks=excluded.lag_blocks,
                    analysis=COALESCE(excluded.analysis, ai_digests.analysis),
                    created_at=datetime('now')
            """, (date, traders, trades, wins, wr_pct, pnl_usd, fee_bd, tvl_usd, lag_blocks, analysis))
            conn.commit()
        logger.info("[ai_digest] Digest salvo para %s (traders=%d, wr=%.1f%%, pnl=%.4f)", date, traders, wr_pct, pnl_usd)
        return True
    except Exception as e:
        logger.error("[ai_digest] Erro ao salvar digest: %s", e)
        return False


def get_recent_digests(conn, db_lock, days: int = 7) -> list:
    """Retorna lista de dicts dos últimos N ciclos (mais antigo primeiro)."""
    try:
        with db_lock:
            _ensure_table(conn)
            rows = conn.execute("""
                SELECT date, traders, trades, wins, wr_pct, pnl_usd, fee_bd, tvl_usd, lag_blocks, analysis
                FROM ai_digests
                ORDER BY date DESC LIMIT ?
            """, (days,)).fetchall()
        result = []
        for r in reversed(rows):  # mais antigo primeiro
            result.append({
                "date": r[0], "traders": r[1], "trades": r[2], "wins": r[3],
                "wr_pct": r[4], "pnl_usd": r[5], "fee_bd": r[6],
                "tvl_usd": r[7], "lag_blocks": r[8], "analysis": r[9],
            })
        return result
    except Exception as e:
        logger.error("[ai_digest] Erro ao ler digests: %s", e)
        return []


def get_latest_digest(conn, db_lock) -> Optional[dict]:
    """Retorna o digest mais recente ou None."""
    digests = get_recent_digests(conn, db_lock, days=1)
    return digests[-1] if digests else None
