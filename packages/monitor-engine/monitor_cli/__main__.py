#!/usr/bin/env python3
# ==============================================================================
# monitor_cli/__main__.py — CLI do OCME bd Monitor Engine
# OCME bd Monitor Engine — Story 7.1 (Constitution Art. I — CLI First)
#
# Uso:
#   python -m monitor_cli status
#   python -m monitor_cli report --period 24h --env AG_C_bd
#   python -m monitor_cli alerts list
#   python -m monitor_cli capital 0xWALLET
#   python -m monitor_cli vigia start
# ==============================================================================
from __future__ import annotations

import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Garante import do pacote pai
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config as cfg
from monitor_db.migrator import migrate, get_version
from monitor_db.queries import (
    config_get,
    ops_summary,
    ops_best_subconta,
    ops_last_inactivity_minutes,
    capital_get,
)


# ── Helpers de output ─────────────────────────────────────────────────────────

def _green(s: str) -> str:  return f'\033[92m{s}\033[0m'
def _red(s: str) -> str:    return f'\033[91m{s}\033[0m'
def _yellow(s: str) -> str: return f'\033[93m{s}\033[0m'
def _bold(s: str) -> str:   return f'\033[1m{s}\033[0m'
def _dim(s: str) -> str:    return f'\033[2m{s}\033[0m'


def _ok(label: str, value: str) -> str:
    return f'  {_green("✅")} {_bold(label):<20} {value}'

def _warn(label: str, value: str) -> str:
    return f'  {_yellow("⚠️ ")} {_bold(label):<20} {value}'

def _err(label: str, value: str) -> str:
    return f'  {_red("🔴")} {_bold(label):<20} {value}'


def _open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL')
    migrate(conn)
    return conn


def _period_hours(period: str) -> int:
    return {'24h': 24, '7d': 168, '30d': 720}.get(period, 24)


# ── Comando: status ───────────────────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> None:
    print()
    print(_bold('  🔭 OCME bd Monitor Engine — Status'))
    print('  ' + '─' * 50)

    conn = _open_db()

    # Vigia state
    last_block_str = config_get(conn, 'vigia_last_block', '0')
    last_block = int(last_block_str or 0)
    try:
        from monitor_chain.block_fetcher import BlockFetcher
        fetcher = BlockFetcher(cfg.RPC_URL)
        current_block = fetcher.get_latest_block()
        lag = current_block - last_block
        vigia_ok = lag < 50
        vigia_label = f'bloco {current_block:,} | lag: {lag} blocos'
        print(_ok('Vigia:', vigia_label) if vigia_ok else _warn('Vigia:', f'lag alto: {lag} blocos'))
    except Exception as exc:
        print(_err('Vigia:', f'RPC indisponível ({exc})'))

    # DB
    try:
        db_size = Path(cfg.DB_PATH).stat().st_size / (1024 * 1024)
        db_ver  = get_version(conn)
        print(_ok('DB:', f'{Path(cfg.DB_PATH).name} ({db_size:.1f} MB) schema v{db_ver}'))
    except Exception:
        print(_warn('DB:', cfg.DB_PATH + ' (não encontrado)'))

    # RPC
    rpc_display = cfg.RPC_URL.split('/v2/')[0] + '/v2/***' if '/v2/' in cfg.RPC_URL else cfg.RPC_URL[:40]
    print(_ok('RPC:', rpc_display))

    # IA
    if cfg.AI_API_KEY:
        print(_ok('IA:', f'{cfg.OPENAI_MODEL} ({"OpenRouter" if cfg.OPENROUTER_API_KEY else "OpenAI"})'))
    else:
        print(_warn('IA:', 'não configurada (sem OPENAI_API_KEY)'))

    # Ops hoje
    since_24h = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    try:
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(valor),0) FROM operacoes WHERE data_hora >= ? AND tipo='Trade'",
            (since_24h,)
        ).fetchone()
        count, profit = row or (0, 0)
        wallets = conn.execute(
            "SELECT COUNT(DISTINCT wallet) FROM op_owner ow "
            "JOIN operacoes o ON o.hash=ow.hash AND o.log_index=ow.log_index "
            "WHERE o.data_hora >= ? AND o.tipo='Trade'",
            (since_24h,)
        ).fetchone()[0] or 0
        print(_ok('Ops 24h:', f'{int(count):,} trades | lucro: ${float(profit):,.2f} | {wallets} wallets'))
    except Exception:
        print(_warn('Ops 24h:', 'sem dados'))

    # Última inatividade global
    try:
        last_dt_row = conn.execute(
            "SELECT MAX(data_hora) FROM operacoes WHERE tipo='Trade'"
        ).fetchone()
        if last_dt_row and last_dt_row[0]:
            dt = datetime.strptime(last_dt_row[0], '%Y-%m-%d %H:%M:%S')
            mins = (datetime.now() - dt).total_seconds() / 60
            label = f'último trade: {mins:.0f} min atrás ({last_dt_row[0]})'
            if mins > cfg.LIMITE_INATIV_MIN:
                print(_warn('Inatividade:', label))
            else:
                print(_ok('Inatividade:', label))
    except Exception:
        pass

    print()
    conn.close()


# ── Comando: report ───────────────────────────────────────────────────────────

def cmd_report(args: argparse.Namespace) -> None:
    period = args.period or '24h'
    env    = args.env
    wallet = args.wallet or cfg.WALLET_ADDRESS

    hours = _period_hours(period)
    conn  = _open_db()

    print()
    env_label = f' — {env}' if env else ''
    print(_bold(f'  📊 Relatório {period}{env_label}'))
    print('  ' + '─' * 50)

    summary = ops_summary(conn, wallet, hours=hours, env=env) if wallet else _global_summary(conn, hours, env)
    best    = ops_best_subconta(conn, wallet, hours=hours) if wallet else None

    print(f'  {"Trades:":<25} {summary["count"]:,}')
    print(f'  {"Lucro bruto:":<25} ${summary["profit_gross"]:,.2f}')
    print(f'  {"Gas gasto:":<25} ${summary["gas_total"]:,.4f}')
    print(f'  {"Taxas:":<25} ${summary["fee_total"]:,.4f}')
    print(f'  {_bold("Lucro líquido:"):<34} {_green("$" + f"{summary['profit_net']:,.2f}")}')

    if best:
        print(f'  {"Melhor subconta:":<25} {best["id"]} (+${best["profit"]:,.2f} | {best["trades"]} trades)')

    if wallet:
        inactiv = ops_last_inactivity_minutes(conn, wallet)
        if inactiv > 5:
            label = _yellow(f'{inactiv:.0f} min') if inactiv > cfg.LIMITE_INATIV_MIN else f'{inactiv:.0f} min'
            print(f'  {"Inatividade atual:":<25} {label}')

    print()
    conn.close()


def _global_summary(conn: sqlite3.Connection, hours: int, env: str | None) -> dict:
    from datetime import timedelta
    since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
    env_clause = 'AND ambiente = ?' if env else ''
    params = [since] + ([env] if env else [])
    try:
        row = conn.execute(f'''
            SELECT COUNT(*), COALESCE(SUM(valor),0), COALESCE(SUM(gas_usd),0), COALESCE(SUM(fee),0)
            FROM operacoes
            WHERE data_hora >= ? AND tipo='Trade' {env_clause}
        ''', params).fetchone() or (0, 0, 0, 0)
        c, g, gas, fee = row
        return {'count': int(c), 'profit_gross': float(g), 'gas_total': float(gas),
                'fee_total': float(fee), 'profit_net': float(g) - float(gas) - float(fee)}
    except Exception:
        return {'count': 0, 'profit_gross': 0, 'gas_total': 0, 'fee_total': 0, 'profit_net': 0}


# ── Comando: alerts ───────────────────────────────────────────────────────────

def cmd_alerts(args: argparse.Namespace) -> None:
    conn = _open_db()
    print()
    print(_bold('  🔔 Alertas'))
    print('  ' + '─' * 50)

    # Lê alertas da config
    keys = [k for k, _ in conn.execute(
        "SELECT chave, valor FROM config WHERE chave LIKE 'sentinela_alert_%'"
    ).fetchall()]

    if not keys:
        print('  Nenhum alerta registrado.')
    else:
        for key in keys:
            val = config_get(conn, key)
            try:
                ts = float(val or 0)
                dt = datetime.fromtimestamp(ts).strftime('%d/%m %H:%M')
                age = (time.time() - ts) / 60
                tipo = key.replace('sentinela_alert_', '').replace('_ts', '')
                status = _green('✅ Resolvido') if age > 30 else _red('🔴 Recente')
                print(f'  {status}  {tipo:<30} às {dt}')
            except Exception:
                print(f'  {key}: {val}')

    # Inatividade global
    try:
        row = conn.execute(
            "SELECT MAX(data_hora) FROM operacoes WHERE tipo='Trade'"
        ).fetchone()
        if row and row[0]:
            dt = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
            mins = (datetime.now() - dt).total_seconds() / 60
            if mins > cfg.LIMITE_INATIV_MIN:
                print(f'\n  {_red("🔴 ATIVO")}  inatividade_global               {mins:.0f} min sem trades')
            else:
                print(f'\n  {_green("✅ OK")}     sistema ativo                   último trade: {mins:.0f} min atrás')
    except Exception:
        pass

    print()
    conn.close()


# ── Comando: capital ──────────────────────────────────────────────────────────

def cmd_capital(args: argparse.Namespace) -> None:
    wallet = args.wallet or cfg.WALLET_ADDRESS
    if not wallet:
        print(_red('  ❌ Wallet não informada. Use: ocme-monitor capital 0xWALLET'))
        return

    conn = _open_db()
    print()
    print(_bold(f'  💰 Capital — {wallet[:10]}...{wallet[-6:]}'))
    print('  ' + '─' * 50)

    # Capital do cache
    cap = capital_get(conn, 0)  # sem chat_id — busca global
    if cap:
        print(f'  {"Capital total:":<25} ${cap["total_usd"]:,.2f}')
        if cap.get('breakdown'):
            for env_name, val in cap['breakdown'].items():
                pct = val / cap['total_usd'] * 100 if cap['total_usd'] else 0
                print(f'  {"├─ " + env_name + ":":<25} ${val:,.2f} ({pct:.1f}%)')
        ts = datetime.fromtimestamp(cap['updated_ts']).strftime('%d/%m %H:%M') if cap.get('updated_ts') else '?'
        print(f'  {_dim("Atualizado em: " + ts)}')
    else:
        print(_yellow('  ⚠️  Capital não encontrado no cache. Execute o vigia para popular.'))

    # Progressão 7d
    try:
        rows = conn.execute('''
            SELECT DATE(ts) as dia, SUM(total_usd) as total
            FROM user_capital_snapshots
            WHERE wallet = ? AND ts >= date('now', '-7 days')
            GROUP BY dia
            ORDER BY dia
        ''', (wallet.lower(),)).fetchall()
        if rows:
            print(f'\n  {"Progressão 7d:"}')
            for dia, total in rows:
                bar = '█' * min(int(float(total or 0) / 1000), 30)
                print(f'    {dia}  ${float(total or 0):>10,.2f}  {bar}')
    except Exception:
        pass

    print()
    conn.close()


# ── Comando: vigia ────────────────────────────────────────────────────────────

def cmd_vigia(args: argparse.Namespace) -> None:
    action = args.action or 'start'
    if action == 'start':
        _vigia_start()
    elif action == 'stop':
        print(_yellow('  Para o vigia: Ctrl+C no processo em execução.'))
    elif action == 'status':
        cmd_status(args)


def _vigia_start() -> None:
    '''Inicia vigia em modo CLI (foreground). Ctrl+C para parar.'''
    from web3 import Web3
    from monitor_chain.block_fetcher import BlockFetcher, TOPIC_OPENPOSITION, TOPIC_TRANSFER
    from monitor_chain.operation_parser import OperationParser
    from monitor_core.vigia import Vigia
    from monitor_core.sentinela import Sentinela
    from monitor_report.dashboard_cache import DashboardCache

    print()
    print(_bold('  🔭 Iniciando Vigia...'))

    conn = _open_db()

    # Configura tokens
    tokens_map = {
        cfg.TOKEN_USDT_ADDRESS.lower():  {'dec': 6, 'sym': 'USDT0',  'icon': '🔵'},
        cfg.TOKEN_LOOP_ADDRESS.lower():  {'dec': 9, 'sym': 'LOOP',   'icon': '🔴'},
    }
    for lp in cfg.TOKEN_LP_ADDRESSES:
        tokens_map[lp.lower()] = {'dec': 6, 'sym': 'LP', 'icon': '🟣'}

    fetcher = BlockFetcher(
        rpc_url=cfg.RPC_URL,
        chunk_size=cfg.MONITOR_FETCH_CHUNK,
    )

    parser = OperationParser(
        contracts=cfg.CONTRACTS,
        tokens_map=tokens_map,
    )

    # Endereços e topics a monitorar
    all_addrs = list({
        Web3.to_checksum_address(v)
        for env_data in cfg.CONTRACTS.values()
        for k, v in env_data.items()
        if k == 'PAYMENTS' and v.startswith('0x')
    })

    vigia = Vigia(
        fetcher=fetcher,
        parser=parser,
        conn=conn,
        addresses=all_addrs,
        topics=[TOPIC_OPENPOSITION],
        max_blocks_per_loop=cfg.MONITOR_MAX_BLOCKS_PER_LOOP,
        idle_sleep=cfg.MONITOR_IDLE_SLEEP,
        busy_sleep=cfg.MONITOR_BUSY_SLEEP,
        backlog_warn_at=cfg.MONITOR_BACKLOG_WARN_AT,
    )

    cache = DashboardCache(conn, vigia=vigia)

    sentinela = Sentinela(
        vigia=vigia,
        fetcher=fetcher,
        conn=conn,
        limite_gwei=cfg.LIMITE_GWEI,
        limite_gas_pol=cfg.LIMITE_GAS_BAIXO_POL,
        limite_inativ_min=cfg.LIMITE_INATIV_MIN,
    )

    # Log de operações no terminal
    def _on_op(op: dict) -> None:
        ts  = op.get('timestamp', '')[-8:]  # HH:MM:SS
        sub = (op.get('sub_conta') or '?')[:12]
        env = op.get('env', '?')
        val = op.get('profit_usd', 0)
        color = _green if val >= 0 else _red
        print(f'  [{ts}] {env:<10} {sub:<12} {color(f"${val:+.4f}")}')

    def _on_alert(tipo: str, dados: dict) -> None:
        print(f'\n  {_yellow("⚠️  ALERTA")} [{tipo}]: {dados.get("msg", "")}')

    def _on_progress(data: dict) -> None:
        lag = data.get('lag', 0)
        blk = data.get('block', 0)
        ops = data.get('ops_count', 0)
        if lag > 0 or ops > 0:
            print(f'  {_dim(f"bloco {blk:,} | lag {lag} | +{ops} ops")}', end='\r')

    vigia.on('operation', _on_op)
    vigia.on('progress',  _on_progress)
    sentinela.on_alert(_on_alert)

    vigia.start()
    sentinela.start()

    print(_green('  ✅ Vigia ativo. Ctrl+C para parar.\n'))
    print('  ' + '─' * 50)
    print(f'  {"Hora":<10} {"Ambiente":<12} {"SubConta":<14} Resultado')
    print('  ' + '─' * 50)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('\n')
        vigia.stop()
        sentinela.stop()
        print(_bold('  Vigia parado.'))

    conn.close()


# ── Parser principal ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog='ocme-monitor',
        description='OCME bd Monitor Engine — CLI (Constitution Art. I: CLI First)',
    )
    sub = parser.add_subparsers(dest='command', required=True)

    # status
    sub.add_parser('status', help='Status do sistema (vigia, DB, RPC, ops do dia)')

    # report
    rp = sub.add_parser('report', help='Relatório de operações')
    rp.add_argument('--period', choices=['24h', '7d', '30d'], default='24h')
    rp.add_argument('--env',    choices=['AG_C_bd', 'bd_v5'], default=None)
    rp.add_argument('--wallet', default=None)

    # alerts
    al = sub.add_parser('alerts', help='Gerenciar alertas')
    al.add_argument('action', nargs='?', choices=['list'], default='list')

    # capital
    cp = sub.add_parser('capital', help='Capital de uma wallet')
    cp.add_argument('wallet', nargs='?', default=None)

    # vigia
    vg = sub.add_parser('vigia', help='Controlar o watchdog')
    vg.add_argument('action', nargs='?', choices=['start', 'stop', 'status'], default='start')

    args = parser.parse_args()

    cmds = {
        'status':  cmd_status,
        'report':  cmd_report,
        'alerts':  cmd_alerts,
        'capital': cmd_capital,
        'vigia':   cmd_vigia,
    }

    cmds[args.command](args)


if __name__ == '__main__':
    main()
