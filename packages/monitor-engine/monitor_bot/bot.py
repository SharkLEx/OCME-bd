# ==============================================================================
# monitor_bot/bot.py — Telegram Bot: apenas UI e notificações
# OCME bd Monitor Engine — Story 7.6
#
# Princípio: handlers NÃO fazem lógica — delegam para os módulos do motor.
# CLI é a fonte da verdade. Bot é o canal de notificação.
# ==============================================================================
from __future__ import annotations

import logging
import queue
import sqlite3
import threading
import time
from typing import Any

import requests
import telebot
from telebot import apihelper

import config as cfg
from monitor_db.migrator import migrate
from monitor_db.queries import (
    config_get, config_set, user_get, user_touch,
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


class _ExceptionHandler(telebot.ExceptionHandler):
    def handle(self, exc: Exception) -> bool:
        err = str(exc)
        if '409' in err or 'Conflict' in err:
            # Outro bot com mesmo token detectado — espera e tenta assumir
            logger.warning('409 Conflict: outro bot com mesmo token ativo. Aguardando 15s para assumir...')
            time.sleep(15)
            return True
        if '502' in err or 'Bad Gateway' in err:
            time.sleep(10)
            return True
        if '429' in err or 'Too Many Requests' in err:
            import re
            m = re.search(r'retry after (\d+)', err, re.I)
            time.sleep(int(m.group(1)) + 1 if m else 10)
            return True
        if any(x in err for x in ['ConnectionReset', 'RemoteDisconnected', 'ReadTimeout']):
            time.sleep(8)
            return True
        return False


class MonitorBot:
    '''Bot do Telegram que consome o motor de monitoramento.'''

    def __init__(
        self,
        conn: sqlite3.Connection,
        vigia: Any | None = None,
        sentinela: Any | None = None,
        dashboard_cache: DashboardCache | None = None,
    ):
        self._conn    = conn
        self._vigia   = vigia
        self._sent    = sentinela
        self._cache   = dashboard_cache or DashboardCache(conn, vigia)
        self._bot     = telebot.TeleBot(
            cfg.TELEGRAM_TOKEN,
            parse_mode='HTML',
            exception_handler=_ExceptionHandler(),
            threaded=True,
        )
        self._notif_worker_thread: threading.Thread | None = None
        self._register_handlers()

        # Subscreve alertas da sentinela
        if sentinela:
            sentinela.on_alert(self._on_sentinel_alert)

        # Subscreve operações on-chain do vigia → notifica admins em tempo real
        if vigia:
            vigia.on('operation', self._on_vigia_operation)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _register_handlers(self) -> None:
        bot = self._bot

        @bot.message_handler(commands=['start'])
        def cmd_start(m: telebot.types.Message) -> None:
            logger.info('/start de @%s (chat_id=%d)', m.from_user.username or '?', m.chat.id)
            user_touch(self._conn, m.chat.id, m.from_user.username)
            markup = self._main_keyboard(m.chat.id)
            self._send(m.chat.id,
                '👋 <b>OCME bd Monitor Engine</b>\n\n'
                'Sistema de monitoramento DeFi na Polygon.\n'
                'Use o menu abaixo ou envie uma mensagem para a IA.',
                markup)

        @bot.message_handler(func=lambda m: m.text == '📊 Dashboard')
        def cmd_dashboard(m: telebot.types.Message) -> None:
            user = user_get(self._conn, m.chat.id)
            wallet = (user or {}).get('wallet') or cfg.WALLET_ADDRESS
            period = (user or {}).get('periodo', '24h')
            env    = (user or {}).get('env')

            # < 500ms: dados do cache
            data = self._cache.get(wallet=wallet, period=period, env=env)
            age  = data.get('_cache_age_s', 0)

            inactiv = data.get('inactivity_min', 0)
            inactiv_icon = '⚠️' if inactiv > cfg.LIMITE_INATIV_MIN else '✅'

            best = data.get('best_subconta')
            best_line = f'\n🏆 Melhor: <code>{best["id"]}</code> +${best["profit"]:,.2f}' if best else ''

            msg = (
                f'📊 <b>Dashboard — {period}</b> {f"({env})" if env else ""}\n'
                f'<code>─────────────────────</code>\n'
                f'💰 Lucro líquido: <b>${data["profit_net"]:,.2f}</b>\n'
                f'🔄 Trades: {data["trades"]:,}\n'
                f'⛽ Gas médio: ${data["gas_avg"]:,.6f}\n'
                f'{inactiv_icon} Inatividade: {inactiv:.0f} min'
                f'{best_line}\n'
                f'<code>─────────────────────</code>\n'
                f'<i>Cache: {age:.1f}s | {data.get("_computed_at", "")}</i>'
            )
            self._send(m.chat.id, msg, self._main_keyboard(m.chat.id))

        @bot.message_handler(func=lambda m: m.text == '📈 Relatório')
        def cmd_relatorio(m: telebot.types.Message) -> None:
            user = user_get(self._conn, m.chat.id)
            wallet = (user or {}).get('wallet') or cfg.WALLET_ADDRESS
            period = (user or {}).get('periodo', '24h')
            hours  = {'24h': 24, '7d': 168, '30d': 720}.get(period, 24)

            if not wallet:
                self._send(m.chat.id, '⚙️ Conecte sua wallet primeiro: /start → Configurar Wallet')
                return

            summary = ops_summary(self._conn, wallet, hours=hours)
            best    = ops_best_subconta(self._conn, wallet, hours=hours)
            inactiv = ops_last_inactivity_minutes(self._conn, wallet)

            best_line = f'\n🏆 Melhor subconta: <code>{best["id"]}</code> +${best["profit"]:,.2f}' if best else ''

            msg = (
                f'📈 <b>Relatório {period}</b>\n'
                f'<code>─────────────────────</code>\n'
                f'Trades:        {summary["count"]:,}\n'
                f'Lucro bruto:   ${summary["profit_gross"]:,.2f}\n'
                f'Gas gasto:     ${summary["gas_total"]:,.4f}\n'
                f'<b>Lucro líquido: ${summary["profit_net"]:,.2f}</b>'
                f'{best_line}\n'
                f'Inatividade:   {inactiv:.0f} min'
            )
            self._send(m.chat.id, msg)

        @bot.message_handler(func=lambda m: m.text == '🤖 IA')
        def cmd_ia_menu(m: telebot.types.Message) -> None:
            if not cfg.AI_API_KEY:
                self._send(m.chat.id, '⚙️ IA não configurada. Adicione OPENAI_API_KEY no .env')
                return
            markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add('💬 Perguntar à IA', '📊 Analisar meu desempenho')
            markup.add('🔙 Menu')
            self._send(m.chat.id, '🤖 <b>IA do OCME bd</b>\nO que deseja?', markup)

        @bot.message_handler(func=lambda m: m.text == '📊 Analisar meu desempenho')
        def cmd_ia_analise(m: telebot.types.Message) -> None:
            user = user_get(self._conn, m.chat.id)
            wallet = (user or {}).get('wallet') or cfg.WALLET_ADDRESS
            if not wallet:
                self._send(m.chat.id, '⚙️ Wallet não configurada.')
                return
            self._send(m.chat.id, '🤖 Analisando seus dados reais...')
            resp = answer(
                'Analise meu desempenho e me dê 3 insights acionáveis.',
                conn=self._conn,
                wallet=wallet,
                chat_id=m.chat.id,
            )
            self._send(m.chat.id, f'🤖 {resp}')

        @bot.message_handler(func=lambda m: m.text == '🔙 Menu')
        def cmd_menu(m: telebot.types.Message) -> None:
            user_touch(self._conn, m.chat.id, m.from_user.username)
            self._send(m.chat.id, '📋 Menu principal', self._main_keyboard(m.chat.id))

        @bot.message_handler(func=lambda m: m.text and m.text not in self._known_buttons())
        def cmd_ai_fallback(m: telebot.types.Message) -> None:
            '''Qualquer texto não reconhecido vai para a IA.'''
            if not self._ai_can_use(m.chat.id):
                return
            user = user_get(self._conn, m.chat.id)
            wallet = (user or {}).get('wallet')
            resp = answer(m.text, conn=self._conn, wallet=wallet, chat_id=m.chat.id)
            self._send(m.chat.id, f'🤖 {resp}')

    # ── Operações on-chain em tempo real (agrupadas a cada 30s) ──────────────

    def __init_op_buffer(self) -> None:
        self._op_buffer: list[dict] = []
        self._op_last_flush: float  = time.time()
        self._op_flush_interval: float = 30.0  # segundos entre resumos
        self._op_lock = threading.Lock()

    def _on_vigia_operation(self, op: dict) -> None:
        '''Acumula operações e envia resumo agrupado a cada 30s para admins.'''
        if not hasattr(self, '_op_buffer'):
            self.__init_op_buffer()
        try:
            with self._op_lock:
                self._op_buffer.append(op)
                now = time.time()
                elapsed = now - self._op_last_flush
                if elapsed < self._op_flush_interval:
                    return
                ops_to_send = list(self._op_buffer)
                self._op_buffer.clear()
                self._op_last_flush = now

            if not ops_to_send:
                return

            # Monta resumo agrupado
            total      = len(ops_to_send)
            profit_sum = sum(o.get('profit_usd', 0) for o in ops_to_send)
            gas_sum    = sum(o.get('gas_usd', 0)    for o in ops_to_send)
            wins       = sum(1 for o in ops_to_send if o.get('profit_usd', 0) >= 0)
            losses     = total - wins
            last_block = max((o.get('block_number', 0) for o in ops_to_send), default=0)
            profit_icon = '🟢' if profit_sum >= 0 else '🔴'

            lines = [f'{profit_icon} <b>Resumo On-Chain — últimos {self._op_flush_interval:.0f}s</b>']
            lines.append('<code>─────────────────────</code>')
            lines.append(f'📊 Ops: {total} | 🟢 {wins} ganhos | 🔴 {losses} perdas')
            lines.append(f'💰 Lucro líquido: <b>${profit_sum:,.4f}</b>')
            lines.append(f'⛽ Gas total: ${gas_sum:,.6f}')
            lines.append(f'🔗 Último bloco: {last_block:,}')

            # Destaque: top 3 ops por lucro
            top3 = sorted(ops_to_send, key=lambda o: abs(o.get('profit_usd', 0)), reverse=True)[:3]
            if top3:
                lines.append('')
                lines.append('<b>Top ops:</b>')
                for o in top3:
                    icon  = '🟢' if o.get('profit_usd', 0) >= 0 else '🔴'
                    lines.append(f'{icon} {o.get("sub_conta","?")} ({o.get("env","?")}) ${o.get("profit_usd",0):+,.4f}')

            msg = '\n'.join(lines)
            logger.info('Resumo on-chain: %d ops | lucro=%.4f', total, profit_sum)
            for admin_id in cfg.ADMIN_USER_IDS:
                try:
                    NOTIF_QUEUE.put_nowait((admin_id, msg))
                except Exception:
                    pass  # queue cheia — descarta
        except Exception as exc:
            logger.warning('_on_vigia_operation error: %s', exc)

    # ── Alertas proativos ─────────────────────────────────────────────────────

    def _on_sentinel_alert(self, tipo: str, dados: dict) -> None:
        '''Recebe alerta da Sentinela e notifica todos os admins.'''
        msg = dados.get('msg', f'Alerta: {tipo}')

        # Enriquece alertas de inatividade com diagnóstico IA
        if tipo == 'inatividade_global' and cfg.AI_API_KEY and cfg.WALLET_ADDRESS:
            try:
                diagnostico = answer_inactivity_diagnostic(
                    conn=self._conn,
                    wallet=cfg.WALLET_ADDRESS,
                    minutes=dados.get('minutes', 0),
                    sigma=dados.get('sigma', 0),
                )
                msg += f'\n\n🤖 <b>Diagnóstico IA:</b>\n{diagnostico}'
            except Exception:
                pass

        for admin_id in cfg.ADMIN_USER_IDS:
            NOTIF_QUEUE.put((admin_id, msg))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _main_keyboard(self, chat_id: int) -> telebot.types.ReplyKeyboardMarkup:
        is_admin = chat_id in cfg.ADMIN_USER_IDS
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add('📊 Dashboard', '📈 Relatório')
        markup.add('🤖 IA', '⚙️ Config')
        if is_admin:
            markup.add('🛠️ ADM')
        return markup

    def _known_buttons(self) -> set[str]:
        return {'📊 Dashboard', '📈 Relatório', '🤖 IA', '⚙️ Config', '🛠️ ADM',
                '🔙 Menu', '💬 Perguntar à IA', '📊 Analisar meu desempenho'}

    def _ai_can_use(self, chat_id: int) -> bool:
        ai_on = config_get(self._conn, 'ai_global_enabled', '1') not in ('0', 'false')
        ai_admin_only = config_get(self._conn, 'ai_admin_only', '0') in ('1', 'true')
        if not ai_on:
            return chat_id in cfg.ADMIN_USER_IDS
        if ai_admin_only:
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
                self._bot.send_message(chat_id, chunk, reply_markup=reply_markup if i == 0 else None)
                time.sleep(0.05)
        except Exception as exc:
            if '403' in str(exc) or 'Forbidden' in str(exc):
                logger.info('Usuário bloqueou o bot: %d', chat_id)
            else:
                logger.warning('send falhou para %d: %s', chat_id, exc)

    def _start_notif_worker(self) -> None:
        def _worker():
            while True:
                try:
                    item = NOTIF_QUEUE.get(timeout=5)
                    chat_id = item[0]
                    text = item[1]
                    markup = item[2] if len(item) > 2 else None
                    self._send(chat_id, text, markup)
                    NOTIF_QUEUE.task_done()
                    time.sleep(0.1)
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
                    skip_pending=True,   # ignora mensagens acumuladas
                )
            except Exception as exc:
                logger.error('infinity_polling error: %s', exc)
                time.sleep(10)


# ── Entry point standalone ────────────────────────────────────────────────────

def main() -> None:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    if not cfg.TELEGRAM_TOKEN or ':' not in cfg.TELEGRAM_TOKEN:
        logger.error('TELEGRAM_TOKEN inválido. Verifique o .env')
        sys.exit(1)

    conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL')
    migrate(conn)

    # Inicializa motor
    from monitor_chain.block_fetcher import BlockFetcher, TOPIC_OPENPOSITION
    from monitor_chain.operation_parser import OperationParser
    from monitor_core.vigia import Vigia
    from monitor_core.sentinela import Sentinela

    tokens_map = {
        cfg.TOKEN_USDT_ADDRESS.lower(): {'dec': 6, 'sym': 'USDT0', 'icon': '🔵'},
        cfg.TOKEN_LOOP_ADDRESS.lower(): {'dec': 9, 'sym': 'LOOP',  'icon': '🔴'},
    }
    for lp in cfg.TOKEN_LP_ADDRESSES:
        tokens_map[lp.lower()] = {'dec': 6, 'sym': 'LP', 'icon': '🟣'}

    from web3 import Web3
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
