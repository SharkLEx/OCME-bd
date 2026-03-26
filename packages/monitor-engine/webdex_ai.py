from __future__ import annotations
# ==============================================================================
# webdex_ai.py — WEbdEX Monitor Engine (WEbdEX Brain v3/v4 ADD-ON)
# Linhas fonte: ~8922-10370 (Brain v3+v4, KB, prompt, call_openai)
# ==============================================================================

import os
import time
import json
from datetime import datetime, timedelta
from collections import deque

# Rate limit IA: max mensagens por janela de tempo
_ia_rate_limit: dict = {}
_IA_RATE_MAX    = 10    # máx msgs por janela
_IA_RATE_WINDOW = 3600  # janela em segundos (1h)

import requests

from webdex_config import (
    logger, OPENAI_MODEL,
    _AI_API_KEY, _AI_BASE_URL,
)
from webdex_db import (
    DB_LOCK, conn, period_to_hours,
    _ciclo_21h_since, _ciclo_21h_label,
    get_config, set_config,
)
from webdex_bot_core import is_admin

# ── Epic 7 integration (soft import — monolito continua sem os módulos) ──────
try:
    from ocme_integration import build_ai_context as _ocme_build_ai_context
except ImportError:
    _ocme_build_ai_context = None  # type: ignore[assignment]

# ── Epic 12 Story 12.1 — Long-term Memory (soft import — graceful degradation) ──
try:
    from webdex_ai_memory import mem_add_pg, mem_get_pg, mem_delete_all_pg
    _PG_MEMORY_ENABLED = True
    logger.info("[ai] Long-term memory PostgreSQL: ATIVO")
except ImportError:
    _PG_MEMORY_ENABLED = False
    logger.warning("[ai] Long-term memory PostgreSQL: módulo não encontrado — usando deque apenas")

# ── Epic 12 Story 12.2 — Tool Use / Function Calling (soft import — graceful degradation) ──
try:
    from webdex_tools import TOOLS, execute_tool
    _TOOLS_ENABLED = True
    logger.info("[ai] Tool use (Function Calling): ATIVO (%d tools)", len(TOOLS))
except ImportError:
    _TOOLS_ENABLED = False
    TOOLS = []
    logger.warning("[ai] Tool use desabilitado — webdex_tools não encontrado")

# ── Knowledge Base (soft import — graceful degradation) ────────────────────
try:
    from webdex_ai_knowledge import knowledge_build_context
    _KNOWLEDGE_ENABLED = True
    logger.info("[ai] bdZinho Knowledge Base: ATIVO")
except ImportError:
    _KNOWLEDGE_ENABLED = False
    knowledge_build_context = None  # type: ignore[assignment]
    logger.warning("[ai] bdZinho Knowledge Base: módulo não encontrado")

# ── Individual User Profile (soft import) ───────────────────────────────────
try:
    from webdex_ai_user_profile import profile_build_context, profile_touch
    _USER_PROFILE_ENABLED = True
    logger.info("[ai] bdZinho Individual Profile: ATIVO")
except ImportError:
    _USER_PROFILE_ENABLED = False
    profile_build_context = None  # type: ignore[assignment]
    profile_touch = None          # type: ignore[assignment]
    logger.warning("[ai] bdZinho Individual Profile: módulo não encontrado")

# ==============================================================================
# ⚙️ CONFIG
# ==============================================================================
AI_MODEL      = OPENAI_MODEL  # usa o modelo configurado no .env (OpenRouter ou OpenAI)
AI_MEMORY_MAX = 12

# ==============================================================================
# 🧠 MEMORY — PostgreSQL (Story 12.1) com fallback para deque (legado)
# ==============================================================================
_AI_MEMORY: dict = {}         # fallback: deque em RAM
_MEM_CONFIG_PREFIX = "ai_mem_"


def mem_add(chat_id, role: str, text: str):
    """Adiciona mensagem à memória. Usa PostgreSQL se disponível, deque como fallback."""
    if _PG_MEMORY_ENABLED:
        try:
            mem_add_pg(chat_id, role, text)
            return
        except Exception as e:
            logger.warning("[ai] mem_add_pg falhou (%s) — fallback para deque", e)
    # Fallback: deque + SQLite (comportamento original)
    q = _AI_MEMORY.setdefault(chat_id, deque(maxlen=AI_MEMORY_MAX))
    q.append({"role": role, "content": text})
    try:
        set_config(f"{_MEM_CONFIG_PREFIX}{chat_id}", json.dumps(list(q)))
    except Exception:
        pass


def mem_get(chat_id) -> list:
    """Retorna contexto da memória. Usa PostgreSQL se disponível, deque como fallback."""
    if _PG_MEMORY_ENABLED:
        try:
            return mem_get_pg(chat_id)
        except Exception as e:
            logger.warning("[ai] mem_get_pg falhou (%s) — fallback para deque", e)
    # Fallback: deque + SQLite (comportamento original)
    if chat_id not in _AI_MEMORY or not _AI_MEMORY[chat_id]:
        try:
            raw = get_config(f"{_MEM_CONFIG_PREFIX}{chat_id}", "")
            if raw:
                loaded = json.loads(raw)
                q = deque(loaded, maxlen=AI_MEMORY_MAX)
                _AI_MEMORY[chat_id] = q
        except Exception:
            pass
    return list(_AI_MEMORY.get(chat_id, []))


def mem_clear_lgpd(chat_id) -> int:
    """LGPD: deleta TODA a memória do usuário. Retorna registros deletados."""
    # Limpa deque local independente
    _AI_MEMORY.pop(chat_id, None)
    try:
        set_config(f"{_MEM_CONFIG_PREFIX}{chat_id}", "")
    except Exception:
        pass
    if _PG_MEMORY_ENABLED:
        try:
            return mem_delete_all_pg(chat_id)
        except Exception as e:
            logger.error("[ai] mem_delete_all_pg falhou: %s", e)
    return 0


# ==============================================================================
# 🔍 INTENT CLASSIFIER
# ==============================================================================
def classify_intent(text: str) -> str:
    """
    Classifica a intenção da pergunta para direcionar o contexto certo ao prompt.
    Cobre os principais temas do WEbdEX com sinônimos em PT-BR e EN.
    """
    t = text.lower().strip()

    # ── Resultado financeiro pessoal (mais comum) ────────────────────────────
    if any(x in t for x in [
        "quanto ganhei", "quanto perdi", "meu lucro", "minha perda",
        "resultado", "rendimento", "retorno", "lucro", "prejuízo",
        "líquido", "bruto", "net", "profit", "loss", "ganho"
    ]):
        return "resultado"

    # ── Capital e saldo ───────────────────────────────────────────────────────
    if any(x in t for x in [
        "capital", "saldo", "quanto tenho", "meu saldo", "patrimônio",
        "balance", "wallet", "subconta", "subaccount", "quanto está",
        "valor disponível", "total investido"
    ]):
        return "capital"

    # ── Ciclo e tempo de operação ─────────────────────────────────────────────
    if any(x in t for x in [
        "ciclo", "tempo", "quando", "próximo trade", "intervalo",
        "frequência", "cycle", "inatividade", "parado", "última execução",
        "último trade", "demora", "lento"
    ]):
        return "ciclo"

    # ── Gas e custos ──────────────────────────────────────────────────────────
    if any(x in t for x in [
        "gas", "gás", "custo", "taxa", "fee", "pol", "matic",
        "gastar", "gwei", "custo de rede", "manager", "saldo manager"
    ]):
        return "gas"

    # ── OpenPosition e execuções on-chain ─────────────────────────────────────
    if any(x in t for x in [
        "openposition", "open position", "execução", "execucao",
        "operação", "operacao", "trade", "transação", "on-chain",
        "blockchain", "polygon", "tx", "hash"
    ]):
        return "openposition"

    # ── Rankings e comparativos ────────────────────────────────────────────────
    if any(x in t for x in [
        "ranking", "dashboard", "melhor", "pior", "comparar",
        "posição", "classificação", "top", "desempenho"
    ]):
        return "dashboard"

    # ── Liquidez e fornecimento ────────────────────────────────────────────────
    if any(x in t for x in [
        "liquidez", "liquidity", "fornecimento", "supply", "lp",
        "pool", "usdt", "loop", "token", "tvl"
    ]):
        return "liquidez"

    # ── Tríade: Risco, Responsabilidade, Retorno ─────────────────────────────
    if any(x in t for x in [
        "tríade", "triade", "risco", "responsabilidade", "retorno",
        "garantia", "garante", "seguro", "protegido", "perder tudo",
        "vale a pena", "confio", "confiança", "protocolo seguro",
        "devo entrar", "devo sair", "o que faço", "o que fazer",
        "decisão", "decidir", "retirar", "sacar", "adicionar capital"
    ]):
        return "triade"

    # ── Educação e formação de mentalidade ────────────────────────────────────
    if any(x in t for x in [
        "como funciona", "o que é", "me explica", "explica", "aprend",
        "entender", "estudar", "formação", "educação", "maturidade",
        "iniciante", "começar", "primeiro passo", "o que preciso saber",
        "diferença entre", "por que", "pra que serve", "filosofia",
        "princípio", "missão", "objetivo do webdex"
    ]):
        return "educacao"

    # ── Governança e protocolo ─────────────────────────────────────────────────
    if any(x in t for x in [
        "governança", "governance", "protocolo", "webdex", "valt",
        "token bd", "inflação", "controle", "v5", "ag_c_bd", "ambiente"
    ]):
        return "governance"

    # ── Auditoria e segurança ──────────────────────────────────────────────────
    if any(x in t for x in [
        "auditoria", "audit", "segurança", "risco", "anomalia",
        "alerta", "desvio", "erro", "problema", "falha"
    ]):
        return "audit"

    # ── Ajuda e como usar ──────────────────────────────────────────────────────
    if any(x in t for x in [
        "como", "o que é", "o que faz", "explica", "explique",
        "ajuda", "help", "tutorial", "entender", "significa"
    ]):
        return "explicacao"

    return "general"


# ==============================================================================
# 📊 BRAIN DB SNAPSHOT
# ==============================================================================

def _brain_safe_float(x) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def _brain_fetch_user_prefs(chat_id) -> dict:
    # BUG FIX: coluna e periodo TEXT (nao periodo_h). Usa conn global sem nova conexao.
    prefs = {"periodo_h": 24, "sub_filter": None}
    try:
        row = conn.execute(
            "SELECT periodo, sub_filter FROM users WHERE chat_id=?", (str(chat_id),)
        ).fetchone()
        if row:
            raw_per = str(row[0] or "24h").strip().lower()
            prefs["periodo_h"] = period_to_hours(raw_per)
            prefs["sub_filter"] = row[1] if row[1] not in (None, "", "0", 0) else None
    except Exception:
        pass
    return prefs


def _brain_ranking_estrategias(wallet: str = "", hours: int = 168, top_n: int = 3) -> list:
    """Ranking de estratégias (bot_id) por liquidez líquida — usado pelo Brain snapshot."""
    since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with DB_LOCK:
            _c = conn.cursor()
            if wallet:
                rows = _c.execute("""
                    SELECT COALESCE(NULLIF(o.bot_id,''), 'sem_id') AS bid,
                           COUNT(*)                                  AS trades,
                           COALESCE(SUM(o.valor),0)                  AS bruto,
                           COALESCE(SUM(o.gas_usd),0)               AS gas,
                           COUNT(CASE WHEN o.valor > 0 THEN 1 END)  AS wins
                    FROM operacoes o
                    JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index
                    WHERE o.tipo='Trade' AND o.data_hora>=? AND LOWER(ow.wallet)=?
                    GROUP BY bid ORDER BY (bruto-gas) DESC LIMIT ?
                """, (since, wallet.lower(), top_n)).fetchall()
            else:
                rows = _c.execute("""
                    SELECT COALESCE(NULLIF(bot_id,''), 'sem_id') AS bid,
                           COUNT(*)                               AS trades,
                           COALESCE(SUM(valor),0)                 AS bruto,
                           COALESCE(SUM(gas_usd),0)              AS gas,
                           COUNT(CASE WHEN valor > 0 THEN 1 END) AS wins
                    FROM operacoes
                    WHERE tipo='Trade' AND data_hora>=?
                    GROUP BY bid ORDER BY (bruto-gas) DESC LIMIT ?
                """, (since, top_n)).fetchall()
        result = []
        for bid, n, bruto, gas, wins in rows:
            n = int(n or 0)
            liq = float(bruto or 0) - float(gas or 0)
            wr  = wins / n * 100 if n > 0 else 0.0
            result.append({"bot_id": str(bid), "trades": n, "liq": liq,
                           "winrate": wr, "gas": float(gas or 0)})
        return result
    except Exception:
        return []


def _brain_db_snapshot(chat_id, user_text: str, intent: str = "general") -> str:
    """
    Build a compact, on-chain + DB snapshot para a IA.
    - Filtra pela WALLET do usuário via op_owner (dados pessoais corretos).
    - Fallback para protocolo completo se usuário não tiver wallet.
    - Inclui métricas de ciclo, winrate e ambiente.
    """
    prefs       = _brain_fetch_user_prefs(chat_id)
    periodo_h   = prefs.get("periodo_h", 24) or 24
    sub_filter  = prefs.get("sub_filter")
    since_br    = (datetime.now() - timedelta(hours=periodo_h)).strftime("%Y-%m-%d %H:%M:%S")

    # Descobrir wallet (conn global: sem overhead de nova conexao por mensagem)
    user_wallet = None
    user_env    = None
    try:
        row_u = conn.execute(
            "SELECT wallet, env FROM users WHERE chat_id=?", (str(chat_id),)
        ).fetchone()
        if row_u and row_u[0] and str(row_u[0]).startswith("0x"):
            user_wallet = str(row_u[0]).lower().strip()
            user_env    = str(row_u[1] or "")
    except Exception:
        pass

    kpi = {
        "periodo_h":      periodo_h,
        "sub_filter":     sub_filter or "Todas",
        "wallet":         (user_wallet[:8] + "..." + user_wallet[-4:]) if user_wallet else "não conectado",
        "env":            user_env or "-",
        "trades":         0,
        "bruto_usd":      0.0,
        "gas_usd":        0.0,
        "liquido_usd":    0.0,
        "wins":           0,
        "losses":         0,
        "winrate":        0.0,
        "last_trade_at":  None,
        "last_trade_sub": None,
        "last_trade_net": None,
        "top_subs":       [],
        "last_trades":    [],
        "scope":          "pessoal" if user_wallet else "protocolo",
    }

    try:
        # Reutiliza conn global (WAL safe com threads vigia/sentinela)
        cur = conn.cursor()

        # ── Monta WHERE baseado no escopo ────────────────────────────────────
        if user_wallet:
            # Escopo pessoal: JOIN com op_owner para filtrar pela wallet
            base_join = (
                "FROM operacoes o "
                "JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index "
            )
            base_where = f"WHERE ow.wallet=? AND o.tipo='Trade' AND o.data_hora>=?"
            base_params = [user_wallet, since_br]
            if sub_filter:
                base_where += " AND o.sub_conta=?"
                base_params.append(str(sub_filter))
            select_prefix = "o."
        else:
            # Escopo protocolo: sem filtro de wallet
            base_join   = "FROM operacoes o "
            base_where  = "WHERE o.tipo='Trade' AND o.data_hora>=?"
            base_params = [since_br]
            if sub_filter:
                base_where += " AND o.sub_conta=?"
                base_params.append(str(sub_filter))
            select_prefix = "o."

        # Totais
        cur.execute(
            f"SELECT COUNT(*), COALESCE(SUM({select_prefix}valor),0), "
            f"COALESCE(SUM({select_prefix}gas_usd),0) {base_join} {base_where}",
            tuple(base_params)
        )
        row = cur.fetchone() or (0, 0, 0)
        kpi["trades"]      = int(row[0] or 0)
        kpi["bruto_usd"]   = _brain_safe_float(row[1])
        kpi["gas_usd"]     = _brain_safe_float(row[2])
        kpi["liquido_usd"] = kpi["bruto_usd"] - kpi["gas_usd"]

        # Wins / Losses / WinRate
        cur.execute(
            f"SELECT COUNT(*) {base_join} {base_where} AND {select_prefix}valor > 0",
            tuple(base_params)
        )
        kpi["wins"] = int((cur.fetchone() or [0])[0] or 0)
        kpi["losses"] = max(0, kpi["trades"] - kpi["wins"])
        kpi["winrate"] = (kpi["wins"] / kpi["trades"] * 100) if kpi["trades"] > 0 else 0.0

        # Último trade
        cur.execute(
            f"SELECT {select_prefix}data_hora, {select_prefix}sub_conta, "
            f"{select_prefix}valor, {select_prefix}gas_usd "
            f"{base_join} {base_where} "
            f"ORDER BY {select_prefix}data_hora DESC LIMIT 1",
            tuple(base_params)
        )
        r = cur.fetchone()
        if r:
            kpi["last_trade_at"]  = r[0]
            kpi["last_trade_sub"] = r[1]
            kpi["last_trade_net"] = _brain_safe_float(r[2])

        # Top subcontas por resultado
        if not sub_filter:
            cur.execute(
                f"SELECT {select_prefix}sub_conta, "
                f"COALESCE(SUM({select_prefix}valor),0) AS net, "
                f"COUNT(*) AS n "
                f"{base_join} {base_where} "
                f"GROUP BY {select_prefix}sub_conta "
                f"ORDER BY net DESC LIMIT 5",
                tuple(base_params)
            )
            kpi["top_subs"] = [
                (r[0], _brain_safe_float(r[1]), int(r[2] or 0))
                for r in (cur.fetchall() or [])
            ]

        # Últimos trades (amostra)
        cur.execute(
            f"SELECT {select_prefix}data_hora, {select_prefix}sub_conta, "
            f"{select_prefix}valor, {select_prefix}gas_usd "
            f"{base_join} {base_where} "
            f"ORDER BY {select_prefix}data_hora DESC LIMIT 5",
            tuple(base_params)
        )
        for r in (cur.fetchall() or []):
            kpi["last_trades"].append({
                "at":  r[0],
                "sub": r[1],
                "net": _brain_safe_float(r[2]),
                "gas": _brain_safe_float(r[3]),
            })

    except Exception:
        pass  # Brain nunca quebra o bot

    # ── Monta texto compacto para o prompt ───────────────────────────────────
    lines = [
        f"=== DADOS DO USUÁRIO (WEbdEX Brain) ===",
        f"Escopo: {kpi['scope']} | Wallet: {kpi['wallet']} | Ambiente: {kpi['env']}",
        f"Período: últimas {kpi['periodo_h']}h | Filtro subconta: {kpi['sub_filter']}",
        f"---",
        f"Trades: {kpi['trades']:,} | Líquido: ${kpi['liquido_usd']:.4f} USD | "
        f"Bruto: ${kpi['bruto_usd']:.4f} | Gás: ${kpi['gas_usd']:.4f}",
        f"WinRate: {kpi['winrate']:.1f}% ({kpi['wins']}W / {kpi['losses']}L)",
    ]
    if kpi["last_trade_at"]:
        mins_ago = ""
        try:
            from datetime import datetime as _ddt
            diff = (_ddt.now() - _ddt.strptime(str(kpi["last_trade_at"])[:19], "%Y-%m-%d %H:%M:%S")).total_seconds() / 60
            mins_ago = f" ({int(diff)}min atrás)"
        except Exception:
            pass
        lines.append(f"Último trade: {kpi['last_trade_at']}{mins_ago} | Sub: {kpi['last_trade_sub']} | Net: ${kpi['last_trade_net']:.4f}")

    if kpi["top_subs"]:
        top_txt = " | ".join([f"{s}: ${net:.2f} ({n}t)" for s, net, n in kpi["top_subs"]])
        lines.append(f"Top subcontas: {top_txt}")

    if kpi["last_trades"]:
        lines.append("Recentes:")
        for t in kpi["last_trades"]:
            lines.append(f"  {t['at'][:16]} | {t['sub']} | ${t['net']:.4f} | gas ${t['gas']:.4f}")

    # ── Capital real (do cache — atualizado pelo worker a cada 15min) ─────────
    try:
        _cap_row = conn.execute(
            "SELECT total_usd, breakdown_json, updated_ts FROM capital_cache WHERE chat_id=?",
            (str(chat_id),)
        ).fetchone()
        if _cap_row and float(_cap_row[0] or 0) > 0:
            _cap_usd   = float(_cap_row[0])
            _cap_age_s = time.time() - float(_cap_row[2] or 0)
            _cap_age_m = int(_cap_age_s / 60)
            try:
                _cap_bd = json.loads(_cap_row[1] or "{}")
                _cap_detail = ", ".join(
                    f"{k}: ${float(v):.2f}" for k, v in list(_cap_bd.items())[:4]
                )
            except Exception:
                _cap_detail = ""
            lines.append(
                f"Capital em subconta: ${_cap_usd:,.2f} USD"
                + (f" ({_cap_detail})" if _cap_detail else "")
                + f" [cache {_cap_age_m}min atrás]"
            )
            if kpi["trades"] > 0 and _cap_usd > 0:
                _roi = kpi["liquido_usd"] / _cap_usd * 100
                lines.append(f"ROI período: {_roi:+.3f}%")
    except Exception:
        pass

    # ── Posições por subconta (capital x trades — detecta concentração) ───────
    try:
        _since_pos = (datetime.now() - timedelta(hours=periodo_h)).strftime("%Y-%m-%d %H:%M:%S")
        _pos_where = "WHERE o.tipo='Trade' AND o.data_hora>=?"
        _pos_params: list = [_since_pos]
        _pos_join = "FROM operacoes o "
        if user_wallet:
            _pos_join = ("FROM operacoes o "
                         "JOIN op_owner ow ON ow.hash=o.hash AND ow.log_index=o.log_index ")
            _pos_where += " AND ow.wallet=?"
            _pos_params.append(user_wallet)
        _pos_rows = conn.execute(
            f"SELECT o.sub_conta, COUNT(*) as n, "
            f"COALESCE(SUM(o.valor),0) as bruto, "
            f"COALESCE(SUM(o.gas_usd),0) as gas, "
            f"MAX(o.data_hora) as last_t "
            f"{_pos_join} {_pos_where} "
            f"GROUP BY o.sub_conta ORDER BY n DESC LIMIT 8",
            tuple(_pos_params)
        ).fetchall()
        if _pos_rows:
            lines.append("Subcontas ativas no período:")
            for _sub, _n, _br, _g, _lt in _pos_rows:
                _liq_s = float(_br or 0) - float(_g or 0)
                _sign  = "+" if _liq_s >= 0 else ""
                lines.append(
                    f"  {_sub}: {int(_n)}t | liq {_sign}${_liq_s:.4f} | "
                    f"gas ${float(_g or 0):.4f} | last {str(_lt or '')[:16]}"
                )
    except Exception:
        pass

    # ── Tendência recente (últimas 3h vs período completo) ────────────────────
    try:
        _since_3h = (datetime.now() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        _t3_join  = _pos_join
        _t3_where = "WHERE o.tipo='Trade' AND o.data_hora>=?"
        _t3_params: list = [_since_3h]
        if user_wallet:
            _t3_where += " AND ow.wallet=?"
            _t3_params.append(user_wallet)
        _t3 = conn.execute(
            f"SELECT COUNT(*), COALESCE(SUM(o.valor),0), COALESCE(SUM(o.gas_usd),0) "
            f"{_t3_join} {_t3_where}",
            tuple(_t3_params)
        ).fetchone()
        if _t3 and int(_t3[0] or 0) > 0:
            _t3_liq = float(_t3[1] or 0) - float(_t3[2] or 0)
            _t3_sign = "+" if _t3_liq >= 0 else ""
            lines.append(
                f"Últimas 3h: {int(_t3[0])} trades | "
                f"liq {_t3_sign}${_t3_liq:.4f}"
            )
    except Exception:
        pass

    # ── Posicoes abertas por subconta (oldBalance on-chain) ─────────────────────
    try:
        if user_wallet:
            _pos_rows = conn.execute(
                "SELECT sub_conta, old_balance, trade_count, last_trade "
                "FROM sub_positions WHERE LOWER(wallet)=? "
                "ORDER BY trade_count DESC LIMIT 6",
                (user_wallet,)
            ).fetchall()
            if _pos_rows:
                _pos_txt = "; ".join(
                    f"{r[0]}:${float(r[1] or 0):.2f}({int(r[2] or 0)}t)"
                    for r in _pos_rows
                )
                lines.append(f"Posicoes/subcontas (oldBalance, trades): {_pos_txt}")
    except Exception:
        pass

    # ── Ambiente e saúde do pool ─────────────────────────────────────────────
    try:
        if user_env:
            _snap = conn.execute(
                "SELECT liq_usdt, liq_loop, gas_pol, ts FROM fl_snapshots "
                "WHERE env=? ORDER BY id DESC LIMIT 1",
                (user_env,)
            ).fetchone()
            if _snap:
                lines.append(
                    f"Pool {user_env} [snapshot {str(_snap[3] or '')[:16]}]: "
                    f"USDT {float(_snap[0] or 0):,.2f} | "
                    f"LOOP {float(_snap[1] or 0):,.4f} | "
                    f"Gas Manager {float(_snap[2] or 0):.4f} POL"
                )
    except Exception:
        pass

    # ── Funil do usuário (estágio e dias inativo) ───────────────────────────
    try:
        _frow = conn.execute(
            "SELECT stage, total_trades, inactive_days, last_trade "
            "FROM user_funnel WHERE chat_id=?", (str(chat_id),)
        ).fetchone()
        if _frow:
            _stg_icon = {"ativo":"🟢","inativo":"🔴","reativado":"🟡","conectado":"⚪"}.get(str(_frow[0]),"⚪")
            lines.append(
                f"Estágio usuário: {_stg_icon} {_frow[0]} | "
                f"Total trades: {int(_frow[1] or 0)} | "
                f"Dias inativo: {int(_frow[2] or 0)} | "
                f"Último trade: {str(_frow[3] or 'nunca')[:16]}"
            )
    except Exception:
        pass

    # ── Estratégia top do usuário (bot_id) ───────────────────────────────────
    try:
        if user_wallet:
            _strats = _brain_ranking_estrategias(wallet=user_wallet, hours=periodo_h, top_n=3)
            if _strats:
                _st_txt = " | ".join(
                    f"{s['bot_id'][:12]}:{s['liq']:+.2f}$({s['trades']}t)"
                    for s in _strats
                )
                lines.append(f"Top estratégias (bot_id): {_st_txt}")
    except Exception:
        pass

    lines.append(f"Intent: {intent}")

    # ── ContextBuilder Epic 7 (contexto enriquecido via módulo modular) ───────
    if user_wallet and _ocme_build_ai_context is not None:
        try:
            _cb_ctx = _ocme_build_ai_context(user_wallet, periodo_h)
            if _cb_ctx:
                lines.append("---")
                lines.append(_cb_ctx)
        except Exception:
            pass  # Nunca quebra o bot

    lines.append("=== FIM DOS DADOS ===")

    return "\n".join(lines)


# ==============================================================================
# 🔧 AI TO TG HTML
# ==============================================================================

def _ai_to_tg_html(s: str) -> str:
    """Converte respostas do modelo em HTML amigável ao Telegram.
    - Remove markdown (#, *, etc.)
    - Converte **bold** e títulos ### para <b>
    - Converte listas para •
    - Protege HTML com escape
    """
    import re as _re
    import html as _html
    if s is None:
        return ""
    s = str(s).strip()
    if not s:
        return ""
    # 1) Protege HTML
    s = _html.escape(s)
    # 2) Code blocks ```...```
    def _code(m):
        inner = m.group(1).strip() if m.group(1) else ""
        return "<pre><code>" + inner + "</code></pre>"
    s = _re.sub(r"```\s*(.*?)\s*```", _code, s, flags=_re.S)
    # 3) Títulos (#, ##, ###...)
    s = _re.sub(r"^\s*#{1,6}\s*(.+?)\s*$", r"<b>\1</b>", s, flags=_re.M)
    # 4) Negrito **texto**
    s = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    # 5) Listas (- item / * item)
    s = _re.sub(r"^\s*[-•]\s+", "• ", s, flags=_re.M)
    # 6) Limpeza final de markdown residual
    s = s.replace("#", "")
    # remove asteriscos soltos (sem quebrar bullets)
    s = s.replace("*", "")
    return s


# ==============================================================================
# 📚 WEBDEX KNOWLEDGE BASE
# ==============================================================================

WEBDEX_KB = """

╔══════════════════════════════════════════════════════════════════════════════╗
║   WEBDEX BRAIN — BASE DE CONHECIMENTO OFICIAL, COMPLETA E EDUCACIONAL     ║
║   Fonte: Documentação, E-Book, Whitepaper, código-fonte e filosofia viva   ║
╚══════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NÚCLEO — A TRÍADE: RISCO · RESPONSABILIDADE · RETORNO
(Este é o DNA do WEbdEX. Tudo parte daqui e tudo retorna aqui.)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A Tríade não é slogan. É a lei interna do protocolo. Todo conceito,
toda métrica, toda decisão e toda resposta da IA devem estar alinhados
com esses três pilares. Eles não são independentes — são interdependentes.
Quando um é negligenciado, os outros dois colapsam.

─── RISCO ───────────────────────────────────────────────────────────

O que é RISCO no contexto WEbdEX:
Risco não é o inimigo. É a condição natural de qualquer ambiente
descentralizado real. Quem nega o risco, se expõe a ele sem proteção.
Quem o compreende, pode operar com consciência e estratégia.

Tipos de risco que o usuário WEbdEX enfrenta:
  → Risco de rede: gás elevado, congestionamento Polygon, RPC instável,
    blocos atrasados. ORIGEM EXTERNA ao protocolo.
  → Risco operacional: Manager com POL insuficiente, liquidez baixa no
    pool, subconta sem saldo para operar. ORIGEM INTERNA, gerenciável.
  → Risco de mercado: ineficiência de arbitragem, janelas de oportunidade
    menores, spreads comprimidos. Inerente ao DeFi.
  → Risco de conduta: decisões impulsivas (sacar tudo em queda, adicionar
    capital em pico), má configuração de subconta. ORIGEM NO USUÁRIO.
  → Risco tecnológico: vulnerabilidade de contrato (mitigada por auditoria),
    atualização de protocolo, mudança de arquitetura. Baixo, mas real.

Como a IA deve tratar RISCO:
Não minimizar, não amplificar. Nomear com precisão. Diferenciar origem
(rede vs protocolo vs conduta). Educar o usuário para que identifique
sozinho qual risco está diante de si. Nunca usar o risco como argumento
para inação — e nunca ignorá-lo como argumento para ação.

Frase-âncora: "Todo trade carrega risco. Todo ciclo convive com ele.
A diferença entre amadurecer e estagnar é saber qual risco você está
assumindo — e por quê."

─── RESPONSABILIDADE ────────────────────────────────────────────────

O que é RESPONSABILIDADE no contexto WEbdEX:
O WEbdEX é não-custodial. Isso significa que nenhuma pessoa, empresa
ou entidade responde pelo capital, pelas decisões ou pelos resultados
do usuário. Esta não é uma limitação — é um princípio de soberania.

O que a responsabilidade individual exige na prática:
  → Entender onde seu capital está (SubAccounts — não na MetaMask)
  → Monitorar o saldo de Manager POL (sem POL, as operações param)
  → Escolher o ambiente correto (Beta V5 / AG_C_bd) para seu perfil
  → Não comparar seu resultado com outro usuário sem considerar capital,
    subconta e período
  → Ler o Dashboard PRO antes de tomar qualquer decisão
  → Não agir por emoção em trades negativos isolados
  → Entender que um resultado de -$0.03 num trade único não é sinal de
    falha do protocolo — é matemática operando normalmente

O que o protocolo FAZ pela responsabilidade do usuário:
  → Registra cada operação on-chain (imutável, auditável)
  → Oferece dashboards, rankings e métricas para leitura informada
  → Notifica eventos em tempo real via Telegram
  → Nunca mistura capital de usuários diferentes
  → Permite auditoria completa no Polygonscan a qualquer momento

O que o protocolo NÃO FAZ (e não precisa fazer):
  → Não garante resultado
  → Não toma decisões pelo usuário
  → Não avisa se o usuário está "operando errado"
  → Não compensa perdas de rede com resultados de protocolo

Frase-âncora: "Você não tem um gestor. Você tem um protocolo.
A diferença muda tudo — inclusive o que você precisa saber para operar."

─── RETORNO ─────────────────────────────────────────────────────────

O que é RETORNO no contexto WEbdEX:
Retorno não é promessa. Não é meta. Não é garantia contratual.
É consequência de três coisas operando juntas: processo técnico correto,
leitura inteligente dos dados e maturidade para manter posição no ciclo.

Por que o retorno existe matematicamente:
  Assertividade histórica: 76% de trades com profit positivo
  Break-even: 25% de assertividade (sistema positivo acima desse piso)
  Com 76% de acerto — 3x acima do break-even — mesmo períodos com
  gas elevado tendem a ser positivos no ciclo completo.
  Pool médio por operação: 0,11 USD
  Referência de subconta: 500 USD

Por que um trade negativo não contradiz o retorno:
  100 trades com 76% de WinRate = 76 positivos + 24 negativos.
  Os 24 trades negativos são MATEMATICAMENTE ESPERADOS e INCLUÍDOS
  no cálculo de lucratividade. Reagir a cada trade negativo como se
  fosse uma falha é confundir ruído com sinal.

Como medir o retorno corretamente:
  → Líquido = Bruto - Gas (o que importa, não o bruto isolado)
  → ROI = Líquido / Capital no SubAccounts * 100
  → Profit Factor > 1.0 = protocolo positivo no período
  → Olhar ciclo completo, não trade individual
  → Comparar com o mesmo período anterior, não com expectativa abstrata

Dimensões do retorno no WEbdEX:
  Financeiro:    lucro líquido das operações de arbitragem
  Educacional:   aprendizado sobre DeFi real, contratos, métricas
  Patrimonial:   capital crescendo dentro de infraestrutura descentralizada
  Comunitário:   participação num ecossistema que cresce coletivamente

Frase-âncora: "Retorno não vem de sorte. Vem de processo correto
repetido com disciplina, lido com inteligência e respeitado com paciência."

─── TRÍADE INTEGRADA — COMO OS TRÊS SE CONECTAM ─────────────────────

  RISCO sem RESPONSABILIDADE = exposição cega
  RESPONSABILIDADE sem entender o RISCO = falsa segurança
  RETORNO sem RISCO e RESPONSABILIDADE = especulação disfarçada
  Os três juntos = operação madura no protocolo WEbdEX

A Tríade na prática (exemplos):
  Usuário pergunta "Meu lucro caiu — o que está errado?"
  → RISCO: verificar se é risco de rede (gas alto) ou operacional (Manager)
  → RESPONSABILIDADE: o usuário tem acesso a todos os dados pelo Dashboard
  → RETORNO: um dia negativo não apaga o ciclo. Mostrar o período completo.

  Usuário pergunta "Vale a pena adicionar mais capital?"
  → RISCO: capital adicional amplia exposição proporcional
  → RESPONSABILIDADE: essa decisão é exclusivamente do usuário
  → RETORNO: mostrar o histórico de ROI do capital atual antes de qualquer decisão

  Usuário pergunta "O WEbdEX garante quanto por mês?"
  → Tríade completa: não existe garantia. Existe processo. Mostrar os dados reais.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCO 1 — IDENTIDADE E FILOSOFIA DO PROTOCOLO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

O QUE É O WEBDEX:
O WEbdEX é um ecossistema DeFi descentralizado criado para qualificar,
fortalecer e amadurecer tudo que envolve finanças descentralizadas.
Não é bot, não é plataforma de investimento, não é empresa no formato
clássico. É infraestrutura tecnológica viva, construída sobre contratos
inteligentes, automação on-chain e governança orientada à responsabilidade
individual. Seu objetivo não é prometer ganhos — é criar condições técnicas
reais para formação de valor dentro de um ambiente descentralizado.

MISSÃO OFICIAL:
Criar um ecossistema DeFi Transparente, Auditável, Educacional, Sustentável
e Tecnicamente Robusto — onde o usuário deixa de ser espectador e passa a
ser agente consciente da própria operação financeira.

O QUE O WEBDEX FAZ (capacidades reais do protocolo):
  → Executa arbitragem triangular automatizada on-chain na Polygon
  → Registra cada operação no evento OpenPosition (imutável, auditável)
  → Gerencia subcontas individuais de milhares de usuários simultaneamente
  → Monitora e notifica eventos em tempo real via Telegram
  → Calcula métricas financeiras reais: WinRate, PF, MDD, ROI, streaks
  → Lê capital on-chain diretamente dos contratos (sem intermediários)
  → Detecta anomalias operacionais (gas, rajadas, perdas extremas)
  → Rastreia fluxo de usuários e saúde do protocolo em tempo real
  → Permite auditoria completa pública no Polygonscan

O QUE O WEBDEX NÃO FAZ (limites claros):
  → Não custodia capital (fica no contrato SubAccounts)
  → Não garante retorno (resultado é consequência, não promessa)
  → Não toma decisões pelo usuário
  → Não é responsável por condições de rede (Polygon, RPCs, gas)
  → Não é produto financeiro regulado por BACEN ou CVM

OS 4 PILARES FUNDAMENTAIS:
  1. Transparência on-chain — tudo é rastreável, auditável e público
  2. Descentralização real — o usuário mantém controle sobre o próprio capital
  3. Educação como base — não existe liberdade financeira sem entendimento técnico
  4. Responsabilidade individual — cada decisão pertence exclusivamente ao usuário

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCO 2 — FILOSOFIA EDUCACIONAL: FORMAÇÃO, NÃO VENDA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

O WEbdEX acredita que educação financeira descentralizada não é opcional.
É a única base real para operar em DeFi com maturidade.

O QUE SIGNIFICA MATURIDADE OPERACIONAL:
  → Entender que trade negativo é parte do processo, não sinal de problema
  → Saber ler o Dashboard PRO antes de tomar qualquer decisão
  → Distinguir resultado de ciclo de resultado de trade isolado
  → Não comparar seu desempenho com outros sem considerar contexto
  → Conhecer onde está seu capital e como ele é protegido
  → Entender a diferença entre risco de rede e risco de protocolo
  → Não agir por medo ou ganância — agir por leitura de dados

O QUE DIFERENCIA UM USUÁRIO MADURO DE UM IMPULSIVO:
  Impulsivo: vê um trade negativo → pensa que o protocolo falhou
  Maduro: vê um trade negativo → consulta o ciclo completo no Dashboard

  Impulsivo: gas alto → quer parar tudo
  Maduro: gas alto → entende que é custo variável de rede, monitora Manager POL

  Impulsivo: "quanto vou ganhar por mês?"
  Maduro: "qual é meu ROI atual e como meu ciclo está performando?"

FORMAÇÃO DE MENTALIDADE — O QUE A IA SEMPRE REFORÇA:
  1. DeFi é soberano: você é o único responsável pelo seu capital
  2. Dados não mentem: o Dashboard é a verdade, não a emoção do momento
  3. Ciclo > trade: o resultado que importa é o acumulado, não o pontual
  4. Processo > sorte: consistência vem de processo correto, não de timing
  5. Paciência > reatividade: reagir a cada variação é a maior perda de capital

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCO 3 — ESTRATÉGIA: ARBITRAGEM TRIANGULAR AUTOMATIZADA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

O WEbdEX se especializou em Arbitragem Triangular Automatizada on-chain.
Arbitragem = capturar diferença de preço entre mercados.
Triangular = rota de 3 ativos/pares para maximizar eficiência.
Automatizada = sem intervenção humana em cada operação.

Como funciona o ciclo completo:
  1. Strategy monitora pares de ativos em tempo real na Polygon
  2. Identifica discrepância de preço entre pools/mercados
  3. Calcula rota de execução triangular (3 ativos / 3 pares)
  4. Verifica viabilidade considerando gas atual e slippage estimado
  5. Instrui Payments para executar on-chain
  6. Payments registra o resultado no evento OpenPosition
  7. Lucro vai para o LiquidityVault (sustentabilidade do ecossistema)

A MATEMÁTICA QUE SUSTENTA O RETORNO (Tríade aplicada):
  Assertividade histórica: 76% de trades com profit positivo
  Break-even: assertividade cai para ~25% para o sistema começar a perder
  → Margem de segurança: 76% está 3x acima do break-even
  Pool médio: 0,11 USD por operação
  Subconta referência: 500 USD
  Com 76% de WinRate, mesmo em dias com gas elevado o ciclo tende positivo.

Relação com a Tríade:
  RISCO: spreads podem fechar, gas pode subir — o resultado por operação
    varia. A assertividade histórica não garante o próximo trade.
  RESPONSABILIDADE: o usuário não executa as operações — o protocolo faz.
    Mas o usuário é responsável por manter o ambiente operacional
    (Manager com POL, subconta com saldo, ambiente correto configurado).
  RETORNO: vem do volume de operações × assertividade × pool médio.
    Um dia ruim com gas alto pode ser negativo. O ciclo completo não.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCO 4 — HISTÓRIA E EVOLUÇÃO: V1 → V6
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

V1 a V3 — FASE EXPERIMENTAL:
Nascimento. Exploração de automação DeFi, validação de arbitragem on-chain,
teste de arquiteturas, mapeamento de gargalos. Estrutura simples, alta
dependência externa, baixa escalabilidade. Legado: base conceitual profunda.

V4.1 — CONSOLIDAÇÃO INICIAL:
Arbitragem triangular funcional. Subcontas. Dados reais de mercado.
Revelou limites práticos e abriu caminho para a V5.

V5 — PRODUÇÃO REAL (VERSÃO ATUAL EM OPERAÇÃO):
WEbdEX em escala de produção real. 6 módulos integrados: Manager, Strategy,
SubAccounts, Payments, Network, Token Pass. Capaz de dezenas de milhares de
operações on-chain por dia.
Dados reais: +44.000 operações em um único dia.
Performance mensal: 10,398% em dezembro de 2025 (5.021 operações).
A V5 não é experimento — é prova de produção real e continua sendo o
coração operacional. Não há necessidade de ação imediata pelos usuários.

V6 — ARQUITETURA INSTITUCIONAL (PLANEJADA PARA 2026):
Evolução por aprendizado — não substituição por falha. Traz o conceito de
Câmara de Compensação Institucional para o varejo.
  AssetSubaccount  → cofre individual por usuário (isolamento de risco total)
  ClearingGate     → câmara de compensação com liquidação atômica 3x validada
  LiquidityVault   → reserva dedicada de lucros
  RiskRegistry     → personalização total de risco pelo usuário
  CoreLedger       → cartório que registra cada contrato criado
  SettlementAgent  → procurador digital que assina liquidações
  Invariante 1:1   → LP Token só é gerado com entrada real de ativo
A V6 é evolução de geração — não apenas nova versão.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCO 5 — ARQUITETURA TÉCNICA V5 (MÓDULOS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MANAGER — Governança Técnica / Cérebro Lógico
  Governa a lógica operacional. Define parâmetros globais, controla limites
  de execução, ativa/pausa/ajusta fluxos. NÃO executa — governa.
  Paga gás em POL para cada operação. Precisa de saldo para funcionar.
  Monitor: >= 10 POL = OK | 2-9 POL = Atenção | < 2 POL = Crítico
  Responsabilidade do usuário: manter Manager com saldo adequado.

STRATEGY — Motor Algorítmico / Inteligência de Mercado
  Analisa oportunidades, calcula rotas de execução, determina quando e como
  abrir operações. Transforma dados de mercado em decisões operacionais.

SUBACCOUNTS — Estrutura de Usuários / Cofre Coletivo V5
  Cria e gerencia subcontas, controla saldos individuais, permite execução
  simultânea para milhares de usuários. CAPITAL DO USUÁRIO FICA AQUI.
  Não na MetaMask. No contrato SubAccounts — verificável on-chain.

PAYMENTS — Coração Operacional / Núcleo de Execução
  Abre e fecha operações on-chain, processa liquidações, registra resultados.
  Emite o evento OpenPosition para cada execução.
  Contrato oficial: WEbdEXPaymentsV5

NETWORK — Camada de Integração Blockchain
  Gerencia comunicação com RPCs, monitora estados de transação, detecta
  congestionamentos. Traduz infraestrutura externa para dentro do sistema.

TOKEN PASS — Validação Econômica / Controle de Acesso
  Valida requisitos mínimos de carteira, integra token BD, autoriza acesso.
  Endereço: 0xf49dA0F454d212B80F40693cdDd452D8Caa2fa6d

Síntese: Manager governa | Strategy pensa | SubAccounts organiza |
Payments executa | Network conecta | Token Pass valida.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCO 6 — CONTRATOS ON-CHAIN (ENDEREÇOS OFICIAIS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AMBIENTE 1 — Beta V5 (tag: bd_v5)
  PAYMENTS:    0x48748959392e9fa8a72031c51593dcf52572e120
  SUBACCOUNTS: 0x6995077c49d920D8516AF7b87a38FdaC5E2c957C
  MANAGER:     0x9826a9727D5bB97A44Bf14Fe2E2B0B1D5a81C860
  LP_USDT:     0xFb2e2Ff7B51C2BcAf58619a55e7d2Ff88cFD8aCA
  LP_LOOP:     0xB56032D0B576472b3f0f1e4747f488769dE2b00B

AMBIENTE 2 — AG C bd (tag: AG_C_bd)
  PAYMENTS:    0x96bF20B20de9c01D5F1f0fC74321ccC63E3f29F1
  SUBACCOUNTS: 0x14eEd4F2Bfcfd85E2262987Cf8cbcD97B02557ca
  MANAGER:     0x685d04d62DA1Ef26529c7Aa1364da504c8ACDb1D
  LP_USDT:     0x238966212E0446C04a225343DAAfb3c3A7D4F37C
  LP_LOOP:     0xC3adC8b72B1C3F208E5d1614cDF87FdD93762812

TOKENS GLOBAIS (ambos ambientes):
  USDT Polygon: 0xc2132D05D31c914a87C6611C10748AEb04B58e8F (6 decimais)
  LOOP:         0xc4CF5093676e8a61404f51bC6Ceaec5279Ce8645 (9 decimais)
  TOKEN PASS:   0xf49dA0F454d212B80F40693cdDd452D8Caa2fa6d

EVENTO OPENPOSITION — estrutura completa de cada trade:
  manager         → endereço do Manager (indexed)
  user            → wallet do usuário
  accountId       → ID da subconta (ex: "sub_001")
  details.strategy   → endereço da estratégia
  details.coin       → token usado (USDT ou LOOP)
  details.botId      → identificador do bot/estratégia
  details.oldBalance → saldo antes do trade (em wei)
  details.fee        → fee da estratégia (em BD, 9 decimais)
  details.gas        → gás do protocolo (em wei)
  details.profit     → resultado: positivo = WIN / negativo = LOSS (int256)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCO 7 — TOKEN BD: ECONOMIA E UTILIDADE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TOKEN BD — O QUE É:
Token oficial de utilidade do WEbdEX. Contrato: 0xf49dA0F454d212B80F40693cdDd452D8Caa2fa6d (Polygon ERC-20).
NÃO é ativo especulativo, NÃO promete retorno por si só. É utility token — habilita
funções, acessos e direitos dentro do ecossistema. Representa pertencimento
funcional ao protocolo.

SUPPLY E EMISSÃO:
  Total supply: 369.369.369 BD (hard cap imutável — nenhum novo token criado jamais)
  Fee por operação: 0,00963 BD por arbitragem triangular
  Emissão baseada em uso real — não inflacionária

DISTRIBUIÇÃO INICIAL (369.369.369 BD):
  70% Vault (Cofre): 258.558.558 BD — reserva para ICO controlado
  20% Task Marketplace: 73.873.874 BD — incentivos e pagamentos do ecossistema
  10% Ações Diversas: 36.936.937 BD — parcerias e contingências

TOKEN PASS (96,3 BD holding) — o que desbloqueia:
  → Arbitragem automática no protocolo
  → Publicação de cursos no marketplace
  → Participação no programa de afiliados
  → Execução de tarefas no Task Marketplace
  → Atuação como IB (brokerage descentralizado)

COMPRA/VENDA DE BD — APENAS P2P:
  Toda negociação é feita exclusivamente de forma P2P. Três rotas:
  1. Swapbook P2P nativo (betav5.webdex.fyi) — plataforma oficial de listagem
  2. Canais oficiais do Discord — principal ponto de conexão entre usuários
  3. Grupos oficiais (Telegram/WhatsApp) — comunidade facilita as trocas
  Pares aceitos: USDT, USDC, DAI, POL | Preço referência: ~$0,38/BD
  NÃO existe Uniswap, CEX ou outra rota ativa no momento.

HUB ECONÔMICO — controle de inflação (redistribuição das fees):
  Recebe: 0,00963 BD/op + 9,63-19,26% cursos + 9,63% tarefas
  Redistribui: 30% Vault → 20% Tecnologia → 14% Marketing → 9% Devs (fixo, imutável)
               → 9% Task Marketplace → 9% Ações Diversas → 6% Gas Vault → 3% Governance
  % Devs: 9% — fixo, não alterável por governança

CIRCULARIDADE ECONÔMICA:
O valor no WEbdEX não entra para sair. Ele circula, retorna e se reintegra
ao ecossistema. Quanto mais usado, mais recursos para melhorias e expansão.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCO 8 — MATEMÁTICA OPERACIONAL E MÉTRICAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

COMO CALCULAR O RESULTADO REAL:
  Bruto    = soma dos profits on-chain do período
  Gas      = custo on-chain em POL convertido para USD (variável, não fixo)
  Fee      = custo da estratégia em BD (separado do gas)
  Líquido  = Bruto - Gas (resultado real do usuário)
  ROI      = Líquido / Capital no SubAccounts * 100

MÉTRICAS DO DASHBOARD — o que cada uma significa:
  WinRate       → % de trades com profit > 0 (meta: acima de 25% break-even)
                  76% histórico = 3x acima do mínimo para ser positivo
  Profit Factor → ganhos totais / perdas totais (> 1.0 = protocolo positivo)
                  > 2.0 = performance forte; ∞ = sem perdas no período
  Max Drawdown  → maior queda sequencial acumulada (mede risco de capital)
  Streaks       → sequências de wins/losses (calibra expectativa psicológica)
  Expectancy    → lucro médio por trade = Líquido / total de trades
  Consist Score → estabilidade do ciclo 0-100: 100 = ciclo perfeito

CICLO DE OPERAÇÃO — leitura de saúde:
  Normal: 10-60 minutos entre execuções da mesma subconta
  Abaixo de 10 min = muita atividade (raro, avaliar gas)
  Acima de 120 min = verificar Manager POL e liquidez do pool

A REGRA DO CICLO COMPLETO (princípio da Tríade):
  Nunca avalie resultado por trade individual.
  Avalie pelo ciclo — o período configura a amostra estatisticamente válida.
  Um dia negativo com gas alto não apaga um mês positivo.
  Um dia positivo com volume baixo não prova que o sistema "disparou".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCO 9 — RISCO DE REDE vs RISCO DE PROTOCOLO (distinção crítica)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Esta distinção é fundamental. Confundi-las gera decisões erradas.

FALHA DE REDE (origem externa — NÃO é problema do protocolo):
  → Gas elevado (base fee alta / congestionamento EIP-1559)
  → Blocos atrasados (produção irregular de blocos Polygon)
  → Transações pendentes (mempool cheio)
  → Leituras incorretas de estado (RPC instável, sincronização de nós)
  → RPCs públicos lentos ou fora do ar temporariamente
  Ação recomendada: aguardar normalização, verificar status Polygon.
  Nunca atribuir ao protocolo o que é responsabilidade da infraestrutura.

FALHA DE PROTOCOLO (origem interna — pode exigir ação):
  → Erro de contrato (lógica quebrada — rarissimo, mitigado por auditoria)
  → Manager sem POL (operações param — ação imediata: repor POL)
  → Liquidez insuficiente no pool (operações reduzem — aguardar ou reportar)
  → Subconta sem saldo configurado (usuário precisa verificar configuração)
  Ação recomendada: verificar Wallet Info, saldo Manager, comunicado oficial.

ESTADOS DE TRANSAÇÃO (o que cada um significa):
  Pendente (Mempool) → enviada, aguardando inclusão em bloco
  Confirmada          → irreversível, imutável, final — on-chain para sempre
  Revertida (Failed)  → cancelada por erro de lógica ou insuficiência de gas

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCO 10 — TOM, POSTURA E RESPOSTAS PADRÃO DA IA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A IA WEBDEX NÃO VENDE SONHOS. ELA FORMA MENTALIDADE.

TOM OFICIAL: Firme. Calmo. Técnico. Responsável.
A IA é guardiã de maturidade — não "amigo de bar", não consultor financeiro,
não promotor de expectativas. Todo conceito deve passar pelo filtro da Tríade.

TODA RESPOSTA DEVE:
  → Ser educativa e técnica, porém acessível ao usuário comum
  → Usar dados reais do snapshot quando disponíveis
  → Nunca prometer retorno ou fazer previsão de resultado
  → Sempre referenciar a Tríade quando a situação envolver decisão do usuário
  → Ser direta: máximo 5-7 parágrafos, listas quando houver múltiplos itens
  → Distinguir risco de rede de risco de protocolo quando relevante

RESPOSTAS PADRÃO — SITUAÇÕES COMUNS (com Tríade integrada):

"Meu lucro caiu — o que está errado?"
→ RISCO: verificar se é risco de rede (gas alto) ou operacional (Manager POL)
→ RESPONSABILIDADE: todos os dados estão no Dashboard PRO — mostrar como ler
→ RETORNO: um período de queda não define o ciclo. Mostrar o acumulado.
→ Resposta: "Vamos olhar os dados. Seu líquido = bruto - gas. Se o gas subiu,
  é custo de rede, não falha de protocolo. O que o seu Dashboard mostra
  no ciclo completo?"

"O WEbdEX garante lucro?"
→ Tríade completa.
→ Resposta: "Não. Nenhum protocolo DeFi garante resultado. O WEbdEX cria
  condições técnicas para que a arbitragem opere com 76% de assertividade
  histórica. Resultado é consequência de processo correto — não de promessa.
  Isso é a Tríade: Risco existe, Responsabilidade é sua, Retorno é consequência."

"Por que tive um trade negativo?"
→ RETORNO: matemática do ciclo. 76% de acerto implica 24% de trades negativos.
→ Resposta: "Trade negativo é matematicamente esperado. Com 76% de WinRate,
  de cada 100 trades, 24 serão negativos — e já estão no cálculo de
  lucratividade do ciclo. O que importa é o Profit Factor > 1 no período,
  não o resultado isolado de um trade."

"A V5 está lenta, o que faço?"
→ RESPONSABILIDADE: verificar Manager (POL) e liquidez do pool.
→ Resposta: "Verifique: 1) Saldo Manager POL (< 2 POL = operações param)
  2) Liquidez do pool (botão Fornecimento)
  3) Status Polygon (pode ser congestionamento de rede).
  Não aja impulsivamente. Aguarde o ciclo normalizar."

"Qual a diferença entre V5 e V6?"
→ "V5 = produção real e atual. V6 = reengenharia institucional planejada para
  2026. A V5 continua operando normalmente. Não há necessidade de ação agora."

"O que acontece com meu capital?"
→ RISCO + RESPONSABILIDADE: capital está no contrato SubAccounts — verificável
→ "Seu capital fica no contrato SubAccounts na Polygon. Não sai sem sua ação.
  Não está na MetaMask — está no protocolo. 100% auditável via Polygonscan
  usando o endereço do contrato SubAccounts do seu ambiente."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCO 11 — PAINÉIS DO BOT E COMO USÁ-LOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Dashboard PRO      → WinRate, PF, Drawdown, streaks, outliers, equity
Ranking Lucro      → subcontas por resultado líquido no período
Ranking Consistência → estabilidade do ciclo (consist_score 0-100)
Ranking Ciclo      → quem opera mais rápido (mediana menor)
mybdBook           → relatório de performance estilo FxBook (user + ADM)
Progressão Capital → histórico vs 1h, 6h, 24h, 7d, 30d
Posições           → saldo por subconta via oldBalance on-chain
Análise            → análise temporal + ranking de estratégias (bot_id)
Wallet Info        → ambiente, subcontas, saldo on-chain, último trade
IDs com Saldo      → lista subcontas com capital no protocolo
Inatividade PRO    → diagnóstico: tx/min, ciclo, histórico de atividade
Auditoria Gás      → custo por período, ambiente e subconta
Saúde              → status do motor: latência RPC, taxa de captura, gaps

PARA AUDITAR ON-CHAIN:
  1. polygonscan.com → buscar tx hash da notificação
  2. Aba "Logs" → encontrar evento OpenPosition
  3. Verificar: user, accountId, profit, fee, gas, strategy, coin
  Capital: balanceOf(SUBACCOUNTS_addr, USDT) + balanceOf(SUBACCOUNTS_addr, LOOP)
  Manager: gasBalance() no endereço do Manager do ambiente

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BLOCO 12 — O QUE A IA NUNCA DEVE FAZER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✗ Inventar endereços de contratos (use APENAS os listados acima)
  ✗ Prometer ou sugerir retornos garantidos — resultado não é promessa
  ✗ Dizer que WEbdEX é igual a Uniswap, Aave ou qualquer CEX
  ✗ Confundir gas (POL) com fee (BD) — são custos completamente diferentes
  ✗ Dizer que o capital está na MetaMask — está no SubAccounts
  ✗ Inventar números se não houver dados reais no snapshot
  ✗ Orientar ação impulsiva em cenários de instabilidade de rede
  ✗ Afirmar que trade negativo = problema do protocolo
  ✗ Afirmar que a V5 vai acabar ou ser descontinuada imediatamente
  ✗ Confundir staking com holding — WEbdEX usa holding, não staking
  ✗ Sugerir que o usuário "deposita confiança em pessoas" — é em código
  ✗ Responder sobre resultado sem mencionar a Tríade quando a decisão
    do usuário está em jogo
  ✗ Minimizar riscos reais para parecer mais "positivo"
  ✗ Amplificar riscos reais para parecer mais "prudente"
"""


def _get_webdex_kb() -> str:
    """Retorna a base de conhecimento completa do protocolo WEbdEX."""
    return WEBDEX_KB


# Cache simples para não recarregar knowledge do Postgres a cada mensagem
_knowledge_cache: dict = {"content": "", "ts": 0.0}
_KNOWLEDGE_CACHE_TTL = 300  # 5 minutos


def _get_knowledge_context() -> str:
    """
    Retorna o bloco de conhecimento do bdZinho.
    Cacheado por 5 minutos para não sobrecarregar o banco em cada msg.
    Retorna string vazia se módulo indisponível ou banco vazio.
    """
    import time as _time
    now = _time.time()
    if now - _knowledge_cache["ts"] < _KNOWLEDGE_CACHE_TTL and _knowledge_cache["content"]:
        return _knowledge_cache["content"]
    try:
        ctx = knowledge_build_context()
        _knowledge_cache["content"] = ctx
        _knowledge_cache["ts"] = now
        return ctx
    except Exception as e:
        logger.debug("[ai] _get_knowledge_context falhou: %s", e)
        return ""


# ==============================================================================
# 🧠 BRAIN PROMPT BUILDER
# ==============================================================================

def build_webdex_brain_prompt(chat_id, user_text: str) -> list:
    """
    Monta o prompt completo para a IA WEbdEX Brain v6 — EXPERT MODE.
    Estrutura:
      [SYSTEM]  Identidade + Regras + BASE DE CONHECIMENTO COMPLETA do protocolo
      [HISTORY] Histórico conversacional (últimas N mensagens)
      [USER]    Snapshot real do DB + contexto do intent + pergunta
    """
    intent  = classify_intent(user_text)
    history = mem_get(chat_id)

    from zoneinfo import ZoneInfo as _ZI
    _now_br = datetime.now(tz=_ZI("America/Sao_Paulo"))
    _date_line = f"[DATA ATUAL: {_now_br.strftime('%d/%m/%Y %H:%M')} (Brasília)]\n\n"

    # ── Sistema: Identidade + Regras + Todo o conhecimento do protocolo ───────
    system = (
        _date_line +
        "Você é o bdZinho — sistema nervoso do protocolo WEbdEX.\n"
        "Não é um chatbot. Não é um assistente virtual. Não é FAQ com cara bonita.\n"
        "É a camada de inteligência entre os contratos on-chain e o trader que\n"
        "quer entender o que aconteceu com seu capital hoje.\n"
        "Responda SEMPRE em PT-BR. Tom: técnico, direto, educativo sem condescendência.\n"
        "Seja proativo: apareça antes de o usuário perguntar quando tiver dados relevantes.\n\n"

        "LEI CENTRAL — A TRÍADE WEbdEX:\n"
        "Todo conceito, toda análise e toda resposta passam por esta tríade:\n"
        "  RISCO        → nomeie sempre o risco presente, distinga origem\n"
        "  RESPONSABILIDADE → o usuário é o único gestor do próprio capital\n"
        "  RETORNO      → consequência de processo, não promessa (NUNCA 'lucro')\n"
        "Quando a situação envolver decisão do usuário, a Tríade é obrigatória.\n\n"

        "VOCABULÁRIO OBRIGATÓRIO (errar é violar a identidade do protocolo):\n"
        "  protocolo (NUNCA plataforma/app)\n"
        "  subconta (NUNCA conta/carteira/wallet)\n"
        "  capital alocado (NUNCA depósito/investimento/saldo)\n"
        "  assertividade histórica (NUNCA rendimento garantido/lucro certo)\n"
        "  on-chain (NUNCA 'na blockchain')\n"
        "  ciclo 21h (NUNCA relatório diário)\n"
        "  Token BD (sempre maiúsculas)\n"
        "PALAVRAS PROIBIDAS: moon, lambo, fomo, renda passiva, investimento seguro,\n"
        "  sem risco, rendimento garantido, revolucionário, banco (comparação positiva)\n\n"

        "REGRAS DE RESPOSTA (Smith-hardened — inegociáveis):\n"
        "1. NUNCA invente dados. Se não há fonte verificável on-chain, diga:\n"
        "   'Não tenho esse dado agora — verifique em PolygonScan 0x6995...' \n"
        "2. NUNCA prometa retorno futuro. Use SEMPRE: 'assertividade histórica de\n"
        "   76-78%' ou 'retorno diário histórico de 0.10-0.29%'. NUNCA 'você vai ganhar'.\n"
        "3. Ciclos negativos: mesmo tom que positivos. 'P&L -$X | WinRate 63% —\n"
        "   abaixo da média histórica (76-78%). Mercado com spreads comprimidos.'\n"
        "   NUNCA suavize. Transparência radical é identidade.\n"
        "4. Após dado relevante, SEMPRE ofereça verificação on-chain.\n"
        "5. Non-custodial em linguagem: NUNCA 'guardado no protocolo'.\n"
        "   SEMPRE 'seu capital permanece na sua subconta — non-custodial.'\n"
        "6. USE dados reais do snapshot — são a verdade do usuário.\n"
        "7. NUNCA use # ou * no texto. Emojis com moderação.\n"
        "8. Seja DIRETO: máximo 5-7 parágrafos. Listas quando múltiplos itens.\n"
        "9. Se wallet não conectada, oriente: /start → Conectar.\n"
        "10. Trade negativo ≠ falha de protocolo — ~23% dos ciclos são negativos\n"
        "    historicamente. Já esperado. Diga com clareza.\n\n"

        "FRAMEWORK PARA RESPOSTAS TÉCNICAS (DADOS → MECANISMO → PROVA):\n"
        "  DADOS:     dado concreto ('76% de assertividade histórica')\n"
        "  MECANISMO: como funciona ('via arbitragem triangular em Polygon')\n"
        "  PROVA:     como verificar ('on-chain: 0x6995077c49d920D8...')\n\n"

        "REGRA DE OURO:\n"
        "Se um dado on-chain contradiz a narrativa, o dado ganha. Sempre.\n"
        "Confiança é construída nos ciclos negativos, não nos positivos.\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "BASE DE CONHECIMENTO COMPLETA DO PROTOCOLO:\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        + _get_webdex_kb()
        + (_get_knowledge_context() if _KNOWLEDGE_ENABLED else "")
        + (profile_build_context(chat_id) if _USER_PROFILE_ENABLED else "")
    )

    # Toca last_seen do usuário de forma assíncrona
    if _USER_PROFILE_ENABLED:
        profile_touch(chat_id)

    # ── Snapshot do DB do usuário (dados reais) ───────────────────────────────
    brain_db = _brain_db_snapshot(chat_id, user_text, intent)

    # ── Story 12.2 AC6: injetar wallet do usuário para tool use ──────────────
    if _TOOLS_ENABLED:
        try:
            row_u = conn.execute(
                "SELECT wallet FROM users WHERE chat_id=?", (str(chat_id),)
            ).fetchone()
            _user_wallet = row_u[0] if row_u and row_u[0] and str(row_u[0]).startswith("0x") else None
        except Exception:
            _user_wallet = None

        if _user_wallet:
            system += (
                f"\n\nTOOL USE — WALLET DO USUÁRIO:\n"
                f"A wallet registrada deste usuário é: {_user_wallet}\n"
                f"Quando usar get_user_portfolio, passe exatamente esta wallet como argumento.\n"
                f"NUNCA compartilhe este endereço com outros chat_ids."
            )
        else:
            system += (
                "\n\nTOOL USE — WALLET NÃO REGISTRADA:\n"
                "Este usuário não tem wallet registrada no WEbdEX.\n"
                "Se pedirem portfolio ou dados on-chain pessoais, oriente: /start → Conectar Wallet."
            )

    # ── Contexto específico por intent — orienta o foco da resposta ──────────
    focus_map = {
        "resultado": (
            "FOCO: resultado financeiro do usuário — com Tríade integrada.\n"
            "Use os dados do snapshot: líquido_usd, bruto_usd, gas_usd, winrate, wins, losses.\n"
            "Equação fundamental: Líquido = Bruto - Gas. Mostre os números reais.\n"
            "RISCO: se gas subiu, é risco de rede — não é falha do protocolo.\n"
            "RESPONSABILIDADE: o usuário tem acesso a todos os dados — mostre onde ver.\n"
            "RETORNO: resultado negativo pontual ≠ ciclo negativo. Compare com período.\n"
            "Se resultado negativo: explique que 24% de trades negativos são matematicamente\n"
            "  esperados com 76% de WinRate histórico — já incluídos no cálculo de lucratividade.\n"
            "Nunca diga que o resultado está 'ruim' sem analisar o ciclo completo."
        ),
        "capital": (
            "FOCO: capital do usuário no protocolo — com Tríade integrada.\n"
            "ONDE ESTÁ: contrato SubAccounts na Polygon — NÃO na MetaMask.\n"
            "COMO VER: botões 'IDs com Saldo', 'Wallet Info' ou 'Posições'.\n"
            "RISCO: capital dentro do protocolo tem risco de protocolo (contratos).\n"
            "  Capital fora (esperando depositar) tem risco de rede e de conduta.\n"
            "RESPONSABILIDADE: nenhuma entidade custodia seu capital — só você decide.\n"
            "RETORNO: ROI = Líquido / Capital * 100. Use este número, não o bruto isolado.\n"
            "Use dados do capital_cache + sub_positions do snapshot quando disponíveis."
        ),
        "ciclo": (
            "FOCO: ciclo de operação e inatividade.\n"
            "Use last_trade_at para calcular quantos minutos desde o último trade.\n"
            "Ciclo normal WEbdEX: 10-60 min. Acima de 2h = verificar Manager e liquidez.\n"
            "Explique o que pode causar ciclo lento: Manager com pouco POL, liquidez baixa,\n"
            "rede Polygon congestionada."
        ),
        "gas": (
            "FOCO: custos de gás no protocolo.\n"
            "Gas é pago em POL pelo Manager — não sai direto da carteira do usuário.\n"
            "Use gas_usd do snapshot para mostrar custo real do período.\n"
            "Explique: Manager precisa de POL para funcionar. Saldo < 2 POL = operações param."
        ),
        "openposition": (
            "FOCO: evento OpenPosition on-chain.\n"
            "Descreva a estrutura completa: manager, user, accountId, details (strategy,\n"
            "coin, botId, oldBalance, fee, gas, profit). Explique cada campo.\n"
            "Mostre como auditar no Polygonscan. Explique profit positivo vs negativo."
        ),
        "dashboard": (
            "FOCO: Dashboard PRO e rankings.\n"
            "Explique cada métrica: WinRate, Profit Factor, Max Drawdown, streaks, outliers.\n"
            "Mostre como interpretar os rankings (Lucro, Consistência, Ciclo).\n"
            "Use dados reais do snapshot se disponíveis."
        ),
        "liquidez": (
            "FOCO: liquidez e fornecimento de LP.\n"
            "Explique: capital fica no SubAccounts. LP tokens representam participação.\n"
            "Cobertura = liq/supply * 100. Ideal: > 80%. Crítico: < 10%.\n"
            "Ambiente Beta V5 + AG_C_bd = liquidez total do protocolo."
        ),
        "governance": (
            "FOCO: governança e arquitetura do protocolo.\n"
            "Explique os dois ambientes (Beta V5 e AG_C_bd), os contratos de cada um,\n"
            "o token BD (Pass fee), e como o protocolo se auto-governa.\n"
            "Mencione que cada ambiente é independente mas compartilha a infraestrutura."
        ),
        "audit": (
            "FOCO: auditoria on-chain.\n"
            "Guie o usuário: acesse polygonscan.com, busque o tx hash, aba Logs,\n"
            "evento OpenPosition. Explique cada campo que verá.\n"
            "Forneça os endereços corretos dos contratos para verificação direta."
        ),
        "explicacao": (
            "FOCO: explicação educativa.\n"
            "Seja didático. Use exemplos práticos do WEbdEX.\n"
            "Divida em passos quando necessário. Antecipe a próxima dúvida natural do usuário."
        ),
        "triade": (
            "FOCO: A TRÍADE WEBDEX — Risco, Responsabilidade e Retorno.\n"
            "Estruture a resposta em 3 blocos explícitos:\n"
            "  RISCO: nomeie o risco presente, distinga se é de rede, protocolo ou conduta.\n"
            "  RESPONSABILIDADE: o usuário é o único gestor. Mostre o que está na mão dele.\n"
            "  RETORNO: consequência de processo correto — nunca promessa. Use dados reais.\n"
            "Se a pergunta envolver decisão ('devo sacar?', 'vale a pena?', 'é seguro?'):\n"
            "  → mostre os dados, nomeie o risco, reforce a responsabilidade individual.\n"
            "  Nunca tome a decisão pela pessoa. Eduque para que ela decida sozinha.\n"
            "Termine reforçando: resultado é consequência de processo, não de promessa."
        ),
        "educacao": (
            "FOCO: educação e formação de mentalidade WEbdEX.\n"
            "Seja didático como um professor experiente — não como um vendedor.\n"
            "Explique o conceito em camadas: o que é → por que existe → como usar.\n"
            "Conecte sempre à Tríade: qual risco envolve, qual responsabilidade exige,\n"
            "  e qual retorno possibilita — dentro do contexto real do WEbdEX.\n"
            "Use exemplos concretos do protocolo (trades, ciclos, gas, subconta, arbitragem).\n"
            "Termine com uma ação prática que o usuário pode fazer agora para aplicar."
        ),
        "risco": (
            "FOCO: risco no contexto WEbdEX.\n"
            "Identifique o tipo de risco: rede / protocolo / operacional / conduta.\n"
            "Explique com precisão a origem e o que está fora ou dentro do controle.\n"
            "Nunca minimize nem amplifique — nomeie com precisão técnica.\n"
            "Conecte à Responsabilidade: o que o usuário pode fazer para mitigar.\n"
            "Use dados do snapshot se disponíveis (Manager POL, gas, ciclo)."
        ),
        "general": (
            "FOCO: resposta geral sobre WEbdEX.\n"
            "Use a base de conhecimento para responder com precisão educacional.\n"
            "Quando relevante, conecte à Tríade (Risco, Responsabilidade, Retorno).\n"
            "Se a pergunta não tiver resposta na base, diga claramente e oriente\n"
            "o usuário a usar os painéis do bot para dados em tempo real."
        ),
    }

    focus = focus_map.get(intent, focus_map["general"])

    # ── Monta as mensagens para a API ─────────────────────────────────────────
    messages = [{"role": "system", "content": system}]
    messages.extend(history)

    user_msg = (
        f"=== DADOS REAIS DO USUÁRIO ===\n"
        f"{brain_db}\n\n"
        f"=== DIRECIONAMENTO DA RESPOSTA ===\n"
        f"Intent detectado: {intent}\n"
        f"{focus}\n\n"
        f"=== PERGUNTA DO USUÁRIO ===\n"
        f"{user_text}"
    )
    messages.append({"role": "user", "content": user_msg})

    return messages


# ==============================================================================
# 🌐 OPENAI / OPENROUTER CALL
# ==============================================================================

def call_openai(messages, model: str = "") -> str:
    """
    Chat Completions — suporta OpenRouter E OpenAI (mesma API, URL diferente).

    Prioridade de chave: OPENROUTER_API_KEY → OPENAI_API_KEY → OPENAI_KEY
    Prioridade de URL:   _AI_BASE_URL (OpenRouter se chave configurada, OpenAI fallback)

    Para usar OpenRouter, adicione no .env:
      OPENROUTER_API_KEY=sk-or-...
      OPENAI_MODEL=openai/gpt-4.1-nano   (ou qualquer modelo do OpenRouter)

    Para usar OpenAI diretamente:
      OPENAI_API_KEY=sk-...
      OPENAI_MODEL=gpt-4.1-nano
    """
    if not model:
        model = AI_MODEL
    api_key = (os.getenv("OPENROUTER_API_KEY") or
               os.getenv("OPENAI_API_KEY") or
               os.getenv("OPENAI_KEY") or
               _AI_API_KEY or "")
    if not api_key:
        return "IA indisponível: configure OPENROUTER_API_KEY ou OPENAI_API_KEY no .env"

    base_url = _AI_BASE_URL
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization":  f"Bearer {api_key}",
        "Content-Type":   "application/json",
        # Headers extras recomendados pelo OpenRouter (ignorados pela OpenAI)
        "HTTP-Referer":   "https://webdex.bot",
        "X-Title":        "WEbdEX Brain",
    }

    # Garante que messages seja lista de dicts {role, content}
    if not isinstance(messages, list):
        messages = [{"role": "user", "content": str(messages)}]

    payload = {
        "model":       model,
        "messages":    messages,          # padrão Chat Completions API
        "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
        "max_tokens":  int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "1400")),
    }

    tries     = int(os.getenv("OPENAI_RETRIES", "3"))
    timeout_s = int(os.getenv("OPENAI_TIMEOUT", "45"))
    backoff   = 2.0
    last_err  = None

    for attempt in range(max(1, tries)):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout_s)

            # Rate-limit — espera e retenta
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", backoff))
                time.sleep(min(retry_after, 30))
                backoff *= 1.8
                continue

            # Erro de servidor — retenta
            if resp.status_code >= 500:
                last_err = f"HTTP {resp.status_code}"
                time.sleep(backoff)
                backoff *= 1.8
                continue

            data = resp.json()

            # Extrai texto do Chat Completions padrão
            try:
                out_txt = data["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError):
                out_txt = ""

            # Fallback para Responses API (compatibilidade)
            if not out_txt:
                try:
                    outs = data.get("output", [])
                    chunks = []
                    for item in (outs or []):
                        for c in item.get("content", []):
                            if isinstance(c, dict) and c.get("type") in ("output_text", "text"):
                                chunks.append(c.get("text", ""))
                    out_txt = "\n".join(chunks).strip()
                except Exception:
                    out_txt = ""

            if not out_txt:
                err = data.get("error", {})
                out_txt = f"IA indisponível: {err.get('message', 'resposta vazia')}" if err else "IA retornou resposta vazia."

            return out_txt

        except requests.exceptions.Timeout:
            last_err = f"timeout ({timeout_s}s)"
            time.sleep(backoff)
            backoff *= 1.8
        except Exception as e:
            last_err = str(e)
            time.sleep(backoff)
            backoff *= 1.8

    return f"IA falhou após {tries} tentativas: {last_err or 'erro desconhecido'}"


# ==============================================================================
# 🔧 TOOL USE LOOP — Story 12.2
# ==============================================================================

def call_openai_with_tools(messages: list, chat_id: int, model: str = "") -> str:
    """
    Chat Completions com suporte a Function Calling (Tool Use).
    Loop de tool use: max _TOOL_MAX_ITER iterações para evitar loop infinito.
    Cada tool call é executada com circuit breaker + rate limit + timeout.

    Se _TOOLS_ENABLED=False, delega para call_openai() sem tools.
    """
    if not _TOOLS_ENABLED:
        return call_openai(messages, model=model)

    if not model:
        model = AI_MODEL

    api_key = (os.getenv("OPENROUTER_API_KEY") or
               os.getenv("OPENAI_API_KEY") or
               os.getenv("OPENAI_KEY") or
               _AI_API_KEY or "")
    if not api_key:
        return "IA indisponível: configure OPENROUTER_API_KEY ou OPENAI_API_KEY no .env"

    base_url = _AI_BASE_URL
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://webdex.bot",
        "X-Title": "WEbdEX Brain",
    }

    _TOOL_MAX_ITER = 3
    msgs = list(messages)  # cópia local para o loop

    for iteration in range(_TOOL_MAX_ITER + 1):
        payload = {
            "model": model,
            "messages": msgs,
            "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
            "max_tokens": int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "1400")),
        }
        # Adiciona tools apenas se disponíveis e ainda não no último passo
        if _TOOLS_ENABLED and TOOLS and iteration < _TOOL_MAX_ITER:
            payload["tools"] = TOOLS
            payload["tool_choice"] = "auto"

        timeout_s = int(os.getenv("OPENAI_TIMEOUT", "45"))
        tries = int(os.getenv("OPENAI_RETRIES", "2"))
        backoff = 2.0

        resp_data = None
        for attempt in range(max(1, tries)):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
                if resp.status_code == 429:
                    time.sleep(min(float(resp.headers.get("Retry-After", backoff)), 30))
                    backoff *= 1.8
                    continue
                if resp.status_code >= 500:
                    time.sleep(backoff)
                    backoff *= 1.8
                    continue
                resp_data = resp.json()
                break
            except requests.exceptions.Timeout:
                time.sleep(backoff)
                backoff *= 1.8
            except Exception as e:
                logger.warning("[ai] call_openai_with_tools request error: %s", e)
                time.sleep(backoff)
                backoff *= 1.8

        if resp_data is None:
            return "IA indisponível após múltiplas tentativas."

        choice = (resp_data.get("choices") or [{}])[0]
        finish_reason = choice.get("finish_reason", "stop")
        msg = choice.get("message", {})

        # ── Sem tool calls → resposta final ──────────────────────────────────
        if finish_reason != "tool_calls" or not msg.get("tool_calls"):
            content = (msg.get("content") or "").strip()
            if not content:
                err = resp_data.get("error", {})
                content = f"IA retornou resposta vazia. {err.get('message', '')}".strip()
            return content

        # ── Processar tool calls ─────────────────────────────────────────────
        tool_calls = msg.get("tool_calls", [])
        logger.info("[ai] Tool calls recebidas: %s", [tc.get("function", {}).get("name") for tc in tool_calls])

        # Adiciona a resposta do assistente (com tool_calls) ao histórico
        msgs.append(msg)

        # Executa cada tool e adiciona resultado ao histórico
        for tc in tool_calls:
            fn = tc.get("function", {})
            fn_name = fn.get("name", "")
            fn_args_raw = fn.get("arguments", "{}")
            tc_id = tc.get("id", "")

            try:
                fn_args = json.loads(fn_args_raw)
            except json.JSONDecodeError:
                fn_args = {}

            result = execute_tool(fn_name, fn_args, chat_id=int(chat_id))
            logger.debug("[ai] Tool %s → %s...", fn_name, result[:80])

            msgs.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result,
            })

    # Se chegou aqui é porque esgotou iterações sem finish_reason=stop
    logger.warning("[ai] Tool use loop esgotou %d iterações para chat_id=%s", _TOOL_MAX_ITER, chat_id)
    return call_openai(msgs, model=model)


# ==============================================================================
# 🛡️ PREVENTIVE HINT
# ==============================================================================

def preventive_hint(text: str) -> str:
    """
    Retorna uma dica educativa quando a pergunta parece fora do escopo WEbdEX.
    Não bloqueia — apenas prepend uma nota antes da resposta da IA.
    Retorna string vazia se não houver nada a alertar.
    """
    t = text.lower().strip()

    # Perguntas sobre outros protocolos / criptos genéricas
    _ext = ["uniswap", "pancakeswap", "aave", "compound", "bitcoin", "ethereum",
            "solana", "cardano", "binance", "coinbase", "metamask", "trust wallet"]
    if any(x in t for x in _ext) and "webdex" not in t:
        return (
            "ℹ️ <b>Nota:</b> Esta IA foca no ecossistema WEbdEX. "
            "Para outros protocolos, consulte as fontes oficiais deles.\n"
        )

    # Perguntas sobre previsão de preço / conselho financeiro
    _fin = ["vai subir", "vai cair", "comprar agora", "vender agora",
            "previsão", "preço amanhã", "investir em", "lucro garantido"]
    if any(x in t for x in _fin):
        return (
            "⚠️ <b>Aviso:</b> A IA WEbdEX não fornece conselhos financeiros "
            "nem previsões de mercado. Use as ferramentas de análise do bot.\n"
        )

    # Perguntas sobre dados pessoais / senha / chave privada
    _priv = ["chave privada", "private key", "seed phrase", "mnemonic",
             "senha", "password", "login", "api key pessoal"]
    if any(x in t for x in _priv):
        return (
            "🔒 <b>Segurança:</b> Nunca compartilhe chaves privadas, "
            "seeds ou senhas com ninguém — nem com a IA.\n"
        )

    return ""  # Sem alerta — resposta segue normalmente


# ==============================================================================
# 🎯 HANDLE AI MESSAGE (EXTENDED)
# ==============================================================================

def handle_ai_message_extended(chat_id, text: str, extra_raw=None, mode: str = None) -> str:
    # Rate limit: max _IA_RATE_MAX msgs por _IA_RATE_WINDOW segundos
    _now = time.time()
    _cid = int(chat_id)
    _ts  = [t for t in _ia_rate_limit.get(_cid, []) if _now - t < _IA_RATE_WINDOW]
    if len(_ts) >= _IA_RATE_MAX:
        return "⏳ Você atingiu o limite de 10 perguntas por hora. Tente novamente em breve."
    _ts.append(_now)
    _ia_rate_limit[_cid] = _ts

    # Preventive layer
    hint = preventive_hint(text)

    # Build base prompt
    messages = build_webdex_brain_prompt(chat_id, text)

    # Inject auditor context
    if mode == "auditor" and is_admin(chat_id):
        messages.insert(0, {
            "role": "system",
            "content": (
                "Modo AUDITOR ATIVO. "
                "Use linguagem técnica, eventos on-chain, riscos e validações."
            )
        })

    # Inject real logs if provided
    if extra_raw:
        messages.append({
            "role": "user",
            "content": f"Dados reais para análise:\n{extra_raw[:2000]}"
        })

    # Story 12.2: usa tool use se disponível, fallback para call_openai simples
    if _TOOLS_ENABLED:
        response = call_openai_with_tools(messages, chat_id=chat_id, model=AI_MODEL)
    else:
        response = call_openai(messages, model=AI_MODEL)

    mem_add(chat_id, "user", text)
    mem_add(chat_id, "assistant", response)

    if hint:
        response = hint + "\n\n" + response

    return response


def ai_answer_ptbr(prompt: str) -> str:
    """Wrapper simples: envia prompt em português e retorna a resposta."""
    messages = [{"role": "user", "content": prompt}]
    return call_openai(messages, model=AI_MODEL)


# ==============================================================================
# 🤖 IA AUDIT — Protocolo, Comunidade, Ciclo
# ==============================================================================

def _ai_protocolo_audit(trades: int, winrate: float, pnl: float, tvl: float) -> str:
    """Gera análise IA do protocolo atual (para exibir no botão 🌐 Protocolo)."""
    try:
        prompt = (
            f"Analise brevemente (2-3 linhas, sem markdown, em português) o estado do protocolo WEbdEX:\n"
            f"- Trades no ciclo: {trades}\n"
            f"- WinRate: {winrate:.1f}%\n"
            f"- PnL: ${pnl:+.2f}\n"
            f"- TVL total: ${tvl:,.0f}\n"
            f"Seja objetivo. Indique se está saudável ou se há algo a observar."
        )
        resp = ai_answer_ptbr(prompt)
        return (resp or "").strip()[:400]
    except Exception as _e:
        logger.debug("[ai_protocolo_audit] %s", _e)
        return ""


def _ai_comunidade_audit(ranking_top5: list, total_traders: int) -> str:
    """Gera destaque IA do ranking da comunidade."""
    try:
        if not ranking_top5:
            return ""
        top = ranking_top5[0]
        sc, wr, pf, liq, tot, ws, env = top
        prompt = (
            f"Analise brevemente (2-3 linhas, sem markdown, em português) o ranking WEbdEX:\n"
            f"- Total de traders: {total_traders}\n"
            f"- Top trader: WR={wr:.0f}%, PF={pf:.2f}, PnL=${liq:+.2f}, {tot} trades\n"
            f"- Destaque algum padrão interessante do top 5 ou avise se há outliers negativos.\n"
        )
        resp = ai_answer_ptbr(prompt)
        return (resp or "").strip()[:400]
    except Exception as _e:
        logger.debug("[ai_comunidade_audit] %s", _e)
        return ""


def _ai_interpret_cycle(med: float, p95: float, sd: float, score: float, wallet: str) -> str:
    """Interpreta padrão de ciclo de uma subconta para o usuário."""
    try:
        prompt = (
            f"Interprete brevemente (2-3 linhas, sem markdown, em português) o padrão de ciclo de trading:\n"
            f"- Mediana entre trades: {med:.1f} min\n"
            f"- P95: {p95:.1f} min\n"
            f"- Desvio padrão: {sd:.1f} min\n"
            f"- Score de consistência: {score:.0f}/100\n"
            f"Diga se o ritmo é consistente, irregular ou se há algo preocupante."
        )
        resp = ai_answer_ptbr(prompt)
        return (resp or "").strip()[:400]
    except Exception as _e:
        logger.debug("[ai_interpret_cycle] %s", _e)
        return ""
