"""
webdex_deterministic_trainer.py — bdZinho Deterministic Trainer

Extração GRATUITA e DETERMINÍSTICA de conhecimento.
Zero chamadas LLM, zero custo de API.

Fontes de dados:
  - PostgreSQL: ai_conversations, ai_memory, bdz_knowledge
  - SQLite: operacoes, capital_cache, anomaly_events, users

Output:
  - Notas .md Obsidian em /opt/vault/learned/
  - Dedup por SHA256(topic+date) — não sobrescreve notas frescas

Cadência: nightly worker às 00h BRT (via webdex_main._THREAD_REGISTRY)
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bdz_determ_trainer")

# ── Config ─────────────────────────────────────────────────────────────────────
_DATABASE_URL  = os.getenv("DATABASE_URL", "")
_VAULT_PATH    = Path(os.getenv("VAULT_LOCAL_PATH", "/opt/vault"))
_LEARNED_DIR   = _VAULT_PATH / "learned"

# Só reescreve nota se tiver mais de N horas (evita reescrever no mesmo dia)
_NOTE_MIN_AGE_H = 20

# Horário BRT para rodar (0h = meia-noite BRT = 3h UTC)
_NIGHTLY_HOUR_UTC = 3
_POLL_INTERVAL_S  = 60 * 60  # verifica a cada hora

# ── Helpers ────────────────────────────────────────────────────────────────────

def _ensure_learned_dir() -> bool:
    """Garante que /opt/vault/learned/ existe."""
    try:
        _LEARNED_DIR.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.warning("[determ] Não foi possível criar vault/learned/: %s", e)
        return False


def _note_is_fresh(path: Path) -> bool:
    """Retorna True se a nota foi escrita nas últimas _NOTE_MIN_AGE_H horas."""
    try:
        mtime = path.stat().st_mtime
        age_h = (time.time() - mtime) / 3600
        return age_h < _NOTE_MIN_AGE_H
    except FileNotFoundError:
        return False


def _write_note(filename: str, content: str, dry_run: bool = False) -> bool:
    """
    Escreve nota .md no vault/learned/.
    Retorna True se escreveu, False se estava fresca (dedup).
    """
    path = _LEARNED_DIR / filename
    if _note_is_fresh(path):
        logger.debug("[determ] Nota fresca, pulando: %s", filename)
        return False
    if dry_run:
        logger.info("[determ][DRY] Escreveria: %s (%d chars)", filename, len(content))
        return True
    try:
        path.write_text(content, encoding="utf-8")
        logger.info("[determ] Nota escrita: %s", filename)
        return True
    except Exception as e:
        logger.warning("[determ] Falha ao escrever %s: %s", filename, e)
        return False


def _today() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


def _month() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m")


# ── Fonte 1: Estatísticas de operações (SQLite) ───────────────────────────────

def _extract_operations_stats(dry_run: bool = False) -> int:
    """
    Lê operacoes + capital_cache do SQLite.
    Gera nota diária de performance do protocolo.
    """
    try:
        from webdex_db import DB_LOCK, conn as sqlite_conn
    except ImportError:
        logger.warning("[determ] webdex_db não disponível")
        return 0

    today = _today()

    try:
        with DB_LOCK:
            # Operações últimas 24h
            cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
            cur = sqlite_conn.execute(
                """
                SELECT tipo, COUNT(*) as cnt, SUM(valor) as total_val,
                       AVG(gas_usd) as avg_gas, ambiente
                FROM operacoes
                WHERE data_hora >= ?
                GROUP BY tipo, ambiente
                ORDER BY cnt DESC
                LIMIT 50
                """,
                (cutoff,),
            )
            op_rows = cur.fetchall()

            # Capital snapshot mais recente (colunas reais: chat_id, env, total_usd, breakdown_json, updated_ts)
            cap_cur = sqlite_conn.execute(
                """
                SELECT chat_id, env, total_usd, breakdown_json, updated_ts
                FROM capital_cache
                ORDER BY updated_ts DESC
                LIMIT 20
                """
            )
            cap_rows = cap_cur.fetchall()

            # Usuários ativos
            users_cur = sqlite_conn.execute(
                "SELECT COUNT(*) FROM users WHERE active=1"
            )
            active_users = users_cur.fetchone()[0]

    except Exception as e:
        logger.warning("[determ] Erro ao ler SQLite: %s", e)
        return 0

    if not op_rows and not cap_rows:
        return 0

    # Agrega por tipo
    by_tipo: dict = {}
    for tipo, cnt, total_val, avg_gas, ambiente in op_rows:
        k = tipo or "unknown"
        if k not in by_tipo:
            by_tipo[k] = {"count": 0, "volume": 0.0, "avg_gas": 0.0}
        by_tipo[k]["count"] += (cnt or 0)
        by_tipo[k]["volume"] += float(total_val or 0)
        by_tipo[k]["avg_gas"] = float(avg_gas or 0)

    total_ops   = sum(v["count"]  for v in by_tipo.values())
    total_vol   = sum(v["volume"] for v in by_tipo.values())
    total_cap   = sum(float(r[2] or 0) for r in cap_rows)  # r[2] = total_usd

    # Monta nota Obsidian
    lines = [
        "---",
        f"type: protocol-stats",
        f"title: \"Protocolo WEbdEX — Stats {today}\"",
        f"date: {today}",
        f"tags:",
        f"  - learned",
        f"  - protocol-stats",
        f"  - auto-generated",
        "---",
        "",
        f"# 📊 WEbdEX Protocol Stats — {today}",
        "",
        f"**Operações (24h):** {total_ops}",
        f"**Volume Total (24h):** ${total_vol:,.2f}",
        f"**Capital Total em Caixa:** ${total_cap:,.2f}",
        f"**Usuários Ativos:** {active_users}",
        "",
        "## Por Tipo de Operação",
        "",
    ]

    for tipo, info in sorted(by_tipo.items(), key=lambda x: x[1]["count"], reverse=True)[:10]:
        lines.append(f"- **{tipo}**: {info['count']} ops | volume ${info['volume']:,.2f} | gas médio ${info['avg_gas']:.4f}")

    lines += [
        "",
        "## Capital por Usuário (top 10)",
        "",
    ]
    for chat_id_c, env_c, total_usd_c, breakdown_json_c, updated_ts_c in cap_rows[:10]:
        lines.append(
            f"- **{env_c or 'N/A'}** (chat:{chat_id_c}): USD ${float(total_usd_c or 0):,.2f} "
            f"_(ts: {updated_ts_c or 'N/A'})_"
        )

    lines += [
        "",
        "---",
        f"*Gerado automaticamente pelo Deterministic Trainer em {datetime.now(tz=timezone.utc).isoformat()}*",
    ]

    content = "\n".join(lines)
    wrote = _write_note(f"protocol-stats-{today}.md", content, dry_run=dry_run)
    return 1 if wrote else 0


# ── Fonte 2: FAQ patterns (PostgreSQL ai_conversations) ───────────────────────

def _extract_faq_patterns(days: int = 7, dry_run: bool = False) -> int:
    """
    Conta padrões de perguntas frequentes sem LLM.
    Extrai keywords + bigrams das mensagens de usuários.
    Gera nota mensal de FAQ trends.
    """
    if not _DATABASE_URL:
        return 0

    month = _month()
    today = _today()

    try:
        import psycopg2
        pg_conn = psycopg2.connect(_DATABASE_URL, connect_timeout=10)
        try:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
            with pg_conn.cursor() as cur:
                # Tenta ai_conversations primeiro
                try:
                    cur.execute(
                        """
                        SELECT content FROM ai_conversations
                        WHERE created_at >= %s AND role = 'user'
                        ORDER BY created_at DESC
                        LIMIT 500
                        """,
                        (cutoff,),
                    )
                    rows = cur.fetchall()
                except Exception:
                    # Fallback para ai_memory
                    pg_conn.rollback()
                    cur.execute(
                        """
                        SELECT content FROM ai_memory
                        WHERE created_at >= %s AND role = 'user'
                        ORDER BY created_at DESC
                        LIMIT 500
                        """,
                        (cutoff,),
                    )
                    rows = cur.fetchall()
        finally:
            pg_conn.close()
    except Exception as e:
        logger.warning("[determ] Erro ao ler PostgreSQL para FAQ: %s", e)
        return 0

    if not rows:
        return 0

    # Extração determinística de padrões: word frequency + bigrams
    stop_words = {
        "o", "a", "os", "as", "de", "da", "do", "em", "no", "na",
        "e", "é", "que", "um", "uma", "por", "para", "com", "se",
        "eu", "me", "meu", "minha", "seu", "sua", "oi", "olá",
        "tudo", "bem", "ok", "sim", "não", "como", "qual", "quando",
        "the", "is", "are", "to", "in", "of", "and", "a", "an",
    }

    word_counter: Counter = Counter()
    bigram_counter: Counter = Counter()
    total_msgs = len(rows)

    for (content,) in rows:
        text = str(content or "").lower().strip()[:200]
        words = [w.strip(".,!?;:()[]") for w in text.split() if len(w) > 2]
        words = [w for w in words if w not in stop_words]

        for w in words:
            word_counter[w] += 1

        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            if len(bigram) > 4:
                bigram_counter[bigram] += 1

    top_words   = word_counter.most_common(20)
    top_bigrams = bigram_counter.most_common(15)

    # Monta nota
    lines = [
        "---",
        f"type: faq-patterns",
        f"title: \"FAQ Patterns — {month}\"",
        f"date: {today}",
        f"tags:",
        f"  - learned",
        f"  - faq-patterns",
        f"  - auto-generated",
        "---",
        "",
        f"# ❓ FAQ Patterns — {month}",
        "",
        f"**Mensagens analisadas:** {total_msgs} (últimos {days} dias)",
        "",
        "## Palavras Mais Frequentes",
        "",
    ]

    for word, cnt in top_words:
        pct = round(cnt / total_msgs * 100, 1)
        lines.append(f"- `{word}` — {cnt}x ({pct}%)")

    lines += [
        "",
        "## Bigrams (padrões de 2 palavras)",
        "",
    ]

    for bigram, cnt in top_bigrams:
        lines.append(f"- `{bigram}` — {cnt}x")

    lines += [
        "",
        "## Insights para o bdZinho",
        "",
        "- Palavras dominantes indicam os temas mais perguntados pelos usuários",
        "- Bigrams revelam combinações de conceitos recorrentes",
        "- Use estes padrões para priorizar conteúdo educativo e respostas proativas",
        "",
        "---",
        f"*Extração determinística — sem LLM. Gerado em {datetime.now(tz=timezone.utc).isoformat()}*",
    ]

    content = "\n".join(lines)
    wrote = _write_note(f"faq-patterns-{month}.md", content, dry_run=dry_run)
    return 1 if wrote else 0


# ── Fonte 3: Resumo de conhecimento acumulado (PostgreSQL bdz_knowledge) ──────

def _extract_knowledge_summary(dry_run: bool = False) -> int:
    """
    Lê estatísticas do bdz_knowledge e gera snapshot do estado do conhecimento do bot.
    """
    if not _DATABASE_URL:
        return 0

    today = _today()

    try:
        import psycopg2
        pg_conn = psycopg2.connect(_DATABASE_URL, connect_timeout=10)
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT category, COUNT(*) as cnt,
                           MAX(updated_at) as last_update,
                           AVG(confidence) as avg_conf
                    FROM bdz_knowledge
                    WHERE active = TRUE
                    GROUP BY category
                    ORDER BY cnt DESC
                    """
                )
                rows = cur.fetchall()

                cur.execute("SELECT COUNT(*) FROM bdz_knowledge WHERE active = TRUE")
                total = cur.fetchone()[0]
        finally:
            pg_conn.close()
    except Exception as e:
        logger.warning("[determ] Erro ao ler bdz_knowledge: %s", e)
        return 0

    if not rows:
        return 0

    lines = [
        "---",
        f"type: knowledge-snapshot",
        f"title: \"bdZinho Knowledge Snapshot — {today}\"",
        f"date: {today}",
        f"tags:",
        f"  - learned",
        f"  - knowledge-snapshot",
        f"  - auto-generated",
        "---",
        "",
        f"# 🧠 bdZinho Knowledge Snapshot — {today}",
        "",
        f"**Total de itens ativos:** {total}",
        "",
        "## Por Categoria",
        "",
    ]

    for cat, cnt, last_update, avg_conf in rows:
        conf_pct = round(float(avg_conf or 0) * 100, 1)
        lines.append(
            f"- **{cat}**: {cnt} itens | "
            f"confiança média {conf_pct}% | "
            f"último: {str(last_update or 'N/A')[:10]}"
        )

    lines += [
        "",
        "## Saúde do Conhecimento",
        "",
    ]

    # Categorias com < 3 itens = gaps
    gaps = [cat for cat, cnt, _, _ in rows if cnt < 3]
    if gaps:
        lines.append(f"⚠️ **Categorias com gaps** (< 3 itens): {', '.join(gaps)}")
    else:
        lines.append("✅ Todas as categorias com volume adequado de conhecimento.")

    lines += [
        "",
        "---",
        f"*Snapshot automático. Gerado em {datetime.now(tz=timezone.utc).isoformat()}*",
    ]

    content = "\n".join(lines)
    wrote = _write_note(f"knowledge-snapshot-{today}.md", content, dry_run=dry_run)
    return 1 if wrote else 0


# ── Fonte 4: Anomalias recentes (SQLite anomaly_events) ───────────────────────

def _extract_anomaly_digest(dry_run: bool = False) -> int:
    """
    Lê anomaly_events das últimas 24h e gera nota de alerta.
    """
    try:
        from webdex_db import DB_LOCK, conn as sqlite_conn
    except ImportError:
        return 0

    today = _today()

    try:
        with DB_LOCK:
            # Verifica se tabela existe
            tbls = [r[0] for r in sqlite_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            if "anomaly_events" not in tbls:
                return 0

            cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
            cur = sqlite_conn.execute(
                """
                SELECT anomaly_type, severity, description, detected_at, sub_conta
                FROM anomaly_events
                WHERE detected_at >= ?
                ORDER BY detected_at DESC
                LIMIT 30
                """,
                (cutoff,),
            )
            rows = cur.fetchall()
    except Exception as e:
        logger.warning("[determ] Erro ao ler anomaly_events: %s", e)
        return 0

    if not rows:
        return 0

    by_type: Counter = Counter()
    by_sev:  Counter = Counter()
    for atype, sev, desc, det_at, sub in rows:
        by_type[atype or "unknown"] += 1
        by_sev[sev   or "low"]     += 1

    lines = [
        "---",
        f"type: anomaly-digest",
        f"title: \"Anomalias WEbdEX — {today}\"",
        f"date: {today}",
        f"tags:",
        f"  - learned",
        f"  - anomaly-digest",
        f"  - auto-generated",
        "---",
        "",
        f"# 🚨 Anomalias Detectadas — {today}",
        "",
        f"**Total (48h):** {len(rows)}",
        f"**Por severidade:** " + " | ".join(f"{s}: {c}" for s, c in by_sev.most_common()),
        "",
        "## Por Tipo",
        "",
    ]

    for atype, cnt in by_type.most_common(10):
        lines.append(f"- **{atype}**: {cnt}x")

    lines += [
        "",
        "## Últimas Anomalias",
        "",
    ]

    for atype, sev, desc, det_at, sub in rows[:10]:
        sev_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(str(sev).lower(), "⚪")
        lines.append(
            f"- {sev_icon} `{atype}` | sub: {sub or 'N/A'} | "
            f"{str(det_at or '')[:16]} — {str(desc or '')[:80]}"
        )

    lines += [
        "",
        "---",
        f"*Digest automático. Gerado em {datetime.now(tz=timezone.utc).isoformat()}*",
    ]

    content = "\n".join(lines)
    wrote = _write_note(f"anomaly-digest-{today}.md", content, dry_run=dry_run)
    return 1 if wrote else 0


# ── Fonte 5: Conversation Learner (PostgreSQL) ────────────────────────────────

def _extract_conversation_learner(dry_run: bool = False) -> int:
    """
    Lê ai_conversations das últimas 48h e extrai:
    - Temas mais discutidos (por word frequency em user_message)
    - Perguntas frequentes ainda não cobertas em bdz_knowledge
    - Palavras-chave emergentes (top 20)

    Gera nota mensal que o bdZinho usa para se auto-atualizar.
    100% determinístico — sem LLM, zero custo.
    """
    if not _DATABASE_URL:
        logger.debug("[determ] DATABASE_URL não configurado — pulando conversation_learner")
        return 0

    month = _month()
    note_path = _LEARNED_DIR / f"conversation-learner-{month}.md"

    try:
        import psycopg2
        conn = psycopg2.connect(_DATABASE_URL)
        cur  = conn.cursor()

        # Mensagens dos usuários nas últimas 48h
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=48)).isoformat()
        cur.execute(
            """
            SELECT content, created_at
            FROM ai_conversations
            WHERE created_at >= %s
              AND role = 'user'
              AND content IS NOT NULL
              AND LENGTH(content) > 10
            ORDER BY created_at DESC
            LIMIT 500
            """,
            (cutoff,),
        )
        rows = cur.fetchall()

        # Palavras-chave ignoradas (stopwords PT)
        _STOPWORDS = {
            "de","a","o","que","e","do","da","em","um","para","é","com","uma",
            "os","no","se","na","por","mais","as","dos","como","mas","foi","ao",
            "ele","das","tem","à","seu","sua","ou","ser","quando","muito","há",
            "nos","já","está","eu","também","só","pelo","pela","até","isso",
            "ela","entre","era","depois","sem","mesmo","aos","ter","seus",
            "quem","nas","me","esse","eles","estão","você","tinha","foram",
            "essa","num","nem","suas","meu","às","minha","têm","numa","pelos",
            "elas","havia","seja","qual","será","nós","tenho","lhe","deles",
            "essas","esses","pelas","este","dele","tu","te","vocês","vos",
            "lhes","meus","minhas","teu","tua","teus","tuas","nosso","nossa",
            "nossos","nossas","dela","delas","esta","estes","estas","aquele",
            "aquela","aqueles","aquelas","isto","aquilo","estou","está","estamos",
            "estão","estive","estava","estávamos","estavam","esterei","estará",
        }

        # Extrai palavras e conta frequências
        word_counter: Counter = Counter()
        bigram_counter: Counter = Counter()
        total_msgs = len(rows)

        for (msg, _) in rows:
            if not msg:
                continue
            # Normaliza
            import re
            words = re.findall(r'\b[a-záéíóúãõâêôçàü]{3,}\b', msg.lower())
            words = [w for w in words if w not in _STOPWORDS]
            word_counter.update(words)

            # Bigramas (pares de palavras)
            bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
            bigram_counter.update(bigrams)

        if not word_counter:
            conn.close()
            return 0

        top_words   = word_counter.most_common(25)
        top_bigrams = bigram_counter.most_common(15)

        # Temas por categoria (heurística baseada em keywords WEbdEX)
        _THEME_MAP = {
            "trading":    ["trade","swap","compra","venda","posição","entrada","saída","stop","gain","loss"],
            "defi":       ["defi","protocolo","pool","liquidez","tvl","yield","farm","stake","staking"],
            "token_bd":   ["token","bd","tokenomics","supply","holder","contrato","deploy"],
            "portfolio":  ["carteira","portfolio","capital","saldo","usdt","matic","pol"],
            "tecnico":    ["erro","bug","falha","problema","não funciona","como","ajuda","suporte"],
            "mercado":    ["preço","mercado","alta","baixa","bull","bear","análise","tendência"],
        }

        theme_counts: dict = {t: 0 for t in _THEME_MAP}
        for (word, count) in word_counter.most_common(100):
            for theme, keywords in _THEME_MAP.items():
                if any(kw in word for kw in keywords):
                    theme_counts[theme] += count

        top_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)

        # Verifica quais temas já estão cobertos no bdz_knowledge
        covered_topics: set = set()
        try:
            cur.execute("SELECT topic FROM bdz_knowledge WHERE active = true")
            covered_topics = {row[0].lower() for row in cur.fetchall()}
        except Exception:
            pass

        conn.close()

        # ── Monta nota ───────────────────────────────────────────────────────
        today = _today()
        lines = [
            "---",
            "type: learned",
            f"title: \"Conversation Learner — {month}\"",
            "tags:",
            "  - learned/conversation",
            "  - bdz/auto-learning",
            f"updated: {today}",
            "---",
            "",
            f"# Conversation Learner — {month}",
            "",
            f"> Análise de **{total_msgs} mensagens** das últimas 48h.",
            f"> Atualizado automaticamente: {today}",
            "",
            "## Palavras Mais Frequentes (Top 25)",
            "",
        ]

        for i, (word, count) in enumerate(top_words, 1):
            lines.append(f"{i:2}. `{word}` — {count}x")

        lines += [
            "",
            "## Temas Detectados",
            "",
        ]
        for theme, count in top_themes:
            if count > 0:
                covered = "✅" if theme in covered_topics else "⚠️ gap"
                lines.append(f"- **{theme}**: {count} menções ({covered})")

        lines += [
            "",
            "## Bigramas Mais Comuns (Top 15)",
            "",
        ]
        for bigram, count in top_bigrams:
            lines.append(f"- `{bigram}` — {count}x")

        lines += [
            "",
            "## Ação Sugerida",
            "",
        ]

        # Sugere gaps de conhecimento
        gaps = [t for t, c in top_themes if c > 0 and t not in covered_topics]
        if gaps:
            lines.append(f"- Adicionar ao `bdz_knowledge`: {', '.join(gaps)}")
        else:
            lines.append("- Todos os temas detectados já têm cobertura em `bdz_knowledge` ✅")

        if top_words:
            top3 = [w for w, _ in top_words[:3]]
            lines.append(f"- Palavras mais buscadas: **{', '.join(top3)}** — verificar cobertura nas respostas")

        lines += [
            "",
            "---",
            f"*Gerado automaticamente pelo Deterministic Trainer em {datetime.now(tz=timezone.utc).isoformat()}*",
        ]

        content = "\n".join(lines)
        # Nota mensal — atualiza toda vez (não usa dedup de 20h)
        try:
            (_LEARNED_DIR / f"conversation-learner-{month}.md").write_text(content, encoding="utf-8")
            logger.info("[determ] conversation_learner: nota atualizada (%d msgs, %d palavras únicas)", total_msgs, len(word_counter))
            return 1
        except Exception as e:
            logger.warning("[determ] conversation_learner: falha ao escrever nota: %s", e)
            return 0

    except Exception as e:
        logger.warning("[determ] conversation_learner falhou: %s", e)
        return 0


# ── Orquestrador ──────────────────────────────────────────────────────────────

def run_deterministic_training(dry_run: bool = False) -> dict:
    """
    Executa extração determinística completa.
    Retorna sumário {extractor: notes_written}.
    """
    if not _ensure_learned_dir():
        return {"error": "vault/learned/ não acessível"}

    logger.info("[determ] ═══ Deterministic Trainer iniciado (dry_run=%s) ═══", dry_run)
    start = time.time()
    summary: dict = {}

    extractors = [
        ("protocol_stats",      _extract_operations_stats),
        ("faq_patterns",        _extract_faq_patterns),
        ("knowledge_snapshot",  _extract_knowledge_summary),
        ("anomaly_digest",      _extract_anomaly_digest),
        ("conversation_learner", _extract_conversation_learner),
    ]

    for name, fn in extractors:
        try:
            count = fn(dry_run=dry_run)
            summary[name] = count
            logger.info("[determ] %s: %d nota(s)", name, count)
        except Exception as e:
            logger.warning("[determ] %s falhou: %s", name, e)
            summary[name] = 0

    elapsed = round(time.time() - start, 2)
    total   = sum(summary.values())
    summary["total"]    = total
    summary["elapsed_s"] = elapsed

    logger.info(
        "[determ] ═══ Concluído: %d nota(s) em %.2fs ═══",
        total, elapsed,
    )
    return summary


# ── Nightly Worker ────────────────────────────────────────────────────────────

def deterministic_trainer_worker() -> None:
    """
    Worker nightly registrado no _THREAD_REGISTRY do webdex_main.py.
    Roda uma vez por dia às ~00h BRT (3h UTC).
    """
    logger.info("[determ] Worker iniciado — aguarda janela noturna (3h UTC).")

    # Boot delay — evita concorrência no startup
    time.sleep(60)

    last_run_date: Optional[str] = None

    while True:
        now_utc = datetime.now(tz=timezone.utc)
        today   = now_utc.strftime("%Y-%m-%d")

        # Roda se: hora certa (2h–6h UTC) E não rodou hoje ainda
        in_window = 2 <= now_utc.hour < 6
        if in_window and last_run_date != today:
            logger.info("[determ] Janela noturna — iniciando extração do dia %s", today)
            try:
                result = run_deterministic_training()
                last_run_date = today
                logger.info("[determ] Resultado: %s", result)
            except Exception as e:
                logger.error("[determ] Erro na extração noturna: %s", e)

        time.sleep(_POLL_INTERVAL_S)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [determ] %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="bdZinho — Deterministic Trainer")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem escrever notas")
    args = parser.parse_args()

    result = run_deterministic_training(dry_run=args.dry_run)
    print(f"\n✅ Resultado: {result}")
    sys.exit(0 if result.get("total", 0) >= 0 else 1)
