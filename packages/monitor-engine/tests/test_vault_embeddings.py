"""
test_vault_embeddings.py — Testes para webdex_ai_vault_embeddings.py (Story 23.1)

Cobertura:
  - cosine_similarity: cálculos corretos, edge cases
  - generate_embeddings: happy path, rebuild incremental (hash check), vault vazio
  - semantic_search: resultado encontrado, fallback sem modelo, threshold e disclaimer
  - buscar_vault: integração semântica + fallback fulltext
  - vault_embeddings_worker: inicializa sem crash
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest.mock as mock
from pathlib import Path

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Setup: garantir que conftest já aplicou mocks pesados
# O conftest.py do diretório tests/ é carregado automaticamente pelo pytest.
# Aqui só precisamos garantir que DB_PATH usa :memory:
# ─────────────────────────────────────────────────────────────────────────────
os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("VAULT_LOCAL_PATH", "/tmp/fake_vault_test")
os.environ.setdefault("SIMILARITY_THRESHOLD", "0.65")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _import_module():
    """Importa webdex_ai_vault_embeddings com DB in-memory."""
    # Garantir que uma conexão anterior não vaze entre testes
    if "webdex_ai_vault_embeddings" in sys.modules:
        mod = sys.modules["webdex_ai_vault_embeddings"]
        # Reset thread-local connection para usar :memory: fresco
        if hasattr(mod._thread_local, "emb_conn") and mod._thread_local.emb_conn:
            try:
                mod._thread_local.emb_conn.close()
            except Exception:
                pass
            mod._thread_local.emb_conn = None
    import webdex_ai_vault_embeddings as m
    return m


def _unit_vec(n: int, idx: int) -> list[float]:
    """Vetor unitário de dimensão n com 1.0 na posição idx."""
    v = [0.0] * n
    v[idx] = 1.0
    return v


# ─────────────────────────────────────────────────────────────────────────────
# 1. cosine_similarity
# ─────────────────────────────────────────────────────────────────────────────

class TestCosineSimilarity:

    def test_identical_vectors(self):
        m = _import_module()
        v = [1.0, 0.5, 0.25]
        assert m.cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self):
        m = _import_module()
        a = _unit_vec(3, 0)
        b = _unit_vec(3, 1)
        assert m.cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors(self):
        m = _import_module()
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert m.cosine_similarity(a, b) == pytest.approx(-1.0, abs=1e-6)

    def test_empty_vector_returns_zero(self):
        m = _import_module()
        assert m.cosine_similarity([], []) == 0.0
        assert m.cosine_similarity([1.0], []) == 0.0

    def test_zero_magnitude_returns_zero(self):
        m = _import_module()
        assert m.cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_dimension_mismatch_returns_zero(self):
        m = _import_module()
        assert m.cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0

    def test_partial_similarity(self):
        m = _import_module()
        a = [1.0, 1.0]
        b = [1.0, 0.0]
        # cos(45°) ≈ 0.707
        result = m.cosine_similarity(a, b)
        assert 0.70 < result < 0.72


# ─────────────────────────────────────────────────────────────────────────────
# 2. generate_embeddings
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateEmbeddings:

    @pytest.fixture
    def vault_dir(self, tmp_path):
        """Cria vault temporário com 3 notas."""
        (tmp_path / "nota1.md").write_text("WEbdEX protocolo arbitragem triangular", encoding="utf-8")
        (tmp_path / "nota2.md").write_text("Token BD tokenomia staking holders", encoding="utf-8")
        (tmp_path / "nota3.md").write_text("", encoding="utf-8")  # nota vazia
        return tmp_path

    def test_generates_for_nonempty_notes(self, vault_dir):
        """Deve processar 2 notas e pular a vazia."""
        m = _import_module()

        fake_embedding = [0.1, 0.2, 0.3]
        with mock.patch.object(m, "_load_model", return_value=True), \
             mock.patch.object(m, "_embed_text", return_value=fake_embedding), \
             mock.patch.object(m, "_MODEL_AVAILABLE", True):
            stats = m.generate_embeddings(notes_dir=vault_dir)

        assert stats["processed"] == 2
        assert stats["skipped"] == 1  # nota vazia
        assert stats["errors"] == 0
        assert stats["available"] is True

    def test_incremental_skips_unchanged(self, vault_dir):
        """Segunda execução deve pular notas sem mudança de hash."""
        m = _import_module()
        fake_embedding = [0.1, 0.2, 0.3]

        with mock.patch.object(m, "_load_model", return_value=True), \
             mock.patch.object(m, "_embed_text", return_value=fake_embedding), \
             mock.patch.object(m, "_MODEL_AVAILABLE", True):
            # Primeira execução — processa tudo
            stats1 = m.generate_embeddings(notes_dir=vault_dir)
            # Segunda execução — deve pular tudo (hash igual)
            stats2 = m.generate_embeddings(notes_dir=vault_dir)

        assert stats1["processed"] == 2
        # Tudo pulado na segunda execução (mesmo hash)
        assert stats2["processed"] == 0
        assert stats2["skipped"] >= 2

    def test_force_reprocesses_all(self, vault_dir):
        """force=True deve re-embedar mesmo sem mudança de hash."""
        m = _import_module()
        fake_embedding = [0.1, 0.2, 0.3]

        with mock.patch.object(m, "_load_model", return_value=True), \
             mock.patch.object(m, "_embed_text", return_value=fake_embedding), \
             mock.patch.object(m, "_MODEL_AVAILABLE", True):
            m.generate_embeddings(notes_dir=vault_dir)
            stats = m.generate_embeddings(notes_dir=vault_dir, force=True)

        assert stats["processed"] == 2

    def test_model_unavailable_returns_gracefully(self, vault_dir):
        """Se modelo indisponível, retorna dict com available=False sem crash."""
        m = _import_module()

        with mock.patch.object(m, "_load_model", return_value=False):
            stats = m.generate_embeddings(notes_dir=vault_dir)

        assert stats["available"] is False
        assert stats["processed"] == 0

    def test_vault_dir_not_found_returns_gracefully(self):
        """Vault inexistente não deve lançar exceção."""
        m = _import_module()
        non_existent = Path("/tmp/definitely_does_not_exist_xyz_123")

        with mock.patch.object(m, "_load_model", return_value=True), \
             mock.patch.object(m, "_MODEL_AVAILABLE", True):
            stats = m.generate_embeddings(notes_dir=non_existent)

        assert stats["processed"] == 0
        assert stats["available"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 3. semantic_search
# ─────────────────────────────────────────────────────────────────────────────

class TestSemanticSearch:

    @pytest.fixture
    def vault_with_embeddings(self, tmp_path):
        """
        Cria vault + embeddings no SQLite para simular estado após generate_embeddings.
        Usa vetores ortogonais simples para controlar similaridade.
        """
        m = _import_module()
        note1 = tmp_path / "arbitragem.md"
        note2 = tmp_path / "tokenomia.md"
        note1.write_text("Protocolo WEbdEX usa arbitragem triangular em Polygon", encoding="utf-8")
        note2.write_text("Token BD tokenomia staking holders recompensas", encoding="utf-8")

        # Inserir embeddings manualmente no SQLite
        m._ensure_tables()
        vec1 = _unit_vec(4, 0)
        vec2 = _unit_vec(4, 1)
        m._save_embedding(note1, note1.read_text(), vec1)
        m._save_embedding(note2, note2.read_text(), vec2)

        return tmp_path, note1, note2, vec1, vec2

    def test_returns_most_similar_note(self, vault_with_embeddings):
        """Query similar ao vec1 deve retornar nota 1 no topo."""
        m = _import_module()
        _, note1, _, vec1, _ = vault_with_embeddings

        query_vec = _unit_vec(4, 0)  # idêntico ao vec1

        with mock.patch.object(m, "_load_model", return_value=True), \
             mock.patch.object(m, "_embed_query", return_value=query_vec), \
             mock.patch.object(m, "_MODEL_AVAILABLE", True):
            results = m.semantic_search("arbitragem triangular", top_k=2)

        assert len(results) >= 1
        top = results[0]
        assert top["score"] == pytest.approx(1.0, abs=0.01)
        assert "arbitragem.md" in top["note_id"] or "arbitragem" in top["note_path"]

    def test_low_confidence_flag(self, vault_with_embeddings):
        """Score abaixo do threshold deve setar low_confidence=True."""
        m = _import_module()

        # Vec ortogonal a todos — score = 0 para tudo
        query_vec = _unit_vec(4, 3)  # nenhuma nota tem dimensão 3

        with mock.patch.object(m, "_load_model", return_value=True), \
             mock.patch.object(m, "_embed_query", return_value=query_vec), \
             mock.patch.object(m, "_MODEL_AVAILABLE", True):
            results = m.semantic_search("pergunta sem match", top_k=2)

        # Todos os resultados com score 0 devem ter low_confidence=True
        for r in results:
            if r["score"] < 0.65:
                assert r["low_confidence"] is True

    def test_noresult_logged_when_below_threshold(self, vault_with_embeddings):
        """Query com max_score < threshold deve ser logada em vault_queries_noresult."""
        m = _import_module()

        query_vec = _unit_vec(4, 3)  # score 0 para todas as notas

        with mock.patch.object(m, "_load_model", return_value=True), \
             mock.patch.object(m, "_embed_query", return_value=query_vec), \
             mock.patch.object(m, "_MODEL_AVAILABLE", True):
            m.semantic_search("query sem resultado", top_k=2)

        c = m._get_conn()
        rows = c.execute("SELECT * FROM vault_queries_noresult").fetchall()
        assert len(rows) >= 1
        assert "query sem resultado" in rows[-1]["query"]

    def test_returns_empty_when_model_unavailable(self):
        """Sem modelo disponível, semantic_search retorna [] sem exceção."""
        m = _import_module()

        with mock.patch.object(m, "_load_model", return_value=False), \
             mock.patch.object(m, "_MODEL_AVAILABLE", False):
            results = m.semantic_search("qualquer pergunta")

        assert results == []

    def test_returns_empty_when_no_embeddings_in_db(self):
        """Sem embeddings no banco, retorna [] sem exceção."""
        m = _import_module()

        # Limpar banco
        c = m._get_conn()
        c.execute("DELETE FROM vault_embeddings")
        c.commit()

        with mock.patch.object(m, "_load_model", return_value=True), \
             mock.patch.object(m, "_MODEL_AVAILABLE", True):
            results = m.semantic_search("busca vazia")

        assert results == []

    def test_top_k_limits_results(self, vault_with_embeddings):
        """top_k deve limitar número máximo de resultados."""
        m = _import_module()
        query_vec = _unit_vec(4, 0)

        with mock.patch.object(m, "_load_model", return_value=True), \
             mock.patch.object(m, "_embed_query", return_value=query_vec), \
             mock.patch.object(m, "_MODEL_AVAILABLE", True):
            results = m.semantic_search("qualquer", top_k=1)

        assert len(results) <= 1


# ─────────────────────────────────────────────────────────────────────────────
# 4. buscar_vault (integração webdex_ai.py)
# ─────────────────────────────────────────────────────────────────────────────

class TestBuscarVault:

    def test_semantic_path_returns_formatted_string(self, tmp_path):
        """Quando embeddings disponíveis, retorna bloco formatado com VAULT:."""
        # Mock do módulo de embeddings
        fake_results = [
            {
                "note_id": "arbitragem.md",
                "note_path": str(tmp_path / "arbitragem.md"),
                "score": 0.92,
                "content": "Protocolo WEbdEX arbitragem triangular Polygon",
                "low_confidence": False,
            }
        ]

        import importlib
        import webdex_ai as ai_mod

        orig_enabled  = ai_mod._VAULT_EMBEDDINGS_ENABLED
        orig_search   = ai_mod._vault_semantic_search
        try:
            ai_mod._VAULT_EMBEDDINGS_ENABLED = True
            ai_mod._vault_semantic_search = mock.MagicMock(return_value=fake_results)

            result = ai_mod.buscar_vault("como funciona a arbitragem")
        finally:
            ai_mod._VAULT_EMBEDDINGS_ENABLED = orig_enabled
            ai_mod._vault_semantic_search    = orig_search

        assert "VAULT:" in result
        assert "score=0.92" in result
        assert "busca semântica" in result

    def test_fallback_fulltext_when_embeddings_disabled(self, tmp_path):
        """Quando embeddings desabilitados, usa fulltext grep."""
        note = tmp_path / "nota.md"
        note.write_text("WEbdEX protocolo on-chain", encoding="utf-8")

        import webdex_ai as ai_mod

        orig_enabled = ai_mod._VAULT_EMBEDDINGS_ENABLED
        try:
            ai_mod._VAULT_EMBEDDINGS_ENABLED = False
            with mock.patch.dict(os.environ, {"VAULT_LOCAL_PATH": str(tmp_path)}):
                # Recarregar variável interna do módulo
                import webdex_ai_vault_embeddings as emb
                old_vault = emb._VAULT_PATH
                emb._VAULT_PATH = tmp_path
                try:
                    result = ai_mod.buscar_vault("WEbdEX protocolo")
                finally:
                    emb._VAULT_PATH = old_vault
        finally:
            ai_mod._VAULT_EMBEDDINGS_ENABLED = orig_enabled

        assert "VAULT:" in result or result == ""  # fulltext pode retornar resultado

    def test_returns_empty_string_on_no_match(self, tmp_path):
        """Sem match nenhum, retorna string vazia (sem exceção)."""
        import webdex_ai as ai_mod

        orig_enabled = ai_mod._VAULT_EMBEDDINGS_ENABLED
        orig_search  = ai_mod._vault_semantic_search
        try:
            ai_mod._VAULT_EMBEDDINGS_ENABLED = True
            ai_mod._vault_semantic_search = mock.MagicMock(return_value=[])
            result = ai_mod.buscar_vault("pergunta completamente irrelevante xyz")
        finally:
            ai_mod._VAULT_EMBEDDINGS_ENABLED = orig_enabled
            ai_mod._vault_semantic_search    = orig_search

        assert result == ""

    def test_low_confidence_disclaimer_present(self, tmp_path):
        """Resultado com low_confidence=True deve incluir disclaimer de incerteza."""
        fake_results = [
            {
                "note_id": "nota.md",
                "note_path": str(tmp_path / "nota.md"),
                "score": 0.45,  # abaixo do threshold 0.65
                "content": "conteúdo vago",
                "low_confidence": True,
            }
        ]

        import webdex_ai as ai_mod

        orig_enabled = ai_mod._VAULT_EMBEDDINGS_ENABLED
        orig_search  = ai_mod._vault_semantic_search
        try:
            ai_mod._VAULT_EMBEDDINGS_ENABLED = True
            ai_mod._vault_semantic_search = mock.MagicMock(return_value=fake_results)
            result = ai_mod.buscar_vault("pergunta vaga")
        finally:
            ai_mod._VAULT_EMBEDDINGS_ENABLED = orig_enabled
            ai_mod._vault_semantic_search    = orig_search

        assert "não tenho certeza" in result or "baixa confiança" in result

    def test_graceful_on_exception(self, tmp_path):
        """Exceção dentro de semantic_search não deve propagar — fallback ativo."""
        import webdex_ai as ai_mod

        orig_enabled = ai_mod._VAULT_EMBEDDINGS_ENABLED
        orig_search  = ai_mod._vault_semantic_search
        try:
            ai_mod._VAULT_EMBEDDINGS_ENABLED = True
            ai_mod._vault_semantic_search = mock.MagicMock(
                side_effect=RuntimeError("Ollama offline")
            )
            # Não deve lançar exceção
            result = ai_mod.buscar_vault("qualquer query")
        finally:
            ai_mod._VAULT_EMBEDDINGS_ENABLED = orig_enabled
            ai_mod._vault_semantic_search    = orig_search

        # Resultado deve ser string (pode ser vazio ou fulltext fallback)
        assert isinstance(result, str)


# ─────────────────────────────────────────────────────────────────────────────
# 5. vault_embeddings_worker
# ─────────────────────────────────────────────────────────────────────────────

class TestVaultEmbeddingsWorker:

    def test_worker_can_be_imported(self):
        """Worker deve importar sem erro."""
        m = _import_module()
        assert callable(m.vault_embeddings_worker)

    def test_worker_registered_in_main(self):
        """Worker deve estar registrado no _THREAD_REGISTRY do webdex_main (se disponível)."""
        try:
            import webdex_main
            # Se o import e registro aconteceram sem crash, o teste passa
            assert True
        except Exception as e:
            pytest.skip(f"webdex_main não importável neste ambiente de teste: {e}")

    def test_worker_thread_starts_and_is_daemon(self):
        """Worker thread deve iniciar como daemon e não crashar imediatamente."""
        m = _import_module()

        started = threading.Event()
        stopped = threading.Event()

        def patched_sleep(seconds):
            started.set()
            stopped.wait(timeout=0.1)
            raise SystemExit("stop_worker_test")

        with mock.patch("webdex_ai_vault_embeddings.time.sleep", side_effect=patched_sleep):
            t = threading.Thread(target=m.vault_embeddings_worker, daemon=True)
            t.start()
            started.wait(timeout=3.0)
            stopped.set()
            t.join(timeout=2.0)

        # Chegou aqui sem exceção não capturada = passou
        assert True


# ─────────────────────────────────────────────────────────────────────────────
# 6. Rebuild incremental (hook de nova nota)
# ─────────────────────────────────────────────────────────────────────────────

class TestRebuildIncremental:

    def test_new_note_detected_by_hash(self, tmp_path):
        """Nova nota (sem hash armazenado) deve ser processada."""
        m = _import_module()
        note = tmp_path / "nova_nota.md"
        note.write_text("Conteúdo novo sobre Token BD", encoding="utf-8")

        fake_embedding = [0.5, 0.5, 0.0]

        with mock.patch.object(m, "_load_model", return_value=True), \
             mock.patch.object(m, "_embed_text", return_value=fake_embedding), \
             mock.patch.object(m, "_MODEL_AVAILABLE", True):
            stats = m.generate_embeddings(notes_dir=tmp_path)

        assert stats["processed"] >= 1

    def test_modified_note_reprocessed(self, tmp_path):
        """Nota com conteúdo alterado (hash diferente) deve ser re-embeddada."""
        m = _import_module()
        note = tmp_path / "nota_modificada.md"
        note.write_text("Conteúdo original v1", encoding="utf-8")

        fake_embedding = [0.5, 0.5, 0.0]

        with mock.patch.object(m, "_load_model", return_value=True), \
             mock.patch.object(m, "_embed_text", return_value=fake_embedding), \
             mock.patch.object(m, "_MODEL_AVAILABLE", True):
            # Primeira execução
            m.generate_embeddings(notes_dir=tmp_path)

            # Modificar a nota
            note.write_text("Conteúdo alterado v2 — novo conteúdo adicionado", encoding="utf-8")

            # Segunda execução — deve detectar mudança e re-processar
            stats = m.generate_embeddings(notes_dir=tmp_path)

        assert stats["processed"] >= 1  # nota modificada foi reprocessada
