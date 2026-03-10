# ==============================================================================
# monitor_bot/bot.py — Telegram Bot: UI e notificações OCME bd
# Story 7.6 — inspirado no design WEbdEX V30
#
# Princípio: handlers NÃO fazem lógica — delegam para os módulos do motor.
# CLI é a fonte da verdade. Bot é o canal de notificação.
# ==============================================================================
from __future__ import annotations

import logging
import queue
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Any

import requests
import telebot
from telebot import apihelper, types

import config as cfg
from monitor_db.migrator import migrate
from monitor_db.queries import (
    config_get, config_set,
    user_get, user_touch, user_upsert, user_get_pending,
    users_by_wallet, users_all_active, users_stats,
    ops_summary, ops_best_subconta, ops_last_inactivity_minutes,
)
from monitor_report.dashboard_cache import DashboardCache
from monitor_ai.ai_engine import answer, answer_inactivity_diagnostic

logger = logging.getLogger('monitor.bot')

# ── Telegram hardening ────────────────────────────────────────────────────────
apihelper.RETRY_ON_ERROR = True
_sess = requests.Session()
_adapter = requests.adapters.HTTPAdapter(max_retries=3, pool_connections=20, pool_maxsize=20)
_sess.mount('https://', _adapter)
apihelper.SESSION = _sess
apihelper.CONNECT_TIMEOUT = 10
apihelper.READ_TIMEOUT = 30

# ── Fila de notificações (anti-flood) ─────────────────────────────────────────
NOTIF_QUEUE: queue.Queue = queue.Queue(maxsize=5000)
_TG_SAFE_LIMIT = 3500


# ── Helpers HTML (estilo WEbdEX) ─────────────────────────────────────────────
def _c(t: str) -> str:
    '''Envolve em <code>.'''
    return f'<code>{t}</code>'


def _b(t: str) -> str:
    return f'<b>{t}</b>'


def _esc(t: Any) -> str:
    return str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _time_ago(ts: int | None) -> str:
    if not ts:
        return '-'
    delta = max(0, int(time.time()) - ts)
    mins = delta // 60
    if mins < 1:
        return 'agora'
    if mins < 60:
        return f'{mins} min atrás'
    if mins < 1440:
        return f'{mins // 60} h atrás'
    return f'{mins // 1440} d atrás'


class _ExceptionHandler(telebot.ExceptionHandler):
    def handle(self, exc: Exception) -> bool:
        err = str(exc)
        if '409' in err or 'Conflict' in err:
            logger.warning('409 Conflict: outro bot ativo. Aguardando 15s...')
            time.sleep(15)
            return True
        if '502' in err or 'Bad Gateway' in err:
            time.sleep(10)
            return True
        if '429' in err or 'Too Many Requests' in err:
            m = re.search(r'retry after (\d+)', err, re.I)
            time.sleep(int(m.group(1)) + 1 if m else 10)
            return True
        if any(x in err for x in ['ConnectionReset', 'RemoteDisconnected', 'ReadTimeout']):
            time.sleep(8)
            return True
        return False


class MonitorBot:
    '''Bot Telegram do OCME bd Monitor Engine.'''

    def __init__(
        self,
        conn: sqlite3.Connection,
        vigia: Any | None = None,
        sentinela: Any | None = None,
        dashboard_cache: DashboardCache | None = None,
    ):
        self._conn  = conn
        self._vigia = vigia
        self._sent  = sentinela
        self._cache = dashboard_cache or DashboardCache(conn, vigia)
        self._bot   = telebot.TeleBot(
            cfg.TELEGRAM_TOKEN,
            parse_mode='HTML',
            exception_handler=_ExceptionHandler(),
            threaded=True,
        )
        # Buffer de ops para resumo agrupado (30 min)
        self._op_buffer: list[dict]  = []
        self._op_last_flush: float   = time.time()
        self._op_flush_interval: float = 1800.0   # 30 minutos
        self._op_lock = threading.Lock()

        self._notif_worker_thread: threading.Thread | None = None
        self._register_handlers()

        if sentinela:
            sentinela.on_alert(self._on_sentinel_alert)
        if vigia:
            vigia.on('operation', self._on_vigia_operation)

    # ═══════════════════════════════════════════════════════════════════════════
    # KEYBOARDS
    # ═══════════════════════════════════════════════════════════════════════════

    def _main_kb(self, chat_id: int) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row('🔌 Conectar', '▶️ Ativar', '⏸️ Pausar')
        kb.row('📈 Dashboard', '📊 Relatório', '🩺 Saúde')
        kb.row('🧠 IA', '🗓️ Período', '🔎 Wallet Info')
        kb.row('📡 Status', '⚙️ Config')
        if chat_id in cfg.ADMIN_USER_IDS:
            kb.row('🛠️ ADM')
        return kb

    def _adm_kb(self) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row('👥 Usuários', '📊 Stats Motor')
        kb.row('🤖 IA ON', '🤖 IA OFF', '🔐 IA Só ADM')
        kb.row('📢 Broadcast', '🔄 Reset Vigia')
        kb.row('🔙 Menu')
        return kb

    def _config_kb(self) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row('🌐 AG_C_bd', '🌐 bd_v5')
        kb.row('⏱️ 24h', '⏱️ 7d', '⏱️ 30d')
        kb.row('🔙 Menu')
        return kb

    def _periodo_kb(self) -> types.ReplyKeyboardMarkup:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row('⏱️ 24h', '⏱️ 7d', '⏱️ 30d')
        kb.row('🔙 Menu')
        return kb

    def _known_buttons(self) -> set[str]:
        return {
            '🔌 Conectar', '▶️ Ativar', '⏸️ Pausar',
            '📈 Dashboard', '📊 Relatório', '🩺 Saúde',
            '🧠 IA', '🗓️ Período', '🔎 Wallet Info',
            '📡 Status', '⚙️ Config', '🛠️ ADM',
            '👥 Usuários', '📊 Stats Motor',
            '🤖 IA ON', '🤖 IA OFF', '🔐 IA Só ADM',
            '📢 Broadcast', '🔄 Reset Vigia',
            '🌐 AG_C_bd', '🌐 bd_v5',
            '⏱️ 24h', '⏱️ 7d', '⏱️ 30d',
            '💬 Perguntar à IA', '📊 Analisar desempenho',
            '🔙 Menu',
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _register_handlers(self) -> None:
        bot = self._bot

        # ── /start ───────────────────────────────────────────────────────────
        @bot.message_handler(commands=['start'])
        def cmd_start(m: types.Message) -> None:
            logger.info('/start de @%s (chat_id=%d)', m.from_user.username or '?', m.chat.id)
            user_upsert(self._conn, m.chat.id, username=m.from_user.username)
            self._send(m.chat.id,
                '👋 <b>WEbdEX — OCME bd Monitor Engine</b>\n\n'
                'Sistema de monitoramento DeFi na Polygon.\n'
                'Use <b>🔌 Conectar</b> para vincular sua wallet e\n'
                'ativar o monitoramento personalizado.',
                self._main_kb(m.chat.id))

        # ── 🔌 Conectar ──────────────────────────────────────────────────────
        @bot.message_handler(func=lambda m: (m.text or '').strip() == '🔌 Conectar')
        def cmd_conectar(m: types.Message) -> None:
            user_upsert(self._conn, m.chat.id, username=m.from_user.username, pending='ASK_WALLET')
            self._send(m.chat.id,
                '🍰 <b>CONFIGURAÇÃO</b>\n\n'
                'Passo 1: Envie sua <b>Wallet</b> (0x...)\n\n'
                'Digite <b>cancelar</b> para sair.',
                types.ReplyKeyboardRemove())

        # ── ▶️ Ativar ────────────────────────────────────────────────────────
        @bot.message_handler(func=lambda m: (m.text or '').strip() == '▶️ Ativar')
        def cmd_ativar(m: types.Message) -> None:
            user_upsert(self._conn, m.chat.id, active=1)
            self._send(m.chat.id,
                '▶️ Monitoramento <b>ATIVADO</b>.\nVocê receberá notificações das suas operações.',
                self._main_kb(m.chat.id))

        # ── ⏸️ Pausar ────────────────────────────────────────────────────────
        @bot.message_handler(func=lambda m: (m.text or '').strip() == '⏸️ Pausar')
        def cmd_pausar(m: types.Message) -> None:
            user_upsert(self._conn, m.chat.id, active=0)
            self._send(m.chat.id,
                '⏸️ Monitoramento <b>PAUSADO</b>.\nUse ▶️ Ativar para retomar.',
                self._main_kb(m.chat.id))

        # ── 📈 Dashboard ─────────────────────────────────────────────────────
        @bot.message_handler(func=lambda m: (m.text or '').strip() == '📈 Dashboard')
        def cmd_dashboard(m: types.Message) -> None:
            u = user_get(self._conn, m.chat.id) or {}
            wallet = u.get('wallet') or cfg.WALLET_ADDRESS
            period = u.get('periodo', '24h')
            env    = u.get('env')

            if not wallet:
                self._send(m.chat.id, '⚠️ Conecte sua wallet primeiro: use 🔌 Conectar', self._main_kb(m.chat.id))
                return

            data = self._cache.get(wallet=wallet, period=period, env=env)
            age  = data.get('_cache_age_s', 0)
            inactiv = data.get('inactivity_min', 0)
            inactiv_icon = '⚠️' if inactiv > cfg.LIMITE_INATIV_MIN else '✅'
            best  = data.get('best_subconta')
            best_line = f'\n🏆 Melhor sub: {_c(best["id"])} +${best["profit"]:,.2f}' if best else ''
            env_tag = f'({_esc(env)})' if env else ''

            msg = (
                f'📈 <b>Dashboard PRO — {_esc(period)}</b> {env_tag}\n'
                f'────────────────────\n'
                f'💰 Lucro líquido: <b>${data["profit_net"]:,.2f}</b>\n'
                f'🔄 Trades: {data["trades"]:,}\n'
                f'⛽ Gas médio: ${data["gas_avg"]:,.6f}\n'
                f'{inactiv_icon} Inatividade: {inactiv:.0f} min'
                f'{best_line}\n'
                f'────────────────────\n'
                f'<i>🕒 Cache: {age:.1f}s | {data.get("_computed_at", "")}</i>'
            )
            self._send(m.chat.id, msg, self._main_kb(m.chat.id))

        # ── 📊 Relatório ─────────────────────────────────────────────────────
        @bot.message_handler(func=lambda m: (m.text or '').strip() == '📊 Relatório')
        def cmd_relatorio(m: types.Message) -> None:
            u = user_get(self._conn, m.chat.id) or {}
            wallet = u.get('wallet') or cfg.WALLET_ADDRESS
            period = u.get('periodo', '24h')
            hours  = {'24h': 24, '7d': 168, '30d': 720}.get(period, 24)

            if not wallet:
                self._send(m.chat.id, '⚠️ Conecte sua wallet primeiro: use 🔌 Conectar', self._main_kb(m.chat.id))
                return

            summary = ops_summary(self._conn, wallet, hours=hours)
            best    = ops_best_subconta(self._conn, wallet, hours=hours)
            inactiv = ops_last_inactivity_minutes(self._conn, wallet)
            best_line = f'\n🏆 Melhor: {_c(best["id"])} +${best["profit"]:,.2f}' if best else ''

            msg = (
                f'📊 <b>Relatório {_esc(period)}</b>\n'
                f'────────────────────\n'
                f'📌 Trades:        {summary["count"]:,}\n'
                f'💹 Lucro bruto:   ${summary["profit_gross"]:,.4f}\n'
                f'⛽ Gas gasto:     ${summary["gas_total"]:,.4f}\n'
                f'<b>💰 Lucro líquido: ${summary["profit_net"]:,.4f}</b>'
                f'{best_line}\n'
                f'⏳ Inatividade:   {inactiv:.0f} min'
            )
            self._send(m.chat.id, msg, self._main_kb(m.chat.id))

        # ── 🩺 Saúde ─────────────────────────────────────────────────────────
        @bot.message_handler(func=lambda m: (m.text or '').strip() == '🩺 Saúde')
        def cmd_saude(m: types.Message) -> None:
            try:
                from monitor_chain.block_fetcher import BlockFetcher
                fetcher = BlockFetcher(cfg.RPC_URL, chunk_size=1)
                current = fetcher.get_latest_block()
                rpc_ok  = '✅'
            except Exception:
                current = 0
                rpc_ok  = '❌'

            last = int(config_get(self._conn, 'vigia_last_block', '0') or 0)
            lag  = max(0, current - last)
            lag_icon = '✅' if lag < 10 else ('⚠️' if lag < 100 else '🔴')
            vigia_running = self._vigia and getattr(self._vigia, '_running', False)

            msg = (
                f'🩺 <b>Saúde do Sistema</b>\n'
                f'────────────────────\n'
                f'{"✅" if vigia_running else "🔴"} Vigia: {"ATIVO" if vigia_running else "PARADO"}\n'
                f'{rpc_ok} RPC: {"OK" if rpc_ok == "✅" else "ERRO"}\n'
                f'{lag_icon} Lag: {lag:,} blocos\n'
                f'🔗 Bloco atual: {current:,}\n'
                f'📦 Bloco vigia: {last:,}'
            )
            self._send(m.chat.id, msg, self._main_kb(m.chat.id))

        # ── 🔎 Wallet Info ───────────────────────────────────────────────────
        @bot.message_handler(func=lambda m: (m.text or '').strip() == '🔎 Wallet Info')
        def cmd_wallet_info(m: types.Message) -> None:
            u = user_get(self._conn, m.chat.id) or {}
            wallet = u.get('wallet') or cfg.WALLET_ADDRESS
            if not wallet:
                self._send(m.chat.id, '⚠️ Nenhuma wallet conectada. Use 🔌 Conectar.', self._main_kb(m.chat.id))
                return
            try:
                from monitor_chain.block_fetcher import BlockFetcher
                fetcher = BlockFetcher(cfg.RPC_URL)
                pol = fetcher.get_pol_balance(wallet)
                gwei = fetcher.get_gas_price_gwei()
                pol_icon = '⚠️' if pol < cfg.LIMITE_GAS_BAIXO_POL else '✅'
                msg = (
                    f'🔎 <b>Wallet Info</b>\n'
                    f'────────────────────\n'
                    f'👛 {_c(wallet[:8] + "..." + wallet[-6:])}\n'
                    f'{pol_icon} POL: <b>{pol:.4f} POL</b>\n'
                    f'⛽ Gas: {gwei:.2f} GWEI\n'
                    f'🌐 Env: {_esc(u.get("env") or "AG_C_bd")}\n'
                    f'⏱️ Período: {_esc(u.get("periodo") or "24h")}'
                )
            except Exception as e:
                msg = f'🔎 <b>Wallet Info</b>\n❌ Erro ao consultar: {_esc(e)}'
            self._send(m.chat.id, msg, self._main_kb(m.chat.id))

        # ── 📡 Status ────────────────────────────────────────────────────────
        @bot.message_handler(func=lambda m: (m.text or '').strip() == '📡 Status')
        def cmd_status(m: types.Message) -> None:
            last = int(config_get(self._conn, 'vigia_last_block', '0') or 0)
            stats = users_stats(self._conn)
            ai_on = config_get(self._conn, 'ai_global_enabled', '1') not in ('0', 'false')
            msg = (
                f'📡 <b>Status OCME bd</b>\n'
                f'────────────────────\n'
                f'🔭 Vigia bloco: {last:,}\n'
                f'👥 Usuários: {stats["total"]} | Ativos: {stats["active"]}\n'
                f'🟢 Online 24h: {stats["online_24h"]}\n'
                f'🧠 IA: {"ON" if ai_on else "OFF"}'
            )
            self._send(m.chat.id, msg, self._main_kb(m.chat.id))

        # ── ⚙️ Config ────────────────────────────────────────────────────────
        @bot.message_handler(func=lambda m: (m.text or '').strip() == '⚙️ Config')
        def cmd_config(m: types.Message) -> None:
            u = user_get(self._conn, m.chat.id) or {}
            wallet = u.get('wallet') or 'N/A'
            sf = wallet[:8] + '...' + wallet[-6:] if len(wallet) > 14 else wallet
            msg = (
                f'⚙️ <b>Config</b>\n'
                f'────────────────────\n'
                f'👛 Wallet: {_c(sf)}\n'
                f'🌐 Ambiente: <b>{_esc(u.get("env") or "AG_C_bd")}</b>\n'
                f'⏱️ Período: <b>{_esc(u.get("periodo") or "24h")}</b>\n'
                f'🔔 Monitoramento: <b>{"ATIVO" if u.get("active") else "PAUSADO"}</b>\n\n'
                f'Selecione ambiente ou período:'
            )
            self._send(m.chat.id, msg, self._config_kb())

        # ── 🌐 Ambiente ──────────────────────────────────────────────────────
        @bot.message_handler(func=lambda m: (m.text or '').strip() in ('🌐 AG_C_bd', '🌐 bd_v5'))
        def cmd_set_env(m: types.Message) -> None:
            env = 'AG_C_bd' if 'AG_C_bd' in (m.text or '') else 'bd_v5'
            user_upsert(self._conn, m.chat.id, env=env)
            self._send(m.chat.id, f'🌐 Ambiente definido: <b>{env}</b>', self._main_kb(m.chat.id))

        # ── ⏱️ Período ───────────────────────────────────────────────────────
        @bot.message_handler(func=lambda m: (m.text or '').strip() in ('⏱️ 24h', '⏱️ 7d', '⏱️ 30d', '🗓️ Período'))
        def cmd_periodo(m: types.Message) -> None:
            text = (m.text or '').strip()
            if text == '🗓️ Período':
                self._send(m.chat.id, '🗓️ Escolha o período de análise:', self._periodo_kb())
                return
            periodo = text.replace('⏱️ ', '')
            user_upsert(self._conn, m.chat.id, periodo=periodo)
            self._send(m.chat.id, f'⏱️ Período definido: <b>{periodo}</b>', self._main_kb(m.chat.id))

        # ── 🧠 IA ────────────────────────────────────────────────────────────
        @bot.message_handler(func=lambda m: (m.text or '').strip() == '🧠 IA')
        def cmd_ia(m: types.Message) -> None:
            if not cfg.AI_API_KEY:
                self._send(m.chat.id, '⚙️ IA não configurada. Adicione OPENAI_API_KEY no .env', self._main_kb(m.chat.id))
                return
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            kb.row('💬 Perguntar à IA', '📊 Analisar desempenho')
            kb.row('🔙 Menu')
            self._send(m.chat.id, '🧠 <b>IA OCME bd</b>\nO que deseja?', kb)

        @bot.message_handler(func=lambda m: (m.text or '').strip() == '📊 Analisar desempenho')
        def cmd_ia_analise(m: types.Message) -> None:
            u = user_get(self._conn, m.chat.id) or {}
            wallet = u.get('wallet') or cfg.WALLET_ADDRESS
            if not wallet:
                self._send(m.chat.id, '⚠️ Wallet não configurada.', self._main_kb(m.chat.id))
                return
            self._send(m.chat.id, '🤖 Analisando seus dados reais...')
            resp = answer('Analise meu desempenho e me dê 3 insights acionáveis.',
                          conn=self._conn, wallet=wallet, chat_id=m.chat.id)
            self._send(m.chat.id, f'🤖 {resp}', self._main_kb(m.chat.id))

        # ── 🔙 Menu ──────────────────────────────────────────────────────────
        @bot.message_handler(func=lambda m: (m.text or '').strip() == '🔙 Menu')
        def cmd_menu(m: types.Message) -> None:
            user_touch(self._conn, m.chat.id, m.from_user.username)
            self._send(m.chat.id, '📋 Menu principal', self._main_kb(m.chat.id))

        # ═══════════════════════════════════════════════════════════════════
        # ADM
        # ═══════════════════════════════════════════════════════════════════
        @bot.message_handler(func=lambda m: (m.text or '').strip() == '🛠️ ADM')
        def cmd_adm(m: types.Message) -> None:
            if m.chat.id not in cfg.ADMIN_USER_IDS:
                self._send(m.chat.id, '⛔ Acesso negado.', self._main_kb(m.chat.id))
                return
            self._send_adm_menu(m.chat.id)

        @bot.message_handler(func=lambda m: (m.text or '').strip() == '👥 Usuários')
        def cmd_adm_users(m: types.Message) -> None:
            if m.chat.id not in cfg.ADMIN_USER_IDS:
                return
            stats = users_stats(self._conn)
            msg = (
                f'👥 <b>Usuários — ADM</b>\n'
                f'────────────────────\n'
                f'Total: {stats["total"]}\n'
                f'✅ Ativos: {stats["active"]}\n'
                f'🟢 Online 24h: {stats["online_24h"]}\n'
                f'👛 Com wallet: {stats["with_wallet"]}'
            )
            self._send(m.chat.id, msg, self._adm_kb())

        @bot.message_handler(func=lambda m: (m.text or '').strip() == '📊 Stats Motor')
        def cmd_adm_stats(m: types.Message) -> None:
            if m.chat.id not in cfg.ADMIN_USER_IDS:
                return
            last  = int(config_get(self._conn, 'vigia_last_block', '0') or 0)
            v_run = self._vigia and getattr(self._vigia, '_running', False)
            total_ops = getattr(self._vigia, '_ops_total', 0) if self._vigia else 0
            msg = (
                f'📊 <b>Stats Motor</b>\n'
                f'────────────────────\n'
                f'{"✅" if v_run else "🔴"} Vigia: {"ATIVO" if v_run else "PARADO"}\n'
                f'🔗 Último bloco: {last:,}\n'
                f'📌 Ops processadas: {total_ops:,}\n'
                f'⛽ GWEI limite: {cfg.LIMITE_GWEI:.0f}\n'
                f'💧 POL limite: {cfg.LIMITE_GAS_BAIXO_POL:.4f}\n'
                f'⏳ Inativ limite: {cfg.LIMITE_INATIV_MIN:.0f} min'
            )
            self._send(m.chat.id, msg, self._adm_kb())

        @bot.message_handler(func=lambda m: (m.text or '').strip() in ('🤖 IA ON', '🤖 IA OFF'))
        def cmd_adm_ia_toggle(m: types.Message) -> None:
            if m.chat.id not in cfg.ADMIN_USER_IDS:
                return
            val = '1' if m.text.strip() == '🤖 IA ON' else '0'
            config_set(self._conn, 'ai_global_enabled', val)
            self._send(m.chat.id, f'🤖 IA Global: <b>{"ON" if val == "1" else "OFF"}</b>', self._adm_kb())

        @bot.message_handler(func=lambda m: (m.text or '').strip() == '🔐 IA Só ADM')
        def cmd_adm_ia_only(m: types.Message) -> None:
            if m.chat.id not in cfg.ADMIN_USER_IDS:
                return
            cur = config_get(self._conn, 'ai_admin_only', '0')
            novo = '0' if cur in ('1', 'true') else '1'
            config_set(self._conn, 'ai_admin_only', novo)
            self._send(m.chat.id, f'🔐 IA Admin-Only: <b>{"ON" if novo == "1" else "OFF"}</b>', self._adm_kb())

        @bot.message_handler(func=lambda m: (m.text or '').strip() == '🔄 Reset Vigia')
        def cmd_adm_reset(m: types.Message) -> None:
            if m.chat.id not in cfg.ADMIN_USER_IDS:
                return
            self._send(m.chat.id, '🔄 Reset Vigia não disponível em tempo de execução. Reinicie o processo.', self._adm_kb())

        # ── Broadcast (ADM) ──────────────────────────────────────────────────
        @bot.message_handler(func=lambda m: (m.text or '').strip() == '📢 Broadcast')
        def cmd_broadcast_start(m: types.Message) -> None:
            if m.chat.id not in cfg.ADMIN_USER_IDS:
                return
            user_upsert(self._conn, m.chat.id, pending='ASK_BROADCAST')
            self._send(m.chat.id,
                '📢 <b>Broadcast</b>\nEnvie a mensagem que deseja enviar a todos os usuários ativos.\nDigite <b>cancelar</b> para sair.',
                types.ReplyKeyboardRemove())

        # ═══════════════════════════════════════════════════════════════════
        # ESTADO PENDENTE (wallet, broadcast)
        # ═══════════════════════════════════════════════════════════════════
        @bot.message_handler(func=lambda m: bool(user_get_pending(self._conn, m.chat.id)))
        def cmd_pending_state(m: types.Message) -> None:
            text    = (m.text or '').strip()
            pending = user_get_pending(self._conn, m.chat.id) or ''

            if text.lower() == 'cancelar':
                user_upsert(self._conn, m.chat.id, pending='')
                self._send(m.chat.id, '❌ Operação cancelada.', self._main_kb(m.chat.id))
                return

            # ── ASK_WALLET ──
            if pending == 'ASK_WALLET':
                if not re.match(r'^0x[0-9a-fA-F]{40}$', text):
                    self._send(m.chat.id,
                        '⚠️ Wallet inválida. Envie um endereço no formato:\n<code>0x1234...abcd</code>')
                    return
                user_upsert(self._conn, m.chat.id, wallet=text, active=1, pending='')
                self._send(m.chat.id,
                    f'✅ <b>Wallet conectada!</b>\n{_c(text[:8] + "..." + text[-6:])}\n\n'
                    f'Monitoramento ATIVADO automaticamente. 🔔',
                    self._main_kb(m.chat.id))
                logger.info('Wallet conectada: chat_id=%d wallet=%s', m.chat.id, text[:10])
                return

            # ── ASK_BROADCAST ──
            if pending == 'ASK_BROADCAST' and m.chat.id in cfg.ADMIN_USER_IDS:
                users = users_all_active(self._conn)
                count = 0
                for u in users:
                    try:
                        NOTIF_QUEUE.put_nowait((u['chat_id'], f'📢 <b>OCME bd:</b>\n{_esc(text)}'))
                        count += 1
                    except Exception:
                        pass
                user_upsert(self._conn, m.chat.id, pending='')
                self._send(m.chat.id, f'✅ Broadcast enfileirado para {count} usuários.', self._adm_kb())
                return

            # Limpa pending desconhecido
            user_upsert(self._conn, m.chat.id, pending='')

        # ── Fallback IA (qualquer texto não reconhecido) ──────────────────────
        @bot.message_handler(func=lambda m: (m.text or '') not in self._known_buttons())
        def cmd_ai_fallback(m: types.Message) -> None:
            if not m.text:
                return
            if not self._ai_can_use(m.chat.id):
                self._send(m.chat.id, '⚙️ IA desabilitada.', self._main_kb(m.chat.id))
                return
            u      = user_get(self._conn, m.chat.id) or {}
            wallet = u.get('wallet')
            resp   = answer(m.text, conn=self._conn, wallet=wallet, chat_id=m.chat.id)
            self._send(m.chat.id, f'🤖 {resp}', self._main_kb(m.chat.id))

    # ═══════════════════════════════════════════════════════════════════════════
    # OPERAÇÕES ON-CHAIN → NOTIFICAÇÃO POR CARTEIRA (formato WEbdEX)
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_vigia_operation(self, op: dict) -> None:
        '''Notifica: 1) dono da wallet individualmente, 2) resumo agrupado para admins a cada 30min.'''
        try:
            # 1) Notificação individual para usuários donos desta wallet
            wallet = op.get('wallet', '')
            if wallet:
                self._notif_exec_individual(op, wallet)

            # 2) Buffer para resumo admin a cada 30min
            self._buffer_op_admin(op)
        except Exception as exc:
            logger.warning('_on_vigia_operation error: %s', exc)

    def _notif_exec_individual(self, op: dict, wallet: str) -> None:
        '''Monta notificação no formato WEbdEX e envia para donos da wallet.'''
        users = users_by_wallet(self._conn, wallet)
        if not users and wallet.lower() not in [str(a).lower() for a in [cfg.WALLET_ADDRESS]]:
            return
        # Inclui o owner padrão se não está na lista
        target_ids: list[int] = [u['chat_id'] for u in users]
        for admin_id in cfg.ADMIN_USER_IDS:
            if admin_id not in target_ids:
                target_ids.append(admin_id)

        env_tag    = op.get('env', 'AG')
        sub        = op.get('sub_conta', '-')
        val        = float(op.get('profit_usd', 0.0))
        gas_usd    = float(op.get('gas_usd', 0.0))
        gas_pol    = float(op.get('gas_pol', 0.0))
        tx         = op.get('tx_hash', '')
        block      = int(op.get('block_number', 0))
        token      = op.get('token', 'USDT0')
        strategy   = op.get('strategy_addr', '-') or '-'
        if len(strategy) > 20:
            strategy = strategy[:8] + '...' + strategy[-6:]

        prof_icon  = '🟢' if val >= 0 else '🔴'
        gas_pct    = f' ({(gas_usd / abs(val)) * 100:.1f}%)' if val and abs(val) > 0 else ''

        if gas_pol and gas_pol > 0:
            gas_line = f'⛽ Gas fee: {gas_pol:.4f} POL • ${gas_usd:.4f}{_esc(gas_pct)}'
        else:
            gas_line = f'⛽ Gas fee: ${gas_usd:.4f}{_esc(gas_pct)}'

        # Time ago
        blk_ts  = None
        try:
            from monitor_db.queries import block_ts_get
            blk_ts = block_ts_get(self._conn, block)
        except Exception:
            pass
        ago = _time_ago(blk_ts)

        short_tx = f'{tx[:10]}...{tx[-8:]}' if len(tx) > 18 else tx

        msg = (
            f'🔵 <b>EXECUÇÃO — WEbdEX [{_esc(env_tag)}]</b>\n\n'
            f'Account: {_c(sub)}\n'
            f'Strategy: {_esc(strategy)}\n'
            f'────────────────────\n'
            f'{prof_icon} Profit: {val:+.4f} {_esc(token)}\n'
            f'{gas_line}\n'
            f'🎟️ Pass fee: -\n'
            f'────────────────────\n'
            f'🧱 Network: Polygon\n'
            f'🕒 {_esc(ago)}\n'
            f'🔗 <a href="https://polygonscan.com/tx/{_esc(tx)}">Ver no Polygonscan</a>'
        )

        for cid in target_ids:
            try:
                NOTIF_QUEUE.put_nowait((cid, msg))
            except Exception:
                pass

    def _buffer_op_admin(self, op: dict) -> None:
        '''Acumula ops e envia resumo para admins a cada 30 minutos.'''
        with self._op_lock:
            self._op_buffer.append(op)
            now     = time.time()
            elapsed = now - self._op_last_flush
            if elapsed < self._op_flush_interval:
                return
            ops_to_send = list(self._op_buffer)
            self._op_buffer.clear()
            self._op_last_flush = now

        if not ops_to_send:
            return

        total      = len(ops_to_send)
        profit_sum = sum(o.get('profit_usd', 0) for o in ops_to_send)
        gas_sum    = sum(o.get('gas_usd', 0)    for o in ops_to_send)
        wins       = sum(1 for o in ops_to_send if o.get('profit_usd', 0) >= 0)
        losses     = total - wins
        last_block = max((o.get('block_number', 0) for o in ops_to_send), default=0)
        profit_icon = '🟢' if profit_sum >= 0 else '🔴'
        mins_str   = f'{self._op_flush_interval / 60:.0f} min'

        top3 = sorted(ops_to_send, key=lambda o: abs(o.get('profit_usd', 0)), reverse=True)[:3]
        top_lines = '\n'.join(
            f'{"🟢" if o.get("profit_usd", 0) >= 0 else "🔴"} '
            f'{o.get("sub_conta","?")[:14]} ({o.get("env","?")}) '
            f'${o.get("profit_usd", 0):+,.4f}'
            for o in top3
        )

        msg = (
            f'{profit_icon} <b>Resumo ADM — últimos {mins_str}</b>\n'
            f'────────────────────\n'
            f'📊 Ops: {total} | 🟢 {wins} | 🔴 {losses}\n'
            f'💰 Lucro total: <b>${profit_sum:+,.4f}</b>\n'
            f'⛽ Gas total: ${gas_sum:,.6f}\n'
            f'🔗 Bloco: {last_block:,}\n'
            f'────────────────────\n'
            f'<b>Top 3:</b>\n{top_lines}'
        )
        logger.info('Resumo admin 30min: %d ops | lucro=%.4f', total, profit_sum)
        for admin_id in cfg.ADMIN_USER_IDS:
            try:
                NOTIF_QUEUE.put_nowait((admin_id, msg))
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════════════════
    # ALERTAS DA SENTINELA
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_sentinel_alert(self, tipo: str, dados: dict) -> None:
        msg = dados.get('msg', f'Alerta: {tipo}')
        if tipo == 'inatividade_global' and cfg.AI_API_KEY and cfg.WALLET_ADDRESS:
            try:
                diagnostico = answer_inactivity_diagnostic(
                    conn=self._conn, wallet=cfg.WALLET_ADDRESS,
                    minutes=dados.get('minutes', 0), sigma=dados.get('sigma', 0),
                )
                msg += f'\n\n🤖 <b>Diagnóstico IA:</b>\n{diagnostico}'
            except Exception:
                pass
        for admin_id in cfg.ADMIN_USER_IDS:
            NOTIF_QUEUE.put((admin_id, msg))

    # ═══════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _send_adm_menu(self, chat_id: int) -> None:
        stats = users_stats(self._conn)
        ai_on  = config_get(self._conn, 'ai_global_enabled', '1') not in ('0', 'false')
        ai_adm = config_get(self._conn, 'ai_admin_only', '0') in ('1', 'true')
        msg = (
            f'🛠️ <b>ADM — OCME bd</b>\n\n'
            f'👥 Usuários: {stats["total"]}\n'
            f'✅ Ativos: {stats["active"]}\n'
            f'🟢 Online 24h: {stats["online_24h"]}\n\n'
            f'🧠 IA Governança\n'
            f'• Global: <b>{"ON" if ai_on else "OFF"}</b>\n'
            f'• ADM-only: <b>{"ON" if ai_adm else "OFF"}</b>'
        )
        self._send(chat_id, msg, self._adm_kb())

    def _ai_can_use(self, chat_id: int) -> bool:
        ai_on      = config_get(self._conn, 'ai_global_enabled', '1') not in ('0', 'false')
        ai_adm_only = config_get(self._conn, 'ai_admin_only', '0') in ('1', 'true')
        if not ai_on:
            return chat_id in cfg.ADMIN_USER_IDS
        if ai_adm_only:
            return chat_id in cfg.ADMIN_USER_IDS
        return bool(cfg.AI_API_KEY)

    def _send(
        self, chat_id: int, text: str,
        reply_markup: Any = None,
        via_queue: bool = False,
    ) -> None:
        if via_queue:
            NOTIF_QUEUE.put((chat_id, text, reply_markup))
            return
        try:
            for i in range(0, len(text), _TG_SAFE_LIMIT):
                chunk = text[i:i + _TG_SAFE_LIMIT]
                self._bot.send_message(
                    chat_id, chunk,
                    reply_markup=reply_markup if i == 0 else None,
                    disable_web_page_preview=True,
                )
                time.sleep(0.05)
        except Exception as exc:
            if '403' in str(exc) or 'Forbidden' in str(exc):
                logger.info('Usuário bloqueou o bot: %d', chat_id)
                user_upsert(self._conn, chat_id, active=0)
            else:
                logger.warning('send falhou para %d: %s', chat_id, exc)

    def _start_notif_worker(self) -> None:
        def _worker():
            while True:
                try:
                    item    = NOTIF_QUEUE.get(timeout=5)
                    chat_id = item[0]
                    text    = item[1]
                    markup  = item[2] if len(item) > 2 else None
                    self._send(chat_id, text, markup)
                    NOTIF_QUEUE.task_done()
                    time.sleep(0.08)
                except queue.Empty:
                    continue
                except Exception as exc:
                    logger.warning('notif_worker error: %s', exc)

        self._notif_worker_thread = threading.Thread(target=_worker, daemon=True, name='notif-worker')
        self._notif_worker_thread.start()

    def run(self) -> None:
        '''Inicia o bot em polling (blocking).'''
        self._start_notif_worker()
        logger.info('Bot Telegram iniciado. Aguardando mensagens...')
        while True:
            try:
                self._bot.infinity_polling(
                    timeout=30,
                    long_polling_timeout=20,
                    skip_pending=True,
                )
            except Exception as exc:
                logger.error('infinity_polling error: %s', exc)
                time.sleep(10)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    if not cfg.TELEGRAM_TOKEN or ':' not in cfg.TELEGRAM_TOKEN:
        logger.error('TELEGRAM_TOKEN inválido. Verifique o .env')
        sys.exit(1)

    conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL')
    migrate(conn)

    from monitor_chain.block_fetcher import BlockFetcher, TOPIC_OPENPOSITION
    from monitor_chain.operation_parser import OperationParser
    from monitor_core.vigia import Vigia
    from monitor_core.sentinela import Sentinela
    from web3 import Web3

    tokens_map = {
        cfg.TOKEN_USDT_ADDRESS.lower(): {'dec': 6, 'sym': 'USDT0', 'icon': '🔵'},
        cfg.TOKEN_LOOP_ADDRESS.lower(): {'dec': 9, 'sym': 'LOOP',  'icon': '🔴'},
    }
    for lp in cfg.TOKEN_LP_ADDRESSES:
        tokens_map[lp.lower()] = {'dec': 6, 'sym': 'LP', 'icon': '🟣'}

    fetcher = BlockFetcher(cfg.RPC_URL, chunk_size=cfg.MONITOR_FETCH_CHUNK)
    parser  = OperationParser(cfg.CONTRACTS, tokens_map)

    all_addrs = list({
        Web3.to_checksum_address(v)
        for env_data in cfg.CONTRACTS.values()
        for k, v in env_data.items()
        if k == 'PAYMENTS' and v.startswith('0x')
    })

    vigia = Vigia(
        fetcher=fetcher, parser=parser, conn=conn,
        addresses=all_addrs, topics=[TOPIC_OPENPOSITION],
        max_blocks_per_loop=cfg.MONITOR_MAX_BLOCKS_PER_LOOP,
        idle_sleep=cfg.MONITOR_IDLE_SLEEP,
        busy_sleep=cfg.MONITOR_BUSY_SLEEP,
        backlog_warn_at=cfg.MONITOR_BACKLOG_WARN_AT,
    )

    sentinela = Sentinela(
        vigia=vigia, fetcher=fetcher, conn=conn,
        limite_gwei=cfg.LIMITE_GWEI,
        limite_gas_pol=cfg.LIMITE_GAS_BAIXO_POL,
        limite_inativ_min=cfg.LIMITE_INATIV_MIN,
    )

    vigia.start()
    sentinela.start()

    bot = MonitorBot(conn=conn, vigia=vigia, sentinela=sentinela)
    bot.run()


if __name__ == '__main__':
    main()
