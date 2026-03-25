#!/usr/bin/env python3
"""
card_server.py — Servidor dinâmico para cards bdZinho
Serve arquivos estáticos de media/ + API de dados ao vivo via SQLite

Zero dependências externas — só módulos built-in do Python.

Uso:
    python card_server.py
    DB_PATH=/caminho/para/db python card_server.py

Porta padrão: 8766
"""
import os
import sys
import json
import sqlite3
import mimetypes
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

# ── Configuração ──────────────────────────────────────────────────────────────

MEDIA_DIR = Path(__file__).parent.resolve()
PORT = int(os.getenv("CARD_SERVER_PORT", "8766"))

# DB: tenta variável de ambiente, depois caminho relativo padrão
DB_PATH = (
    os.getenv("DB_PATH") or
    os.getenv("WEbdEX_DB_PATH") or
    str(MEDIA_DIR / ".." / "packages" / "monitor-engine" / "webdex_v5_final.db")
)

# ── DB helpers ────────────────────────────────────────────────────────────────

def _db_connect():
    path = Path(DB_PATH).resolve()
    if not path.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None

def _query(sql, params=()):
    conn = _db_connect()
    if not conn:
        return []
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()

def _scalar(sql, params=(), default=0):
    rows = _query(sql, params)
    if not rows:
        return default
    v = list(rows[0].values())[0]
    return v if v is not None else default

def _ciclo_since():
    """Timestamp do início do ciclo 21h atual."""
    now = datetime.now()
    corte = now.replace(hour=21, minute=0, second=0, microsecond=0)
    if now < corte:
        corte -= timedelta(days=1)
    return corte.strftime("%Y-%m-%d %H:%M:%S")

def _today():
    return datetime.now().strftime("%Y-%m-%d")

def _fmt_short_addr(addr):
    if not addr or len(addr) < 10:
        return addr or "—"
    return addr[:6] + "..." + addr[-4:]

def _fmt_num(v, decimals=0):
    if v is None:
        return "—"
    try:
        f = float(v)
        if decimals == 0:
            return f"{int(f):,}".replace(",", ".")
        return f"{f:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(v)

# ── Dados por card ────────────────────────────────────────────────────────────

def data_token_bd():
    since = _ciclo_since()
    holders = _scalar("SELECT COUNT(*) FROM known_wallets WHERE trade_count > 0", default=0)
    volume = _scalar(
        "SELECT COALESCE(SUM(valor),0) FROM operacoes WHERE tipo='SwapTokens' AND data_hora>=?",
        (since,), default=0
    )
    supply_cfg = _scalar("SELECT valor FROM config WHERE chave='bd_supply'", default=None)
    mcap_cfg   = _scalar("SELECT valor FROM config WHERE chave='bd_market_cap'", default=None)
    return {
        "holders_total":  _fmt_num(holders),
        "holders_raw":    int(holders or 0),
        "supply":         str(supply_cfg) if supply_cfg else "LIVE",
        "market_cap":     str(mcap_cfg)   if mcap_cfg   else "BDX",
        "volume_ciclo":   _fmt_num(volume, 2),
    }

def data_webdex_onchain():
    since = _ciclo_since()
    events  = _scalar("SELECT COUNT(*) FROM operacoes WHERE data_hora>=?", (since,), default=0)
    anomaly = _scalar(
        "SELECT COUNT(*) FROM operacoes WHERE tipo='Anomalia' AND data_hora>=?", (since,), default=0
    )
    holders = _scalar("SELECT COUNT(*) FROM known_wallets WHERE trade_count > 0", default=0)
    volume  = _scalar(
        "SELECT COALESCE(SUM(valor),0) FROM operacoes WHERE tipo='SwapTokens' AND data_hora>=?",
        (since,), default=0
    )
    last = _query(
        "SELECT tipo FROM operacoes ORDER BY data_hora DESC LIMIT 1"
    )
    last_tipo = last[0]["tipo"] if last else "ONLINE"
    return {
        "anomaly_value": str(anomaly) if anomaly else "—",
        "volume_value":  _fmt_num(volume, 2),
        "holders_value": _fmt_num(holders),
        "events_value":  str(events),
        "last_tipo":     last_tipo,
    }

def data_conquistas():
    holders = _scalar("SELECT COUNT(*) FROM known_wallets WHERE trade_count > 0", default=0)
    milestones = [10, 25, 50, 100, 250, 500, 1000, 2500]
    next_m = next((m for m in milestones if m > holders), milestones[-1])
    new_today = _scalar(
        "SELECT COUNT(*) FROM known_wallets WHERE created_at >= ?", (_today(),), default=0
    )
    return {
        "holders_total":   _fmt_num(holders),
        "holders_raw":     int(holders or 0),
        "next_milestone":  _fmt_num(next_m),
        "new_today":       str(int(new_today or 0)),
        "milestone_text":  f"{_fmt_num(holders)} holders — próximo: {_fmt_num(next_m)}",
        "new_wallets_text": f"+{int(new_today or 0)} novas carteiras hoje",
    }

def data_operacoes():
    since = _ciclo_since()
    total_ops = _scalar("SELECT COUNT(*) FROM operacoes WHERE data_hora>=?", (since,), default=0)
    new_wallets = _scalar("SELECT COUNT(*) FROM known_wallets WHERE created_at>=?", (_today(),), default=0)
    last_rows = _query(
        "SELECT tipo, sub_conta, data_hora FROM operacoes ORDER BY data_hora DESC LIMIT 4"
    )
    logs = []
    for r in last_rows:
        sub = r.get("sub_conta") or "WALLET"
        logs.append(f"{r.get('tipo','OP')}\n{_fmt_short_addr(sub)}")
    # preenche até 4 entradas
    while len(logs) < 4:
        logs.append("PROTOCOL ACTIVE\nWEBDEX_V1")
    return {
        "log1": logs[0],
        "log2": logs[1],
        "log3": logs[2],
        "log4": logs[3],
        "total_ops":    str(int(total_ops or 0)),
        "new_wallets":  str(int(new_wallets or 0)),
    }

def data_swaps():
    since = _ciclo_since()
    create_c = _scalar(
        "SELECT COUNT(*) FROM operacoes WHERE tipo='CreateSwap' AND data_hora>=?", (since,), default=0
    )
    swap_c = _scalar(
        "SELECT COUNT(*) FROM operacoes WHERE tipo='SwapTokens' AND data_hora>=?", (since,), default=0
    )
    volume = _scalar(
        "SELECT COALESCE(SUM(valor),0) FROM operacoes WHERE tipo='SwapTokens' AND data_hora>=?",
        (since,), default=0
    )
    last = _query(
        "SELECT tipo, valor, token, data_hora FROM operacoes "
        "WHERE tipo IN ('CreateSwap','SwapTokens') ORDER BY data_hora DESC LIMIT 1"
    )
    l = last[0] if last else {}
    return {
        "create_text": f"📋 Create Swap  {int(create_c or 0)}",
        "swap_text":   f"⚡ Swap Tokens  {int(swap_c or 0)}",
        "volume_text": _fmt_num(volume, 2),
        "last_tipo":   l.get("tipo", "—"),
        "last_valor":  _fmt_num(l.get("valor", 0), 4),
    }

def data_relatorio():
    since = _ciclo_since()
    total_ops = _scalar("SELECT COUNT(*) FROM operacoes WHERE data_hora>=?", (since,), default=0)
    holders   = _scalar("SELECT COUNT(*) FROM known_wallets WHERE trade_count > 0", default=0)
    active_h  = _scalar(
        "SELECT COUNT(DISTINCT ow.wallet) FROM operacoes o "
        "JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index "
        "WHERE o.data_hora>=?", (since,), default=0
    )
    swaps_c = _scalar(
        "SELECT COUNT(*) FROM operacoes WHERE tipo='SwapTokens' AND data_hora>=?", (since,), default=0
    )
    # % para as barras (0-100)
    onchain_pct = min(100, int((total_ops / max(total_ops + 50, 100)) * 100 + 30)) if total_ops else 20
    holders_pct = min(100, int((active_h  / max(holders, 1)) * 100)) if holders else 10
    swaps_pct   = min(100, int((swaps_c   / max(swaps_c + 5, 10)) * 100 + 20)) if swaps_c else 15

    return {
        "onchain_pct":       str(onchain_pct),
        "onchain_pct_width": f"{onchain_pct}%",
        "holders_pct":       str(holders_pct),
        "holders_pct_width": f"{holders_pct}%",
        "swaps_pct":         str(swaps_pct),
        "swaps_pct_width":   f"{swaps_pct}%",
    }

def data_gm():
    now = datetime.now()
    dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    return {
        "hora":       now.strftime("%H:%M"),
        "data":       now.strftime("%d/%m"),
        "dia_semana": dias[now.weekday()],
    }

def data_bdzinho_ia():
    total_convs = _scalar("SELECT COUNT(DISTINCT chat_id) FROM ai_memory", default=0)
    total_msgs  = _scalar("SELECT COUNT(*) FROM ai_memory WHERE role='user'", default=0)
    hoje = _today()
    msgs_hoje   = _scalar(
        "SELECT COUNT(*) FROM ai_memory WHERE role='user' AND created_at>=?",
        (hoje,), default=0
    )
    return {
        "users_ia":     str(int(total_convs or 0)),
        "total_msgs":   str(int(total_msgs  or 0)),
        "msgs_hoje":    str(int(msgs_hoje   or 0)),
        "status":       "ONLINE",
    }

# Roteador de dados
DATA_ROUTES = {
    "/api/data/token-bd":          data_token_bd,
    "/api/data/webdex-onchain":    data_webdex_onchain,
    "/api/data/conquistas":        data_conquistas,
    "/api/data/operacoes":         data_operacoes,
    "/api/data/swaps":             data_swaps,
    "/api/data/relatorio-diario":  data_relatorio,
    "/api/data/gm-wagmi":          data_gm,
    "/api/data/bdzinho-ia":        data_bdzinho_ia,
}

# ── HTTP Handler ──────────────────────────────────────────────────────────────

class CardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(MEDIA_DIR), **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path

        # API de dados
        if path in DATA_ROUTES:
            try:
                payload = DATA_ROUTES[path]()
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_error(500, str(e))
            return

        # Arquivos estáticos
        super().do_GET()

    def log_message(self, fmt, *args):
        # Suprimir logs de assets (img, css, js) — só mostra páginas HTML e API
        path = args[0] if args else ""
        if any(ext in path for ext in [".png", ".jpg", ".css", ".js", ".ico"]):
            return
        print(f"[card_server] {self.address_string()} {fmt % args}")

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    db_abs = Path(DB_PATH).resolve()
    print(f"🃏 Card Server  →  http://0.0.0.0:{PORT}")
    print(f"📂 Media dir    →  {MEDIA_DIR}")
    print(f"🗄️  DB           →  {db_abs} {'✅' if db_abs.exists() else '⚠️ não encontrado'}")
    print()

    server = HTTPServer(("0.0.0.0", PORT), CardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Card Server encerrado.")
        server.server_close()
