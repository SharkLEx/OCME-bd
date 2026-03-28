from __future__ import annotations
# ==============================================================================
# monitors/socios.py — Monitor de Comissões dos Sócios
# Rastreia pagamentos via evento BalanceNetworkRemove no contrato Network.
# Cobre TODOS os tokens (USDT, DAI, LOOP) — ambiente detectado diretamente
# pelo campo `manager` do evento (sem RPC extra por transação).
# Envia relatório diário às 07:00 UTC + alerta imediato a cada pagamento.
# Destinatário: apenas OWNER_CHAT_ID (privado).
# ==============================================================================

import os, time, json, threading
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Dict

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

# Decimais por token (para converter value raw → float)
TOKEN_DECIMALS: Dict[str, int] = {
    '0xc2132d05d31c914a87c6611c10748aeb04b58e8f': 1_000_000,     # USDT (6 dec)
    '0x8f3cf7ad23cd3cadbd9735aff958023239c6a063': 10 ** 18,      # DAI  (18 dec)
    '0x9bb05b6c3bc29bfc68df7ebc70a19f7badfdd7dd8': 10 ** 18,    # LOOP (18 dec)
}
TOKEN_LABELS: Dict[str, str] = {
    '0xc2132d05d31c914a87c6611c10748aeb04b58e8f': 'USDT',
    '0x8f3cf7ad23cd3cadbd9735aff958023239c6a063': 'DAI',
    '0x9bb05b6c3bc29bfc68df7ebc70a19f7badfdd7dd8': 'LOOP',
}

# manager → ambiente
MANAGER_TO_ENV: Dict[str, str] = {
    '0x685d04d62da1ef26529c7aa1364da504c8acdb1d': 'AG_C_bd',
    '0x9826a9727d5bb97a44bf14fe2e2b0b1d5a81c860': 'bd_v5',
}
ENV_LABELS = {'AG_C_bd': '🔵 AG_C_bd', 'bd_v5': '🟢 bd_v5', 'desconhecido': '⚪ ?'}

# Tópico do evento correto
TOPIC_NET_REMOVE = Web3.to_hex(
    Web3.keccak(text='BalanceNetworkRemove(address,address,address,uint256,uint256,uint256)')
)

# ABI mínimo — apenas BalanceNetworkRemove
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

# Tópicos dos endereços dos sócios para filtro getLogs (topic[2] = user indexed)
_SOCIO_TOPICS = [
    '0x' + '0' * 24 + addr[2:].lower()
    for addr in SOCIOS
]

# Estado acumulado thread-safe
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
    return f'{addr[:6]}...{addr[-6:]}'


def _fmt_usdt(val: float) -> str:
    return f'${val:,.2f}'


def _send_telegram(text: str, reply_markup: dict | None = None) -> int | None:
    if not TELEGRAM_TOKEN or not OWNER_CHAT_ID:
        return None
    try:
        payload: dict = {'chat_id': OWNER_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}
        if reply_markup:
            payload['reply_markup'] = json.dumps(reply_markup)
        r = requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
            json=payload, timeout=10,
        )
        if r.ok:
            return r.json().get('result', {}).get('message_id')
    except Exception as e:
        logger.warning('[socios] Telegram erro: %s', e)
    return None


def _refresh_button() -> dict:
    return {'inline_keyboard': [[{'text': '🔄 Ver agora', 'callback_data': 'socios_report'}]]}


def _token_decimals(coin_addr: str) -> int:
    return TOKEN_DECIMALS.get(coin_addr.lower(), 1_000_000)


def _token_label(coin_addr: str) -> str:
    return TOKEN_LABELS.get(coin_addr.lower(), coin_addr[:8])


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

    # Tokens rastreados para backfill
    TRACKED = {
        'USDT': ('0xc2132D05D31c914a87C6611C10748AEb04B58e8F', 1_000_000),
        'DAI':  ('0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063', 10**18),
        'LOOP': ('0x9Bb05B6C3bC29BFC68DF7EbC70A19F7bAdFd7dd8', 10**18),
    }

    for addr, label in SOCIOS.items():
        for tok_name, (tok_addr, tok_dec) in TRACKED.items():
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
                    with _lock:
                        _history[addr]['desconhecido'][day] += val
                        _tx_counts[addr][day]               += 1
                        _seen_hashes.add(tx['hash'].lower())
                        prev = _last_payment.get(addr)
                        if prev is None or ts > prev['ts']:
                            _last_payment[addr] = {
                                'amount': val, 'token': tok_name, 'day': day,
                                'ts': ts, 'env': 'desconhecido', 'hash': tx['hash'][:16],
                            }

            except Exception as e:
                logger.warning('[socios] Backfill erro %s %s: %s', label, tok_name, e)

        with _lock:
            total = sum(sum(d.values()) for d in _history[addr].values())
        logger.info('[socios] Backfill %s: %.2f$ em history', label, total)

    logger.info('[socios] Backfill concluído.')


# ─────────────────────────────────────────────────────────────
# Relatório
# ─────────────────────────────────────────────────────────────
def _tc(s: str, width: int, right: bool = False) -> str:
    s = s[:width]
    return s.rjust(width) if right else s.ljust(width)


def build_socios_report_text() -> str:
    now_utc  = datetime.now(tz=timezone.utc)
    now_str  = now_utc.strftime('%d/%m/%Y · %H:%M UTC')
    days7    = {(now_utc - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)}
    days30   = {(now_utc - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30)}
    days24   = {(now_utc - timedelta(hours=24 * i // 24)).strftime('%Y-%m-%d') for i in range(2)}

    def _money(v: float) -> str:
        if v == 0:     return '$0'
        if v >= 10000: return f'${v/1000:.0f}k'
        if v >= 1000:  return f'${v:,.0f}'
        return f'${v:,.0f}'

    def _cell(n: int, v: float) -> str:
        return '—' if n == 0 else f'{n}x {_money(v)}'

    with _lock:
        rows = []
        grand_24h = grand_7d = grand_30d = (0, 0.0)
        grand_tot = 0.0
        counts_snap = {a: dict(d) for a, d in _tx_counts.items()}
        last_snap   = dict(_last_payment)

        for addr, label in SOCIOS.items():
            env_hist = _history[addr]
            total    = sum(sum(d.values()) for d in env_hist.values())

            def _period(day_set: set) -> tuple:
                v = sum(v for d in env_hist.values() for day, v in d.items() if day in day_set)
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

    W   = [10, 9, 9, 10, 8]
    SEP = '─' * (sum(W) + len(W) - 1)

    def _row(c0: str, c1: str, c2: str, c3: str, c4: str) -> str:
        return (
            _tc(c0, W[0]) + ' ' + _tc(c1, W[1], True) + ' ' +
            _tc(c2, W[2], True) + ' ' + _tc(c3, W[3], True) + ' ' +
            _tc(c4, W[4], True)
        )

    table = [_row('Sócio', '24h', '7d', '30d', 'Total'), SEP]
    for addr, label, n24, v24, n7, v7, n30, v30, total in rows:
        tag   = label.replace('Sócio ', 'S')
        short = addr[-6:]
        table.append(_row(
            f'{tag} …{short}', _cell(n24, v24), _cell(n7, v7), _cell(n30, v30), _money(total),
        ))
    table.append(SEP)
    table.append(_row('Total', _cell(*grand_24h), _cell(*grand_7d), _cell(*grand_30d), _money(grand_tot)))

    lp_lines = []
    for addr, label in SOCIOS.items():
        lp  = last_snap.get(addr)
        tag = label.replace('Sócio ', 'S')
        if not lp:
            lp_lines.append(f'• {tag} — sem dados')
            continue
        days_ago = (now_utc.date() - datetime.fromtimestamp(lp['ts'], tz=timezone.utc).date()).days
        ago_str  = 'hoje' if days_ago == 0 else ('ontem' if days_ago == 1 else f'{days_ago}d atrás')
        env_icon = {'AG_C_bd': '🔵', 'bd_v5': '🟢'}.get(lp['env'], '⚪')
        tok      = lp.get('token', 'USDT')
        lp_lines.append(
            f'{env_icon} <b>{tag}</b> · {lp["day"]} ({ago_str}) · <b>${lp["amount"]:,.2f} {tok}</b>'
        )

    parts = [
        '📊 <b>Comissões dos Sócios</b>',
        f'<i>{now_str}</i>\n',
        '<pre>' + '\n'.join(table) + '</pre>',
        '🕐 <b>Último pagamento</b>\n' + '\n'.join(lp_lines),
        f'\n🌐 <code>{NETWORK_CONTRACT[:20]}...</code>',
    ]
    return '\n'.join(parts)


def send_socios_report() -> None:
    text = build_socios_report_text()
    _send_telegram(text, reply_markup=_refresh_button())
    logger.info('[socios] Relatório enviado.')


# ─────────────────────────────────────────────────────────────
# Alerta imediato
# ─────────────────────────────────────────────────────────────
def _alert_payment(addr: str, amount: float, token: str, tx_hash: str, env: str) -> None:
    label     = SOCIOS.get(addr, addr[:10] + '...')
    env_label = ENV_LABELS.get(env, '⚪ ?')

    with _lock:
        today     = datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')
        total     = sum(sum(d.values()) for d in _history[addr].values())
        today_val = sum(d.get(today, 0.0) for d in _history[addr].values())
        grand_tot = sum(sum(sum(d.values()) for d in v.values()) for v in _history.values())
        pct       = (total / grand_tot * 100) if grand_tot > 0 else 0

    msg = (
        f'💰 <b>Comissão recebida — {label}</b>\n\n'
        f'💵 <b>Valor:</b> {_fmt_usdt(amount)} {token}\n'
        f'🏦 <b>Ambiente:</b> {env_label}\n'
        f'📅 <b>Hoje:</b> {_fmt_usdt(today_val)}\n'
        f'📊 <b>Acumulado:</b> {_fmt_usdt(total)} ({pct:.1f}%)\n\n'
        f'👛 <code>{_short_addr(addr)}</code>\n'
        f'🔗 <code>{tx_hash[:16]}...</code>'
    )
    _send_telegram(msg)


# ─────────────────────────────────────────────────────────────
# Loop principal — escuta BalanceNetworkRemove diretamente
# ─────────────────────────────────────────────────────────────
def _monitor_loop() -> None:
    w3 = _w3()
    net_contract = w3.eth.contract(
        address=Web3.to_checksum_address(NETWORK_CONTRACT),
        abi=ABI_NETWORK,
    )
    socio_addrs = set(SOCIOS.keys())

    last_block = w3.eth.block_number - 50
    last_daily = 0

    logger.info('[socios] Monitor iniciado | bloco:%d | %d sócios | evento:BalanceNetworkRemove',
                last_block, len(SOCIOS))

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
                        'address': Web3.to_checksum_address(NETWORK_CONTRACT),
                        'fromBlock': last_block + 1,
                        'toBlock':   current,
                        'topics': [
                            TOPIC_NET_REMOVE,  # topic[0] — event sig
                            None,              # topic[1] — manager (any)
                            _SOCIO_TOPICS,     # topic[2] — user = nossos sócios
                        ],
                    })

                    for log in logs:
                        try:
                            tx_hash = log['transactionHash'].hex().lower()
                            if tx_hash in _seen_hashes:
                                continue

                            ev      = net_contract.events.BalanceNetworkRemove().process_log(log)
                            manager = ev['args']['manager'].lower()
                            user    = ev['args']['user'].lower()
                            coin    = ev['args']['coin'].lower()
                            value   = ev['args']['value']

                            if user not in socio_addrs:
                                continue

                            decimals = _token_decimals(coin)
                            token    = _token_label(coin)
                            amount   = value / decimals
                            env      = MANAGER_TO_ENV.get(manager, 'desconhecido')
                            day      = datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')
                            ts_now   = int(time.time())

                            with _lock:
                                _seen_hashes.add(tx_hash)
                                _history[user][env][day] += amount
                                _tx_counts[user][day]    += 1
                                prev = _last_payment.get(user)
                                if prev is None or ts_now > prev.get('ts', 0):
                                    _last_payment[user] = {
                                        'amount': amount, 'token': token, 'day': day,
                                        'ts': ts_now, 'env': env, 'hash': tx_hash[:16],
                                    }

                            logger.info('[socios] Comissão: %s env=%s +%.2f %s',
                                        SOCIOS.get(user, user[:10]), env, amount, token)
                            _alert_payment(user, amount, token, tx_hash, env)

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
