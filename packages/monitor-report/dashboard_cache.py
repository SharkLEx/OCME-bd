"""monitor-report/dashboard_cache.py — DashboardCache para OCME Engine.

Pré-calcula KPIs a cada ciclo do Vigia — não no clique do usuário.
Garante resposta < 500ms para o Dashboard/Bot (Story 7.5).

Standalone: sem dependência do monolito webdex_*.py.

Uso:
    from dashboard_cache import DashboardCache

    cache = DashboardCache(db_path="webdex_v5_final.db", ttl_seconds=15)

    # Liga ao Vigia (event-driven):
    vigia.on('operation', cache.on_new_op)
    vigia.on('progress', cache.on_progress)

    # Leitura instantânea (<1ms):
    kpis = cache.get()
    env_kpis = cache.get_env("bd_v5")
"""

from __future__ import annotations

import io
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("monitor-report.dashboard_cache")


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


class DashboardCache:
    """Cache de KPIs pré-calculados do protocolo WEbdEX.

    Atualiza automaticamente:
        - Quando Vigia emite evento 'operation' (nova op)
        - Quando Vigia emite evento 'progress' (ciclo completo)
        - A cada `ttl_seconds` (fallback por tempo)

    Dados disponíveis (get()):
        {
            "pnl_24h":        float,
            "pnl_7d":         float,
            "pnl_30d":        float,
            "trades_24h":     int,
            "winrate_24h":    float,
            "best_sub":       {"sub", "env", "liquido"},
            "worst_sub":      {"sub", "env", "liquido"},
            "avg_gas_24h":    float,
            "total_capital":  float,
            "last_block":     int,
            "capture_rate":   float,
            "updated_at":     float,
            "stale":          bool,
            "by_env":         [...],
        }
    """

    def __init__(
        self,
        db_path: str,
        ttl_seconds: Optional[int] = None,
        charts_dir: Optional[str] = None,
    ):
        self._db_path = db_path
        self._ttl = ttl_seconds or _env_int("DASHBOARD_CACHE_TTL", 15)
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        self._updated_at: float = 0.0
        self._dirty: bool = True          # True = precisa recalcular
        # Gráficos em background (Matplotlib headless)
        self._charts_dir = charts_dir or os.environ.get("CHARTS_DIR", "")
        self._chart_bytes: Dict[str, bytes] = {}  # nome → PNG bytes
        self._charts_lock = threading.Lock()
        self._chart_thread: Optional[threading.Thread] = None

    # ── Event listeners (liga ao Vigia) ───────────────────────────────────
    def on_new_op(self, op: Dict):
        """Chamado quando Vigia emite evento 'operation'."""
        with self._lock:
            self._dirty = True
        # Agenda regeneração de gráficos em background (não bloqueia)
        self.request_chart_update()

    def on_progress(self, progress: Dict):
        """Chamado quando Vigia emite evento 'progress'."""
        with self._lock:
            if progress.get("ops_in_cycle", 0) > 0:
                self._dirty = True
            # Atualiza last_block e capture_rate sem recalcular KPIs pesados
            if self._data:
                self._data["last_block"] = progress.get("last_block", self._data.get("last_block", 0))
                self._data["capture_rate"] = progress.get("capture_rate", self._data.get("capture_rate", 100.0))
            # Força refresh por TTL
            if time.time() - self._updated_at > self._ttl:
                self._dirty = True

    # ── Leitura ───────────────────────────────────────────────────────────
    def get(self, force: bool = False) -> Dict[str, Any]:
        """Retorna KPIs. Recalcula se dirty ou TTL expirado."""
        with self._lock:
            expired = (time.time() - self._updated_at) > self._ttl
            if force or self._dirty or expired:
                self._recalculate()
            result = dict(self._data)
            result["stale"] = (time.time() - self._updated_at) > (self._ttl * 2)
            return result

    def get_env(self, env: str) -> Optional[Dict]:
        """Retorna KPIs de um ambiente específico."""
        data = self.get()
        for e in data.get("by_env", []):
            if e.get("env") == env:
                return e
        return None

    def invalidate(self):
        """Força recalculo na próxima chamada get()."""
        with self._lock:
            self._dirty = True

    # ── Gráficos em background ─────────────────────────────────────────────
    def get_chart(self, name: str) -> Optional[bytes]:
        """Retorna PNG bytes do gráfico, ou None se ainda não gerado."""
        with self._charts_lock:
            return self._chart_bytes.get(name)

    def request_chart_update(self):
        """Agenda geração de gráficos em thread background (não bloqueia)."""
        with self._charts_lock:
            if self._chart_thread and self._chart_thread.is_alive():
                return  # já está gerando
            self._chart_thread = threading.Thread(
                target=self._generate_charts,
                name="chart-generator",
                daemon=True,
            )
            self._chart_thread.start()

    def _generate_charts(self):
        """Gera gráficos Matplotlib headless. Chamado em thread separada."""
        try:
            import matplotlib
            matplotlib.use("Agg")  # headless — sem display
            import matplotlib.pyplot as plt
            import matplotlib.ticker as mticker
        except ImportError:
            logger.debug("[dashboard_cache] matplotlib não disponível — gráficos desabilitados")
            return

        try:
            self._chart_pnl_24h(plt, mticker)
        except Exception as exc:
            logger.warning("[dashboard_cache] chart_pnl_24h error: %s", exc)

        try:
            self._chart_winrate(plt)
        except Exception as exc:
            logger.warning("[dashboard_cache] chart_winrate error: %s", exc)

    def _chart_pnl_24h(self, plt, mticker):
        """Gráfico de P&L acumulado nas últimas 24h (linha temporal)."""
        try:
            c = sqlite3.connect(self._db_path)
            from datetime import datetime as _dt, timedelta as _td
            since = (_dt.now() - _td(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
            rows = c.execute("""
                SELECT data_hora, CAST(valor AS REAL) - CAST(gas_usd AS REAL)
                FROM operacoes
                WHERE tipo='Trade' AND data_hora>=?
                ORDER BY data_hora ASC
            """, (since,)).fetchall()
            c.close()
        except Exception as exc:
            logger.debug("[chart_pnl_24h] DB error: %s", exc)
            return

        if not rows:
            return

        times = [r[0][:16] for r in rows]
        liquidos = [float(r[1] or 0) for r in rows]
        cumulative = []
        acc = 0.0
        for v in liquidos:
            acc += v
            cumulative.append(acc)

        fig, ax = plt.subplots(figsize=(8, 3))
        color = "#2ecc71" if cumulative[-1] >= 0 else "#e74c3c"
        ax.plot(range(len(cumulative)), cumulative, color=color, linewidth=2)
        ax.fill_between(range(len(cumulative)), cumulative, alpha=0.15, color=color)
        ax.axhline(0, color="#888", linewidth=0.8, linestyle="--")
        ax.set_title("P&L Acumulado — 24h", fontsize=11, pad=8)
        ax.set_ylabel("USD", fontsize=9)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
        ax.set_xticks([])
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        with self._charts_lock:
            self._chart_bytes["pnl_24h"] = buf.read()

        logger.debug("[dashboard_cache] chart pnl_24h gerado (%d trades)", len(rows))

    def _chart_winrate(self, plt):
        """Gráfico de barras WinRate por ambiente."""
        data = self.get()
        by_env = data.get("by_env", [])
        if not by_env:
            return

        envs = [e["env"] for e in by_env]
        winrates = [e.get("winrate", 0.0) for e in by_env]
        colors = ["#2ecc71" if w >= 50 else "#e74c3c" for w in winrates]

        fig, ax = plt.subplots(figsize=(6, 3))
        bars = ax.bar(envs, winrates, color=colors, width=0.5)
        ax.axhline(50, color="#888", linewidth=0.8, linestyle="--", label="50%")
        ax.set_title("WinRate por Ambiente — 24h", fontsize=11, pad=8)
        ax.set_ylabel("%", fontsize=9)
        ax.set_ylim(0, 100)
        for bar, val in zip(bars, winrates):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                    f"{val:.0f}%", ha="center", va="bottom", fontsize=9)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        with self._charts_lock:
            self._chart_bytes["winrate"] = buf.read()

    # ── Cálculo ────────────────────────────────────────────────────────────
    def _recalculate(self):
        """Recalcula todos os KPIs do DB. Chamado com lock já adquirido."""
        t0 = time.time()
        try:
            new_data = self._compute_kpis()
            new_data["updated_at"] = time.time()
            new_data["calc_ms"] = round((time.time() - t0) * 1000, 1)
            self._data = new_data
            self._updated_at = time.time()
            self._dirty = False
            logger.debug("[dashboard_cache] recalculado em %.1fms", new_data["calc_ms"])
        except Exception as exc:
            logger.warning("[dashboard_cache] recalculate error: %s", exc)
            if not self._data:
                self._data = self._empty_kpis()
                self._data["updated_at"] = time.time()
                self._updated_at = time.time()

    def _compute_kpis(self) -> Dict:
        c = sqlite3.connect(self._db_path)
        try:
            return {
                **self._global_kpis(c),
                "by_env": self._env_kpis(c),
                "best_sub": self._best_sub(c),
                "worst_sub": self._worst_sub(c),
                "total_capital": self._total_capital(c),
                "last_block": self._last_block(c),
                "capture_rate": 100.0,
            }
        finally:
            c.close()

    def _global_kpis(self, c: sqlite3.Connection) -> Dict:
        def _pnl(hours: int):
            since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
            row = c.execute("""
                SELECT COUNT(*),
                       COALESCE(SUM(CAST(valor AS REAL))-SUM(CAST(gas_usd AS REAL)),0),
                       COUNT(CASE WHEN CAST(valor AS REAL)>0 THEN 1 END),
                       COALESCE(SUM(CAST(gas_usd AS REAL)),0)
                FROM operacoes
                WHERE tipo='Trade' AND data_hora>=?
            """, (since,)).fetchone()
            if row:
                t = int(row[0] or 0)
                return {
                    "pnl": float(row[1] or 0),
                    "trades": t,
                    "winrate": round(int(row[2] or 0) / t * 100, 1) if t > 0 else 0.0,
                    "gas": float(row[3] or 0),
                }
            return {"pnl": 0.0, "trades": 0, "winrate": 0.0, "gas": 0.0}

        p24 = _pnl(24)
        p7d = _pnl(168)
        p30d = _pnl(720)

        return {
            "pnl_24h": p24["pnl"],
            "pnl_7d": p7d["pnl"],
            "pnl_30d": p30d["pnl"],
            "trades_24h": p24["trades"],
            "winrate_24h": p24["winrate"],
            "avg_gas_24h": p24["gas"] / p24["trades"] if p24["trades"] > 0 else 0.0,
        }

    def _env_kpis(self, c: sqlite3.Connection) -> List[Dict]:
        since = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        rows = c.execute("""
            SELECT COALESCE(ambiente,'UNKNOWN'),
                   COUNT(*),
                   ROUND(SUM(valor)-SUM(gas_usd),4),
                   COUNT(CASE WHEN valor>0 THEN 1 END)
            FROM operacoes
            WHERE tipo='Trade' AND data_hora>=?
            GROUP BY 1 ORDER BY 3 DESC
        """, (since,)).fetchall()
        result = []
        for amb, t, liq, w in rows:
            result.append({
                "env": amb,
                "trades": int(t or 0),
                "liquido": float(liq or 0),
                "winrate": round(int(w or 0) / int(t or 1) * 100, 1) if t and int(t) > 0 else 0.0,
            })
        return result

    def _best_sub(self, c: sqlite3.Connection) -> Optional[Dict]:
        since = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        row = c.execute("""
            SELECT sub_conta, COALESCE(ambiente,'?'),
                   COUNT(*), ROUND(SUM(valor)-SUM(gas_usd),4)
            FROM operacoes
            WHERE tipo='Trade' AND data_hora>=?
            GROUP BY sub_conta, ambiente
            ORDER BY 4 DESC LIMIT 1
        """, (since,)).fetchone()
        if row:
            return {"sub": row[0], "env": row[1], "trades": row[2], "liquido": float(row[3] or 0)}
        return None

    def _worst_sub(self, c: sqlite3.Connection) -> Optional[Dict]:
        since = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        row = c.execute("""
            SELECT sub_conta, COALESCE(ambiente,'?'),
                   COUNT(*), ROUND(SUM(valor)-SUM(gas_usd),4)
            FROM operacoes
            WHERE tipo='Trade' AND data_hora>=?
            GROUP BY sub_conta, ambiente
            ORDER BY 4 ASC LIMIT 1
        """, (since,)).fetchone()
        if row:
            return {"sub": row[0], "env": row[1], "trades": row[2], "liquido": float(row[3] or 0)}
        return None

    def _total_capital(self, c: sqlite3.Connection) -> float:
        try:
            row = c.execute(
                "SELECT COALESCE(SUM(total_usd),0) FROM capital_cache WHERE total_usd>0"
            ).fetchone()
            return float(row[0] or 0)
        except Exception:
            return 0.0

    def _last_block(self, c: sqlite3.Connection) -> int:
        try:
            row = c.execute("SELECT MAX(bloco) FROM operacoes").fetchone()
            return int(row[0] or 0)
        except Exception:
            return 0

    @staticmethod
    def _empty_kpis() -> Dict:
        return {
            "pnl_24h": 0.0, "pnl_7d": 0.0, "pnl_30d": 0.0,
            "trades_24h": 0, "winrate_24h": 0.0, "avg_gas_24h": 0.0,
            "by_env": [], "best_sub": None, "worst_sub": None,
            "total_capital": 0.0, "last_block": 0, "capture_rate": 100.0,
        }
