"""monitor-ai/context_builder.py — Construtor de Contexto On-Chain para IA.

Agrega dados reais do usuário (capital, trades, subcontas, inatividade, gas, liquidez)
para injetar como contexto no system prompt da IA.

v2: TVL dinâmico do DB, suporte a intent-directed context, dados de liquidez/LP.

Standalone: sem dependência do monolito webdex_*.py.
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

    def _gas_detail(self, wallet: str, since: str) -> Dict:
        """Gas detalhado por período e ambiente."""
        try:
            c = self._conn()
            rows = c.execute("""
                SELECT COALESCE(o.ambiente,'?'),
                       COUNT(*),
                       COALESCE(SUM(CAST(o.gas_usd AS REAL)),0),
                       COALESCE(AVG(CAST(o.gas_usd AS REAL)),0),
                       COALESCE(MAX(CAST(o.gas_usd AS REAL)),0)
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE o.tipo='Trade' AND LOWER(ow.wallet)=? AND o.data_hora>=?
                GROUP BY 1
            """, (wallet.lower(), since)).fetchall()
            c.close()
            total = sum(float(r[2] or 0) for r in rows)
            by_env = [{"env": r[0], "trades": r[1], "total": float(r[2] or 0),
                       "avg": float(r[3] or 0), "max": float(r[4] or 0)} for r in rows]
            return {"total": total, "by_env": by_env}
        except Exception:
            return {"total": 0.0, "by_env": []}

    def _liquidity(self, env: Optional[str] = None) -> Dict:
        """Dados de liquidez do pool (fl_snapshots) — snapshot mais recente."""
        try:
            c = self._conn()
            query = """
                SELECT env, lp_usdt_supply, lp_loop_supply, liq_usdt, liq_loop,
                       pol_price, total_usd, ts
                FROM fl_snapshots
                WHERE 1=1
            """
            params: List = []
            if env:
                query += " AND env=?"
                params.append(env)
            query += " ORDER BY ts DESC LIMIT 2"
            rows = c.execute(query, params).fetchall()
            c.close()
            if not rows:
                return {}
            result = {}
            for r in rows:
                result[r[0]] = {
                    "lp_usdt_supply": float(r[1] or 0),
                    "lp_loop_supply": float(r[2] or 0),
                    "liq_usdt": float(r[3] or 0),
                    "liq_loop": float(r[4] or 0),
                    "pol_price": float(r[5] or 0),
                    "total_usd": float(r[6] or 0),
                    "ts": r[7],
                }
            return result
        except Exception:
            return {}

    def _tvl_dynamic(self) -> Dict:
        """TVL e estado do protocolo — direto do DB, sempre atualizado."""
        try:
            c = self._conn()
            # TVL total agregando últimos snapshots por env
            row = c.execute("""
                SELECT COALESCE(SUM(total_usd), 0), COUNT(DISTINCT env)
                FROM (
                    SELECT env, total_usd, ROW_NUMBER() OVER (PARTITION BY env ORDER BY ts DESC) AS rn
                    FROM fl_snapshots
                ) WHERE rn=1
            """).fetchone()
            tvl = float(row[0] or 0) if row else 0.0
            envs = int(row[1] or 0) if row else 0

            # Total de usuários ativos (com wallet)
            users_row = c.execute(
                "SELECT COUNT(*) FROM users WHERE wallet IS NOT NULL AND wallet != ''"
            ).fetchone()
            users = int(users_row[0] or 0) if users_row else 0

            # POL price
            pol_row = c.execute(
                "SELECT pol_price FROM fl_snapshots ORDER BY ts DESC LIMIT 1"
            ).fetchone()
            pol_price = float(pol_row[0] or 0) if pol_row else 0.0

            c.close()
            return {"tvl_usd": tvl, "envs": envs, "users_monitored": users, "pol_price": pol_price}
        except Exception:
            return {"tvl_usd": 0.0, "envs": 0, "users_monitored": 0, "pol_price": 0.0}

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
    def build(self, wallet: Optional[str] = None, period: str = "24h", intent: str = "general") -> Dict:
        """Constrói contexto direcionado por intent para injeção na IA.

        Args:
            wallet: Endereço 0x do usuário (None → modo genérico)
            period: Período de análise (24h, 7d, 30d, ciclo)
            intent: Intent classificado (resultado, capital, gas, liquidez, ciclo, etc.)

        Returns:
            Dict com dados contextuais direcionados ao intent
        """
        hours = _period_hours(period)
        since = _since_dt(hours)
        ctx: Dict[str, Any] = {
            "period": period,
            "hours": hours,
            "since": since,
            "wallet": wallet,
            "has_wallet": bool(wallet),
            "intent": intent,
        }

        # Sempre injeta TVL dinâmico do protocolo
        ctx["protocol"] = self._tvl_dynamic()

        if not wallet:
            ctx["mode"] = "generic"
            # Para perguntas sobre liquidez/protocolo, injeta dados mesmo sem wallet
            if intent in ("liquidez", "governance", "educacao"):
                ctx["liquidity"] = self._liquidity()
            return ctx

        ctx["mode"] = "user"

        # Dados base — sempre carregados
        ctx["capital"] = self._capital(wallet)
        ctx["pnl"] = self._pnl(wallet, since)
        ctx["by_env"] = self._by_env(wallet, since)

        # Dados por intent — carrega apenas o que é relevante
        if intent in ("resultado", "capital", "dashboard", "general"):
            ctx["top_subs"] = self._top_subs(wallet, since, top_n=3)
            ctx["worst_sub"] = self._worst_sub(wallet, since)

        if intent in ("gas", "resultado", "general"):
            ctx["gas_detail"] = self._gas_detail(wallet, since)
        else:
            ctx["gas_total"] = ctx["pnl"].get("gas", 0.0)

        if intent in ("ciclo", "general", "resultado"):
            ctx["last_inactivity"] = self._last_inactivity()

        if intent in ("liquidez", "capital", "triade"):
            ctx["liquidity"] = self._liquidity(env=ctx["capital"].get("env"))

        return ctx

    def to_system_prompt(self, ctx: Dict, base_prompt: str = "") -> str:
        """Converte o contexto em texto para o system prompt da IA."""
        protocol = ctx.get("protocol", {})
        tvl = protocol.get("tvl_usd", 0.0)
        pol_price = protocol.get("pol_price", 0.0)
        users_monitored = protocol.get("users_monitored", 0)
        intent = ctx.get("intent", "general")

        # System prompt base com TVL dinâmico
        dynamic_base = _build_base_prompt(tvl, pol_price, users_monitored)

        if ctx.get("mode") == "generic":
            prompt = base_prompt or dynamic_base
            liq = ctx.get("liquidity", {})
            if liq:
                prompt += "\n\n" + _format_liquidity(liq)
            return prompt

        wallet = ctx.get("wallet", "?")
        ws = f"{wallet[:6]}…{wallet[-4:]}" if wallet and len(wallet) > 10 else wallet
        period = ctx.get("period", "24h")
        cap = ctx.get("capital", {})
        pnl = ctx.get("pnl", {})
        top = ctx.get("top_subs", [])
        worst = ctx.get("worst_sub")
        inact = ctx.get("last_inactivity")
        gas_detail = ctx.get("gas_detail")
        gas_total = ctx.get("gas_total", pnl.get("gas", 0.0))
        by_env = ctx.get("by_env", [])
        liq = ctx.get("liquidity", {})

        lines = [
            base_prompt or dynamic_base,
            "",
            "═══════════════════════════════════════",
            f"DADOS REAIS DO USUÁRIO — {ws} | Período: {period} | Intent: {intent}",
            "═══════════════════════════════════════",
        ]

        if cap.get("total_usd", 0) > 0:
            lines.append(f"Capital on-chain: ${float(cap['total_usd']):,.2f} USD ({cap.get('env','?')})")

        lines += [
            f"Trades: {pnl.get('trades', 0)} | WinRate: {pnl.get('winrate', 0):.1f}% "
            f"({pnl.get('wins',0)}W / {pnl.get('losses',0)}L)",
            f"P&L Bruto: {pnl.get('bruto', 0):+.4f} USD",
        ]

        if gas_detail:
            lines.append(f"Gás total: ${gas_detail['total']:.4f} USD")
            for ge in gas_detail.get("by_env", []):
                lines.append(f"  {ge['env']}: {ge['trades']} trades, "
                             f"total ${ge['total']:.4f}, avg ${ge['avg']:.4f}, max ${ge['max']:.4f}")
        else:
            lines.append(f"Gás gasto: ${gas_total:.4f} USD")

        lines.append(f"P&L Líquido: {pnl.get('liquido', 0):+.4f} USD")

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

        if liq:
            lines.append("")
            lines.append(_format_liquidity(liq))

        lines += [
            "═══════════════════════════════════════",
            "Responda sempre em português. Use os dados acima para contextualizar.",
            "Não invente dados — apenas use o que está fornecido acima.",
            f"Foco da pergunta: {intent}",
        ]

        return "\n".join(lines)


# ── Helpers ─────────────────────────────────────────────────────────────────
def _format_liquidity(liq: Dict) -> str:
    if not liq:
        return ""
    lines = ["Dados de Liquidez do Pool:"]
    for env, d in liq.items():
        lines.append(
            f"  {env}: TVL ${d.get('total_usd', 0):,.0f} | "
            f"LP-USDT supply {d.get('lp_usdt_supply', 0):,.2f} | "
            f"LP-LOOP supply {d.get('lp_loop_supply', 0):,.2f} | "
            f"POL ${d.get('pol_price', 0):.4f}"
        )
    return "\n".join(lines)


def _build_base_prompt(tvl: float, pol_price: float, users_monitored: int) -> str:
    tvl_str = f"~${tvl:,.0f}" if tvl > 0 else "em atualização"
    pol_str = f"${pol_price:.4f}" if pol_price > 0 else "em atualização"
    users_str = str(users_monitored) if users_monitored > 0 else "~17"
    return f"""Você é o OCME Intelligence — assistente especializado no protocolo WEbdEX.

MISSÃO: Ajudar participantes a entenderem o protocolo WEbdEX com clareza,
baseando-se na Tríade Risco · Responsabilidade · Retorno.

FILOSOFIA: Números 3·6·9 (supply 369,369,369 BD), 6 Cápsulas de Inteligência,
Economia Digital Descentralizada em Polygon.

CONTEXTO TÉCNICO ATUALIZADO:
- Dois ambientes: AG_C_bd (original) e bd_v5 (otimizado)
- Token BD: fee de 0.00963 BD/op, supply fixo 369,369,369
- TVL atual do protocolo: {tvl_str}
- Preço POL atual: {pol_str}
- OCME monitora {users_str} participantes ativamente on-chain

Responda SEMPRE em português, de forma clara, direta e educacional.
Nunca invente dados. Se não souber, diga que não sabe."""
