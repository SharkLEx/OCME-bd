"""
webdex_network_dash.py — Network Fees Dashboard
Sincroniza todas as Pay Fee do contrato Network (Polygonscan API)
para SQLite local e serve um painel HTML na porta 7070.

Endpoints:
  GET /           → Dashboard HTML
  GET /api/fees   → JSON com transações (filtros: token, from, date_from, date_to, page)
  GET /api/stats  → JSON com estatísticas globais
  GET /api/sync   → Força re-sync manual
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

# Tokens legítimos do protocolo — qualquer outro é spam/airdrop
LEGIT_TOKENS = {'USDT0', 'WEbdEX', 'DAI', 'USDT', 'LP USD', 'LOOP', 'MATIC', 'POL'}
# Tokens spam conhecidos (substrings) — excluídos do sync
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
                token_symbol  TEXT,
                token_address TEXT,
                amount        REAL,
                direction     TEXT DEFAULT "in"
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ts       ON pay_fees(ts)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_from     ON pay_fees(from_addr)')
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
    """Busca todas as transações históricas e salva no SQLite. Retorna total inserido."""
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
                # Filtrar spam tokens (airdrops com URLs/texto no símbolo)
                sym = t.get('tokenSymbol', '')
                if any(s.lower() in sym.lower() for s in SPAM_SUBSTRINGS):
                    continue

                direction = 'in' if t['to'].lower() == net_lower else 'out'
                dec = int(t.get('tokenDecimal', 6))
                amount = int(t['value']) / (10 ** dec)
                try:
                    conn.execute(
                        'INSERT OR IGNORE INTO pay_fees '
                        '(tx_hash,block_number,ts,from_addr,token_symbol,token_address,amount,direction) '
                        'VALUES (?,?,?,?,?,?,?,?)',
                        (
                            t['hash'].lower(),
                            int(t.get('blockNumber', 0)),
                            int(t['timeStamp']),
                            t['from'].lower(),
                            t.get('tokenSymbol', '?'),
                            t.get('contractAddress', '').lower(),
                            amount,
                            direction,
                        )
                    )
                    inserted += conn.execute(
                        'SELECT changes()'
                    ).fetchone()[0]
                except Exception as e:
                    logger.debug('[fees_dash] insert erro: %s', e)
            conn.commit()
            conn.close()

        if len(txs) < 1000:
            break  # última página
        page += 1
        time.sleep(0.25)  # rate limit gentil

    logger.info('[fees_dash] Sync concluído: %d registros | total páginas: %d', inserted, page)
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
# API helpers
# ─────────────────────────────────────────────────────────────
def _query_fees(token: str = '', from_addr: str = '', date_from: str = '',
                date_to: str = '', direction: str = 'in',
                page: int = 1, per_page: int = 50) -> dict[str, Any]:
    conditions = ['direction = ?']
    params: list[Any] = [direction]

    if token:
        conditions.append('token_symbol = ?')
        params.append(token)
    if from_addr:
        conditions.append('from_addr LIKE ?')
        params.append(f'%{from_addr.lower()}%')
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
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': max(1, (total + per_page - 1) // per_page),
        'rows': [dict(r) for r in rows],
    }


def _query_stats() -> dict[str, Any]:
    with _db_lock:
        conn = _get_db()
        # Totais por token (incoming)
        by_token = conn.execute(
            "SELECT token_symbol, COUNT(*) as cnt, SUM(amount) as total "
            "FROM pay_fees WHERE direction='in' GROUP BY token_symbol ORDER BY total DESC"
        ).fetchall()
        # Totais por dia (últimos 30d)
        ts30 = int((datetime.now(tz=timezone.utc) - timedelta(days=30)).timestamp())
        by_day = conn.execute(
            "SELECT date(ts,'unixepoch') as day, token_symbol, COUNT(*) as cnt, SUM(amount) as total "
            "FROM pay_fees WHERE direction='in' AND ts >= ? "
            "GROUP BY day, token_symbol ORDER BY day DESC LIMIT 90",
            (ts30,)
        ).fetchall()
        # Payers únicos
        unique_payers = conn.execute(
            "SELECT COUNT(DISTINCT from_addr) FROM pay_fees WHERE direction='in'"
        ).fetchone()[0]
        # Total txns
        total_txns = conn.execute(
            "SELECT COUNT(*) FROM pay_fees WHERE direction='in'"
        ).fetchone()[0]
        # Última sync
        last_ts = conn.execute("SELECT MAX(ts) FROM pay_fees").fetchone()[0]
        conn.close()

    return {
        'total_txns':     total_txns,
        'unique_payers':  unique_payers,
        'last_sync':      datetime.fromtimestamp(last_ts, tz=timezone.utc).strftime('%d/%m/%Y %H:%M UTC') if last_ts else '-',
        'by_token':       [dict(r) for r in by_token],
        'daily_30d':      [dict(r) for r in by_day],
    }


# ─────────────────────────────────────────────────────────────
# HTML Dashboard (single-file, vanilla JS)
# ─────────────────────────────────────────────────────────────
_HTML = r"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WEbdEX · Network Fees</title>
<style>
  :root{--bg:#0d0d0d;--card:#161616;--border:#2a2a2a;--accent:#00e5ff;--text:#e0e0e0;--muted:#888;--green:#00c853;--red:#ff1744}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:'Courier New',monospace;font-size:13px;padding:16px}
  h1{color:var(--accent);font-size:18px;margin-bottom:4px}
  .subtitle{color:var(--muted);font-size:11px;margin-bottom:20px}
  .cards{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:20px}
  .card{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:14px 18px;min-width:160px;flex:1}
  .card-label{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:1px}
  .card-value{color:var(--accent);font-size:22px;font-weight:bold;margin-top:4px}
  .card-sub{color:var(--muted);font-size:11px;margin-top:2px}
  .token-cards{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px}
  .token-card{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:10px 14px;flex:1;min-width:120px}
  .token-card .sym{color:var(--accent);font-weight:bold;font-size:12px}
  .token-card .val{font-size:16px;margin-top:2px}
  .token-card .cnt{color:var(--muted);font-size:10px}
  .filters{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px;align-items:flex-end}
  .filters label{display:flex;flex-direction:column;gap:3px;font-size:10px;color:var(--muted)}
  .filters input,.filters select{background:#1e1e1e;border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:4px;font-family:inherit;font-size:12px;outline:none}
  .filters input:focus,.filters select:focus{border-color:var(--accent)}
  .btn{background:var(--accent);color:#000;border:none;padding:7px 16px;border-radius:4px;cursor:pointer;font-weight:bold;font-size:12px}
  .btn:hover{opacity:.85}
  .btn-sm{padding:4px 10px;font-size:11px}
  .btn-outline{background:transparent;border:1px solid var(--border);color:var(--text)}
  table{width:100%;border-collapse:collapse;font-size:11px}
  thead{background:#111;position:sticky;top:0;z-index:1}
  th{padding:8px 10px;color:var(--muted);text-align:left;border-bottom:1px solid var(--border);font-weight:normal;text-transform:uppercase;font-size:10px;letter-spacing:.5px}
  td{padding:7px 10px;border-bottom:1px solid #1a1a1a;vertical-align:middle}
  tr:hover td{background:#1c1c1c}
  .hash{color:var(--accent);text-decoration:none;font-size:10px}
  .hash:hover{text-decoration:underline}
  .addr{color:var(--muted);font-size:10px}
  .tag{display:inline-block;padding:2px 6px;border-radius:3px;font-size:10px;font-weight:bold}
  .tag-usdt{background:#1a3a2a;color:#00c853}
  .tag-webdex{background:#1a1a3a;color:#7c7cff}
  .tag-dai{background:#3a2a00;color:#ffb300}
  .tag-other{background:#2a2a2a;color:#888}
  .amount{font-weight:bold;color:var(--text)}
  .amount-tiny{color:var(--muted)}
  .pagination{display:flex;gap:6px;align-items:center;margin-top:14px;justify-content:flex-end}
  .page-info{color:var(--muted);font-size:11px}
  .table-wrap{overflow-x:auto}
  .status-bar{background:var(--card);border:1px solid var(--border);border-radius:4px;padding:8px 14px;margin-bottom:14px;font-size:11px;color:var(--muted);display:flex;justify-content:space-between;align-items:center}
  .dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--green);margin-right:6px;animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
  .loading{text-align:center;padding:40px;color:var(--muted)}
  .section-title{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
</style>
</head>
<body>
<h1>⬡ WEbdEX · Network Fees Dashboard</h1>
<p class="subtitle">Contrato: 0xfB2486E93E4Ab8A36d2e6C23004FacaAD3Bad5Db · Polygon</p>

<div class="status-bar">
  <span><span class="dot"></span><span id="sync-status">Carregando...</span></span>
  <button class="btn btn-outline btn-sm" onclick="forceSync()">⟳ Sync agora</button>
</div>

<div class="cards" id="stats-cards">
  <div class="card"><div class="card-label">Total Transações</div><div class="card-value" id="c-txns">—</div><div class="card-sub">Pay Fee incoming</div></div>
  <div class="card"><div class="card-label">Pagadores Únicos</div><div class="card-value" id="c-payers">—</div><div class="card-sub">wallets distintas</div></div>
</div>

<div class="section-title">Volume por token (histórico)</div>
<div class="token-cards" id="token-cards"><div class="loading">Carregando...</div></div>

<div class="section-title" style="margin-top:20px">Transações</div>
<div class="filters">
  <label>Token<select id="f-token" onchange="load()">
    <option value="">Todos</option>
    <option>USDT0</option><option>WEbdEX</option><option>DAI</option>
  </select></label>
  <label>Carteira (from)<input id="f-from" placeholder="0x..." oninput="debounce(load,500)()"></label>
  <label>De<input type="date" id="f-from-date" onchange="load()"></label>
  <label>Até<input type="date" id="f-to-date" onchange="load()"></label>
  <label>Direção<select id="f-dir" onchange="load()">
    <option value="in">Pay Fee (in)</option>
    <option value="out">Saques sócios (out)</option>
  </select></label>
  <label>&nbsp;<button class="btn" onclick="reset()">Limpar</button></label>
</div>

<div class="table-wrap">
<table>
  <thead>
    <tr>
      <th>Data / Hora</th>
      <th>De</th>
      <th>Token</th>
      <th>Valor</th>
      <th>TX Hash</th>
    </tr>
  </thead>
  <tbody id="tbody"><tr><td colspan="5" class="loading">Carregando...</td></tr></tbody>
</table>
</div>

<div class="pagination">
  <span class="page-info" id="page-info"></span>
  <button class="btn btn-outline btn-sm" id="btn-prev" onclick="goPage(-1)">← Anterior</button>
  <button class="btn btn-outline btn-sm" id="btn-next" onclick="goPage(1)">Próxima →</button>
</div>

<script>
let currentPage = 1;
let totalPages  = 1;
let _debounce   = null;

function debounce(fn, ms) {
  return function(...args) {
    clearTimeout(_debounce);
    _debounce = setTimeout(() => fn(...args), ms);
  };
}

function tokenTag(sym) {
  const cls = sym === 'USDT0' ? 'tag-usdt' : sym === 'WEbdEX' ? 'tag-webdex' : sym === 'DAI' ? 'tag-dai' : 'tag-other';
  return `<span class="tag ${cls}">${sym}</span>`;
}

function fmtAmt(v, sym) {
  const n = parseFloat(v);
  const s = n < 0.01 ? n.toFixed(6) : n < 1 ? n.toFixed(4) : n.toFixed(2);
  const cls = n < 0.01 ? 'amount-tiny' : 'amount';
  return `<span class="${cls}">$${parseFloat(s).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</span>`;
}

function shortAddr(a) {
  return a.slice(0,8)+'...'+a.slice(-6);
}

function fmtTs(ts) {
  const d = new Date(ts * 1000);
  return d.toISOString().replace('T',' ').slice(0,16) + ' UTC';
}

async function loadStats() {
  try {
    const r = await fetch('/api/stats');
    const d = await r.json();
    document.getElementById('c-txns').textContent   = d.total_txns.toLocaleString();
    document.getElementById('c-payers').textContent = d.unique_payers.toLocaleString();
    document.getElementById('sync-status').textContent = 'Último sync: ' + d.last_sync;

    // Token cards
    const sel = document.getElementById('f-token');
    const existingOpts = ['', 'USDT0', 'WEbdEX', 'DAI'];
    let tc = '';
    d.by_token.forEach(t => {
      tc += `<div class="token-card">
        <div class="sym">${tokenTag(t.token_symbol)}</div>
        <div class="val">$${parseFloat(t.total).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})}</div>
        <div class="cnt">${t.cnt.toLocaleString()} txns</div>
      </div>`;
      if (!existingOpts.includes(t.token_symbol)) {
        sel.innerHTML += `<option>${t.token_symbol}</option>`;
        existingOpts.push(t.token_symbol);
      }
    });
    document.getElementById('token-cards').innerHTML = tc || '<span style="color:var(--muted)">Sem dados ainda</span>';
  } catch(e) {
    document.getElementById('sync-status').textContent = 'Erro ao carregar stats';
  }
}

async function load() {
  currentPage = 1;
  await fetchRows();
}

async function fetchRows() {
  const token    = document.getElementById('f-token').value;
  const from     = document.getElementById('f-from').value;
  const dateFrom = document.getElementById('f-from-date').value;
  const dateTo   = document.getElementById('f-to-date').value;
  const dir      = document.getElementById('f-dir').value;

  const qs = new URLSearchParams({
    page: currentPage, token, from_addr: from,
    date_from: dateFrom, date_to: dateTo, direction: dir
  });

  document.getElementById('tbody').innerHTML = '<tr><td colspan="5" class="loading">Buscando...</td></tr>';
  try {
    const r = await fetch('/api/fees?' + qs);
    const d = await r.json();
    totalPages = d.pages;

    document.getElementById('page-info').textContent = `Pág ${d.page}/${d.pages} · ${d.total.toLocaleString()} registros`;
    document.getElementById('btn-prev').disabled = currentPage <= 1;
    document.getElementById('btn-next').disabled = currentPage >= totalPages;

    if (!d.rows.length) {
      document.getElementById('tbody').innerHTML = '<tr><td colspan="5" style="color:var(--muted);padding:20px;text-align:center">Nenhum resultado</td></tr>';
      return;
    }

    const pscan = 'https://polygonscan.com/tx/';
    let html = '';
    d.rows.forEach(row => {
      html += `<tr>
        <td>${fmtTs(row.ts)}</td>
        <td><span class="addr" title="${row.from_addr}">${shortAddr(row.from_addr)}</span></td>
        <td>${tokenTag(row.token_symbol)}</td>
        <td>${fmtAmt(row.amount, row.token_symbol)}</td>
        <td><a class="hash" href="${pscan}${row.tx_hash}" target="_blank" title="${row.tx_hash}">${row.tx_hash.slice(0,16)}...</a></td>
      </tr>`;
    });
    document.getElementById('tbody').innerHTML = html;
  } catch(e) {
    document.getElementById('tbody').innerHTML = `<tr><td colspan="5" style="color:var(--red)">Erro: ${e.message}</td></tr>`;
  }
}

function goPage(delta) {
  const next = currentPage + delta;
  if (next < 1 || next > totalPages) return;
  currentPage = next;
  fetchRows();
}

function reset() {
  document.getElementById('f-token').value = '';
  document.getElementById('f-from').value  = '';
  document.getElementById('f-from-date').value = '';
  document.getElementById('f-to-date').value   = '';
  document.getElementById('f-dir').value   = 'in';
  load();
}

async function forceSync() {
  document.getElementById('sync-status').textContent = 'Sincronizando...';
  await fetch('/api/sync');
  setTimeout(() => { loadStats(); load(); }, 2000);
}

// Init
loadStats();
load();
setInterval(() => { loadStats(); }, 60000);
</script>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────
# HTTP Handler
# ─────────────────────────────────────────────────────────────
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        pass  # silenciar logs HTTP padrão

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

        def qs_get(key: str, default: str = '') -> str:
            return qs.get(key, [default])[0]

        if path == '/':
            self._send(200, _HTML, 'text/html; charset=utf-8')

        elif path == '/api/fees':
            result = _query_fees(
                token     = qs_get('token'),
                from_addr = qs_get('from_addr'),
                date_from = qs_get('date_from'),
                date_to   = qs_get('date_to'),
                direction = qs_get('direction', 'in'),
                page      = int(qs_get('page', '1')),
                per_page  = int(qs_get('per_page', '50')),
            )
            # Converter ts → string legível
            for row in result['rows']:
                row['date'] = datetime.fromtimestamp(row['ts'], tz=timezone.utc).strftime('%d/%m/%Y %H:%M UTC')
            self._send(200, json.dumps(result))

        elif path == '/api/stats':
            self._send(200, json.dumps(_query_stats()))

        elif path == '/api/sync':
            threading.Thread(target=_sync_all, daemon=True).start()
            self._send(200, json.dumps({'status': 'sync_started'}))

        else:
            self._send(404, json.dumps({'error': 'not found'}))


# ─────────────────────────────────────────────────────────────
# Entry point (worker thread)
# ─────────────────────────────────────────────────────────────
def network_fees_dash_worker() -> None:
    """Inicia sync periódico + servidor HTTP. Roda como daemon thread."""
    logger.info('[fees_dash] Worker iniciado | porta %d | db: %s', DASH_PORT, FEES_DB_PATH)
    _init_db()

    # Sync inicial em background (não bloqueia o start do servidor)
    threading.Thread(target=_sync_worker, daemon=True, name='fees_sync').start()

    # HTTP server
    try:
        server = HTTPServer(('0.0.0.0', DASH_PORT), _Handler)
        logger.info('[fees_dash] HTTP server em 0.0.0.0:%d', DASH_PORT)
        server.serve_forever()
    except Exception as e:
        logger.error('[fees_dash] HTTP server erro: %s', e)
