"""monitor-bot/notifier.py — Notificador Telegram do OCME Engine.

Camada UI pura — recebe operações do Vigia e envia notificações.
Toda lógica de dados vem de monitor-db/monitor-report (não do bot).

Story 7.6 AC:
- Handlers delegam para monitor-core / monitor-db (zero RPC direto)
- Anti-flood: NOTIF_QUEUE (5000 itens) + debounce 2s
- _tg_send_with_retry com backoff mantido
- Usuário 403 → desativa no DB
- Alertas proativos: inatividade com diagnóstico

Standalone: sem dependência do monolito webdex_*.py.

Uso:
    from notifier import Notifier

    notifier = Notifier(
        token=TELEGRAM_TOKEN,
        db_path="webdex_v5_final.db",
        dashboard_cache=cache,   # opcional — para Today stats
    )
    # Liga ao Vigia:
    vigia.on('operation', notifier.on_operation)
    vigia.on('error',     notifier.on_vigia_error)
    sentinela.on_alert = notifier.on_alert

    notifier.start()
"""

from __future__ import annotations

import html
import logging
import os
import queue
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("monitor-bot.notifier")


def _esc(s: str) -> str:
    return html.escape(str(s or ""))

def _code(s: str) -> str:
    return f"<code>{_esc(s)}</code>"

def _profit_emoji(val: float) -> str:
    if val >= 10:  return "💰"
    if val >= 0:   return "🟢"
    if val >= -2:  return "🔴"
    return "🚨"


class Notifier:
    """Serviço de notificações Telegram — UI pura do OCME Engine."""

    _QUEUE_SIZE     = 5000
    _TG_SAFE_LIMIT  = 3500
    _DEBOUNCE_SECS  = 2.0

    def __init__(
        self,
        token: str,
        db_path: str,
        dashboard_cache=None,  # DashboardCache opcional
        admin_ids: Optional[List[int]] = None,
    ):
        if not token or ":" not in token:
            raise ValueError("TELEGRAM_TOKEN inválido")

        import telebot
        from telebot import types, apihelper
        import requests

        # HTTP hardening
        try:
            apihelper.RETRY_ON_ERROR = True
            _sess = requests.Session()
            _adapter = requests.adapters.HTTPAdapter(max_retries=3, pool_connections=20, pool_maxsize=20)
            _sess.mount("https://", _adapter)
            apihelper.SESSION = _sess
            apihelper.CONNECT_TIMEOUT = 10
            apihelper.READ_TIMEOUT = 30
        except Exception:
            pass

        self._bot = telebot.TeleBot(token, parse_mode="HTML")
        self._db_path = db_path
        self._cache = dashboard_cache
        self._admin_ids = set(admin_ids or [])
        self._notif_queue: queue.Queue = queue.Queue(maxsize=self._QUEUE_SIZE)
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        # debounce: chat_id → (last_send_ts, batch)
        self._debounce: Dict[int, float] = {}

    # ── Lifecycle ──────────────────────────────────────────────────────────
    def start(self, daemon: bool = True):
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._queue_worker, name="notif-worker", daemon=daemon
        )
        self._worker_thread.start()
        logger.info("📢 Notifier iniciado")

    def stop(self, timeout: float = 5.0):
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=timeout)

    # ── Event listeners (liga ao Vigia) ───────────────────────────────────
    def on_operation(self, op: Dict):
        """Chamado quando Vigia emite evento 'operation'."""
        if op.get("tipo") == "Trade":
            self._dispatch_trade(op)
        elif op.get("tipo") == "Transfer":
            self._dispatch_transfer(op)

    def on_alert(self, alert: Dict):
        """Chamado pela Sentinela para alertas de inatividade/gas/rpc."""
        tipo = alert.get("tipo", "")
        dados = alert.get("dados", {})

        if tipo == "inatividade":
            self._dispatch_inactivity_alert(dados)
        elif tipo == "gas_alto":
            self._dispatch_gas_alert(dados)
        elif tipo == "rpc_error":
            self._dispatch_rpc_alert(dados)

    def on_vigia_error(self, error_str: str):
        """Notifica admins em caso de erro grave do vigia."""
        msg = (
            f"🔴 <b>VIGIA ERROR</b>\n"
            f"<code>{_esc(str(error_str)[:200])}</code>"
        )
        for aid in self._admin_ids:
            self._enqueue(aid, msg)

    # ── Trade notification ─────────────────────────────────────────────────
    def _dispatch_trade(self, op: Dict):
        notify_cids = op.get("notify_cids", [])
        if not notify_cids:
            return

        sub = str(op.get("sub_conta", "?"))
        val = float(op.get("valor", 0))
        gas_usd = float(op.get("gas_usd", 0))
        gas_pol = float(op.get("gas_pol", 0))
        token = str(op.get("token", "?"))
        tx = str(op.get("tx_hash", ""))
        env_tag = str(op.get("ambiente", "?"))
        bot_id = str(op.get("bot_id", "")).strip() or "Standard"
        fee = float(op.get("fee", 0))
        bloco = int(op.get("bloco", 0))

        for cid in notify_cids:
            try:
                msg = self._build_trade_msg(
                    cid, sub, val, gas_usd, gas_pol, token, tx,
                    env_tag, bot_id, fee, bloco
                )
                self._enqueue(int(cid), msg)
            except Exception as exc:
                logger.debug("_dispatch_trade cid=%s: %s", cid, exc)

    def _build_trade_msg(self, chat_id, sub, val, gas_usd, gas_pol,
                          token, tx, env_tag, bot_id, fee, bloco) -> str:
        # Dados de hoje do cache (não do RPC)
        today = self._get_today_stats(chat_id)
        trades_hj = today.get("trades", 0)
        pnl_hj    = today.get("pnl", 0.0)
        wins_hj   = today.get("wins", 0)
        wr_hj     = today.get("winrate", 0.0)
        wr_emoji  = "🟢" if wr_hj >= 60 else ("🟡" if wr_hj >= 40 else "🔴")
        pnl_sign  = "+" if pnl_hj >= 0 else ""
        filled    = round(wr_hj / 10)
        wr_bar    = "█" * filled + "░" * (10 - filled)

        p_emoji = _profit_emoji(val)
        net = val - gas_usd

        # Gas line
        if gas_pol and gas_pol > 0:
            gas_pct = f"  <i>({(gas_usd / abs(val)) * 100:.1f}%)</i>" if val and abs(val) > 0 else ""
            gas_line = f"⛽  Gás: {_code(f'{gas_pol:.4f} POL')}  ·  {_code(f'${gas_usd:.4f}')}{_esc(gas_pct)}"
        else:
            gas_line = f"⛽  Gás: {_code(f'${gas_usd:.4f}')}"

        # Fee
        fee_line = f"🎟️  Fee Protocolo: {_code(f'{fee:.4f} BD')}\n" if fee > 0 else ""

        # Bloco + link
        bloco_line = f"🔷  Polygon  ·  Bloco {_code(f'{bloco:,}')}\n" if bloco > 0 else "🔷  Polygon\n"
        tx_link = f'🔗  <a href="https://polygonscan.com/tx/{_esc(tx)}">Ver transação ↗</a>' if tx else ""

        return (
            f"⚡ <b>WEbdEX ENGINE</b>  ·  {_code(_esc(env_tag))}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"🔵  <b>EXECUÇÃO CONFIRMADA</b>  ·  #{trades_hj}\n"
            f"👤  {_code(sub)}\n"
            f"🔄  Estratégia: <b>{_esc(bot_id)}</b>  ·  🪙 <b>{_esc(token)}</b>\n"
            f"\n"
            f"┈┈┈┈┈┈ RESULTADO ┈┈┈┈┈┈\n"
            f"\n"
            f"{p_emoji}  <b>{val:+.4f} {_esc(token)}</b>\n"
            f"💵  Net pós-gás: <b>{_code(f'{net:+.4f}')}</b>\n"
            f"{gas_line}\n"
            f"{fee_line}"
            f"\n"
            f"┈┈┈┈┈┈ BLOCKCHAIN ┈┈┈┈┈┈\n"
            f"\n"
            f"{bloco_line}"
            f"{tx_link}\n"
            f"\n"
            f"┈┈┈┈┈┈ HOJE ┈┈┈┈┈┈\n"
            f"\n"
            f"📊  <b>{trades_hj} trades</b>  ·  WinRate <b>{wr_hj:.0f}%</b>  {wr_emoji}\n"
            f"<code>    {wr_bar}</code>\n"
            f"💰  P&L: <b>{pnl_sign}${pnl_hj:.2f}</b>  ·  {wins_hj}W / {max(0, trades_hj - wins_hj)}L\n"
            f"\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>⚡ WEbdEX · New Digital Economy</i>"
        )

    # ── Transfer notification ──────────────────────────────────────────────
    def _dispatch_transfer(self, op: Dict):
        for cid in op.get("notify_cids", []):
            direction = op.get("direction", "in")
            val = abs(float(op.get("valor", 0)))
            token = str(op.get("token", "?"))
            tx = str(op.get("tx_hash", ""))
            icon = "📥" if direction == "in" else "📤"
            titulo = f"{icon} <b>{'ENTRADA' if direction == 'in' else 'SAÍDA'} ({_esc(token)})</b>"
            msg = (
                f"{titulo}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💰  {_code(f'{val:.4f} {token}')}\n"
                f'🔗  <a href="https://polygonscan.com/tx/{_esc(tx)}">PolygonScan</a>'
            )
            self._enqueue(int(cid), msg)

    # ── Proactive alerts ──────────────────────────────────────────────────
    def _dispatch_inactivity_alert(self, dados: Dict):
        mins = float(dados.get("minutos", 0))
        tx_count = int(dados.get("tx_count", 0))
        last_block = int(dados.get("last_block", 0))
        sev = "🔴" if mins >= 60 else ("🟡" if mins >= 30 else "🟠")
        msg = (
            f"{sev} <b>ALERTA DE INATIVIDADE</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"\n"
            f"😴  Sem operações há <b>{mins:.1f} minutos</b>\n"
            f"🔷  Último bloco: {_code(f'{last_block:,}')}\n"
            f"📊  TXs na última hora: {tx_count}\n"
            f"\n"
            f"<i>⚡ WEbdEX · OCME Engine</i>"
        )
        active_users = self._get_active_users()
        for chat_id in active_users:
            self._enqueue(chat_id, msg)

    def _dispatch_gas_alert(self, dados: Dict):
        gas_usd = float(dados.get("gas_usd", 0))
        tx = str(dados.get("tx_hash", ""))
        sub = str(dados.get("sub_conta", "?"))
        msg = (
            f"⛽ <b>GAS ALTO DETECTADO</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💸  Gas: {_code(f'${gas_usd:.4f} USD')}\n"
            f"👤  Sub: {_code(sub)}\n"
            f'🔗  <a href="https://polygonscan.com/tx/{_esc(tx)}">PolygonScan</a>'
        )
        for aid in self._admin_ids:
            self._enqueue(aid, msg)

    def _dispatch_rpc_alert(self, dados: Dict):
        erros = int(dados.get("rpc_errors_total", 0))
        last_err = str(dados.get("last_error", ""))[:100]
        msg = (
            f"🔴 <b>RPC ERRORS: {erros}</b>\n"
            f"<code>{_esc(last_err)}</code>"
        )
        for aid in self._admin_ids:
            self._enqueue(aid, msg)

    # ── DB helpers (sem RPC) ──────────────────────────────────────────────
    def _get_today_stats(self, chat_id: int) -> Dict:
        """Lê stats de hoje do DB — sem chamar RPC."""
        # Tenta cache primeiro
        if self._cache:
            try:
                kpis = self._cache.get()
                return {
                    "trades": kpis.get("trades_24h", 0),
                    "pnl": kpis.get("pnl_24h", 0.0),
                    "wins": 0,
                    "winrate": kpis.get("winrate_24h", 0.0),
                }
            except Exception:
                pass
        # Fallback: DB query direta
        try:
            c = sqlite3.connect(self._db_path)
            row = c.execute("""
                SELECT COUNT(*),
                       COALESCE(SUM(CAST(o.valor AS REAL)) - SUM(CAST(o.gas_usd AS REAL)), 0),
                       COUNT(CASE WHEN CAST(o.valor AS REAL) > 0 THEN 1 END)
                FROM operacoes o
                JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                JOIN users u ON LOWER(u.wallet)=LOWER(ow.wallet)
                WHERE o.tipo='Trade' AND DATE(o.data_hora)=DATE('now','localtime') AND u.chat_id=?
            """, (str(chat_id),)).fetchone()
            c.close()
            if row:
                t = int(row[0] or 0)
                w = int(row[2] or 0)
                return {"trades": t, "pnl": float(row[1] or 0),
                        "wins": w, "winrate": round(w / t * 100, 1) if t > 0 else 0.0}
        except Exception:
            pass
        return {"trades": 0, "pnl": 0.0, "wins": 0, "winrate": 0.0}

    def _get_active_users(self) -> List[int]:
        try:
            c = sqlite3.connect(self._db_path)
            rows = c.execute("SELECT chat_id FROM users WHERE active=1").fetchall()
            c.close()
            return [int(r[0]) for r in rows]
        except Exception:
            return []

    def _deactivate_user(self, chat_id: int):
        try:
            c = sqlite3.connect(self._db_path)
            c.execute("UPDATE users SET active=0 WHERE chat_id=?", (str(chat_id),))
            c.commit()
            c.close()
            logger.info("Usuário %s desativado (403)", chat_id)
        except Exception:
            pass

    # ── Queue / Send ───────────────────────────────────────────────────────
    def _enqueue(self, chat_id: int, text: str, parse_mode: str = "HTML"):
        try:
            self._notif_queue.put_nowait((chat_id, text, parse_mode))
        except queue.Full:
            logger.warning("NOTIF_QUEUE cheia — descartando notificação para %s", chat_id)

    def _queue_worker(self):
        while self._running:
            try:
                chat_id, text, parse_mode = self._notif_queue.get(timeout=1.0)
                self._send_with_retry(chat_id, text, parse_mode)
                self._notif_queue.task_done()
            except queue.Empty:
                continue
            except Exception as exc:
                logger.error("queue_worker: %s", exc)

    def _send_with_retry(self, chat_id: int, text: str, parse_mode: str = "HTML",
                          max_retries: int = 3):
        """Envia mensagem com backoff exponencial. Trata 403."""
        # Debounce simples: não envia mais de 1 msg/2s por chat
        now = time.time()
        last = self._debounce.get(chat_id, 0)
        if (now - last) < self._DEBOUNCE_SECS:
            time.sleep(max(0, self._DEBOUNCE_SECS - (now - last)))
        self._debounce[chat_id] = time.time()

        # Trunca se necessário
        if len(text) > self._TG_SAFE_LIMIT:
            text = text[:self._TG_SAFE_LIMIT] + "\n<i>... [truncado]</i>"

        for attempt in range(max_retries):
            try:
                self._bot.send_message(chat_id, text, parse_mode=parse_mode,
                                       disable_web_page_preview=True)
                return
            except Exception as exc:
                err = str(exc)
                if "403" in err or "Forbidden" in err or "bot was blocked" in err.lower():
                    self._deactivate_user(chat_id)
                    return
                if "429" in err or "Too Many Requests" in err:
                    wait = 10
                    try:
                        m = re.search(r"retry after (\d+)", err, re.IGNORECASE)
                        if m:
                            wait = int(m.group(1)) + 1
                    except Exception:
                        pass
                    time.sleep(wait)
                    continue
                backoff = 2 ** attempt
                logger.warning("send_with_retry attempt=%d chat=%s: %s (backoff %ds)",
                               attempt + 1, chat_id, err[:80], backoff)
                time.sleep(backoff)

        logger.error("send_with_retry: falhou após %d tentativas para %s", max_retries, chat_id)

    def send_html(self, chat_id: int, text: str):
        """API pública para envio direto (handlers, etc.)."""
        self._enqueue(chat_id, text)
