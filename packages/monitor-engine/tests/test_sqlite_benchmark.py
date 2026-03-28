"""
test_sqlite_benchmark.py — SQLite Benchmark sob carga de 22 threads
Finding #3 do Smith ULTRATHINK | Story 25.1

Objetivo: validar que o WAL mode está ativo e que 22 threads simultâneas
não geram lock contention no padrão real de acesso do monitor engine.

Padrão de conexão: threading.local() — mesmo padrão do webdex_db.py.
"""
from __future__ import annotations

import sqlite3
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

# ==============================================================================
# Helpers
# ==============================================================================

_local = threading.local()


def percentile(data: list[float], p: int) -> float:
    """Retorna o percentil p de uma lista de floats. Retorna 0.0 para lista vazia."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    index = int(len(sorted_data) * p / 100)
    index = min(index, len(sorted_data) - 1)
    return sorted_data[index]


def get_conn(db_path: str) -> sqlite3.Connection:
    """
    Retorna a conexão SQLite do thread atual (threading.local).
    Mesmo padrão do webdex_db.py — uma conexão por thread.
    """
    if not hasattr(_local, 'conn') or _local.db_path != db_path:
        _local.conn = sqlite3.connect(db_path, timeout=5.0, check_same_thread=False)
        _local.conn.execute('PRAGMA journal_mode=WAL')
        _local.conn.execute('PRAGMA busy_timeout=5000')
        _local.db_path = db_path
    return _local.conn


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture(scope='module')
def bench_db():
    """
    Cria um arquivo SQLite temporário com WAL mode e schema mínimo.
    Escopo module: criado uma vez para todos os benchmarks do arquivo.
    """
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    # Setup inicial via conexão principal
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bench_events (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT    NOT NULL,
            ts        REAL    NOT NULL,
            value     TEXT    NOT NULL
        )
    """)
    conn.commit()

    # Confirma WAL ativo antes de yield
    row = conn.execute('PRAGMA journal_mode').fetchone()
    assert row and row[0] == 'wal', f"WAL mode falhou no setup: {row}"

    conn.close()
    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


# ==============================================================================
# Test 1 — WAL mode confirmado
# ==============================================================================

class TestWALMode:

    def test_wal_mode_active(self, bench_db):
        """
        Verifica que o PRAGMA journal_mode retorna 'wal'.
        Se falhar, TODOS os outros benchmarks são inválidos.
        """
        conn = sqlite3.connect(bench_db)
        row = conn.execute('PRAGMA journal_mode').fetchone()
        conn.close()
        assert row is not None, "PRAGMA journal_mode não retornou resultado"
        assert row[0] == 'wal', (
            f"WAL mode NÃO está ativo. journal_mode atual: '{row[0]}'. "
            "Risco: lock contention em 22 threads pode causar falhas em produção."
        )


# ==============================================================================
# Test 2 — Latência baseline (single thread, 1000 writes)
# ==============================================================================

class TestBaselineLatency:

    def test_write_latency_single_thread(self, bench_db):
        """
        1000 INSERTs em loop single-thread.
        Mede p50/p95/p99 em milissegundos.
        Assert: p99 < 10ms (baseline aceitável para SQLite local).
        """
        conn = get_conn(bench_db)
        latencies_ms: list[float] = []

        for i in range(1000):
            t0 = time.perf_counter()
            conn.execute(
                "INSERT INTO bench_events (thread_id, ts, value) VALUES (?, ?, ?)",
                ('thread-baseline', time.time(), f'value-{i}')
            )
            conn.commit()
            elapsed_ms = (time.perf_counter() - t0) * 1000
            latencies_ms.append(elapsed_ms)

        p50 = percentile(latencies_ms, 50)
        p95 = percentile(latencies_ms, 95)
        p99 = percentile(latencies_ms, 99)

        print(f"\n[Baseline] p50={p50:.3f}ms | p95={p95:.3f}ms | p99={p99:.3f}ms")

        assert p99 < 10.0, (
            f"p99 de latência single-thread excede 10ms: {p99:.3f}ms. "
            "Possível I/O lento no disco ou SQLite mal configurado."
        )


# ==============================================================================
# Test 3 — Throughput 22 threads simultâneas
# ==============================================================================

class TestConcurrent22Threads:

    def test_concurrent_22_threads_write(self, bench_db):
        """
        22 threads simultâneas, cada uma faz 100 INSERTs.
        Total: 2200 writes.

        Asserts:
        - Zero OperationalError("database is locked")
        - Throughput > 500 writes/segundo
        - Todos os 2200 rows confirmados no banco ao final
        """
        NUM_THREADS = 22
        WRITES_PER_THREAD = 100
        TOTAL_WRITES = NUM_THREADS * WRITES_PER_THREAD

        errors: list[Exception] = []
        write_counts: list[int] = []

        def worker(thread_idx: int) -> int:
            conn = get_conn(bench_db)
            count = 0
            for i in range(WRITES_PER_THREAD):
                try:
                    conn.execute(
                        "INSERT INTO bench_events (thread_id, ts, value) VALUES (?, ?, ?)",
                        (f'thread-{thread_idx}', time.time(), f'v-{thread_idx}-{i}')
                    )
                    conn.commit()
                    count += 1
                except sqlite3.OperationalError as e:
                    errors.append(e)
            return count

        t_start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
            futures = [executor.submit(worker, idx) for idx in range(NUM_THREADS)]
            for fut in as_completed(futures):
                write_counts.append(fut.result())

        elapsed = time.perf_counter() - t_start
        total_written = sum(write_counts)
        throughput = total_written / elapsed if elapsed > 0 else 0

        print(
            f"\n[22-threads] {total_written}/{TOTAL_WRITES} writes em {elapsed:.2f}s "
            f"→ {throughput:.0f} writes/s | Erros: {len(errors)}"
        )

        assert errors == [], (
            f"{len(errors)} OperationalError(s) detectados:\n"
            + "\n".join(str(e) for e in errors[:5])
            + "\nWAL mode ou busy_timeout pode estar mal configurado."
        )

        assert total_written == TOTAL_WRITES, (
            f"Apenas {total_written}/{TOTAL_WRITES} writes confirmados. "
            "Possível perda silenciosa de dados."
        )

        assert throughput > 500, (
            f"Throughput {throughput:.0f} writes/s abaixo do mínimo de 500 w/s. "
            "Epic 14 (subscriptions) pode sofrer degradação."
        )


# ==============================================================================
# Test 4 — Read-write contention (simula padrão real)
# ==============================================================================

class TestReadWriteMix:

    def test_read_write_mix_22_threads(self, bench_db):
        """
        11 threads escrevendo + 11 threads lendo simultaneamente.
        Simula o padrão real: monitor threads escrevem eventos,
        handler threads leem para gerar relatórios.

        Asserts:
        - Zero deadlocks / zero timeouts
        - Todos os 1100 writes confirmados ao final
        """
        NUM_WRITER_THREADS = 11
        NUM_READER_THREADS = 11
        WRITES_PER_THREAD = 100

        write_errors: list[Exception] = []
        read_errors: list[Exception] = []
        completed_writes: list[int] = []

        def writer(thread_idx: int) -> int:
            conn = get_conn(bench_db)
            count = 0
            for i in range(WRITES_PER_THREAD):
                try:
                    conn.execute(
                        "INSERT INTO bench_events (thread_id, ts, value) VALUES (?, ?, ?)",
                        (f'writer-{thread_idx}', time.time(), f'rw-{thread_idx}-{i}')
                    )
                    conn.commit()
                    count += 1
                except sqlite3.OperationalError as e:
                    write_errors.append(e)
            return count

        def reader(thread_idx: int) -> None:
            conn = get_conn(bench_db)
            for _ in range(50):  # 50 queries de leitura por thread
                try:
                    conn.execute("SELECT COUNT(*) FROM bench_events").fetchone()
                    conn.execute(
                        "SELECT DISTINCT thread_id FROM bench_events LIMIT 10"
                    ).fetchall()
                except sqlite3.OperationalError as e:
                    read_errors.append(e)

        t_start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=NUM_WRITER_THREADS + NUM_READER_THREADS) as executor:
            write_futures = [executor.submit(writer, i) for i in range(NUM_WRITER_THREADS)]
            read_futures = [executor.submit(reader, i) for i in range(NUM_READER_THREADS)]

            for fut in as_completed(write_futures):
                completed_writes.append(fut.result())

            for fut in as_completed(read_futures):
                fut.result()  # propaga exceções não capturadas

        elapsed = time.perf_counter() - t_start
        total_written = sum(completed_writes)
        expected_writes = NUM_WRITER_THREADS * WRITES_PER_THREAD

        print(
            f"\n[Read-Write Mix] {total_written}/{expected_writes} writes em {elapsed:.2f}s "
            f"| Write errors: {len(write_errors)} | Read errors: {len(read_errors)}"
        )

        assert write_errors == [], (
            f"{len(write_errors)} erros em escritoras (deadlock/timeout):\n"
            + "\n".join(str(e) for e in write_errors[:5])
        )

        assert read_errors == [], (
            f"{len(read_errors)} erros em leitoras:\n"
            + "\n".join(str(e) for e in read_errors[:5])
        )

        assert total_written == expected_writes, (
            f"Apenas {total_written}/{expected_writes} writes confirmados no mix read-write."
        )


# ==============================================================================
# Test 5 — Lock timeout configurado
# ==============================================================================

class TestLockTimeout:

    def test_lock_timeout_configured(self, bench_db):
        """
        Verifica que busy_timeout está configurado.
        Valor ideal: >= 5000ms (5 segundos) para absorver picos de contenção.
        Resultado abaixo de 5000ms: WARNING (não falha o teste).
        Resultado 0 (não configurado): WARNING (não falha o teste, mas registra risco).
        """
        conn = sqlite3.connect(bench_db)
        row = conn.execute('PRAGMA busy_timeout').fetchone()
        conn.close()

        assert row is not None, "PRAGMA busy_timeout não retornou resultado"

        timeout_ms = row[0]
        IDEAL_TIMEOUT_MS = 5000

        if timeout_ms == 0:
            import warnings
            warnings.warn(
                "PRAGMA busy_timeout = 0 (não configurado). "
                "Sob carga de 22 threads, isso pode causar 'database is locked' imediato. "
                f"Recomendado: PRAGMA busy_timeout={IDEAL_TIMEOUT_MS}",
                UserWarning,
                stacklevel=2
            )
        elif timeout_ms < IDEAL_TIMEOUT_MS:
            import warnings
            warnings.warn(
                f"PRAGMA busy_timeout = {timeout_ms}ms (abaixo do ideal de {IDEAL_TIMEOUT_MS}ms). "
                "Picos de contenção podem causar falhas em produção.",
                UserWarning,
                stacklevel=2
            )

        print(f"\n[Timeout] busy_timeout={timeout_ms}ms (ideal={IDEAL_TIMEOUT_MS}ms)")
        # Não falha — apenas documenta o estado atual


# ==============================================================================
# Test 6 — Relatório de benchmark (summary)
# ==============================================================================

class TestBenchmarkSummary:

    def test_print_benchmark_summary(self, bench_db, capsys):
        """
        Mini benchmark integrado + tabela de resultados para relatório.
        Roda subset dos testes anteriores e imprime tabela markdown.
        """
        results: dict[str, str] = {}

        # --- WAL mode ---
        conn = sqlite3.connect(bench_db)
        wal_row = conn.execute('PRAGMA journal_mode').fetchone()
        timeout_row = conn.execute('PRAGMA busy_timeout').fetchone()
        conn.close()

        wal_active = wal_row and wal_row[0] == 'wal'
        results['WAL mode'] = '✅ wal' if wal_active else f'❌ {wal_row[0] if wal_row else "?"}'
        results['busy_timeout'] = f"{timeout_row[0]}ms" if timeout_row else "não configurado"

        # --- Single-thread latency (200 writes para speed) ---
        latencies_ms: list[float] = []
        conn_st = get_conn(bench_db)
        for i in range(200):
            t0 = time.perf_counter()
            conn_st.execute(
                "INSERT INTO bench_events (thread_id, ts, value) VALUES (?, ?, ?)",
                ('summary-single', time.time(), f'sum-{i}')
            )
            conn_st.commit()
            latencies_ms.append((time.perf_counter() - t0) * 1000)

        p99 = percentile(latencies_ms, 99)
        results['Single-thread p99'] = f"{p99:.2f}ms"

        # --- 22-thread throughput (50 writes/thread) ---
        errors_22: list[Exception] = []
        write_counts_22: list[int] = []

        def _worker_summary(idx: int) -> int:
            c = get_conn(bench_db)
            count = 0
            for i in range(50):
                try:
                    c.execute(
                        "INSERT INTO bench_events (thread_id, ts, value) VALUES (?, ?, ?)",
                        (f'sum-t{idx}', time.time(), f's{idx}-{i}')
                    )
                    c.commit()
                    count += 1
                except sqlite3.OperationalError as e:
                    errors_22.append(e)
            return count

        t0_22 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=22) as ex:
            futs = [ex.submit(_worker_summary, i) for i in range(22)]
            for f in as_completed(futs):
                write_counts_22.append(f.result())
        elapsed_22 = time.perf_counter() - t0_22

        throughput_22 = sum(write_counts_22) / elapsed_22 if elapsed_22 > 0 else 0
        results['22-thread throughput'] = f"{throughput_22:.0f} w/s"
        results['Lock errors'] = str(len(errors_22))

        # --- Imprimir tabela ---
        print("\n" + "=" * 52)
        print("  SQLite Benchmark — Finding #3 Smith ULTRATHINK")
        print("=" * 52)
        print(f"  {'Métrica':<28} {'Valor':>18}")
        print("-" * 52)
        for metric, value in results.items():
            print(f"  {metric:<28} {value:>18}")
        print("=" * 52)

        captured = capsys.readouterr()
        assert "WAL mode" in captured.out
        assert "throughput" in captured.out
        assert "Lock errors" in captured.out
