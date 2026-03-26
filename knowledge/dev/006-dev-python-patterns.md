---
type: knowledge
title: "Dev — Padrões Python: Threading, Graceful Degradation e Error Handling"
tags:
  - dev
  - python
  - patterns
  - threading
  - boas-praticas
created: 2026-03-26
source: neo-sensei
---

# Padrões Python do WEbdEX

> Módulo 06 de 10 — Professor: Neo
> Convenções não escritas que todo arquivo do projeto segue.

---

## Padrão 1 — Graceful Degradation

Nunca deixar um import opcional quebrar o módulo inteiro:

```python
# CORRETO
_MEU_MODULO_ENABLED = False
_minha_funcao = None

try:
    from meu_modulo import minha_funcao as _mf
    _MEU_MODULO_ENABLED = True
    _minha_funcao = _mf
    logger.info("[ai_discord] meu_modulo: ATIVO")
except ImportError:
    logger.warning("[ai_discord] meu_modulo indisponível — feature desativada")

# Uso posterior
if _MEU_MODULO_ENABLED:
    resultado = _minha_funcao(args)
```

**Por que:** Os containers podem rodar sem todos os arquivos opcionais. O bot não pode cair por um feature que não está disponível.

---

## Padrão 2 — Thread Safety com Lock

```python
import threading

# Lock global para proteger uma estrutura compartilhada
_meu_cache: dict = {}
_cache_lock = threading.Lock()

def ler_cache(chave: str):
    with _cache_lock:
        return _meu_cache.get(chave)

def escrever_cache(chave: str, valor):
    with _cache_lock:
        _meu_cache[chave] = valor

# Para escritas SQLite: SEMPRE usar DB_LOCK
from webdex_db import DB_LOCK, conn

def salvar_operacao(dados: dict):
    with DB_LOCK:
        conn.execute(
            "INSERT OR IGNORE INTO operacoes VALUES (?,?,?,?,?)",
            (dados['hash'], dados['log_index'], ...)
        )
        conn.commit()
```

---

## Padrão 3 — Workers Robustos

Todo worker loop deve ser resiliente a falhas:

```python
import time
import logging

logger = logging.getLogger("webdex.meu_worker")

def meu_worker():
    logger.info("[meu_worker] Iniciado")
    while True:
        try:
            _executar_logica()
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error("[meu_worker] Erro inesperado: %s", e, exc_info=True)
            # NÃO re-raise — o worker continua rodando
        time.sleep(60)  # aguarda antes do próximo ciclo
```

---

## Padrão 4 — Logging Consistente

```python
import logging

# Nome do logger segue a hierarquia do módulo
logger = logging.getLogger("webdex.nome_do_modulo")

# Prefixo com nome do worker entre colchetes
logger.info("[meu_worker] Operação processada: hash=%s valor=%.2f", hash, valor)
logger.warning("[meu_worker] RPC lento: %dms", latencia)
logger.error("[meu_worker] Falha crítica: %s", str(e))

# NÃO usar print() — sempre logger
# NÃO incluir secrets nos logs
```

---

## Padrão 5 — Variáveis de Ambiente

```python
import os

# Com valor padrão
VAULT_PATH = os.getenv("VAULT_PATH", "/app/vault")
CACHE_MINUTES = int(os.getenv("VAULT_CACHE_MINUTES", "60"))

# Obrigatória — falha rápida
DB_URL = os.environ["DATABASE_URL"]  # KeyError se ausente = fail fast

# Verificação na inicialização
API_KEY = os.getenv("OPENROUTER_API_KEY", "")
if not API_KEY:
    logger.critical("[ai_discord] OPENROUTER_API_KEY não configurada")
    # NÃO raise — graceful degradation
```

---

## Padrão 6 — Cache com TTL

```python
import time
import threading

class _CacheComTTL:
    def __init__(self, ttl_seconds: int = 3600):
        self._data = None
        self._last_load = 0.0
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    def get(self) -> any:
        with self._lock:
            if time.time() - self._last_load > self._ttl:
                self._data = self._carregar()
                self._last_load = time.time()
            return self._data

    def _carregar(self):
        # implementar carregamento
        pass
```

---

## Padrão 7 — async/await no Discord

O Discord usa `asyncio`. Código bloqueante precisa de `run_in_executor`:

```python
import asyncio

async def minha_funcao_async(dados):
    # CORRETO: código bloqueante (DB, API sync) roda em executor
    resultado = await asyncio.get_event_loop().run_in_executor(
        None, _funcao_bloqueante, dados
    )
    return resultado

# Para calls à API OpenAI: usar AsyncOpenAI (já configurado em ai_handler.py)
```

---

## Padrão 8 — Nomenclatura

```python
# Variáveis de módulo privadas: prefixo _
_CACHE: dict = {}
_client = None

# Funções internas: prefixo _
def _processar_interno(dados):
    pass

# Constantes globais: SCREAMING_SNAKE_CASE
MAX_RETRIES = 3
VAULT_CACHE_MINUTES = 60

# Funções públicas (exportadas): snake_case sem prefixo
def search_vault(query: str) -> list[dict]:
    pass
```
