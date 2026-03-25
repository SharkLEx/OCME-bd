---
type: knowledge
id: "042"
title: "Error Patterns OCME — O Que Quebra e Como Tratar"
layer: L5-tech
tags: [tech, errors, debugging, resilencia, rpc, api, telegram, postgres, graceful-degradation]
links: ["040-tech-stack-ocme", "041-deploy-pattern", "015-rpc-pool", "025-bdzinho-capacidades"]
---

# 042 — Error Patterns OCME

> **Ideia central:** O OCME opera em ambiente adverso (RPC instável, API rate limits, Telegram floods). Todo erro esperado tem tratamento. Todo módulo opcional usa soft import. O sistema nunca derruba o bot por um erro isolado.

---

## Hierarquia de Erros

```
CRÍTICO (derruba o processo)
  └── Sem tratamento → bot offline

ALTO (módulo falha, bot funciona)
  └── Com tratamento → graceful degradation

MÉDIO (operação específica falha, retry)
  └── Com retry/fallback → usuário recebe resposta degradada

BAIXO (warning, log e segue)
  └── Silencioso para o usuário
```

**Princípio:** Apenas erros CRÍTICOS devem derrubar o bot. Todo o resto: log + fallback.

---

## Erro 1: RPC Failure (Blockchain)

**Sintoma:** `web3.exceptions.ConnectionError`, `requests.exceptions.Timeout`

**Causa:** RPC endpoint instável ou rate-limited

```python
# PADRÃO DE TRATAMENTO:
from webdex_monitor import get_web3_connection

MAX_RPC_RETRIES = 3

for attempt in range(MAX_RPC_RETRIES):
    try:
        w3 = get_web3_connection()  # rotaciona RPC pool
        result = w3.eth.get_block("latest")
        break
    except Exception as e:
        logger.warning(f"[rpc] tentativa {attempt+1} falhou: {e}")
        if attempt == MAX_RPC_RETRIES - 1:
            logger.error("[rpc] todos os endpoints falharam")
            result = None
```

**Ver:** [[015-rpc-pool]] para padrão completo de pool rotativo.

---

## Erro 2: Claude API Rate Limit

**Sintoma:** `anthropic.RateLimitError`, status 429

**Causa:** Muitas requests simultâneas ou burst de mensagens

```python
import time
import anthropic

MAX_RETRIES = 3
RETRY_DELAY = 60  # segundos (rate limit window)

for attempt in range(MAX_RETRIES):
    try:
        response = client.messages.create(...)
        break
    except anthropic.RateLimitError:
        if attempt < MAX_RETRIES - 1:
            logger.warning(f"[ai] rate limit, aguardando {RETRY_DELAY}s")
            time.sleep(RETRY_DELAY)
        else:
            logger.error("[ai] rate limit persistente, usando fallback")
            return _fallback_response()
```

**Fallback:** Resposta pré-definida para o usuário: `"Sistema temporariamente sobrecarregado. Tente em instantes."`

---

## Erro 3: Telegram Flood

**Sintoma:** `telebot.apihelper.ApiTelegramException: Too Many Requests`

**Causa:** Muitas mensagens enviadas em curto período

```python
# PADRÃO: usar throttle/queue para envios em massa
import time

def send_with_throttle(bot, chat_id, text, delay=0.5):
    try:
        bot.send_message(chat_id, text)
    except telebot.apihelper.ApiTelegramException as e:
        if "Too Many Requests" in str(e):
            retry_after = int(str(e).split("retry after ")[-1]) + 1
            logger.warning(f"[telegram] flood, aguardando {retry_after}s")
            time.sleep(retry_after)
            bot.send_message(chat_id, text)  # retry uma vez
        else:
            raise
    time.sleep(delay)  # throttle entre mensagens
```

---

## Erro 4: PostgreSQL Connection Lost

**Sintoma:** `psycopg2.OperationalError: server closed the connection unexpectedly`

**Causa:** Timeout de idle connection, restart do DB

```python
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """Sempre criar conexão nova. Não usar pooling sem reconexão automática."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"[db] conexão falhou: {e}")
        return None

# PADRÃO de uso:
def query_with_fallback(sql, params=None):
    conn = get_db_connection()
    if not conn:
        return None  # graceful degradation
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    except Exception as e:
        logger.error(f"[db] query falhou: {e}")
        return None
    finally:
        conn.close()
```

---

## Erro 5: Módulo Opcional Não Disponível

**Sintoma:** `ImportError`, `ModuleNotFoundError`

**Causa:** Dependência não instalada, arquivo não deployado

```python
# PADRÃO OBRIGATÓRIO — soft import
try:
    from webdex_ai_proactive import run_proactive
    _PROACTIVE_MODULE_ENABLED = True
    logger.info("[proactive] módulo carregado")
except ImportError as e:
    _PROACTIVE_MODULE_ENABLED = False
    run_proactive = None
    logger.warning(f"[proactive] módulo indisponível: {e}")

# USO:
if _PROACTIVE_MODULE_ENABLED and run_proactive:
    try:
        result = run_proactive(context)
    except Exception as e:
        logger.error(f"[proactive] execução falhou: {e}")
        result = None
```

---

## Erro 6: Timeout em Request LLM

**Sintoma:** `anthropic.APITimeoutError`, request demora > 30s

**Causa:** Claude API sobrecarregado, context muito longo

```python
# PADRÃO: timeout explícito + fallback
try:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        timeout=30.0,  # 30s max
        messages=[...]
    )
except anthropic.APITimeoutError:
    logger.warning("[ai] timeout, usando resposta básica")
    return "Processando... Tente novamente em instantes."
```

---

## Checklist de Resiliência

Para cada módulo novo do OCME, verificar:

```
[ ] Soft import com try/except
[ ] Flag booleana: _MODULO_ENABLED
[ ] Todos os usos verificam a flag
[ ] Fallback gracioso quando módulo off
[ ] Logs: INFO quando carregado, WARNING quando falha
[ ] Timeout configurado em todas as chamadas externas
[ ] Retry com backoff para operações críticas
[ ] Nunca levanta exceção para o bot principal
```

---

## Log Levels de Referência

```python
logger.debug(...)    # Detalhes internos, desativado em produção
logger.info(...)     # Operação normal: "ciclo 21h executado", "usuário autenticado"
logger.warning(...)  # Degradação: "RPC lento, alternando", "rate limit"
logger.error(...)    # Falha real: "DB down", "API key inválida"
logger.critical(...) # Sistema comprometido: não usado normalmente
```

---

## Links

← [[040-tech-stack-ocme]] — A stack sujeita a esses erros
← [[015-rpc-pool]] — Padrão de resilência para RPC
→ [[041-deploy-pattern]] — Como resolver erros em produção
→ [[043-faq-tecnico]] — Perguntas frequentes sobre o sistema
