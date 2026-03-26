---
type: knowledge
title: "Dev — Monitor Engine: Workers, Ciclos e Blockchain"
tags:
  - dev
  - monitor-engine
  - workers
  - blockchain
created: 2026-03-26
source: neo-sensei
---

# Monitor Engine: Workers, Ciclos e Blockchain

> Módulo 02 de 10 — Professor: Neo
> O coração do protocolo. Tudo começa aqui.

---

## Entry Point: webdex_main.py

O `webdex_main.py` inicia todos os workers como threads separadas:

```python
# Threads que rodam em paralelo
threading.Thread(target=sentinela_worker, daemon=True).start()
threading.Thread(target=agendador_21h_worker, daemon=True).start()
threading.Thread(target=capital_snapshot_worker, daemon=True).start()
threading.Thread(target=user_capital_refresh_worker, daemon=True).start()
threading.Thread(target=subscription_worker_loop, daemon=True).start()
threading.Thread(target=funnel_worker, daemon=True).start()
```

Cada worker é uma função em `webdex_workers.py` com loop `while True` + `time.sleep()`.

---

## O Ciclo de 21 Horas (agendador_21h)

O ciclo de 21h é o coração financeiro do protocolo:

```
00:00 BRT ← Nightly Trainer (aprende conversas, escreve vault)
21:00 BRT ← agendador_21h dispara
  ↓
capital_snapshot() ← lê subcontas on-chain → salva no DB
user_capital_refresh() ← atualiza capital por usuário
  ↓
webdex_ai_digest.py ← gera narrativa do ciclo (Claude)
webdex_ai_image.py  ← gera card visual (PIL ou Creatomate)
webdex_ai_content.py ← formata post Discord/Telegram
  ↓
notify_protocolo_relatorio() ← webhook Discord #relatorio
_gerar_post_telegram() ← Telegram (grupo de usuários)
  ↓
(opcional) _proactive_nudge() ← mensagem de engajamento
(opcional) _cycle_bdzinho()   ← animação expressão bdZinho
```

---

## Sentinel Worker (sentinela)

O `sentinela` monitora operações em tempo real:

```python
# Loop principal em webdex_monitor.py
def vigia():
    while True:
        operacoes_novas = _scan_novos_blocos()
        for op in operacoes_novas:
            salvar_operacao(op)          # SQLite
            notificar_usuario(op)        # Telegram/Discord
            atualizar_stats_protocolo()  # métricas
        time.sleep(5)  # polling a cada 5s
```

---

## Banco de Dados SQLite (webdex_db.py)

**CRÍTICO — thread-local connections:**
```python
# CORRETO: cada thread cria sua própria conexão
_thread_local = threading.local()

def _get_thread_conn():
    if not hasattr(_thread_local, 'conn'):
        _thread_local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        # aplica PRAGMAs: WAL, cache 8000 páginas, temp_store=MEMORY
    return _thread_local.conn

# DB_LOCK: serializa TODAS as escritas (evita SQLITE_BUSY)
DB_LOCK = threading.Lock()
```

**Regra de ouro:** NUNCA compartilhar uma conexão SQLite entre threads. O `_ConnProxy` gerencia isso automaticamente.

---

## Tabelas SQLite Principais

```sql
-- Operações do protocolo (core)
CREATE TABLE operacoes (
    hash TEXT, log_index INTEGER,
    data_hora TEXT, tipo TEXT,     -- 'swap', 'deposit', 'withdraw'
    valor REAL, gas_usd REAL,
    token TEXT, sub_conta TEXT,
    ambiente TEXT,                 -- 'bd_v5' ou 'AG_C_bd'
    PRIMARY KEY (hash, log_index)
);

-- Usuários Telegram/Discord
CREATE TABLE users (
    chat_id INTEGER PRIMARY KEY,
    wallet TEXT, env TEXT,
    ai_enabled INTEGER DEFAULT 1,
    subscription_expires TEXT      -- atualizado pelo subscription_worker
);

-- Config chave-valor (state dos workers)
CREATE TABLE config (
    chave TEXT PRIMARY KEY,
    valor TEXT
);
-- Exemplo: config WHERE chave='sub_last_block' → último bloco processado
```

---

## Blockchain (webdex_chain.py)

Todos os acessos on-chain passam por `webdex_chain.py`:

```python
# Leitura de saldo de subconta
def get_subconta_balance(sub_addr: str, env: str) -> float:
    contract = _get_contract(env)  # bd_v5 ou AG_C_bd
    return contract.functions.getBalance(sub_addr).call()

# Pool de RPCs com fallback automático (round-robin)
# RPC_URL (Alchemy 1) → RPC_CAPITAL (Alchemy 2) → RPC_FALLBACK (1rpc.io)
# Cooldown 60s após erro -32001 (quota Alchemy)
```

---

## Como Adicionar um Novo Worker

1. **Criar função** em `webdex_workers.py`:
```python
def meu_worker():
    logger.info("[meu_worker] Iniciado")
    while True:
        try:
            # lógica aqui
            pass
        except Exception as e:
            logger.error("[meu_worker] Erro: %s", e)
        time.sleep(300)  # a cada 5 minutos
```

2. **Registrar** em `webdex_main.py`:
```python
threading.Thread(target=meu_worker, daemon=True, name="meu_worker").start()
```

3. **Importar** dependências no topo com try/except (graceful degradation).

---

## Como Adicionar uma Nova Notificação Telegram

Em `notification_engine.py`:
```python
def notify_meu_evento(chat_id: int, dados: dict):
    texto = f"🎯 *Evento:* {dados['valor']:.2f}"
    send_html(bot, chat_id, texto)
```

Chamar de `webdex_workers.py` ou `webdex_monitor.py` quando o evento ocorrer.
