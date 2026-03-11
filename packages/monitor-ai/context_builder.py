"""monitor-ai/context_builder.py — Construtor de Contexto On-Chain para IA.

Agrega dados reais do usuário (capital, trades, subcontas, inatividade, gas)
para injetar como contexto no system prompt da IA.

Standalone: sem dependência do monolito webdex_*.py.

Uso:
    from context_builder import ContextBuilder

    cb = ContextBuilder(db_path="webdex_v5_final.db")
    ctx = cb.build(wallet="0xabc...", period="24h")
    # ctx → dict com capital, pnl, top_subs, etc.
    system_prompt = cb.to_system_prompt(ctx)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any


def _period_hours(period: str) -> int:
    mapping = {"1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720, "ciclo": 21}
    return mapping.get(str(period).lower().strip(), 24)


def _since_dt(hours: int) -> str:
    return (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")


class ContextBuilder:
    """Constrói contexto on-chain real para injeção no system prompt da IA."""

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    # ── Queries ────────────────────────────────────────────────────────────
    def _capital(self, wallet: str) -> Dict:
        try:
            c = self._conn()
            row = c.execute("""
                SELECT cc.total_usd, cc.env, cc.updated_ts
                FROM capital_cache cc
                JOIN users u ON u.chat_id = cc.chat_id
                WHERE LOWER(u.wallet) = ?
                ORDER BY cc.updated_ts DESC LIMIT 1
            """, (wallet.lower(),)).fetchone()
            c.close()
            if row:
                return {"total_usd": float(row[0] or 0), "env": row[1] or "?", "updated_ts": row[2]}
        except Exception:
            pass
        return {"total_usd": 0.0, "env": "?", "updated_ts": None}

    def _pnl(self, wallet: str, since: str) -> Dict:
        try:
            c = self._conn()
            row = c.execute("""
                SELECT COUNT(*),
                       COALESCE(SUM(CAST(o.valor AS REAL)), 0),
                       COALESCE(SUM(CAST(o.gas_usd AS REAL)), 0),
                       COALESCE(SUM(CAST(o.valor AS REAL)) - SUM(CAST(o.gas_usd AS REAL)), 0),
                       COUNT(CASE WHEN CAST(o.valor AS REAL) > 0 THEN 1 END)
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE o.tipo='Trade' AND LOWER(ow.wallet)=? AND o.data_hora>=?
            """, (wallet.lower(), since)).fetchone()
            c.close()
            if row:
                trades = int(row[0] or 0)
                wins = int(row[4] or 0)
                return {
                    "trades": trades,
                    "bruto": float(row[1] or 0),
                    "gas": float(row[2] or 0),
                    "liquido": float(row[3] or 0),
                    "wins": wins,
                    "losses": max(0, trades - wins),
                    "winrate": round(wins / trades * 100, 1) if trades > 0 else 0.0,
                }
        except Exception:
            pass
        return {"trades": 0, "bruto": 0.0, "gas": 0.0, "liquido": 0.0, "wins": 0, "losses": 0, "winrate": 0.0}

    def _top_subs(self, wallet: str, since: str, top_n: int = 3) -> List[Dict]:
        try:
            c = self._conn()
            rows = c.execute("""
                SELECT o.sub_conta, o.ambiente,
                       COUNT(*), ROUND(SUM(o.valor)-SUM(o.gas_usd),4),
                       COUNT(CASE WHEN o.valor>0 THEN 1 END)
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE o.tipo='Trade' AND LOWER(ow.wallet)=? AND o.data_hora>=?
                GROUP BY o.sub_conta, o.ambiente
                ORDER BY 4 DESC LIMIT ?
            """, (wallet.lower(), since, top_n)).fetchall()
            c.close()
            return [
                {"sub": r[0], "env": r[1], "trades": r[2], "liquido": float(r[3] or 0),
                 "wins": r[4], "winrate": round(r[4] / r[2] * 100, 1) if r[2] > 0 else 0.0}
                for r in rows
            ]
        except Exception:
            return []

    def _worst_sub(self, wallet: str, since: str) -> Optional[Dict]:
        try:
            c = self._conn()
            row = c.execute("""
                SELECT o.sub_conta, o.ambiente,
                       COUNT(*), ROUND(SUM(o.valor)-SUM(o.gas_usd),4)
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE o.tipo='Trade' AND LOWER(ow.wallet)=? AND o.data_hora>=?
                GROUP BY o.sub_conta, o.ambiente
                ORDER BY 4 ASC LIMIT 1
            """, (wallet.lower(), since)).fetchone()
            c.close()
            if row:
                return {"sub": row[0], "env": row[1], "trades": row[2], "liquido": float(row[3] or 0)}
        except Exception:
            pass
        return None

    def _last_inactivity(self) -> Optional[Dict]:
        try:
            c = self._conn()
            row = c.execute(
                "SELECT end_block, minutes, tx_count, created_at FROM inactivity_stats "
                "ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            c.close()
            if row:
                return {"block": row[0], "minutes": float(row[1] or 0), "tx_count": row[2], "at": row[3]}
        except Exception:
            pass
        return None

    def _gas_total(self, wallet: str, since: str) -> float:
        try:
            c = self._conn()
            row = c.execute("""
                SELECT COALESCE(SUM(CAST(o.gas_usd AS REAL)),0)
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE o.tipo='Trade' AND LOWER(ow.wallet)=? AND o.data_hora>=?
            """, (wallet.lower(), since)).fetchone()
            c.close()
            return float(row[0] or 0)
        except Exception:
            return 0.0

    def _by_env(self, wallet: str, since: str) -> List[Dict]:
        try:
            c = self._conn()
            rows = c.execute("""
                SELECT COALESCE(o.ambiente,'?'),
                       COUNT(*), ROUND(SUM(o.valor)-SUM(o.gas_usd),4)
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE o.tipo='Trade' AND LOWER(ow.wallet)=? AND o.data_hora>=?
                GROUP BY 1 ORDER BY 3 DESC
            """, (wallet.lower(), since)).fetchall()
            c.close()
            return [{"env": r[0], "trades": r[1], "liquido": float(r[2] or 0)} for r in rows]
        except Exception:
            return []

    # ── Main builder ───────────────────────────────────────────────────────
    def build(self, wallet: Optional[str] = None, period: str = "24h") -> Dict:
        """Constrói contexto completo do usuário para injeção na IA.

        Args:
            wallet: Endereço 0x do usuário (None → modo genérico)
            period: Período de análise (24h, 7d, 30d, ciclo)

        Returns:
            Dict com todos os dados contextuais
        """
        hours = _period_hours(period)
        since = _since_dt(hours)
        ctx: Dict[str, Any] = {
            "period": period,
            "hours": hours,
            "since": since,
            "wallet": wallet,
            "has_wallet": bool(wallet),
        }

        if not wallet:
            ctx["mode"] = "generic"
            return ctx

        ctx["mode"] = "user"
        ctx["capital"] = self._capital(wallet)
        ctx["pnl"] = self._pnl(wallet, since)
        ctx["top_subs"] = self._top_subs(wallet, since, top_n=3)
        ctx["worst_sub"] = self._worst_sub(wallet, since)
        ctx["by_env"] = self._by_env(wallet, since)
        ctx["gas_total"] = self._gas_total(wallet, since)
        ctx["last_inactivity"] = self._last_inactivity()

        return ctx

    def to_system_prompt(self, ctx: Dict, base_prompt: str = "") -> str:
        """Converte o contexto em texto para o system prompt da IA."""
        if ctx.get("mode") == "generic":
            return base_prompt or _BASE_SYSTEM_PROMPT

        wallet = ctx.get("wallet", "?")
        ws = f"{wallet[:6]}…{wallet[-4:]}" if wallet and len(wallet) > 10 else wallet
        period = ctx.get("period", "24h")
        cap = ctx.get("capital", {})
        pnl = ctx.get("pnl", {})
        top = ctx.get("top_subs", [])
        worst = ctx.get("worst_sub")
        inact = ctx.get("last_inactivity")
        gas = ctx.get("gas_total", 0.0)
        by_env = ctx.get("by_env", [])

        lines = [
            base_prompt or _BASE_SYSTEM_PROMPT,
            "",
            "═══════════════════════════════════════",
            f"DADOS REAIS DO USUÁRIO — {ws} | Período: {period}",
            "═══════════════════════════════════════",
        ]

        if cap.get("total_usd", 0) > 0:
            lines.append(f"Capital on-chain: ${float(cap['total_usd']):,.2f} USD ({cap.get('env','?')})")

        lines += [
            f"Trades: {pnl.get('trades', 0)} | WinRate: {pnl.get('winrate', 0):.1f}%",
            f"P&L Bruto: {pnl.get('bruto', 0):+.4f} USD",
            f"Gás gasto: ${gas:.4f} USD",
            f"P&L Líquido: {pnl.get('liquido', 0):+.4f} USD",
        ]

        if by_env:
            lines.append("Por ambiente: " + " | ".join(
                f"{e['env']}: {e['trades']} trades / {e['liquido']:+.4f}" for e in by_env
            ))

        if top:
            lines.append("Top subcontas:")
            for i, s in enumerate(top, 1):
                lines.append(
                    f"  #{i} {s['sub']} ({s['env']}): {s['trades']} trades, "
                    f"WR {s['winrate']:.0f}%, Líq {s['liquido']:+.4f}"
                )

        if worst and worst.get("liquido", 0) < 0:
            lines.append(
                f"Pior subconta: {worst['sub']} ({worst['env']}): "
                f"{worst['trades']} trades, Líq {worst['liquido']:+.4f}"
            )

        if inact:
            lines.append(
                f"Última inatividade: {inact.get('minutes', 0):.1f} min em {inact.get('at', '?')}"
            )

        lines += [
            "═══════════════════════════════════════",
            "Responda sempre em português. Use os dados acima para contextualizar.",
            "Não invente dados — apenas use o que está fornecido acima.",
        ]

        return "\n".join(lines)


# ── Base system prompt ──────────────────────────────────────────────────────
_BASE_SYSTEM_PROMPT = """Você é o OCME Intelligence — assistente especializado no protocolo WEbdEX.

MISSÃO: Ajudar participantes a entenderem o protocolo WEbdEX com clareza,
baseando-se na Tríade Risco · Responsabilidade · Retorno.

FILOSOFIA: Números 3·6·9 (supply 369,369,369 BD), 6 Cápsulas de Inteligência,
Economia Digital Descentralizada em Polygon.

CONTEXTO TÉCNICO:
- Dois ambientes: AG_C_bd (original) e bd_v5 (otimizado)
- Token BD: fee de 0.00963 BD/op, supply fixo
- TVL real: ~$1.585M | OCME monitora ~5.7% dos 609 LP holders on-chain

Responda SEMPRE em português, de forma clara, direta e educacional.
Nunca invente dados. Se não souber, diga que não sabe."""
