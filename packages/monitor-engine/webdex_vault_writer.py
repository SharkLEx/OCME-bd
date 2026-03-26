"""
webdex_vault_writer.py — Vault Writer do Nightly Trainer

Escreve notas Obsidian no vault a partir do conhecimento descoberto pelo Nexo.
Fecha o loop: Conversas → Nexo aprende → bdz_knowledge (DB) + Vault (.md)

Fluxo:
  1. Nexo extrai nexo_learned das conversas Discord + Telegram
  2. Para cada item relevante (confidence >= 0.75), escreve nota .md no vault
  3. Notas ficam disponíveis para vault_reader na próxima query do bdZinho
  4. Cron diário no VPS: git pull → docker cp vault → reinicia nada (vault é lido em tempo real)

Configuração (env vars):
  VAULT_LOCAL_PATH    — caminho local do vault para escrita (default: /app/vault)
  VAULT_LEARNED_DIR   — subpasta para notas aprendidas (default: learned)
  VAULT_MIN_CONFIDENCE — confiança mínima para criar nota (default: 0.75)

Formato das notas criadas:
  knowledge/learned/nexo-YYYYMMDD-HHMMSS-{topic}.md
"""
from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
_VAULT_LOCAL_PATH  = Path(os.getenv("VAULT_LOCAL_PATH", "/app/vault"))
_LEARNED_SUBDIR    = os.getenv("VAULT_LEARNED_DIR", "learned")
_MIN_CONFIDENCE    = float(os.getenv("VAULT_MIN_CONFIDENCE", "0.75"))

# Brasília = UTC-3
_TZ_BR = timezone(timedelta(hours=-3))


def _safe_filename(topic: str) -> str:
    """Converte topic para nome de arquivo seguro."""
    safe = re.sub(r'[^\w\-]', '_', topic.lower().replace(' ', '_'))
    return safe[:40]


def _make_frontmatter(title: str, topic: str, tags: list[str], source: str) -> str:
    now_br = datetime.now(tz=_TZ_BR)
    tags_yaml = "\n".join(f"  - {t}" for t in tags)
    return (
        f"---\n"
        f"type: knowledge\n"
        f"title: \"{title}\"\n"
        f"tags:\n"
        f"{tags_yaml}\n"
        f"created: {now_br.strftime('%Y-%m-%d')}\n"
        f"source: nexo-{source}\n"
        f"auto_generated: true\n"
        f"---\n\n"
    )


def write_learned_note(
    topic: str,
    content: str,
    confidence: float = 0.85,
    source_channel: str = "conversations",
    extra_tags: Optional[list[str]] = None,
    dry_run: bool = False,
) -> Optional[Path]:
    """
    Cria uma nota Obsidian a partir de um item aprendido pelo Nexo.

    Args:
        topic:          Identificador curto do conhecimento (ex: 'stablecoin_tvl_growth')
        content:        Conteúdo da nota (2-4 frases)
        confidence:     Confiança do Nexo (0.0-1.0). Abaixo de MIN_CONFIDENCE → ignorado.
        source_channel: Canal de origem ('telegram', 'discord', 'both')
        extra_tags:     Tags adicionais além das padrão
        dry_run:        Se True, apenas loga sem criar arquivo

    Returns:
        Path da nota criada ou None se ignorada/falhou
    """
    if confidence < _MIN_CONFIDENCE:
        logger.debug("[vault_writer] Ignorado (confidence=%.2f < %.2f): %s", confidence, _MIN_CONFIDENCE, topic)
        return None

    if not content or not topic:
        logger.debug("[vault_writer] Ignorado: topic ou content vazio")
        return None

    # Monta tags automáticas
    tags = ["knowledge", "nexo", "auto-aprendizado", "webdex"]
    if extra_tags:
        tags.extend(extra_tags)

    title = topic.replace("_", " ").replace("-", " ").title()

    # Gera frontmatter + corpo
    now_br   = datetime.now(tz=_TZ_BR)
    timestamp = now_br.strftime("%Y%m%d-%H%M%S")
    filename  = f"nexo-{timestamp}-{_safe_filename(topic)}.md"

    body = (
        f"# {title}\n\n"
        f"> Gerado automaticamente pelo Nexo — Nightly Trainer do bdZinho\n"
        f"> Fonte: conversas {source_channel} | {now_br.strftime('%d/%m/%Y %H:%M')} (Brasília)\n"
        f"> Confiança: {confidence:.0%}\n\n"
        f"{content}\n\n"
        f"---\n\n"
        f"← [[MOC-bdZinho-Learning-Map]] — mapa de aprendizado\n"
    )

    note_content = _make_frontmatter(title, topic, tags, source_channel) + body

    if dry_run:
        logger.info("[vault_writer][DRY-RUN] %s: %s", filename, content[:80])
        return _VAULT_LOCAL_PATH / _LEARNED_SUBDIR / filename

    # Garante que o diretório existe
    learned_dir = _VAULT_LOCAL_PATH / _LEARNED_SUBDIR
    try:
        learned_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning("[vault_writer] Não foi possível criar dir %s: %s", learned_dir, e)
        return None

    note_path = learned_dir / filename
    try:
        note_path.write_text(note_content, encoding="utf-8")
        logger.info("[vault_writer] Nota criada: %s (confidence=%.2f)", note_path.name, confidence)
        return note_path
    except Exception as e:
        logger.warning("[vault_writer] Falhou ao escrever %s: %s", note_path, e)
        return None


def write_nexo_batch(
    nexo_learned: list[dict],
    source_channel: str = "both",
    dry_run: bool = False,
) -> int:
    """
    Escreve todas as entradas nexo_learned no vault como notas Obsidian.

    Args:
        nexo_learned:   Lista de dicts {topic, content, confidence} do Nexo
        source_channel: Canal de origem das conversas
        dry_run:        Simula sem criar arquivos

    Returns:
        Número de notas criadas
    """
    if not nexo_learned:
        return 0

    created = 0
    for item in nexo_learned:
        topic      = item.get("topic", "")
        content    = item.get("content", "")
        confidence = float(item.get("confidence", 0.85))

        path = write_learned_note(
            topic          = topic,
            content        = content,
            confidence     = confidence,
            source_channel = source_channel,
            dry_run        = dry_run,
        )
        if path:
            created += 1
        time.sleep(0.05)  # evita burst de I/O

    logger.info("[vault_writer] Lote concluído: %d/%d notas criadas", created, len(nexo_learned))
    return created


def vault_writer_status() -> dict:
    """Retorna status do vault writer."""
    learned_dir = _VAULT_LOCAL_PATH / _LEARNED_SUBDIR
    notes_count = 0
    if learned_dir.exists():
        notes_count = len(list(learned_dir.glob("nexo-*.md")))
    return {
        "vault_path":   str(_VAULT_LOCAL_PATH),
        "learned_dir":  str(learned_dir),
        "vault_exists": _VAULT_LOCAL_PATH.exists(),
        "notes_created": notes_count,
        "min_confidence": _MIN_CONFIDENCE,
    }
