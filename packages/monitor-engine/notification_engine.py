"""
notification_engine.py — Motor de Notificações Proativas WEbdEX → Discord

Detecta eventos de protocolo no banco SQLite e envia notificações via webhook
Discord sem esperar o usuário perguntar.

Eventos monitorados:
  - new_holder   → nova carteira ativa no protocolo
  - milestone    → TVL total cruzou um novo patamar ($10k incrementos)
  - anomaly      → nova anomalia registrada em anomaly_events

Cooldown: 30 min por tipo de evento (configável via COOLDOWN_SECS).
Estado persistido em JSON para sobreviver a restarts.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import requests

logger = logging.getLogger(__name__)

# ─── Design tokens com fallback (monitor-engine não tem orchestrator no path) ─
try:
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator", "discord"))
    from design_tokens import SUCCESS, WARNING, RED_LIGHT, PINK_LIGHT, ERROR, FOOTER_TEXT
    _sys.path.pop(0)
except ImportError:
    SUCCESS    = 0x00FFB2
    WARNING    = 0xFF8800
    RED_LIGHT  = 0xD90048
    PINK_LIGHT = 0xFB0491
    ERROR      = 0xFF4455
    FOOTER_TEXT = "WEbdEX Protocol · bdZinho"

# ─── Configuração ─────────────────────────────────────────────────────────────
STATE_FILE    = os.getenv("NOTIFICATION_STATE_FILE", "/app/notification_state.json")
COOLDOWN_SECS = int(os.getenv("NOTIFICATION_COOLDOWN_SECS", "1800"))  # 30 min

# Webhooks — reutiliza os do canal de conquistas e on-chain
_WEBHOOK_CONQUISTAS = os.getenv("DISCORD_WEBHOOK_CONQUISTAS", "").strip()
_WEBHOOK_ONCHAIN    = os.getenv("DISCORD_WEBHOOK_ONCHAIN", "").strip()

# Milestones de TVL: dispara a cada $10k (configurável)
TVL_MILESTONE_STEP = float(os.getenv("NOTIFICATION_TVL_STEP", "10000"))

# ─── Utilitários de estado ─────────────────────────────────────────────────────

def _load_state() -> dict:
    """Carrega estado persistido do arquivo JSON."""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.warning("[notif] load_state falhou: %s — reiniciando estado.", e)
    return {}


def _save_state(state: dict) -> None:
    """Persiste estado em JSON (atomic write via rename)."""
    try:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f)
        os.replace(tmp, STATE_FILE)
    except Exception as e:
        logger.warning("[notif] save_state falhou: %s", e)


def _can_notify(state: dict, event_type: str) -> bool:
    """Retorna True se cooldown expirou para este tipo de evento."""
    last = float(state.get(f"last_{event_type}", 0))
    return (time.time() - last) >= COOLDOWN_SECS


def _mark_notified(state: dict, event_type: str) -> None:
    state[f"last_{event_type}"] = time.time()


# ─── Envio de embed via webhook ────────────────────────────────────────────────

def _post_embed(webhook_url: str, title: str, description: str, color: int) -> bool:
    """Envia embed para webhook Discord. Retorna True em sucesso."""
    if not webhook_url:
        logger.debug("[notif] webhook URL vazia — notificação descartada.")
        return False
    payload = {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "footer": {"text": FOOTER_TEXT},
        }]
    }
    for attempt in range(3):
        try:
            resp = requests.post(webhook_url, json=payload, timeout=20)
            if resp.status_code in (200, 204):
                logger.info("[notif] Enviado: %s", title)
                return True
            if resp.status_code == 429:
                retry_after = float(resp.json().get("retry_after", 2.0))
                time.sleep(retry_after + 0.2)
                continue
            logger.warning("[notif] Webhook %s: %s", resp.status_code, resp.text[:120])
            return False
        except Exception as e:
            logger.warning("[notif] Tentativa %d/3 falhou: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(3)
    return False


# ─── Detectores de eventos ─────────────────────────────────────────────────────

def _check_new_holders(db_path: str, state: dict) -> list[dict]:
    """
    Detecta novas carteiras no protocolo (wallets em protocol_ops não vistas antes).
    Compara com conjunto persistido em state["known_wallets"].
    """
    events = []
    if not _can_notify(state, "new_holder"):
        return events
    try:
        with sqlite3.connect(db_path, timeout=5, check_same_thread=False) as db:
            rows = db.execute(
                "SELECT DISTINCT LOWER(wallet) FROM protocol_ops WHERE wallet <> ''"
            ).fetchall()
        current_wallets = {r[0] for r in rows if r[0]}
        known_wallets   = set(state.get("known_wallets", []))

        new_ones = current_wallets - known_wallets
        if new_ones and known_wallets:  # só notifica se já tinha estado anterior
            events.append({
                "type":        "new_holder",
                "webhook":     _WEBHOOK_CONQUISTAS,
                "color":       RED_LIGHT,
                "title":       "🎉 Novo holder no protocolo!",
                "description": (
                    f"**{len(new_ones)}** nova{'s' if len(new_ones) > 1 else ''} "
                    f"carteira{'s' if len(new_ones) > 1 else ''} entraram no WEbdEX.\n"
                    f"Total ativo: **{len(current_wallets)}** carteiras."
                ),
            })

        # Sempre atualiza a lista conhecida
        state["known_wallets"] = list(current_wallets)

    except Exception as e:
        logger.debug("[notif] check_new_holders falhou: %s", e)
    return events


def _check_milestones(db_path: str, state: dict) -> list[dict]:
    """
    Detecta quando o TVL total cruzou um novo patamar ($10k steps).
    Usa capital_cache — soma total_usd de todos os registros.
    """
    events = []
    if not _can_notify(state, "milestone"):
        return events
    try:
        with sqlite3.connect(db_path, timeout=5, check_same_thread=False) as db:
            row = db.execute("SELECT SUM(total_usd) FROM capital_cache").fetchone()
        if not row or row[0] is None:
            return events

        tvl = float(row[0])
        last_milestone = float(state.get("last_milestone_tvl", 0))
        # Qual é o maior patamar cruzado agora?
        current_tier = (tvl // TVL_MILESTONE_STEP) * TVL_MILESTONE_STEP

        if current_tier > last_milestone and current_tier > 0:
            events.append({
                "type":        "milestone",
                "webhook":     _WEBHOOK_CONQUISTAS,
                "color":       PINK_LIGHT,
                "title":       "🏆 Milestone atingido!",
                "description": (
                    f"O WEbdEX ultrapassou **${current_tier:,.0f}** em TVL!\n"
                    f"TVL atual: **${tvl:,.2f}**"
                ),
            })
            state["last_milestone_tvl"] = current_tier

    except Exception as e:
        logger.debug("[notif] check_milestones falhou: %s", e)
    return events


def _check_anomalies(db_path: str, state: dict) -> list[dict]:
    """
    Detecta novas anomalias em anomaly_events (tabela pode não existir — graceful).
    Persiste último ID visto para não renotificar.
    """
    events = []
    if not _can_notify(state, "anomaly"):
        return events
    try:
        with sqlite3.connect(db_path, timeout=5, check_same_thread=False) as db:
            # Verifica se a tabela existe
            tbl = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='anomaly_events'"
            ).fetchone()
            if not tbl:
                return events

            last_id = int(state.get("last_anomaly_id", 0))
            rows = db.execute(
                "SELECT id, type, description, ts FROM anomaly_events WHERE id > ? ORDER BY id DESC LIMIT 5",
                (last_id,)
            ).fetchall()

        if not rows:
            return events

        newest_id = max(r[0] for r in rows)
        count = len(rows)
        latest_type = rows[0][1] if rows[0][1] else "desconhecida"
        latest_desc = rows[0][2] if rows[0][2] else ""

        events.append({
            "type":        "anomaly",
            "webhook":     _WEBHOOK_ONCHAIN,
            "color":       ERROR,
            "title":       f"🚨 Alerta de Anomalia ({count} nova{'s' if count > 1 else ''})",
            "description": (
                f"Tipo: `{latest_type}`\n"
                + (f"{latest_desc[:200]}\n" if latest_desc else "")
                + f"\nVerifique o painel on-chain."
            ),
        })
        state["last_anomaly_id"] = newest_id

    except Exception as e:
        logger.debug("[notif] check_anomalies falhou: %s", e)
    return events


# ─── API pública ───────────────────────────────────────────────────────────────

def run_notification_check(db_path: str) -> int:
    """
    Executa todos os checks e envia notificações necessárias.
    Retorna o número de notificações enviadas.
    """
    state = _load_state()
    sent  = 0

    all_events: list[dict] = []
    all_events += _check_new_holders(db_path, state)
    all_events += _check_milestones(db_path, state)
    all_events += _check_anomalies(db_path, state)

    for evt in all_events:
        ok = _post_embed(evt["webhook"], evt["title"], evt["description"], evt["color"])
        if ok:
            _mark_notified(state, evt["type"])
            sent += 1

    if all_events:
        _save_state(state)
    elif state != _load_state():
        # Estado atualizado por um detector mesmo sem envio (ex: known_wallets)
        _save_state(state)

    return sent


# ─── Worker loop (registrado em webdex_main.py) ───────────────────────────────

_WORKER_INTERVAL = int(os.getenv("NOTIFICATION_INTERVAL_SECS", "300"))  # 5 minutos


def notification_engine_worker() -> None:
    """
    Worker periódico — inicia com delay de 90s para o sistema carregar,
    depois executa run_notification_check a cada 5 minutos.
    Registrado em webdex_main._THREAD_REGISTRY como daemon thread.
    """
    import os as _os
    db_path = _os.getenv("SQLITE_DB_PATH", "/app/webdex.db")
    logger.info("[notif] Motor de notificações proativas: Ativo... (intervalo=%ds)", _WORKER_INTERVAL)
    time.sleep(90)  # aguarda sistema inicializar
    while True:
        try:
            n = run_notification_check(db_path)
            if n:
                logger.info("[notif] %d notificação(ões) enviada(s).", n)
        except Exception as e:
            logger.warning("[notif] Erro no worker: %s", e)
        time.sleep(_WORKER_INTERVAL)
