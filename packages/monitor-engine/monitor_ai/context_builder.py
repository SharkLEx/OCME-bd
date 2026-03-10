# ==============================================================================
# monitor_ai/context_builder.py — Contexto real do usuário para a IA
# OCME bd Monitor Engine — Story 7.4
# ==============================================================================
from __future__ import annotations

import sqlite3
from typing import Any

from monitor_db.queries import (
    ops_summary,
    ops_best_subconta,
    ops_last_inactivity_minutes,
    capital_get,
)


def build_user_context(
    conn: sqlite3.Connection,
    wallet: str,
    chat_id: int | None = None,
    period_hours: int = 24,
) -> dict[str, Any]:
    '''
    Agrega dados reais do DB para enriquecer o contexto da IA.
    Retorna dict pronto para injetar no system prompt.
    '''
    summary   = ops_summary(conn, wallet, hours=period_hours)
    best_sub  = ops_best_subconta(conn, wallet, hours=period_hours)
    inactiv   = ops_last_inactivity_minutes(conn, wallet)
    capital   = capital_get(conn, chat_id) if chat_id else None

    # Busca subconta pior no período
    worst_sub = _get_worst_subconta(conn, wallet, period_hours)

    return {
        'wallet':              wallet,
        'period_hours':        period_hours,
        'trades_count':        summary['count'],
        'profit_gross_usd':    summary['profit_gross'],
        'profit_net_usd':      summary['profit_net'],
        'gas_total_usd':       summary['gas_total'],
        'fee_total_usd':       summary['fee_total'],
        'best_subconta':       best_sub,
        'worst_subconta':      worst_sub,
        'last_inactivity_min': inactiv,
        'capital_total_usd':   capital['total_usd'] if capital else None,
        'capital_breakdown':   capital['breakdown'] if capital else None,
        'capital_env':         capital['env'] if capital else None,
    }


def format_context_for_prompt(ctx: dict[str, Any]) -> str:
    '''Formata o contexto como texto para injetar no system prompt da IA.'''
    lines = ['📊 DADOS REAIS DO USUÁRIO (use estes números nas respostas):']

    if ctx.get('capital_total_usd') is not None:
        lines.append(f'• Capital total: ${ctx["capital_total_usd"]:,.2f} ({ctx.get("capital_env", "?")})')
        if ctx.get('capital_breakdown'):
            for env_name, val in ctx['capital_breakdown'].items():
                lines.append(f'  └─ {env_name}: ${val:,.2f}')

    lines.append(f'• Período: últimas {ctx["period_hours"]}h')
    lines.append(f'• Trades: {ctx["trades_count"]}')
    lines.append(f'• Lucro bruto: ${ctx["profit_gross_usd"]:,.2f}')
    lines.append(f'• Gas gasto: ${ctx["gas_total_usd"]:,.4f}')
    lines.append(f'• Lucro líquido: ${ctx["profit_net_usd"]:,.2f}')

    if ctx.get('best_subconta'):
        b = ctx['best_subconta']
        lines.append(f'• Melhor subconta: {b["id"]} (+${b["profit"]:,.2f} | {b["trades"]} trades)')

    if ctx.get('worst_subconta'):
        w = ctx['worst_subconta']
        lines.append(f'• Subconta atenção: {w["id"]} (${w["profit"]:,.2f})')

    inactiv = ctx.get('last_inactivity_min', 0)
    if inactiv > 5:
        lines.append(f'• Inatividade atual: {inactiv:.0f} min sem trades')
    else:
        lines.append('• Sistema: operando ativamente')

    return '\n'.join(lines)


def _get_worst_subconta(
    conn: sqlite3.Connection,
    wallet: str,
    hours: int,
) -> dict | None:
    from datetime import datetime, timedelta
    since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
    try:
        row = conn.execute('''
            SELECT o.sub_conta, SUM(o.valor) as lucro, COUNT(*) as trades
            FROM operacoes o
            JOIN op_owner ow ON ow.hash = o.hash AND ow.log_index = o.log_index
            WHERE o.data_hora >= ?
              AND LOWER(ow.wallet) = ?
              AND o.tipo = 'Trade'
            GROUP BY o.sub_conta
            ORDER BY lucro ASC
            LIMIT 1
        ''', (since, wallet.lower())).fetchone()
    except Exception:
        return None
    if not row:
        return None
    return {'id': row[0], 'profit': float(row[1] or 0), 'trades': int(row[2] or 0)}
