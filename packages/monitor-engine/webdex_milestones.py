from __future__ import annotations
# ==============================================================================
# webdex_milestones.py — WEbdEX Monitor Engine — Milestone Notifications
# Detecta conquistas dos usuários e envia notificações de engajamento.
#
# Marcos monitorados:
#   Trades:  10, 50, 100, 250, 500, 1000
#   PnL ($): 50, 100, 500, 1000, 5000
#   Win streak: 5, 10, 20 trades consecutivos
#   Primeiro dia positivo (WinRate ≥ 60% com ≥10 trades em 24h)
# ==============================================================================

import time
from datetime import datetime, timedelta

from webdex_config import logger, TZ_BR
from webdex_db import DB_LOCK, conn, _ciclo_21h_since
from webdex_bot_core import send_html
from webdex_discord_sync import notify_milestone

# ==============================================================================
# ⚙️ PARÂMETROS
# ==============================================================================
_CYCLE_INTERVAL_S = 30 * 60   # roda a cada 30 minutos
_BOOT_WAIT_S      = 3 * 60    # aguarda 3min no boot

_TRADE_MILESTONES = [10, 50, 100, 250, 500, 1000]
_PNL_MILESTONES   = [50, 100, 500, 1000, 5000]
_STREAK_MILESTONES = [5, 10, 20]

# ==============================================================================
# 🗃️ DB — tabela de flags para deduplicar milestones
# ==============================================================================

def init_milestone_table() -> None:
    with DB_LOCK:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS milestone_flags (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id   INTEGER NOT NULL,
                milestone TEXT    NOT NULL,
                fired_at  TEXT    NOT NULL,
                UNIQUE(chat_id, milestone)
            )
        """)
        conn.commit()


def _already_fired(chat_id: int, milestone: str) -> bool:
    with DB_LOCK:
        row = conn.execute(
            "SELECT 1 FROM milestone_flags WHERE chat_id=? AND milestone=? LIMIT 1",
            (chat_id, milestone)
        ).fetchone()
    return row is not None


def _mark_fired(chat_id: int, milestone: str) -> None:
    now_str = datetime.now(tz=TZ_BR).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with DB_LOCK:
            conn.execute(
                "INSERT OR IGNORE INTO milestone_flags (chat_id, milestone, fired_at) VALUES (?,?,?)",
                (chat_id, milestone, now_str)
            )
            conn.commit()
    except Exception as e:
        logger.debug("[milestones] mark_fired error: %s", e)


# ==============================================================================
# 🔍 CHECKS
# ==============================================================================

def _check_trade_milestones(chat_id: int, wallet: str) -> list[dict]:
    """Retorna lista de marcos de trades atingidos e ainda não disparados."""
    try:
        with DB_LOCK:
            row = conn.execute("""
                SELECT COUNT(*) FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE ow.wallet=? AND o.tipo='Trade'
            """, (wallet,)).fetchone()
        total = int(row[0] or 0) if row else 0
    except Exception as e:
        logger.debug("[milestones] trade_count error: %s", e)
        return []

    results = []
    for threshold in _TRADE_MILESTONES:
        if total >= threshold and not _already_fired(chat_id, f"trades_{threshold}"):
            results.append({"type": "trades", "threshold": threshold, "total": total})
    return results


def _check_pnl_milestones(chat_id: int, wallet: str) -> list[dict]:
    """Retorna lista de marcos de PnL ($) atingidos e ainda não disparados."""
    try:
        with DB_LOCK:
            row = conn.execute("""
                SELECT SUM(CAST(o.valor AS REAL) - CAST(o.gas_usd AS REAL))
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE ow.wallet=? AND o.tipo='Trade'
            """, (wallet,)).fetchone()
        total_pnl = float(row[0] or 0) if row else 0.0
    except Exception as e:
        logger.debug("[milestones] pnl_total error: %s", e)
        return []

    if total_pnl <= 0:
        return []

    results = []
    for threshold in _PNL_MILESTONES:
        if total_pnl >= threshold and not _already_fired(chat_id, f"pnl_{threshold}"):
            results.append({"type": "pnl", "threshold": threshold, "total_pnl": total_pnl})
    return results


def _check_streak_milestones(chat_id: int, wallet: str) -> list[dict]:
    """Retorna lista de marcos de win streak atingidos e ainda não disparados."""
    try:
        with DB_LOCK:
            rows = conn.execute("""
                SELECT CAST(o.valor AS REAL) - CAST(o.gas_usd AS REAL)
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE ow.wallet=? AND o.tipo='Trade'
                ORDER BY o.data_hora DESC LIMIT 30
            """, (wallet,)).fetchall()
    except Exception as e:
        logger.debug("[milestones] streak error: %s", e)
        return []

    streak = 0
    for (net,) in rows:
        if float(net or 0) > 0:
            streak += 1
        else:
            break

    results = []
    for threshold in _STREAK_MILESTONES:
        if streak >= threshold and not _already_fired(chat_id, f"streak_{threshold}"):
            results.append({"type": "streak", "threshold": threshold, "streak": streak})
    return results


def _check_first_positive_day(chat_id: int, wallet: str) -> list[dict]:
    """Detecta primeiro ciclo com WinRate ≥ 60% e ≥ 10 trades.
    Usa corte 21h (igual ao resto do sistema) — não meia-noite.
    """
    key = "first_positive_day"
    if _already_fired(chat_id, key):
        return []

    since_ciclo = _ciclo_21h_since()
    try:
        with DB_LOCK:
            row = conn.execute("""
                SELECT COUNT(*),
                       SUM(CASE WHEN CAST(o.valor AS REAL) - CAST(o.gas_usd AS REAL) > 0 THEN 1 ELSE 0 END)
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE ow.wallet=? AND o.tipo='Trade'
                  AND o.data_hora >= ?
            """, (wallet, since_ciclo)).fetchone()
        total_today = int(row[0] or 0)
        wins_today  = int(row[1] or 0)
    except Exception as e:
        logger.debug("[milestones] first_positive_day error: %s", e)
        return []

    if total_today >= 10 and (wins_today / total_today) >= 0.60:
        wr = round(wins_today / total_today * 100, 1)
        return [{"type": "first_positive_day", "threshold": 0,
                 "total": total_today, "winrate": wr}]
    return []


# ==============================================================================
# 📬 NOTIFICAÇÃO
# ==============================================================================

def _send_milestone(chat_id: int, wallet: str, m: dict) -> None:
    w_short = wallet[:6] + "..." + wallet[-4:] if len(wallet) > 10 else wallet

    if m["type"] == "trades":
        emoji   = {10: "🎯", 50: "⭐", 100: "🏆", 250: "💎", 500: "🚀", 1000: "🌟"}.get(m["threshold"], "🏅")
        heading = f"{emoji} <b>{m['threshold']} trades executados!</b>"
        detail  = (f"Você completou <b>{m['total']:,} operações</b> no protocolo.\n"
                   f"🔑 Carteira: <code>{w_short}</code>")
        tip     = "Use 📊 mybdBook para ver sua evolução completa."

    elif m["type"] == "pnl":
        emoji   = {50: "💰", 100: "💵", 500: "🤑", 1000: "🏆", 5000: "🌟"}.get(m["threshold"], "💰")
        heading = f"{emoji} <b>${m['threshold']:,} USD de lucro acumulado!</b>"
        detail  = (f"Seu lucro total no protocolo ultrapassou <b>${m['threshold']:,}</b>.\n"
                   f"💹 Total atual: <b>+${m['total_pnl']:,.2f} USD</b>")
        tip     = "Use 📈 Dashboard PRO para analisar sua performance."

    elif m["type"] == "streak":
        heading = f"🔥 <b>{m['threshold']} trades consecutivos no positivo!</b>"
        detail  = (f"Sua sequência atual: <b>{m['streak']} wins seguidos</b>.\n"
                   f"Continue assim — consistência é o diferencial!")
        tip     = "Use 🏆 Ranking Lucro para ver onde você está no protocolo."

    elif m["type"] == "first_positive_day":
        heading = "🌟 <b>Primeiro dia positivo confirmado!</b>"
        detail  = (f"Hoje você operou com <b>WinRate {m['winrate']}%</b> "
                   f"em {m['total']} trades.\n"
                   f"Esse é um grande marco! 🎯")
        tip     = "Use 📊 mybdBook para acompanhar sua evolução."

    else:
        return

    text = (
        f"🏆 <b>CONQUISTA DESBLOQUEADA!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{heading}\n\n"
        f"{detail}\n\n"
        f"<i>{tip}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>⚡ WEbdEX · New Digital Economy</i>"
    )
    try:
        send_html(chat_id, text)
        # Sync para Discord (anonimizado — sem chat_id/wallet)
        notify_milestone(
            title="Conquista Desbloqueada no Protocolo!",
            description=text
        )
    except Exception as e:
        logger.warning("[milestones] falha ao notificar chat_id=%s: %s", chat_id, e)


# ==============================================================================
# 🔄 CICLO
# ==============================================================================

def _milestone_check_cycle() -> None:
    """Verifica todos os usuários ativos para novos milestones."""
    try:
        with DB_LOCK:
            users = conn.execute(
                "SELECT chat_id, wallet FROM users WHERE chat_id IS NOT NULL AND wallet IS NOT NULL"
            ).fetchall()
    except Exception as e:
        logger.warning("[milestones] erro ao listar usuários: %s", e)
        return

    if not users:
        return

    logger.info("[milestones] verificando %d usuários...", len(users))

    for (chat_id, wallet) in users:
        if not wallet or not str(wallet).startswith("0x"):
            continue
        chat_id = int(chat_id)
        wallet  = wallet.lower()

        checks = (
            _check_trade_milestones(chat_id, wallet)
            + _check_pnl_milestones(chat_id, wallet)
            + _check_streak_milestones(chat_id, wallet)
            + _check_first_positive_day(chat_id, wallet)
        )

        for milestone in checks:
            _send_milestone(chat_id, wallet, milestone)
            key = f"{milestone['type']}_{milestone['threshold']}"
            _mark_fired(chat_id, key)
            time.sleep(0.1)

        time.sleep(0.05)


# ==============================================================================
# 🧵 WORKER
# ==============================================================================

def milestone_worker() -> None:
    """
    Worker de milestones. Aguarda 3min no boot, depois roda a cada 30min.
    Registrado em webdex_main._THREAD_REGISTRY como 'milestone_worker'.
    """
    logger.info("[milestones] Worker iniciado — aguardando %ds...", _BOOT_WAIT_S)
    time.sleep(_BOOT_WAIT_S)

    try:
        init_milestone_table()
        logger.info("[milestones] Tabela milestone_flags pronta.")
    except Exception as e:
        logger.error("[milestones] Falha ao criar tabela: %s", e)

    while True:
        try:
            _milestone_check_cycle()
        except Exception as e:
            logger.error("[milestones] Erro no ciclo: %s", e)
        time.sleep(_CYCLE_INTERVAL_S)
