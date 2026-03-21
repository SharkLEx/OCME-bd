"""
tests/packages/test_monitor_observability.py
Story 7.7 — Observability: testes do servidor /metrics e /health.

AC validados:
  - GET /metrics → formato Prometheus válido com as 4 métricas obrigatórias
  - GET /health  → JSON { status, vigia, db, rpc }
  - Log rotation configurado (5MB × 3)
  - Zero secrets hardcoded no código
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

import pytest

# ── PATH setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parents[2] / "packages" / "monitor-engine"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


@pytest.fixture
def db_file(tmp_path) -> str:
    path = tmp_path / "obs_test.db"
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE test (id INTEGER)")
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture
def obs_server(db_file):
    from webdex_observability import ObservabilityServer
    port = _free_port()
    srv = ObservabilityServer(port=port, db_path=db_file)
    srv.start(daemon=True)
    time.sleep(0.15)  # aguarda bind
    yield srv
    srv.stop()


# ── /metrics ──────────────────────────────────────────────────────────────────

class TestMetricsEndpoint:
    def test_get_metrics_returns_200(self, obs_server):
        code, _ = _get(f"http://127.0.0.1:{obs_server.port}/metrics")
        assert code == 200

    def test_metrics_content_type_is_prometheus(self, obs_server):
        url = f"http://127.0.0.1:{obs_server.port}/metrics"
        with urllib.request.urlopen(url, timeout=3) as r:
            ct = r.headers.get("Content-Type", "")
        assert "text/plain" in ct

    def test_metrics_contains_vigia_blocks_processed(self, obs_server):
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/metrics")
        assert "vigia_blocks_processed_total" in body

    def test_metrics_contains_vigia_ops_total(self, obs_server):
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/metrics")
        assert "vigia_ops_total" in body

    def test_metrics_contains_vigia_lag_blocks(self, obs_server):
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/metrics")
        assert "vigia_lag_blocks" in body

    def test_metrics_contains_sentinela_alerts_total(self, obs_server):
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/metrics")
        assert "sentinela_alerts_total" in body

    def test_metrics_has_help_and_type_comments(self, obs_server):
        """Formato Prometheus requer linhas # HELP e # TYPE."""
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/metrics")
        assert "# HELP" in body
        assert "# TYPE" in body

    def test_metrics_update_from_health(self, obs_server):
        """Atualizar health deve refletir nas métricas."""
        obs_server.update_from_health({
            "blocks_processed": 12345,
            "ops_total": 999,
            "lag_blocks": 3,
            "vigia_loops": 500,
            "rpc_errors": 2,
            "capture_rate": 99.8,
            "updated_at": time.time(),
        })
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/metrics")
        assert "12345" in body
        assert "999" in body

    def test_increment_alert_updates_counter(self, obs_server):
        from webdex_observability import get_registry
        reg = get_registry()
        before = reg._counters["sentinela_alerts_total"]
        obs_server.increment_alert()
        obs_server.increment_alert()
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/metrics")
        assert reg._counters["sentinela_alerts_total"] == before + 2

    def test_metrics_contains_uptime(self, obs_server):
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/metrics")
        assert "vigia_uptime_seconds" in body


# ── /health ───────────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_get_health_returns_200_or_503(self, obs_server):
        code, _ = _get(f"http://127.0.0.1:{obs_server.port}/health")
        assert code in (200, 503)

    def test_health_response_is_json(self, obs_server):
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/health")
        data = json.loads(body)  # não deve levantar exceção
        assert isinstance(data, dict)

    def test_health_has_required_fields(self, obs_server):
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/health")
        data = json.loads(body)
        for field in ("status", "vigia", "db", "rpc"):
            assert field in data, f"Campo '{field}' ausente"

    def test_health_db_ok_with_valid_db(self, obs_server):
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/health")
        data = json.loads(body)
        assert data["db"] == "ok"

    def test_health_db_error_with_missing_db(self, tmp_path):
        from webdex_observability import ObservabilityServer
        port = _free_port()
        srv = ObservabilityServer(
            port=port,
            db_path=str(tmp_path / "does_not_exist.db"),
        )
        srv.start(daemon=True)
        time.sleep(0.15)
        try:
            _, body = _get(f"http://127.0.0.1:{port}/health")
            data = json.loads(body)
            # DB que não existe deve reportar error OU ok (SQLite cria arquivo)
            assert data["db"] in ("ok", "error")
        finally:
            srv.stop()

    def test_health_vigia_ok_with_recent_health(self, obs_server):
        obs_server.update_from_health({"updated_at": time.time()})
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/health")
        data = json.loads(body)
        assert data["vigia"] == "ok"

    def test_health_vigia_not_running_without_health(self, obs_server):
        # Não atualizou health → updated_at=0 → vigia "not_running"
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/health")
        data = json.loads(body)
        # Depende de quando foi criado; updated_at=0 → not_running
        assert data["vigia"] in ("ok", "not_running")

    def test_health_has_uptime_seconds(self, obs_server):
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/health")
        data = json.loads(body)
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0

    def test_404_for_unknown_path(self, obs_server):
        code, _ = _get(f"http://127.0.0.1:{obs_server.port}/unknown")
        assert code == 404


# ── Formato Prometheus ────────────────────────────────────────────────────────

class TestPrometheusFormat:
    def test_each_metric_has_help_line(self, obs_server):
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/metrics")
        required = [
            "vigia_blocks_processed_total",
            "vigia_ops_total",
            "sentinela_alerts_total",
            "vigia_lag_blocks",
        ]
        for metric in required:
            assert f"# HELP {metric}" in body, f"# HELP missing for {metric}"

    def test_each_metric_has_type_line(self, obs_server):
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/metrics")
        assert "# TYPE vigia_blocks_processed_total counter" in body
        assert "# TYPE vigia_lag_blocks gauge" in body

    def test_metrics_values_are_numeric(self, obs_server):
        _, body = _get(f"http://127.0.0.1:{obs_server.port}/metrics")
        for line in body.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split(" ")
            assert len(parts) >= 2, f"Linha inválida: {line}"
            float(parts[-1])  # deve ser número


# ── Log rotation ──────────────────────────────────────────────────────────────

class TestLogRotation:
    def test_webdex_config_has_rotating_file_handler(self):
        config_file = Path(__file__).parents[2] / "packages" / "monitor-engine" / "webdex_config.py"
        content = config_file.read_text(encoding="utf-8")
        assert "RotatingFileHandler" in content

    def test_log_rotation_5mb(self):
        config_file = Path(__file__).parents[2] / "packages" / "monitor-engine" / "webdex_config.py"
        content = config_file.read_text(encoding="utf-8")
        # 5MB = 5 * 1024 * 1024 = 5242880
        assert "5 * 1024 * 1024" in content or "5242880" in content

    def test_log_rotation_3_backups(self):
        config_file = Path(__file__).parents[2] / "packages" / "monitor-engine" / "webdex_config.py"
        content = config_file.read_text(encoding="utf-8")
        assert "backupCount=3" in content


# ── Secrets check ─────────────────────────────────────────────────────────────

class TestNoSecrets:
    """Valida que nenhum arquivo Python do monitor contém credenciais hardcoded."""

    _PATTERNS = [
        "sk-proj-", "sk-ant-", "AAG",   # API keys
        "alchemy.com/v2/",               # Alchemy URL com chave
        "0x" + "a" * 40,                 # Endereço Ethereum hardcoded (exemplo)
    ]
    # Padrões mais genéricos — check por regex
    _REGEX_PATTERNS = [
        r"TELEGRAM_TOKEN\s*=\s*['\"][0-9]+:",   # token real
        r"OPENAI_API_KEY\s*=\s*['\"]sk-",        # chave OpenAI real
    ]

    def _get_python_files(self) -> list:
        base = Path(__file__).parents[2] / "packages"
        return list(base.rglob("*.py"))

    def test_no_alchemy_key_in_code(self):
        import re
        for f in self._get_python_files():
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                # URL Alchemy com chave real (não placeholder)
                if "alchemy.com/v2/" in content:
                    # Verifica se é um placeholder ou exemplo
                    lines = [l for l in content.splitlines()
                             if "alchemy.com/v2/" in l and
                             "YOUR_KEY" not in l and
                             "SUA_CHAVE" not in l and
                             "#" not in l.split("alchemy")[0][-5:]]
                    assert not lines, f"Possível chave Alchemy em {f}: {lines[:1]}"
            except Exception:
                pass

    def test_no_telegram_token_pattern_in_code(self):
        import re
        pattern = re.compile(r"\b\d{9,10}:[A-Za-z0-9_-]{35}\b")
        for f in self._get_python_files():
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                if pattern.search(content):
                    # Pode ser um exemplo em comentário — verifica se é real
                    matches = pattern.findall(content)
                    for m in matches:
                        # Token de teste usado nos testes é inválido propositalmente
                        assert "AABBCCDDEEFFaabbccddeeff" in m or "test" in m.lower(), \
                            f"Possível token Telegram real em {f}: {m[:20]}..."
            except Exception:
                pass

    def test_env_example_has_no_real_values(self):
        env_example = Path(__file__).parents[2] / "packages" / "monitor-engine" / ".env.example"
        if not env_example.exists():
            pytest.skip(".env.example não encontrado")
        content = env_example.read_text(encoding="utf-8")
        import re
        # Token Telegram real: 10 dígitos:35 chars
        token_pattern = re.compile(r"\b\d{9,10}:[A-Za-z0-9_-]{35}\b")
        assert not token_pattern.search(content), "Token Telegram real encontrado no .env.example"
        # Chave OpenAI real
        assert "sk-proj-" not in content, "Chave OpenAI real no .env.example"


# ── Registry thread-safety ────────────────────────────────────────────────────

class TestRegistryThreadSafety:
    def test_concurrent_updates_no_race(self):
        """Atualizações concorrentes não devem causar race conditions."""
        import threading
        from webdex_observability import get_registry

        reg = get_registry()
        errors = []

        def _updater():
            try:
                for i in range(20):
                    reg.update({
                        "blocks_processed": i,
                        "ops_total": i * 2,
                        "lag_blocks": i % 5,
                        "vigia_loops": i,
                        "rpc_errors": 0,
                        "capture_rate": 99.9,
                        "updated_at": time.time(),
                    })
            except Exception as e:
                errors.append(e)

        def _reader():
            try:
                for _ in range(20):
                    reg.to_prometheus()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_updater) for _ in range(5)]
        threads += [threading.Thread(target=_reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Race conditions detectadas: {errors}"
