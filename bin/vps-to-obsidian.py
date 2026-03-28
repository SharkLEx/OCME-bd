#!/usr/bin/env python3
"""
vps-to-obsidian.py — Sync VPS monitor data → Obsidian daily note
Puxa métricas do ocme-monitor (porta 9090) e escreve na daily note de hoje.

Uso:
  python bin/vps-to-obsidian.py           # Append na daily note
  python bin/vps-to-obsidian.py --dry-run # Mostra o que seria escrito

Pode ser agendado via Task Scheduler do Windows:
  pythonw bin\vps-to-obsidian.py          # Sem janela, silencioso
"""
import json
import pathlib
import sys
import urllib.request
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
VPS_HEALTH_URL  = "http://76.13.100.67:9090/health"
VPS_METRICS_URL = "http://76.13.100.67:9090/metrics"
TIMEOUT         = 5

# Vault local — escrita direta no arquivo (evita bug de template duplicado da REST API)
_SCRIPT_DIR = pathlib.Path(__file__).parent
VAULT_DIR   = _SCRIPT_DIR.parent / "daily-notes"

DRY_RUN = "--dry-run" in sys.argv


def _fetch(url: str, timeout: int = TIMEOUT) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "vps-to-obsidian/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode()
    except Exception as e:
        print(f"[WARN] fetch {url}: {e}", file=sys.stderr)
        return None


def _fetch_health() -> dict:
    raw = _fetch(VPS_HEALTH_URL)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _fetch_metrics() -> dict[str, float]:
    raw = _fetch(VPS_METRICS_URL)
    if not raw:
        return {}
    result = {}
    for line in raw.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.rsplit(" ", 1)
        if len(parts) == 2:
            try:
                # Strip Prometheus labels: metric_name{label="val"} → metric_name
                key = parts[0].split("{")[0].strip()
                result[key] = float(parts[1])
            except ValueError:
                pass
    return result


def _write_to_daily(markdown: str) -> bool:
    """Append markdown diretamente na daily note (evita bug de template duplicado da REST API)."""
    today = datetime.now().strftime("%Y-%m-%d")
    path = VAULT_DIR / f"{today}.md"
    try:
        VAULT_DIR.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(markdown)
        return True
    except Exception as e:
        print(f"[ERROR] Write daily note {path}: {e}", file=sys.stderr)
        return False


def build_note(health: dict, metrics: dict[str, float]) -> str:
    ts = datetime.now().strftime("%H:%M")

    status_icon = "✅" if health.get("status") == "ok" else "⚠️"
    vigia_icon  = "✅" if health.get("vigia") == "ok" else "⚠️"
    db_icon     = "✅" if health.get("db") == "ok" else "⚠️"
    rpc_icon    = "✅" if health.get("rpc") == "configured" else "⚠️"

    uptime_h  = int(metrics.get("vigia_uptime_seconds", 0)) // 3600
    blocks    = int(metrics.get("vigia_blocks_processed_total", 0))
    ops       = int(metrics.get("vigia_ops_total", 0))
    lag       = int(metrics.get("vigia_lag_blocks", 0))
    capture   = metrics.get("vigia_capture_rate", 0.0)
    rpc_errs  = int(metrics.get("vigia_rpc_errors_total", 0))
    alerts    = int(metrics.get("sentinela_alerts_total", 0))

    lag_icon    = "✅" if lag == 0 else f"⚠️ {lag} blocos"
    capture_ico = "✅" if capture >= 99.0 else f"⚠️ {capture:.1f}%"

    return f"""
## 🖥️ WEbdEX Monitor — {ts} BRT

| Componente | Status |
|-----------|--------|
| Monitor geral | {status_icon} |
| Vigia (on-chain) | {vigia_icon} |
| Database | {db_icon} |
| RPC Pool | {rpc_icon} |

| Métrica | Valor |
|---------|-------|
| Uptime | {uptime_h}h |
| Blocos processados | {blocks:,} |
| Operações detectadas | {ops:,} |
| Lag da chain | {lag_icon} |
| Taxa de captura | {capture_ico} |
| Erros RPC | {rpc_errs} |
| Alertas sentinela | {alerts} |

"""


def main():
    print("[vps-to-obsidian] Buscando dados do VPS...")
    health  = _fetch_health()
    metrics = _fetch_metrics()

    if not health and not metrics:
        print("[ERROR] Não foi possível buscar dados do VPS. Abortando.")
        sys.exit(1)

    note = build_note(health, metrics)

    if DRY_RUN:
        print("── DRY RUN ─────────────────────────────────────────")
        print(note)
        return

    print("[vps-to-obsidian] Escrevendo na daily note do Obsidian...")
    ok = _write_to_daily(note)
    if ok:
        print("[vps-to-obsidian] ✅ Daily note atualizada.")
    else:
        print("[vps-to-obsidian] ❌ Falha ao escrever na daily note. Verifique se daily-notes/ existe.")
        sys.exit(1)


if __name__ == "__main__":
    main()
