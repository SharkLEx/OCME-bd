from __future__ import annotations
# ==============================================================================
# webdex_socios_monitor.py — Monitor de Comissões dos Sócios
# Rastreia USDT recebido pelo contrato Network para 6 carteiras de sócios.
# Envia relatório diário às 07:00 UTC + alerta imediato a cada pagamento.
# Destinatário: apenas OWNER_CHAT_ID (privado).
# Relatório separado por ambiente (AG_C_bd / bd_v5), com últimos chars da carteira.
# Botão inline "🔄 Ver agora" para relatório on-demand.
# ==============================================================================

import os, time, json, threading
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Dict, Tuple

import requests
from web3 import Web3
try:
    from web3.middleware import ExtraDataToPOAMiddleware as _POA_MW
except ImportError:
    from web3.middleware import geth_poa_middleware as _POA_MW  # type: ignore[no-redef]

from webdex_config import logger, RPC_URL, RPC_FALLBACK

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
TELEGRAM_TOKEN  = os.getenv('TELEGRAM_TOKEN', '')
OWNER_CHAT_ID   = os.getenv('OWNER_CHAT_ID', '')
POLYGONSCAN_KEY = os.getenv('POLYGONSCAN_API_KEY', '')

NETWORK_CONTRACT = '0xfB2486E93E4Ab8A36d2e6C23004FacaAD3Bad5Db'
USDT_CONTRACT    = '0xc2132D05D31c914a87C6611C10748AEb04B58e8F'
USDT_DECIMALS    = 1_000_000  # 6 casas

# Todos os tokens rastreados (confirmado via Polygonscan: DAI e LOOP sem pagamentos até agora)
TRACKED_TOKENS: Dict[str, tuple] = {
    'USDT': ('0xc2132D05D31c914a87C6611C10748AEb04B58e8F', 1_000_000),
    'DAI':  ('0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063', 10**18),
    'LOOP': ('0x9Bb05B6C3bC29BFC68DF7EbC70A19F7bAdFd7dd8', 10**18),
}

# Mapa manager → ambiente (para separação por env)
MANAGER_TO_ENV: Dict[str, str] = {
    '0x685d04d62da1ef26529c7aa1364da504c8acdb1d': 'AG_C_bd',
    '0x9826a9727d5bb97a44bf14fe2e2b0b1d5a81c860': 'bd_v5',
}
ENV_LABELS = {'AG_C_bd': '🔵 AG_C_bd', 'bd_v5': '🟢 bd_v5', 'desconhecido': '⚪ ?'}

# Tópicos
TOPIC_TRANSFER      = Web3.to_hex(Web3.keccak(text='Transfer(address,address,uint256)'))
TOPIC_NET_REMOVE    = Web3.to_hex(Web3.keccak(text='BalanceNetworkRemove(address,address,address,uint256,uint256,uint256)'))

# ABIs mínimos
ABI_ERC20 = json.dumps([{
    'anonymous': False,
    'inputs': [
        {'indexed': True,  'name': 'from',  'type': 'address'},
        {'indexed': True,  'name': 'to',    'type': 'address'},
        {'indexed': False, 'name': 'value', 'type': 'uint256'},
    ],
    'name': 'Transfer', 'type': 'event',
}])

ABI_NETWORK = json.dumps([{
    'anonymous': False,
    'inputs': [
        {'indexed': True,  'name': 'manager', 'type': 'address'},
        {'indexed': True,  'name': 'user',    'type': 'address'},
        {'indexed': False, 'name': 'coin',    'type': 'address'},
        {'indexed': False, 'name': 'balance', 'type': 'uint256'},
        {'indexed': False, 'name': 'value',   'type': 'uint256'},
        {'indexed': False, 'name': 'fee',     'type': 'uint256'},
    ],
    'name': 'BalanceNetworkRemove', 'type': 'event',
}])

# 6 carteiras de sócios (lowercase)
SOCIOS: Dict[str, str] = {
    '0x7403305b41f96fc9f2e02ae79f79a59fc7fcafbb': 'Sócio 1',
    '0x1bbd1003c5643db910738e6ddf16754b7d6c7063': 'Sócio 2',
    '0x87e0cdf1a73be38a103e3f33282e621bf48ebec8': 'Sócio 3',
    '0xaf635b4e1ab085e9b8bf677aebe8a0d98511894f': 'Sócio 4',
    '0xe42e0c17edbed3f313ad4c9e93bd5e4a2b25edcd': 'Sócio 5',
    '0x403fd451beff4f71dfa0ef39d23ebe82b64c820d': 'Sócio 6',
}

# Estado acumulado thread-safe
# _history[addr][env][day]  = USDT amount
# _tx_counts[addr][day]     = número de transações naquele dia (todos tokens)
# _last_payment[addr]       = {'amount', 'token', 'day', 'ts', 'env', 'hash'}
_lock      = threading.Lock()
_history: Dict[str, Dict[str, Dict[str, float]]] = {
    addr: defaultdict(lambda: defaultdict(float)) for addr in SOCIOS
}
_tx_counts: Dict[str, Dict[str, int]] = {addr: defaultdict(int) for addr in SOCIOS}
_last_payment: Dict[str, dict] = {}
_seen_hashes: set = set()

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _w3() -> Web3:
    for rpc in [RPC_URL, RPC_FALLBACK]:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 20}))
            w3.middleware_onion.inject(_POA_MW, layer=0)
            if w3.is_connected():
                return w3
        except Exception:
            pass
    raise RuntimeError('[socios] Nenhum RPC disponível')


def _short_addr(addr: str) -> str:
    """Exibe início + últimos 6 chars: 0x7403...fcafbb"""
    return f'{addr[:6]}...{addr[-6:]}'


def _fmt_usdt(val: float) -> str:
    return f'${val:,.2f}'


def _send_telegram(text: str, reply_markup: dict | None = None) -> int | None:
    """Envia mensagem apenas para OWNER_CHAT_ID. Retorna message_id."""
    if not TELEGRAM_TOKEN or not OWNER_CHAT_ID:
        return None
    try:
        payload: dict = {
            'chat_id': OWNER_CHAT_ID,
            'text': text,
            'parse_mode': 'HTML',
        }
        if reply_markup:
            payload['reply_markup'] = json.dumps(reply_markup)
        url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
        r = requests.post(url, json=payload, timeout=10)
        if r.ok:
            return r.json().get('result', {}).get('message_id')
    except Exception as e:
        logger.warning('[socios] Telegram erro: %s', e)
    return None


def _refresh_button() -> dict:
    """Inline keyboard com botão de atualização."""
    return {'inline_keyboard': [[{'text': '🔄 Ver agora', 'callback_data': 'socios_report'}]]}


# ─────────────────────────────────────────────────────────────
# Detecção de ambiente via BalanceNetworkRemove na mesma tx
# ─────────────────────────────────────────────────────────────
def _detect_env(w3: Web3, tx_hash: str) -> str:
    """Lê o receipt da tx e acha o BalanceNetworkRemove para extrair o manager → env."""
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        net_contract = Web3.to_checksum_address(NETWORK_CONTRACT)
        net_abi_contract = w3.eth.contract(
            address=net_contract,
            abi=ABI_NETWORK,
        )
        for log in receipt['logs']:
            if log['address'].lower() != NETWORK_CONTRACT.lower():
                continue
            if not log['topics'] or log['topics'][0].hex() != TOPIC_NET_REMOVE:
                continue
            try:
                ev = net_abi_contract.events.BalanceNetworkRemove().process_log(log)
                mgr = ev['args']['manager'].lower()
                return MANAGER_TO_ENV.get(mgr, 'desconhecido')
            except Exception:
                pass
    except Exception as e:
        logger.debug('[socios] detect_env erro: %s', e)
    return 'desconhecido'


# ─────────────────────────────────────────────────────────────
# Backfill histórico via Polygonscan (últimos 90 dias)
# ─────────────────────────────────────────────────────────────
def _backfill_history() -> None:
    if not POLYGONSCAN_KEY:
        logger.warning('[socios] POLYGONSCAN_API_KEY ausente — backfill ignorado')
        return

    logger.info('[socios] Iniciando backfill histórico (90 dias)...')
    ninety_ago = int((datetime.now(tz=timezone.utc) - timedelta(days=90)).timestamp())
    net_lower  = NETWORK_CONTRACT.lower()

    for addr, label in SOCIOS.items():
        for tok_name, (tok_addr, tok_dec) in TRACKED_TOKENS.items():
            try:
                url = (
                    'https://api.etherscan.io/v2/api?chainid=137'
                    '&module=account&action=tokentx'
                    f'&address={addr}&contractaddress={tok_addr}'
                    f'&page=1&offset=500&sort=desc&apikey={POLYGONSCAN_KEY}'
                )
                r = requests.get(url, timeout=15).json()
                txs = r.get('result', [])
                if not isinstance(txs, list):
                    continue

                for tx in txs:
                    ts = int(tx['timeStamp'])
                    if ts < ninety_ago:
                        continue
                    if tx['from'].lower() != net_lower or tx['to'].lower() != addr:
                        continue

                    val = int(tx['value']) / tok_dec
                    day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d')
                    env = 'desconhecido'
                    with _lock:
                        _history[addr][env][day] += val
                        _tx_counts[addr][day]    += 1
                        _seen_hashes.add(tx['hash'].lower())
                        prev = _last_payment.get(addr)
                        if prev is None or ts > prev['ts']:
                            _last_payment[addr] = {
                                'amount': val,
                                'token':  tok_name,
                                'day':    day,
                                'ts':     ts,
                                'env':    env,
                                'hash':   tx['hash'][:16],
                            }

            except Exception as e:
                logger.warning('[socios] Backfill erro %s %s: %s', label, tok_name, e)

        with _lock:
            total = sum(sum(d.values()) for d in _history[addr].values())
        logger.info('[socios] Backfill %s: %.2f$ em history', label, total)

    logger.info('[socios] Backfill concluído.')


# ─────────────────────────────────────────────────────────────
# Construção do texto do relatório (exportado para callback)
# ─────────────────────────────────────────────────────────────
def _tc(s: str, width: int, right: bool = False) -> str:
    """Trunca e alinha string em campo de largura fixa (monospace)."""
    s = s[:width]
    return s.rjust(width) if right else s.ljust(width)


def build_socios_report_text() -> str:
    """
    Relatório limpo em 2 partes:
      1) Tabela monospace: Sócio | 24h (Nx $) | 7d (Nx $) | 30d (Nx $) | Total
      2) Último pagamento por sócio (data, valor, token, ambiente)
    Enviado SOMENTE para OWNER_CHAT_ID.
    """
    now_utc  = datetime.now(tz=timezone.utc)
    now_str  = now_utc.strftime('%d/%m/%Y · %H:%M UTC')

    days24: set = {(now_utc - timedelta(hours=24 * i // 24)).strftime('%Y-%m-%d') for i in range(2)}
    # Usar timestamps exatos para 24h
    ts24h = int((now_utc - timedelta(hours=24)).timestamp())
    days7:  set = {(now_utc - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)}
    days30: set = {(now_utc - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30)}

    def _money(v: float) -> str:
        if v == 0:      return '$0'
        if v >= 10000:  return f'${v/1000:.0f}k'
        if v >= 1000:   return f'${v:,.0f}'
        return f'${v:,.0f}'

    def _cell(n: int, v: float) -> str:
        """Formata 'Nx $val' — mostra traço se zero."""
        if n == 0:
            return '—'
        return f'{n}x {_money(v)}'

    with _lock:
        rows       = []
        grand_24h  = (0, 0.0)
        grand_7d   = (0, 0.0)
        grand_30d  = (0, 0.0)
        grand_tot  = 0.0
        counts_snap = {a: dict(d) for a, d in _tx_counts.items()}
        last_snap   = dict(_last_payment)

        for addr, label in SOCIOS.items():
            env_hist = _history[addr]
            total = sum(sum(d.values()) for d in env_hist.values())

            def _period(day_set: set) -> tuple:
                v = sum(
                    v for d in env_hist.values()
                    for day, v in d.items() if day in day_set
                )
                n = sum(cnt for day, cnt in counts_snap[addr].items() if day in day_set)
                return n, v

            n24, v24 = _period(days24)
            n7,  v7  = _period(days7)
            n30, v30 = _period(days30)
            grand_24h = (grand_24h[0] + n24, grand_24h[1] + v24)
            grand_7d  = (grand_7d[0]  + n7,  grand_7d[1]  + v7)
            grand_30d = (grand_30d[0] + n30, grand_30d[1] + v30)
            grand_tot += total
            rows.append((addr, label, n24, v24, n7, v7, n30, v30, total))

    # ── Tabela ────────────────────────────────────────────────
    # Colunas: Sócio(10) | 24h(9) | 7d(9) | 30d(10) | Total(8)
    W = [10, 9, 9, 10, 8]
    SEP = '─' * (sum(W) + len(W) - 1)

    def _row(c0: str, c1: str, c2: str, c3: str, c4: str) -> str:
        return (
            _tc(c0, W[0]) + ' ' +
            _tc(c1, W[1], right=True) + ' ' +
            _tc(c2, W[2], right=True) + ' ' +
            _tc(c3, W[3], right=True) + ' ' +
            _tc(c4, W[4], right=True)
        )

    table = [_row('Sócio', '24h', '7d', '30d', 'Total'), SEP]
    for addr, label, n24, v24, n7, v7, n30, v30, total in rows:
        tag   = label.replace('Sócio ', 'S')
        short = addr[-6:]
        table.append(_row(
            f'{tag} …{short}',
            _cell(n24, v24),
            _cell(n7,  v7),
            _cell(n30, v30),
            _money(total),
        ))

    table.append(SEP)
    table.append(_row(
        'Total',
        _cell(*grand_24h),
        _cell(*grand_7d),
        _cell(*grand_30d),
        _money(grand_tot),
    ))

    # ── Último pagamento ──────────────────────────────────────
    lp_lines = []
    for addr, label in SOCIOS.items():
        lp  = last_snap.get(addr)
        tag = label.replace('Sócio ', 'S')
        if not lp:
            lp_lines.append(f'• {tag} — sem dados')
            continue
        days_ago = (now_utc.date() -
                    datetime.fromtimestamp(lp['ts'], tz=timezone.utc).date()).days
        ago_str  = 'hoje' if days_ago == 0 else ('ontem' if days_ago == 1 else f'{days_ago}d atrás')
        env_icon = {'AG_C_bd': '🔵', 'bd_v5': '🟢'}.get(lp['env'], '⚪')
        tok      = lp.get('token', 'USDT')
        lp_lines.append(
            f'{env_icon} <b>{tag}</b> · {lp["day"]} ({ago_str})'
            f' · <b>${lp["amount"]:,.2f} {tok}</b>'
        )

    parts = [
        '📊 <b>Comissões dos Sócios</b>',
        f'<i>{now_str}</i>\n',
        '<pre>' + '\n'.join(table) + '</pre>',
        '🕐 <b>Último pagamento</b>\n' + '\n'.join(lp_lines),
        f'\n🌐 <code>{NETWORK_CONTRACT[:20]}...</code>',
    ]
    return '\n'.join(parts)


# ─────────────────────────────────────────────────────────────
# Alerta imediato de pagamento
# ─────────────────────────────────────────────────────────────
def _alert_payment(addr: str, amount: float, tx_hash: str, env: str) -> None:
    label = SOCIOS.get(addr, addr[:10] + '...')
    short_addr = _short_addr(addr)
    short_hash = tx_hash[:16] + '...'
    env_label = ENV_LABELS.get(env, '⚪ ?')

    with _lock:
        today = datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')
        total = sum(sum(d.values()) for d in _history[addr].values())
        today_val = sum(d.get(today, 0.0) for d in _history[addr].values())
        grand_total = sum(sum(sum(d.values()) for d in v.values()) for v in _history.values())
        pct = (total / grand_total * 100) if grand_total > 0 else 0

    msg = (
        f'💰 <b>Comissão recebida — {label}</b>\n\n'
        f'💵 <b>Valor:</b> {_fmt_usdt(amount)} USDT\n'
        f'🏦 <b>Ambiente:</b> {env_label}\n'
        f'📅 <b>Hoje:</b> {_fmt_usdt(today_val)} USDT\n'
        f'📊 <b>Acumulado:</b> {_fmt_usdt(total)} USDT ({pct:.1f}%)\n\n'
        f'👛 <code>{short_addr}</code>\n'
        f'🔗 <code>{short_hash}</code>'
    )
    _send_telegram(msg)


# ─────────────────────────────────────────────────────────────
# Relatório diário com botão
# ─────────────────────────────────────────────────────────────
def send_socios_report() -> None:
    """Envia o relatório para OWNER_CHAT_ID com botão inline."""
    text = build_socios_report_text()
    _send_telegram(text, reply_markup=_refresh_button())
    logger.info('[socios] Relatório enviado.')


# ─────────────────────────────────────────────────────────────
# Loop principal de monitoramento
# ─────────────────────────────────────────────────────────────
def _monitor_loop() -> None:
    w3 = _w3()
    usdt_contract = w3.eth.contract(
        address=Web3.to_checksum_address(USDT_CONTRACT),
        abi=ABI_ERC20,
    )
    socio_addrs   = set(SOCIOS.keys())
    topic1_network = '0x' + '0' * 24 + NETWORK_CONTRACT[2:].lower()

    last_block = w3.eth.block_number - 50
    last_daily = 0

    logger.info('[socios] Monitor iniciado | bloco:%d | %d sócios', last_block, len(SOCIOS))

    while True:
        try:
            current = w3.eth.block_number

            # Relatório diário às 07:00 UTC
            now_utc = datetime.now(tz=timezone.utc)
            if now_utc.hour == 7 and now_utc.minute < 5 and (time.time() - last_daily) > 3600:
                send_socios_report()
                last_daily = time.time()

            if current > last_block:
                try:
                    logs = w3.eth.get_logs({
                        'address': Web3.to_checksum_address(USDT_CONTRACT),
                        'fromBlock': last_block + 1,
                        'toBlock': current,
                        'topics': [TOPIC_TRANSFER, topic1_network],
                    })
                    for log in logs:
                        try:
                            tx_hash = log['transactionHash'].hex().lower()
                            if tx_hash in _seen_hashes:
                                continue
                            ev = usdt_contract.events.Transfer().process_log(log)
                            to_addr = ev['args']['to'].lower()
                            if to_addr not in socio_addrs:
                                continue

                            amount = ev['args']['value'] / USDT_DECIMALS
                            day    = datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')
                            env    = _detect_env(w3, tx_hash)

                            with _lock:
                                _seen_hashes.add(tx_hash)
                                _history[to_addr][env][day] += amount
                                ts_now = int(time.time())
                                _tx_counts[to_addr][day] += 1
                                prev = _last_payment.get(to_addr)
                                if prev is None or ts_now > prev.get('ts', 0):
                                    _last_payment[to_addr] = {
                                        'amount': amount,
                                        'token':  'USDT',
                                        'day':    day,
                                        'ts':     ts_now,
                                        'env':    env,
                                        'hash':   tx_hash[:16],
                                    }

                            logger.info('[socios] Comissão: %s env=%s +%.2f USDT',
                                        SOCIOS.get(to_addr, to_addr[:10]), env, amount)
                            _alert_payment(to_addr, amount, tx_hash, env)

                        except Exception as e:
                            logger.debug('[socios] log erro: %s', e)

                    last_block = current
                except Exception as e:
                    if 'invalid block range' not in str(e).lower():
                        logger.warning('[socios] getLogs erro: %s', e)

        except Exception as e:
            logger.error('[socios] Loop erro: %s', e)
            try:
                w3 = _w3()
            except Exception:
                pass

        time.sleep(30)


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
def socios_monitor_worker() -> None:
    logger.info('[socios] Worker iniciado')
    t = threading.Thread(target=_backfill_history, daemon=True, name='socios_backfill')
    t.start()
    t.join(timeout=120)
    send_socios_report()
    _monitor_loop()
