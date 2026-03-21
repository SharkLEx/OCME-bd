from __future__ import annotations
# ==============================================================================
# webdex_anomaly.py — WEbdEX Monitor Engine — Anomaly Detection Worker
# Detecta padrões anômalos nas operações e notifica usuários/ADM conforme
# as regras de roteamento:
#   - frequency_drop  → USER (variação no padrão de abertura)
#   - inactivity      → USER (subconta inativa)
#   - burst           → ADM only (rajada de trades)
#   - loss_streak     → ADM only + IA audit (streak de perdas)
# ==============================================================================

import time
import threading
from datetime import datetime, timedelta
from typing import Optional

from webdex_config import logger, ADMIN_USER_IDS, ai_answer_ptbr, TZ_BR
from webdex_db import DB_LOCK, conn, cursor

# ── Importa helpers de envio ──────────────────────────────────────────────────
from webdex_bot_core import send_html
from webdex_discord_sync import notify_anomaly

# ==============================================================================
# ⚙️ PARÂMETROS
# ==============================================================================
_CYCLE_INTERVAL_S   = 15 * 60   # roda a cada 15 minutos
_BOOT_WAIT_S        = 5  * 60   # aguarda 5 min ao iniciar (bot ainda aquecendo)

_FREQ_DROP_THRESH   = 0.50       # >50% queda vs média 7d → alerta usuário
_BURST_WINDOW_MIN   = 10         # janela burst em minutos
_BURST_THRESH       = 15         # >15 trades em 10min → alerta ADM
_LOSS_STREAK_MIN    = 5          # ≥5 perdas consecutivas → alerta ADM + IA
_COOLDOWN_H         = 4          # cooldown entre alertas do mesmo tipo/subconta

# ==============================================================================
# 🗃️ DB — tabela de flags para deduplicate alertas
# ==============================================================================

def init_anomaly_table() -> None:
    """Cria a tabela anomaly_flags caso não exista."""
    with DB_LOCK:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_flags (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet      TEXT    NOT NULL,
                sub_conta   TEXT    NOT NULL,
                ambiente    TEXT    NOT NULL,
                anom_type   TEXT    NOT NULL,
                fired_at    TEXT    NOT NULL,
                detail      TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomaly_flags_lookup
            ON anomaly_flags (wallet, sub_conta, ambiente, anom_type, fired_at)
        """)
        conn.commit()


def _was_recently_fired(wallet: str, sub_conta: str, ambiente: str,
                        anom_type: str, hours: int = _COOLDOWN_H) -> bool:
    """Retorna True se esse tipo de anomalia já foi disparada no cooldown recente."""
    cutoff = (datetime.now(tz=TZ_BR) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    with DB_LOCK:
        row = cursor.execute("""
            SELECT 1 FROM anomaly_flags
            WHERE wallet=? AND sub_conta=? AND ambiente=? AND anom_type=?
              AND fired_at >= ?
            LIMIT 1
        """, (wallet, sub_conta, ambiente, anom_type, cutoff)).fetchone()
    return row is not None


def _mark_fired(wallet: str, sub_conta: str, ambiente: str,
                anom_type: str, detail: str = "") -> None:
    now_str = datetime.now(tz=TZ_BR).strftime("%Y-%m-%d %H:%M:%S")
    with DB_LOCK:
        conn.execute("""
            INSERT INTO anomaly_flags (wallet, sub_conta, ambiente, anom_type, fired_at, detail)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (wallet, sub_conta, ambiente, anom_type, now_str, detail))
        conn.commit()


# ==============================================================================
# 🔍 DETECÇÃO — 4 tipos de anomalia
# ==============================================================================

def _check_frequency_drop(wallet: str, sub_conta: str, ambiente: str) -> Optional[dict]:
    """
    Detecta queda >50% na frequência de abertura vs média dos 7 dias anteriores.
    Compara: operações nas últimas 24h vs média diária dos 7 dias anteriores.
    Retorna dict com detalhes ou None se não há anomalia.
    """
    now = datetime.now(tz=TZ_BR)
    cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_7d  = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_8d  = (now - timedelta(days=8)).strftime("%Y-%m-%d %H:%M:%S")

    try:
        with DB_LOCK:
            _r24 = cursor.execute("""
                SELECT COUNT(*) FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE ow.wallet=? AND o.sub_conta=? AND o.ambiente=?
                  AND o.tipo='Trade' AND o.data_hora >= ?
            """, (wallet, sub_conta, ambiente, cutoff_24h)).fetchone()
            count_24h = int(_r24[0]) if _r24 and _r24[0] is not None else 0

            _r7d = cursor.execute("""
                SELECT COUNT(*) FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE ow.wallet=? AND o.sub_conta=? AND o.ambiente=?
                  AND o.tipo='Trade' AND o.data_hora >= ? AND o.data_hora < ?
            """, (wallet, sub_conta, ambiente, cutoff_8d, cutoff_24h)).fetchone()
            count_7d = int(_r7d[0]) if _r7d and _r7d[0] is not None else 0
    except Exception as e:
        logger.debug("[anomaly] freq_drop query error: %s", e)
        return None

    if count_7d < 7:
        return None  # histórico insuficiente

    daily_avg_7d = count_7d / 7.0
    if daily_avg_7d < 1:
        return None

    drop_ratio = 1.0 - (count_24h / daily_avg_7d)
    if drop_ratio >= _FREQ_DROP_THRESH:
        return {
            "type": "frequency_drop",
            "count_24h": count_24h,
            "daily_avg_7d": round(daily_avg_7d, 1),
            "drop_pct": round(drop_ratio * 100, 1),
        }
    return None


def _check_inactivity(wallet: str, sub_conta: str, ambiente: str) -> Optional[dict]:
    """
    Detecta subconta sem nenhuma operação nas últimas 48h (mas com histórico).
    Só dispara se a subconta tem operações nos últimos 30 dias.
    """
    now = datetime.now(tz=TZ_BR)
    cutoff_48h = (now - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

    try:
        with DB_LOCK:
            count_recent = cursor.execute("""
                SELECT COUNT(*) FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE ow.wallet=? AND o.sub_conta=? AND o.ambiente=?
                  AND o.tipo='Trade' AND o.data_hora >= ?
            """, (wallet, sub_conta, ambiente, cutoff_48h)).fetchone()[0]

            count_30d = cursor.execute("""
                SELECT COUNT(*) FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE ow.wallet=? AND o.sub_conta=? AND o.ambiente=?
                  AND o.tipo='Trade' AND o.data_hora >= ?
            """, (wallet, sub_conta, ambiente, cutoff_30d)).fetchone()[0]
    except Exception as e:
        logger.debug("[anomaly] inactivity query error: %s", e)
        return None

    if count_30d < 5:
        return None  # subconta quase sem histórico

    if count_recent == 0:
        with DB_LOCK:
            last_row = cursor.execute("""
                SELECT o.data_hora FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE ow.wallet=? AND o.sub_conta=? AND o.ambiente=? AND o.tipo='Trade'
                ORDER BY o.data_hora DESC LIMIT 1
            """, (wallet, sub_conta, ambiente)).fetchone()
        last_trade = last_row[0] if last_row else "desconhecido"
        return {
            "type": "inactivity",
            "last_trade": last_trade,
        }
    return None


def _check_burst(wallet: str, sub_conta: str, ambiente: str) -> Optional[dict]:
    """
    Detecta rajada: >15 trades em 10 minutos (pode indicar loop descontrolado).
    """
    now = datetime.now(tz=TZ_BR)
    cutoff = (now - timedelta(minutes=_BURST_WINDOW_MIN)).strftime("%Y-%m-%d %H:%M:%S")

    try:
        with DB_LOCK:
            count = cursor.execute("""
                SELECT COUNT(*) FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE ow.wallet=? AND o.sub_conta=? AND o.ambiente=?
                  AND o.tipo='Trade' AND o.data_hora >= ?
            """, (wallet, sub_conta, ambiente, cutoff)).fetchone()[0]
    except Exception as e:
        logger.debug("[anomaly] burst query error: %s", e)
        return None

    if count >= _BURST_THRESH:
        return {
            "type": "burst",
            "count": count,
            "window_min": _BURST_WINDOW_MIN,
        }
    return None


def _check_loss_streak(wallet: str, sub_conta: str, ambiente: str) -> Optional[dict]:
    """
    Detecta ≥5 perdas consecutivas nas últimas operações.
    """
    try:
        with DB_LOCK:
            rows = cursor.execute("""
                SELECT o.resultado FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE ow.wallet=? AND o.sub_conta=? AND o.ambiente=? AND o.tipo='Trade'
                  AND o.resultado IS NOT NULL
                ORDER BY o.data_hora DESC LIMIT 20
            """, (wallet, sub_conta, ambiente)).fetchall()
    except Exception as e:
        logger.debug("[anomaly] loss_streak query error: %s", e)
        return None

    streak = 0
    for (res,) in rows:
        try:
            val = float(str(res).replace(",", "."))
        except Exception:
            break
        if val < 0:
            streak += 1
        else:
            break

    if streak >= _LOSS_STREAK_MIN:
        return {
            "type": "loss_streak",
            "streak": streak,
        }
    return None


# ==============================================================================
# 📬 NOTIFICAÇÕES
# ==============================================================================

def _notify_user(chat_id: int, wallet: str, sub_conta: str,
                 ambiente: str, anom: dict) -> None:
    """Notifica o usuário sobre variação de padrão ou inatividade."""
    env_icon = "🔵" if ambiente == "bd_v5" else "🟠"
    w_short = wallet[:6] + "..." + wallet[-4:] if len(wallet) > 10 else wallet

    if anom["type"] == "frequency_drop":
        text = (
            f"⚠️ <b>Variação no padrão de abertura</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 Subconta: <code>{sub_conta}</code> {env_icon} {ambiente}\n"
            f"🔑 Carteira: <code>{w_short}</code>\n\n"
            f"📉 Trades últimas 24h: <b>{anom['count_24h']}</b>\n"
            f"📊 Média diária 7d: <b>{anom['daily_avg_7d']}</b>\n"
            f"⬇️ Queda: <b>{anom['drop_pct']}%</b>\n\n"
            f"<i>Verifique se o protocolo está operando normalmente.</i>"
        )
    elif anom["type"] == "inactivity":
        text = (
            f"💤 <b>Subconta inativa</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 Subconta: <code>{sub_conta}</code> {env_icon} {ambiente}\n"
            f"🔑 Carteira: <code>{w_short}</code>\n\n"
            f"🕐 Última operação: <code>{anom['last_trade']}</code>\n"
            f"⏱️ Sem trades nas últimas 48h.\n\n"
            f"<i>Verifique se o protocolo está ativo e com saldo suficiente.</i>"
        )
    elif anom["type"] == "loss_streak":
        text = (
            f"📉 <b>Atenção: sequência de perdas</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 Subconta: <code>{sub_conta}</code> {env_icon} {ambiente}\n\n"
            f"⚠️ <b>{anom['streak']} perdas consecutivas</b> detectadas.\n"
            f"Revise a configuração ou aguarde nova oportunidade.\n\n"
            f"<i>Use 📊 mybdBook para acompanhar seu capital atual.</i>"
        )
    else:
        return

    try:
        send_html(chat_id, text)
    except Exception as e:
        logger.warning("[anomaly] falha ao notificar user %s: %s", chat_id, e)


def _notify_adm(wallet: str, sub_conta: str, ambiente: str,
                anom: dict, ai_audit: str | None = None) -> None:
    """Notifica todos os ADMs sobre burst ou loss_streak."""
    env_icon = "🔵" if ambiente == "bd_v5" else "🟠"
    w_short = wallet[:6] + "..." + wallet[-4:] if len(wallet) > 10 else wallet

    if anom["type"] == "burst":
        text = (
            f"🚨 <b>ALERTA: Rajada de operações</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 Subconta: <code>{sub_conta}</code> {env_icon} {ambiente}\n"
            f"🔑 Carteira: <code>{w_short}</code>\n\n"
            f"⚡ <b>{anom['count']} trades</b> em {anom['window_min']} minutos.\n\n"
            f"<i>Verifique se há loop descontrolado ou comportamento anômalo.</i>"
        )
    elif anom["type"] == "loss_streak":
        text = (
            f"🔴 <b>ALERTA: Streak de perdas</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 Subconta: <code>{sub_conta}</code> {env_icon} {ambiente}\n"
            f"🔑 Carteira: <code>{w_short}</code>\n\n"
            f"📉 <b>{anom['streak']} perdas consecutivas</b> detectadas.\n"
        )
        if ai_audit:
            text += f"\n🤖 <b>Auditoria IA:</b>\n{ai_audit}"
    else:
        return

    for adm_id in ADMIN_USER_IDS:
        try:
            send_html(int(adm_id), text)
            time.sleep(0.05)
        except Exception as e:
            logger.warning("[anomaly] falha ao notificar adm %s: %s", adm_id, e)
    # Sync para Discord (sem dados de wallet)
    severity = "critical" if anom["type"] == "burst" else "warning"
    notify_anomaly(text, severity=severity)


# ==============================================================================
# 🤖 IA AUDIT — loss streak
# ==============================================================================

def _ai_loss_streak_audit(wallet: str, sub_conta: str,
                          ambiente: str, streak: int) -> str:
    """
    Monta contexto com as últimas operações e pede à IA uma análise das causas
    do streak de perdas.
    """
    try:
        with DB_LOCK:
            rows = cursor.execute("""
                SELECT o.data_hora, o.token, o.resultado, o.gas_usd, o.sub_conta
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE ow.wallet=? AND o.sub_conta=? AND o.ambiente=? AND o.tipo='Trade'
                ORDER BY o.data_hora DESC LIMIT 10
            """, (wallet, sub_conta, ambiente)).fetchall()
    except Exception as e:
        logger.debug("[anomaly] ai_audit query error: %s", e)
        return ""

    if not rows:
        return ""

    ops_lines = []
    for data_hora, token, resultado, gas_usd, sc in rows:
        res_str = f"{float(resultado):+.4f}" if resultado else "N/A"
        g_str   = f"${float(gas_usd):.4f}" if gas_usd else "N/A"
        ops_lines.append(f"  {data_hora} | {token or '?'} | Resultado: {res_str} | Gas: {g_str}")

    ops_text = "\n".join(ops_lines)
    env_icon = "🔵" if ambiente == "bd_v5" else "🟠"

    prompt = (
        f"Você é o Motor de Auditoria da WEbdEX. Analise as últimas operações da subconta "
        f"'{sub_conta}' ({env_icon} {ambiente}) e identifique possíveis causas para "
        f"{streak} perdas consecutivas. Seja objetivo e técnico. Máximo 3 parágrafos.\n\n"
        f"Operações recentes (da mais recente para a mais antiga):\n{ops_text}"
    )

    try:
        result = ai_answer_ptbr(prompt)
        return result[:1200] if result else ""
    except Exception as e:
        logger.warning("[anomaly] IA audit falhou: %s", e)
        return ""


# ==============================================================================
# 🔄 CICLO PRINCIPAL
# ==============================================================================

def _anomaly_check_cycle() -> None:
    """
    Itera sobre todas as subcontas ativas (últimos 30 dias via protocol_ops ou operacoes)
    e executa os 4 checks de anomalia com cooldown por tipo.
    """
    now = datetime.now(tz=TZ_BR)
    cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

    # Obtém lista de (wallet, sub_conta, ambiente) com atividade recente
    try:
        with DB_LOCK:
            subcontas = cursor.execute("""
                SELECT DISTINCT ow.wallet, o.sub_conta, o.ambiente
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                WHERE o.tipo='Trade' AND o.data_hora >= ?
                  AND ow.wallet IS NOT NULL AND o.sub_conta IS NOT NULL
                  AND o.ambiente IS NOT NULL AND o.ambiente != 'UNKNOWN'
            """, (cutoff_30d,)).fetchall()
    except Exception as e:
        logger.warning("[anomaly] erro ao listar subcontas: %s", e)
        return

    if not subcontas:
        logger.debug("[anomaly] nenhuma subconta com atividade nos últimos 30d")
        return

    logger.info("[anomaly] verificando %d subcontas ativas...", len(subcontas))

    for (wallet, sub_conta, ambiente) in subcontas:
        # Busca chat_id do dono da carteira
        try:
            with DB_LOCK:
                row = cursor.execute(
                    "SELECT chat_id FROM users WHERE wallet=? AND chat_id IS NOT NULL LIMIT 1",
                    (wallet,)
                ).fetchone()
            chat_id = int(row[0]) if row else None
        except Exception:
            chat_id = None

        # ── 1. Frequency Drop → USER ─────────────────────────────────────────
        if chat_id and not _was_recently_fired(wallet, sub_conta, ambiente, "frequency_drop"):
            anom = _check_frequency_drop(wallet, sub_conta, ambiente)
            if anom:
                logger.info("[anomaly] frequency_drop detectado: %s / %s / %s — queda %.1f%%",
                            wallet[:10], sub_conta, ambiente, anom["drop_pct"])
                _notify_user(chat_id, wallet, sub_conta, ambiente, anom)
                _mark_fired(wallet, sub_conta, ambiente, "frequency_drop",
                            f"drop={anom['drop_pct']}%")

        # ── 2. Inactivity → USER ─────────────────────────────────────────────
        if chat_id and not _was_recently_fired(wallet, sub_conta, ambiente, "inactivity",
                                               hours=24):
            anom = _check_inactivity(wallet, sub_conta, ambiente)
            if anom:
                logger.info("[anomaly] inactivity detectado: %s / %s / %s — last=%s",
                            wallet[:10], sub_conta, ambiente, anom["last_trade"])
                _notify_user(chat_id, wallet, sub_conta, ambiente, anom)
                _mark_fired(wallet, sub_conta, ambiente, "inactivity",
                            f"last={anom['last_trade']}")

        # ── 3. Burst → ADM only ──────────────────────────────────────────────
        if not _was_recently_fired(wallet, sub_conta, ambiente, "burst", hours=1):
            anom = _check_burst(wallet, sub_conta, ambiente)
            if anom:
                logger.warning("[anomaly] burst detectado: %s / %s / %s — %d trades em %dmin",
                               wallet[:10], sub_conta, ambiente,
                               anom["count"], anom["window_min"])
                _notify_adm(wallet, sub_conta, ambiente, anom)
                _mark_fired(wallet, sub_conta, ambiente, "burst",
                            f"count={anom['count']}")

        # ── 4. Loss Streak → ADM + IA audit + USER (notificação suave) ─────
        if not _was_recently_fired(wallet, sub_conta, ambiente, "loss_streak", hours=8):
            anom = _check_loss_streak(wallet, sub_conta, ambiente)
            if anom:
                logger.warning("[anomaly] loss_streak detectado: %s / %s / %s — %d perdas",
                               wallet[:10], sub_conta, ambiente, anom["streak"])
                ai_audit = _ai_loss_streak_audit(wallet, sub_conta, ambiente, anom["streak"])
                _notify_adm(wallet, sub_conta, ambiente, anom, ai_audit=ai_audit)
                if chat_id:
                    _notify_user(chat_id, wallet, sub_conta, ambiente, anom)
                _mark_fired(wallet, sub_conta, ambiente, "loss_streak",
                            f"streak={anom['streak']}")

        time.sleep(0.1)  # evita rajada de queries


# ==============================================================================
# 🧵 WORKER — thread registrada no _THREAD_REGISTRY do webdex_main.py
# ==============================================================================

def anomaly_worker() -> None:
    """
    Worker de detecção de anomalias.
    Aguarda 5min no boot, depois roda a cada 15min.
    Registrado em webdex_main._THREAD_REGISTRY como 'anomaly_worker'.
    """
    logger.info("[anomaly] Worker iniciado — aguardando %ds (boot warmup)...", _BOOT_WAIT_S)
    time.sleep(_BOOT_WAIT_S)

    # Garante tabela existente (idempotente)
    try:
        init_anomaly_table()
        logger.info("[anomaly] Tabela anomaly_flags pronta.")
    except Exception as e:
        logger.error("[anomaly] Falha ao criar tabela anomaly_flags: %s", e)

    while True:
        try:
            _anomaly_check_cycle()
        except Exception as e:
            logger.error("[anomaly] Erro no ciclo de verificação: %s", e)
        time.sleep(_CYCLE_INTERVAL_S)
