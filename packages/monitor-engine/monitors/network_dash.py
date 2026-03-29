"""
monitors/network_dash.py — Network Fees Dashboard v2
Sincroniza Pay Fees do contrato Network (Polygonscan API) → SQLite local
e serve painel HTML na porta 7070 com visual WEbdEX.

Abas: Pagamentos Confirmados (saques sócios) / Pagamentos Pendentes (fees acumuladas)
Filtros: por carteira, por token, por data
Agrupado: por carteira/sócio
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import logging
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
POLYGONSCAN_KEY  = os.getenv('POLYGONSCAN_API_KEY', '')
NETWORK_CONTRACT = '0xfB2486E93E4Ab8A36d2e6C23004FacaAD3Bad5Db'
DASH_PORT        = int(os.getenv('FEES_DASH_PORT', '7070'))
FEES_DB_PATH     = os.getenv('FEES_DB_PATH', 'network_fees.db')
SYNC_INTERVAL    = 300  # segundos entre re-syncs

# Mapeamento de endereços de sócios → nomes
SOCIOS_MAP: dict[str, str] = {
    '0x7403305b41f96fc9f2e02ae79f79a59fc7fcafbb': 'Sócio 1',
    '0x1bbd1003c5643db910738e6ddf16754b7d6c7063': 'Sócio 2',
    '0x87e0cdf1a73be38a103e3f33282e621bf48ebec8': 'Sócio 3',
    '0xaf635b4e1ab085e9b8bf677aebe8a0d98511894f': 'Sócio 4',
    '0xe42e0c17edbed3f313ad4c9e93bd5e4a2b25edcd': 'Sócio 5',
    '0x403fd451beff4f71dfa0ef39d23ebe82b64c820d': 'Sócio 6',
}

# Managers → ambientes
MANAGER_MAP: dict[str, str] = {
    '0x685d04d62da1ef26529c7aa1364da504c8acdb1d': 'AG_C_bd',
    '0x9826a9727d5bb97a44bf14fe2e2b0b1d5a81c860': 'bd_v5',
}

# Tokens legítimos do protocolo
LEGIT_TOKENS = {'USDT0', 'WEbdEX', 'DAI', 'USDT', 'LP USD', 'LOOP', 'MATIC', 'POL'}
SPAM_SUBSTRINGS = ['t.me', 'http', 'claim', 'airdrop', 'visit', 'free', '.com', '.io', 'PAWS']

# ─────────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────────
_db_lock = threading.Lock()


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(FEES_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _db_lock:
        conn = _get_db()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS pay_fees (
                tx_hash       TEXT PRIMARY KEY,
                block_number  INTEGER,
                ts            INTEGER,
                from_addr     TEXT,
                to_addr       TEXT DEFAULT '',
                token_symbol  TEXT,
                token_address TEXT,
                amount        REAL,
                direction     TEXT DEFAULT "in"
            )
        ''')
        # Migration: adicionar to_addr em DBs existentes sem a coluna
        try:
            conn.execute("ALTER TABLE pay_fees ADD COLUMN to_addr TEXT DEFAULT ''")
        except Exception:
            pass  # coluna já existe

        conn.execute('CREATE INDEX IF NOT EXISTS idx_ts       ON pay_fees(ts)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_from     ON pay_fees(from_addr)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_to       ON pay_fees(to_addr)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_token    ON pay_fees(token_symbol)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_dir      ON pay_fees(direction)')
        conn.commit()
        conn.close()


# ─────────────────────────────────────────────────────────────
# Sync Polygonscan → SQLite
# ─────────────────────────────────────────────────────────────
def _fetch_page(page: int, offset: int = 1000) -> list[dict]:
    url = (
        'https://api.etherscan.io/v2/api?chainid=137'
        '&module=account&action=tokentx'
        f'&address={NETWORK_CONTRACT}'
        f'&page={page}&offset={offset}&sort=asc&apikey={POLYGONSCAN_KEY}'
    )
    try:
        r = requests.get(url, timeout=20)
        data = r.json()
        result = data.get('result', [])
        return result if isinstance(result, list) else []
    except Exception as e:
        logger.warning('[fees_dash] Polygonscan erro pág %d: %s', page, e)
        return []


def _sync_all() -> int:
    if not POLYGONSCAN_KEY:
        logger.warning('[fees_dash] POLYGONSCAN_API_KEY ausente — sync ignorado')
        return 0

    net_lower = NETWORK_CONTRACT.lower()
    inserted  = 0
    page      = 1

    logger.info('[fees_dash] Iniciando sync histórico...')
    while True:
        txs = _fetch_page(page)
        if not txs:
            break

        with _db_lock:
            conn = _get_db()
            for t in txs:
                sym = t.get('tokenSymbol', '')
                if any(s.lower() in sym.lower() for s in SPAM_SUBSTRINGS):
                    continue

                to_addr   = t.get('to', '').lower()
                from_addr = t.get('from', '').lower()
                direction = 'in' if to_addr == net_lower else 'out'
                dec    = int(t.get('tokenDecimal', 6))
                amount = int(t['value']) / (10 ** dec)
                try:
                    conn.execute(
                        'INSERT OR IGNORE INTO pay_fees '
                        '(tx_hash,block_number,ts,from_addr,to_addr,token_symbol,token_address,amount,direction) '
                        'VALUES (?,?,?,?,?,?,?,?,?)',
                        (
                            t['hash'].lower(),
                            int(t.get('blockNumber', 0)),
                            int(t['timeStamp']),
                            from_addr,
                            to_addr,
                            sym,
                            t.get('contractAddress', '').lower(),
                            amount,
                            direction,
                        )
                    )
                    inserted += conn.execute('SELECT changes()').fetchone()[0]
                except Exception as e:
                    logger.debug('[fees_dash] insert erro: %s', e)
            conn.commit()
            conn.close()

        if len(txs) < 1000:
            break
        page += 1
        time.sleep(0.25)

    logger.info('[fees_dash] Sync concluído: %d registros | páginas: %d', inserted, page)
    return inserted


def _sync_worker() -> None:
    _init_db()
    while True:
        try:
            _sync_all()
        except Exception as e:
            logger.error('[fees_dash] sync_worker erro: %s', e)
        time.sleep(SYNC_INTERVAL)


# ─────────────────────────────────────────────────────────────
# Queries
# ─────────────────────────────────────────────────────────────
def _query_wallets(direction: str = 'out', token: str = '',
                   search: str = '', date_from: str = '', date_to: str = '') -> dict:
    """Retorna totais agrupados por carteira para a aba Confirmados (out) ou Pendentes (in)."""
    addr_col = 'to_addr' if direction == 'out' else 'from_addr'

    conditions = ['direction = ?', f'{addr_col} != ?']
    params: list[Any] = [direction, '']

    if token:
        conditions.append('token_symbol = ?')
        params.append(token)
    if search:
        conditions.append(f'{addr_col} LIKE ?')
        params.append(f'%{search.lower()}%')
    if date_from:
        try:
            ts = int(datetime.strptime(date_from, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp())
            conditions.append('ts >= ?')
            params.append(ts)
        except ValueError:
            pass
    if date_to:
        try:
            ts = int((datetime.strptime(date_to, '%Y-%m-%d').replace(tzinfo=timezone.utc) + timedelta(days=1)).timestamp())
            conditions.append('ts < ?')
            params.append(ts)
        except ValueError:
            pass

    where = ' AND '.join(conditions)

    with _db_lock:
        conn = _get_db()
        # Totais por carteira + token
        rows = conn.execute(
            f'SELECT {addr_col} as wallet, token_symbol, '
            f'SUM(amount) as total, COUNT(*) as cnt, MAX(ts) as last_ts '
            f'FROM pay_fees WHERE {where} '
            f'GROUP BY {addr_col}, token_symbol ORDER BY total DESC',
            params
        ).fetchall()
        # Total geral
        total_row = conn.execute(
            f'SELECT SUM(amount), COUNT(*) FROM pay_fees WHERE {where}', params
        ).fetchone()
        conn.close()

    total_amount = float(total_row[0] or 0)
    total_count  = int(total_row[1] or 0)

    # Agrupar por carteira (consolidar tokens)
    wallets: dict[str, dict] = {}
    for r in rows:
        w = r['wallet']
        if w not in wallets:
            wallets[w] = {
                'wallet':  w,
                'name':    SOCIOS_MAP.get(w, 'Carteira Externa'),
                'tokens':  {},
                'total':   0.0,
                'cnt':     0,
                'last_ts': 0,
            }
        wallets[w]['tokens'][r['token_symbol']] = float(r['total'])
        wallets[w]['total']   += float(r['total'])
        wallets[w]['cnt']     += int(r['cnt'])
        wallets[w]['last_ts']  = max(wallets[w]['last_ts'], int(r['last_ts'] or 0))

    return {
        'wallets':      list(wallets.values()),
        'total_amount': total_amount,
        'total_count':  total_count,
    }


def _query_summary() -> dict:
    """Totais globais: total IN (fees), total OUT (saques), pendente = IN - OUT."""
    with _db_lock:
        conn = _get_db()
        total_in  = conn.execute("SELECT SUM(amount) FROM pay_fees WHERE direction='in'").fetchone()[0] or 0
        total_out = conn.execute("SELECT SUM(amount) FROM pay_fees WHERE direction='out'").fetchone()[0] or 0
        tokens_in = conn.execute(
            "SELECT token_symbol, SUM(amount) as t FROM pay_fees WHERE direction='in' GROUP BY token_symbol"
        ).fetchall()
        tokens_out = conn.execute(
            "SELECT token_symbol, SUM(amount) as t FROM pay_fees WHERE direction='out' GROUP BY token_symbol"
        ).fetchall()
        last_ts = conn.execute("SELECT MAX(ts) FROM pay_fees").fetchone()[0]
        conn.close()

    return {
        'total_in':   float(total_in),
        'total_out':  float(total_out),
        'pendente':   float(total_in - total_out),
        'by_token_in':  [dict(r) for r in tokens_in],
        'by_token_out': [dict(r) for r in tokens_out],
        'last_sync': datetime.fromtimestamp(last_ts, tz=timezone.utc).strftime('%d/%m/%Y %H:%M UTC') if last_ts else '—',
    }


def _query_fees(token: str = '', from_addr: str = '', date_from: str = '',
                date_to: str = '', direction: str = 'in',
                page: int = 1, per_page: int = 50) -> dict[str, Any]:
    conditions = ['direction = ?']
    params: list[Any] = [direction]

    if token:
        conditions.append('token_symbol = ?')
        params.append(token)
    if from_addr:
        conditions.append('(from_addr LIKE ? OR to_addr LIKE ?)')
        params += [f'%{from_addr.lower()}%', f'%{from_addr.lower()}%']
    if date_from:
        try:
            ts = int(datetime.strptime(date_from, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp())
            conditions.append('ts >= ?')
            params.append(ts)
        except ValueError:
            pass
    if date_to:
        try:
            ts = int((datetime.strptime(date_to, '%Y-%m-%d').replace(tzinfo=timezone.utc) + timedelta(days=1)).timestamp())
            conditions.append('ts < ?')
            params.append(ts)
        except ValueError:
            pass

    where  = ' AND '.join(conditions)
    offset = (page - 1) * per_page

    with _db_lock:
        conn = _get_db()
        total = conn.execute(f'SELECT COUNT(*) FROM pay_fees WHERE {where}', params).fetchone()[0]
        rows  = conn.execute(
            f'SELECT * FROM pay_fees WHERE {where} ORDER BY ts DESC LIMIT ? OFFSET ?',
            params + [per_page, offset]
        ).fetchall()
        conn.close()

    return {
        'total':    total,
        'page':     page,
        'per_page': per_page,
        'pages':    max(1, (total + per_page - 1) // per_page),
        'rows':     [dict(r) for r in rows],
    }


# ─────────────────────────────────────────────────────────────
# HTML Dashboard — visual WEbdEX (dark, match screenshots)
# ─────────────────────────────────────────────────────────────
_HTML = r"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WEbdEX · Pagamentos de Rede</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0a0a0f;--sidebar:#0d0d14;--card:#12121c;--border:#1e1e2e;
  --accent:#e8943a;--accent2:#ff6b35;--cyan:#00d4ff;
  --text:#d0d0e0;--muted:#555570;--green:#00c853;--red:#ff1744;
  --confirmed:#e8943a;--pending:#ff6b35;
}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px;display:flex;min-height:100vh}

/* Sidebar */
.sidebar{width:220px;background:var(--sidebar);border-right:1px solid var(--border);display:flex;flex-direction:column;padding:20px 0;flex-shrink:0}
.logo{padding:0 20px 24px;border-bottom:1px solid var(--border);margin-bottom:16px}
.logo-title{color:var(--cyan);font-size:15px;font-weight:700;letter-spacing:1px}
.logo-sub{color:var(--muted);font-size:10px;margin-top:2px}
.sidebar-stats{padding:10px 20px;margin-bottom:8px}
.stat-row{display:flex;justify-content:space-between;margin-bottom:4px}
.stat-label{color:var(--muted);font-size:10px}
.stat-val{color:var(--text);font-size:10px;font-weight:600}
.nav-item{padding:10px 20px;cursor:pointer;display:flex;align-items:center;gap:10px;color:var(--muted);font-size:12px;transition:all .15s}
.nav-item:hover{color:var(--text);background:rgba(255,255,255,.03)}
.nav-item.active{color:var(--accent);background:rgba(232,148,58,.08);border-right:2px solid var(--accent)}
.nav-icon{font-size:14px;width:16px;text-align:center}
.sidebar-footer{margin-top:auto;padding:16px 20px;border-top:1px solid var(--border)}
.sync-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--green);margin-right:6px;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

/* Main */
.main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.topbar{background:var(--sidebar);border-bottom:1px solid var(--border);padding:12px 24px;display:flex;align-items:center;justify-content:space-between}
.topbar-addr{font-size:11px;color:var(--muted);font-family:monospace}
.topbar-network{color:var(--cyan);font-size:11px;font-weight:600}
.content{flex:1;overflow-y:auto;padding:24px}

/* Page header */
.page-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
.page-title{font-size:20px;font-weight:700;color:var(--text)}
.controls{display:flex;gap:10px;align-items:center}
.select-wrap{display:flex;flex-direction:column;gap:3px}
.select-label{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
select,input{background:#0d0d14;border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:4px;font-size:12px;font-family:inherit;outline:none;cursor:pointer}
select:focus,input:focus{border-color:var(--accent)}
select option{background:#0d0d14}

/* Summary cards */
.summary-cards{display:flex;gap:16px;margin-bottom:20px}
.scard{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px 20px;flex:1}
.scard-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}
.scard-amount{font-size:26px;font-weight:700}
.scard-token{font-size:11px;color:var(--muted);margin-left:4px;font-weight:400}
.scard-confirmed .scard-amount{color:var(--confirmed)}
.scard-pending   .scard-amount{color:var(--pending)}

/* Tabs */
.tabs{display:flex;gap:0;margin-bottom:20px;border-bottom:1px solid var(--border)}
.tab{padding:10px 20px;cursor:pointer;font-size:13px;color:var(--muted);border-bottom:2px solid transparent;margin-bottom:-1px;transition:all .15s}
.tab:hover{color:var(--text)}
.tab.active{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}

/* Search */
.search-bar{display:flex;gap:10px;margin-bottom:16px;align-items:center}
.search-input{flex:1;max-width:340px;padding:8px 14px;border-radius:6px}
.btn{background:var(--accent);color:#000;border:none;padding:8px 18px;border-radius:5px;cursor:pointer;font-weight:700;font-size:12px;font-family:inherit}
.btn:hover{opacity:.85}
.btn-outline{background:transparent;border:1px solid var(--border);color:var(--text)}
.chip{display:inline-flex;align-items:center;gap:6px;background:#1a1a2e;border:1px solid var(--border);padding:3px 10px;border-radius:20px;font-size:11px;color:var(--muted);cursor:pointer}
.chip:hover{border-color:var(--accent);color:var(--accent)}

/* Wallet list */
.wallet-list-header{display:flex;justify-content:space-between;padding:6px 14px;margin-bottom:4px}
.wlh-col{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.wallet-item{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:14px 16px;margin-bottom:8px;display:flex;align-items:center;justify-content:space-between;cursor:pointer;transition:border-color .15s}
.wallet-item:hover{border-color:var(--accent)}
.wallet-left{display:flex;flex-direction:column;gap:3px}
.wallet-name{font-size:13px;font-weight:600;color:var(--text)}
.wallet-addr{font-size:10px;color:var(--muted);font-family:monospace;display:flex;align-items:center;gap:6px}
.wallet-copy{cursor:pointer;opacity:.5;font-size:11px}
.wallet-copy:hover{opacity:1}
.wallet-right{text-align:right}
.wallet-amount{font-size:15px;font-weight:700;color:var(--accent)}
.wallet-token{font-size:10px;color:var(--muted)}
.wallet-tokens{display:flex;gap:6px;margin-top:3px;justify-content:flex-end;flex-wrap:wrap}
.token-pill{font-size:10px;padding:1px 6px;border-radius:3px;border:1px solid var(--border);color:var(--muted)}
.empty{text-align:center;padding:48px;color:var(--muted);font-size:13px}
.loading{text-align:center;padding:40px;color:var(--muted)}

/* Txn table (detail view) */
.detail-table{width:100%;border-collapse:collapse;font-size:11px;margin-top:12px}
.detail-table th{padding:7px 10px;color:var(--muted);text-align:left;border-bottom:1px solid var(--border);text-transform:uppercase;font-size:9px;letter-spacing:.5px;font-weight:400}
.detail-table td{padding:7px 10px;border-bottom:1px solid #0f0f1a;vertical-align:middle}
.detail-table tr:hover td{background:#0d0d16}
.hash-link{color:var(--cyan);text-decoration:none;font-size:10px;font-family:monospace}
.hash-link:hover{text-decoration:underline}
.tag{display:inline-block;padding:2px 6px;border-radius:3px;font-size:10px;font-weight:700}
.tag-usdt{background:#0d2018;color:#00c853}
.tag-webdex{background:#0d0d2a;color:#7c7cff}
.tag-dai{background:#2a1800;color:#ffb300}
.tag-loop{background:#1a0d2a;color:#c77dff}
.tag-other{background:#1a1a1a;color:#888}
.pagination{display:flex;gap:6px;align-items:center;margin-top:12px;justify-content:flex-end}
.page-info{color:var(--muted);font-size:11px}
.expanded-row{background:#0d0d14;border-top:none}

/* Date filters */
.date-filters{display:flex;gap:8px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.date-filters label{display:flex;flex-direction:column;gap:2px;font-size:10px;color:var(--muted)}
input[type="date"]{padding:5px 8px;font-size:11px}
</style>
</head>
<body>

<!-- Sidebar -->
<aside class="sidebar">
  <div class="logo">
    <div class="logo-title">⬡ WEbdEX</div>
    <div class="logo-sub">Network Fees Monitor</div>
  </div>
  <div class="sidebar-stats">
    <div class="stat-row"><span class="stat-label">Total de sócios</span><span class="stat-val" id="s-socios">6</span></div>
    <div class="stat-row"><span class="stat-label">Bot selecionado</span><span class="stat-val" id="s-bot">WEbdEX V.x</span></div>
  </div>
  <nav>
    <div class="nav-item"><span class="nav-icon">📊</span>Painel</div>
    <div class="nav-item"><span class="nav-icon">👥</span>Lista de usuários</div>
    <div class="nav-item"><span class="nav-icon">🏛️</span>Lista de admins</div>
    <div class="nav-item active"><span class="nav-icon">💸</span>Pagamentos de rede</div>
  </nav>
  <div class="sidebar-footer">
    <div style="font-size:10px;color:var(--muted)"><span class="sync-dot"></span><span id="sync-label">Sincronizando...</span></div>
    <div style="font-size:9px;color:var(--muted);margin-top:4px;font-family:monospace" id="last-sync-time">—</div>
    <button class="btn btn-outline" style="margin-top:10px;width:100%;font-size:11px;padding:6px" onclick="forceSync()">⟳ Sync agora</button>
  </div>
</aside>

<!-- Main -->
<div class="main">
  <!-- Topbar -->
  <div class="topbar">
    <span class="topbar-addr" id="contract-addr">Contrato: 0xfB2486E93E4Ab8A36d2e6C23004FacaAD3Bad5Db</span>
    <span class="topbar-network">Rede principal da Polygon</span>
  </div>

  <!-- Content -->
  <div class="content">
    <!-- Page header -->
    <div class="page-header">
      <div class="page-title" id="page-title">PAGAMENTOS CONFIRMADOS</div>
      <div class="controls">
        <div class="select-wrap">
          <span class="select-label">Modo de visualização</span>
          <select id="view-mode" onchange="onViewMode()">
            <option value="wallet">Por carteira</option>
            <option value="txn">Por transação</option>
          </select>
        </div>
        <div class="select-wrap">
          <span class="select-label">Filtrar por moeda</span>
          <select id="f-token" onchange="load()">
            <option value="">Todas</option>
            <option>WEbdEX</option>
            <option>Loop (LBSS)</option>
            <option value="USDT0">(Poly) Tether USD</option>
            <option>DAI</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Summary cards -->
    <div class="summary-cards">
      <div class="scard scard-confirmed">
        <div class="scard-label">Total pago</div>
        <div><span class="scard-amount" id="total-pago">—</span><span class="scard-token">USDT</span></div>
      </div>
      <div class="scard scard-pending">
        <div class="scard-label">Total pendente</div>
        <div><span class="scard-amount" id="total-pendente">—</span><span class="scard-token">USDT</span></div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <div class="tab active" id="tab-confirmed" onclick="switchTab('confirmed')">Pagamentos confirmados</div>
      <div class="tab" id="tab-pending" onclick="switchTab('pending')">Pagamentos Pendentes</div>
    </div>

    <!-- Search bar -->
    <div class="search-bar">
      <input class="search-input" id="f-search" placeholder="Buscar usuário (endereço ou nome)..." oninput="debounce(load,400)()">
      <button class="btn" onclick="load()">Filtro</button>
      <button class="btn btn-outline" onclick="resetFilters()">✕ Limpar</button>
    </div>
    <div class="chip" id="chip-filter" style="display:none;margin-bottom:12px">
      <span id="chip-text"></span>
      <span onclick="resetFilters()">✕</span>
    </div>

    <!-- Date filters -->
    <div class="date-filters">
      <label>De: <input type="date" id="f-date-from" onchange="load()"></label>
      <label>Até: <input type="date" id="f-date-to" onchange="load()"></label>
    </div>

    <!-- Wallet list header -->
    <div class="wallet-list-header">
      <span class="wlh-col">Administrador / Carteira</span>
      <span class="wlh-col">Pagamento Total</span>
    </div>

    <!-- Content area -->
    <div id="content-area"><div class="loading">Carregando...</div></div>

    <!-- Pagination (txn mode) -->
    <div class="pagination" id="pagination" style="display:none">
      <span class="page-info" id="page-info"></span>
      <button class="btn btn-outline" id="btn-prev" onclick="goPage(-1)">← Anterior</button>
      <button class="btn btn-outline" id="btn-next" onclick="goPage(1)">Próxima →</button>
    </div>
  </div>
</div>

<script>
const SOCIOS = {
  '0x7403305b41f96fc9f2e02ae79f79a59fc7fcafbb': 'Sócio 1',
  '0x1bbd1003c5643db910738e6ddf16754b7d6c7063': 'Sócio 2',
  '0x87e0cdf1a73be38a103e3f33282e621bf48ebec8': 'Sócio 3',
  '0xaf635b4e1ab085e9b8bf677aebe8a0d98511894f': 'Sócio 4',
  '0xe42e0c17edbed3f313ad4c9e93bd5e4a2b25edcd': 'Sócio 5',
  '0x403fd451beff4f71dfa0ef39d23ebe82b64c820d': 'Sócio 6',
};

let currentTab  = 'confirmed';  // confirmed | pending
let currentPage = 1;
let totalPages  = 1;
let _deb        = null;

function debounce(fn, ms) {
  return function(...args) { clearTimeout(_deb); _deb = setTimeout(() => fn(...args), ms); };
}

function shortAddr(a) { return a.slice(0,8)+'...'+a.slice(-6); }

function fmtAmt(v) {
  const n = parseFloat(v);
  if (n === 0) return '0.00';
  if (n < 0.01) return n.toFixed(8);
  return n.toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:6});
}

function fmtTs(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleDateString('pt-BR') + ' ' + d.toLocaleTimeString('pt-BR', {hour:'2-digit',minute:'2-digit'}) + ' UTC';
}

function tokenTag(sym) {
  const map = {
    'USDT0': 'tag-usdt', 'USDT': 'tag-usdt',
    'WEbdEX': 'tag-webdex',
    'DAI': 'tag-dai',
    'LOOP': 'tag-loop', 'Loop (LBSS)': 'tag-loop',
  };
  const cls = map[sym] || 'tag-other';
  return `<span class="tag ${cls}">${sym}</span>`;
}

function walletName(addr) {
  const a = addr.toLowerCase();
  return SOCIOS[a] || ('Carteira ' + shortAddr(addr));
}

function copyAddr(addr) {
  navigator.clipboard.writeText(addr).catch(() => {});
}

// Tabs
function switchTab(tab) {
  currentTab = tab;
  document.getElementById('tab-confirmed').classList.toggle('active', tab === 'confirmed');
  document.getElementById('tab-pending').classList.toggle('active', tab === 'pending');
  document.getElementById('page-title').textContent =
    tab === 'confirmed' ? 'PAGAMENTOS CONFIRMADOS' : 'PAGAMENTOS PENDENTES';
  currentPage = 1;
  load();
}

function onViewMode() { currentPage = 1; load(); }

function resetFilters() {
  document.getElementById('f-search').value    = '';
  document.getElementById('f-token').value     = '';
  document.getElementById('f-date-from').value = '';
  document.getElementById('f-date-to').value   = '';
  document.getElementById('chip-filter').style.display = 'none';
  load();
}

// Load summary cards
async function loadSummary() {
  try {
    const r = await fetch('/api/summary');
    const d = await r.json();
    document.getElementById('total-pago').textContent    = fmtAmt(d.total_out);
    document.getElementById('total-pendente').textContent = fmtAmt(d.pendente);
    document.getElementById('last-sync-time').textContent = d.last_sync;
    document.getElementById('sync-label').textContent = 'Última sincronização';

    // Populate token select from real data
    const sel = document.getElementById('f-token');
    const existing = new Set([...sel.options].map(o => o.value));
    [...d.by_token_in, ...d.by_token_out].forEach(t => {
      if (!existing.has(t.token_symbol) && t.token_symbol) {
        const opt = document.createElement('option');
        opt.value = opt.textContent = t.token_symbol;
        sel.appendChild(opt);
        existing.add(t.token_symbol);
      }
    });
  } catch(e) {
    document.getElementById('sync-label').textContent = 'Erro ao carregar';
  }
}

// Main load
async function load() {
  const mode = document.getElementById('view-mode').value;
  if (mode === 'wallet') await loadWallets();
  else await loadTxns();

  // Update chip
  const search = document.getElementById('f-search').value;
  const token  = document.getElementById('f-token').value;
  if (search || token) {
    const parts = [];
    if (search) parts.push(shortAddr(search) || search);
    if (token)  parts.push(token);
    document.getElementById('chip-text').textContent = parts.join(' · ');
    document.getElementById('chip-filter').style.display = 'inline-flex';
  } else {
    document.getElementById('chip-filter').style.display = 'none';
  }
}

async function loadWallets() {
  document.getElementById('pagination').style.display = 'none';
  document.getElementById('content-area').innerHTML = '<div class="loading">Carregando carteiras...</div>';

  const direction = currentTab === 'confirmed' ? 'out' : 'in';
  const qs = new URLSearchParams({
    direction,
    token:     document.getElementById('f-token').value,
    search:    document.getElementById('f-search').value,
    date_from: document.getElementById('f-date-from').value,
    date_to:   document.getElementById('f-date-to').value,
  });

  try {
    const r = await fetch('/api/wallets?' + qs);
    const d = await r.json();

    if (!d.wallets.length) {
      document.getElementById('content-area').innerHTML =
        '<div class="empty">Nenhum pagamento encontrado para os filtros selecionados.</div>';
      return;
    }

    let html = '';
    d.wallets.forEach(w => {
      const name = SOCIOS[w.wallet] || w.name;
      const addr = w.wallet;
      const tokens = Object.entries(w.tokens)
        .map(([sym, amt]) => `<span class="token-pill">${sym}: ${fmtAmt(amt)}</span>`)
        .join('');

      html += `
        <div class="wallet-item" onclick="toggleWalletDetail('${addr}', '${currentTab === 'confirmed' ? 'out' : 'in'}')">
          <div class="wallet-left">
            <div class="wallet-name">Nome: ${name}</div>
            <div class="wallet-addr">
              Endereço: <span>${shortAddr(addr)}</span>
              <span class="wallet-copy" onclick="event.stopPropagation();copyAddr('${addr}')" title="${addr}">⧉</span>
            </div>
          </div>
          <div class="wallet-right">
            <div class="wallet-amount">${fmtAmt(w.total)} USDT</div>
            <div class="wallet-tokens">${tokens}</div>
          </div>
        </div>
        <div id="detail-${addr}" style="display:none;margin-bottom:8px"></div>`;
    });
    document.getElementById('content-area').innerHTML = html;
  } catch(e) {
    document.getElementById('content-area').innerHTML =
      `<div class="empty" style="color:var(--red)">Erro: ${e.message}</div>`;
  }
}

async function toggleWalletDetail(addr, direction) {
  const el = document.getElementById('detail-' + addr);
  if (!el) return;
  if (el.style.display !== 'none') { el.style.display = 'none'; return; }

  el.style.display = 'block';
  el.innerHTML = '<div class="loading" style="padding:16px">Carregando transações...</div>';

  const qs = new URLSearchParams({ direction, from_addr: addr, per_page: 20 });
  try {
    const r = await fetch('/api/fees?' + qs);
    const d = await r.json();
    if (!d.rows.length) { el.innerHTML = '<div class="loading">Sem transações</div>'; return; }

    let html = `<table class="detail-table"><thead><tr>
      <th>Data</th><th>Token</th><th>Valor</th><th>TX Hash</th>
    </tr></thead><tbody>`;
    d.rows.forEach(row => {
      html += `<tr>
        <td>${fmtTs(row.ts)}</td>
        <td>${tokenTag(row.token_symbol)}</td>
        <td style="color:var(--accent);font-weight:600">${fmtAmt(row.amount)}</td>
        <td><a class="hash-link" href="https://polygonscan.com/tx/${row.tx_hash}" target="_blank">${row.tx_hash.slice(0,20)}…</a></td>
      </tr>`;
    });
    html += `</tbody></table>`;
    if (d.total > 20) html += `<div style="text-align:right;font-size:10px;color:var(--muted);margin-top:6px">${d.total} transações no total</div>`;
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = `<div style="color:var(--red);padding:10px;font-size:11px">Erro: ${e.message}</div>`;
  }
}

async function loadTxns() {
  document.getElementById('pagination').style.display = 'flex';
  const direction = currentTab === 'confirmed' ? 'out' : 'in';
  const qs = new URLSearchParams({
    page:      currentPage,
    direction,
    token:     document.getElementById('f-token').value,
    from_addr: document.getElementById('f-search').value,
    date_from: document.getElementById('f-date-from').value,
    date_to:   document.getElementById('f-date-to').value,
  });

  document.getElementById('content-area').innerHTML = '<div class="loading">Buscando...</div>';
  try {
    const r = await fetch('/api/fees?' + qs);
    const d = await r.json();
    totalPages = d.pages;

    document.getElementById('page-info').textContent = `Pág ${d.page}/${d.pages} · ${d.total.toLocaleString()} registros`;
    document.getElementById('btn-prev').disabled = currentPage <= 1;
    document.getElementById('btn-next').disabled = currentPage >= totalPages;

    if (!d.rows.length) {
      document.getElementById('content-area').innerHTML = '<div class="empty">Nenhum resultado.</div>';
      return;
    }

    let html = `<table class="detail-table"><thead><tr>
      <th>Data/Hora</th><th>Carteira</th><th>Token</th><th>Valor</th><th>TX Hash</th>
    </tr></thead><tbody>`;
    d.rows.forEach(row => {
      const addr = direction === 'out' ? row.to_addr : row.from_addr;
      const name = addr ? (SOCIOS[addr] || shortAddr(addr)) : '—';
      html += `<tr>
        <td>${fmtTs(row.ts)}</td>
        <td><span title="${addr}">${name}</span></td>
        <td>${tokenTag(row.token_symbol)}</td>
        <td style="color:var(--accent);font-weight:600">${fmtAmt(row.amount)}</td>
        <td><a class="hash-link" href="https://polygonscan.com/tx/${row.tx_hash}" target="_blank">${row.tx_hash.slice(0,20)}…</a></td>
      </tr>`;
    });
    html += '</tbody></table>';
    document.getElementById('content-area').innerHTML = html;
  } catch(e) {
    document.getElementById('content-area').innerHTML =
      `<div class="empty" style="color:var(--red)">Erro: ${e.message}</div>`;
  }
}

function goPage(delta) {
  const next = currentPage + delta;
  if (next < 1 || next > totalPages) return;
  currentPage = next;
  loadTxns();
}

async function forceSync() {
  document.getElementById('sync-label').textContent = 'Sincronizando...';
  await fetch('/api/sync');
  setTimeout(() => { loadSummary(); load(); }, 3000);
}

// Init
loadSummary();
load();
setInterval(() => loadSummary(), 60000);
</script>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────
# HTTP Handler
# ─────────────────────────────────────────────────────────────
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def _send(self, code: int, body: str | bytes, content_type: str = 'application/json') -> None:
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path   = parsed.path
        qs     = parse_qs(parsed.query)

        def q(key: str, default: str = '') -> str:
            return qs.get(key, [default])[0]

        if path == '/':
            self._send(200, _HTML, 'text/html; charset=utf-8')

        elif path == '/api/wallets':
            result = _query_wallets(
                direction = q('direction', 'out'),
                token     = q('token'),
                search    = q('search'),
                date_from = q('date_from'),
                date_to   = q('date_to'),
            )
            self._send(200, json.dumps(result))

        elif path == '/api/summary':
            self._send(200, json.dumps(_query_summary()))

        elif path == '/api/fees':
            result = _query_fees(
                token     = q('token'),
                from_addr = q('from_addr'),
                date_from = q('date_from'),
                date_to   = q('date_to'),
                direction = q('direction', 'in'),
                page      = int(q('page', '1')),
                per_page  = int(q('per_page', '50')),
            )
            for row in result['rows']:
                row['date'] = datetime.fromtimestamp(row['ts'], tz=timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
            self._send(200, json.dumps(result))

        elif path == '/api/sync':
            threading.Thread(target=_sync_all, daemon=True).start()
            self._send(200, json.dumps({'status': 'sync_started'}))

        elif path == '/api/stats':
            self._send(200, json.dumps(_query_summary()))

        else:
            self._send(404, json.dumps({'error': 'not found'}))


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
def network_fees_dash_worker() -> None:
    """Inicia sync periódico + servidor HTTP. Roda como daemon thread."""
    logger.info('[fees_dash] Worker iniciado | porta %d | db: %s', DASH_PORT, FEES_DB_PATH)
    _init_db()
    threading.Thread(target=_sync_worker, daemon=True, name='fees_sync').start()
    try:
        server = HTTPServer(('0.0.0.0', DASH_PORT), _Handler)
        logger.info('[fees_dash] HTTP server em 0.0.0.0:%d', DASH_PORT)
        server.serve_forever()
    except Exception as e:
        logger.error('[fees_dash] HTTP server erro: %s', e)
