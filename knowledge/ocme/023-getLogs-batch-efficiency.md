---
type: knowledge
id: "023"
title: "getLogs Batch Efficiency — Por que 2000 blocos"
layer: L4-ocme
tags: [ocme, getLogs, performance, batching, alchemy, eip2929]
links: ["003-eventos-logs", "020-gas-economics", "015-rpc-pool", "022-web3py-call-patterns"]
---

# 023 — getLogs Batch Efficiency: Por que 2000 blocos

> **Ideia central:** O tamanho do batch no getLogs não é arbitrário. 2000 blocos é o **máximo da Alchemy free tier** e o ponto ótimo entre eficiência de CU e memória. Mais que isso → erro. Menos → desperdício de quota.

---

## O Constraint da Alchemy

```python
_PROTO_SYNC_BATCH = 2000  # blocos por lote — máx Alchemy getLogs
```

Alchemy free tier limita `eth_getLogs` a 2000 blocos por chamada. Ultrapassar retorna erro:
```
ValueError: {"code":-32602,"message":"eth_getLogs is limited to 2000 blocks range"}
```

---

## Compute Units (CU): A Moeda da Quota

Cada chamada RPC consome CUs:

| Chamada | CU |
|---------|-----|
| `eth_getLogs` | 75 CUs |
| `eth_call` (balanceOf) | 26 CUs |
| `eth_blockNumber` | 10 CUs |
| `eth_getTransactionReceipt` | 15 CUs |

Alchemy free: 300M CUs/dia.

**Com 2 keys (RPC_URL + RPC_CAPITAL):** 600M CUs/dia.

**Uso estimado do OCME (modo incremental):**
```
sync worker:    1 getLogs/30min × 75 CU = 3.600 CU/dia (incremental)
capital worker: 1 eth_call/usuário × 26 CU × ~100 usuários × 48 runs = 124.800 CU/dia
sentinela:      1 call/30s × 26 CU × 2880 runs = 74.880 CU/dia
─────────────────────────────────────────────────────────
Total incremental:  ~203.280 CU/dia  (34% de uma chave)

Backfill (200k blocos gap):
  200.000 blocos / 2.000 por batch = 100 batches
  100 × 75 CU = 7.500 CU em minutos
```

O protocolo está bem dentro dos limites com 2 chaves.

---

## EIP-2929: Por que Batching é Mais Eficiente

(Explicado em [[020-gas-economics]])

Quando o nó RPC processa um `getLogs` de 2000 blocos:
- Primeira vez que acessa o endereço do contrato: **cold** (2100 gas internamente)
- Todas as outras verificações no mesmo batch: **warm** (100 gas)

Para 500 eventos em um batch de 2000 blocos:
```
500 eventos × 100 gas (warm) + 1 × 2100 gas (cold) = 52.100 gas
vs
500 chamadas individuais × 2100 gas = 1.050.000 gas

Eficiência: 20x melhor com batch
```

Isso não afeta o seu custo (calls são grátis), mas afeta o **tempo de resposta** do nó RPC — batch é mais rápido.

---

## O Algoritmo de Sync com Dois Modos

```python
# webdex_workers.py
_PROTO_BACKFILL_THRESHOLD = 200_000  # gap > 200k blocos → backfill

gap = curr_block - last_synced
in_backfill = gap > _PROTO_BACKFILL_THRESHOLD

if in_backfill:
    batch_sleep = 0.3   # 300ms entre batches — agressivo
else:
    batch_sleep = 1.0   # 1s entre batches — respeitoso com RPC

# Processa até 200 batches por ciclo
# Para gap de 200k blocos: 200k/2000 = 100 batches = 100 × 75 CU = 7500 CU
```

**Modo incremental** (dia a dia): ~1 batch/30min — extremamente leve.
**Modo backfill** (deploy novo ou restart): processa histórico completo em horas.

---

## O Sleep de 300ms — Não é Opcional

```python
time.sleep(batch_sleep)  # 0.3s em backfill
```

Por que 300ms e não 0ms?

1. **Rate limiting do RPC:** Alchemy free tier tem limite de 330 req/s. 300ms = ~3 req/s — confortável.
2. **CPU do VPS:** 100% de CPU por horas durante backfill causaria impacto no bot principal.
3. **Cortesia:** RPC providers desaceleram ou bloqueiam clients que spammam.

---

## A Janela de 200 Batches por Ciclo

```python
to_block = min(curr_block, from_block + batch_size * 200)
```

Por que limitar a 200 batches (400.000 blocos) por ciclo?

Sem limite, o sync poderia rodar por **horas** num único ciclo, bloqueando outras threads. Com 200 batches:
- Backfill de 400k blocos por ciclo
- Depois dorme e deixa outras threads respirar
- No próximo ciclo, continua de onde parou (via `proto_sync_block_*` config)

---

## Diagrama do Fluxo Completo

```
início do ciclo
     ↓
curr_block = web3.eth.block_number  (eth_blockNumber = 10 CU)
last_synced = get_config('proto_sync_block_bd_v5')
     ↓
gap = curr_block - last_synced
     ↓
┌──────────────────┐         ┌───────────────────┐
│ gap > 200.000    │         │ gap ≤ 200.000      │
│ BACKFILL MODE    │         │ INCREMENTAL MODE   │
│ sleep: 0.3s      │         │ sleep: 1.0s        │
│ até 200 batches  │         │ até 200 batches    │
└──────────────────┘         └───────────────────┘
          ↓                            ↓
    getLogs(from, to)          getLogs(from, to)
    decode events              decode events
    INSERT protocol_ops        INSERT protocol_ops
    set_config(last_block)     set_config(last_block)
          ↓                            ↓
    sleep(5s)                  sleep(1800s = 30min)
```

---

## Conexões Einstein

**Batch size ↔ CU economics:** 2000 blocos não é só o limite da Alchemy — é também o ponto onde uma única chamada cobre ~66 minutos de dados do Polygon (2000 × 2s = ~4000s ≈ 66min). Um batch por hora é suficiente para modo incremental.

**300ms sleep ↔ 330 req/s limit:** 300ms × 330 = 99 segundos. O OCME em backfill agressivo poderia usar até 100% do rate limit se rodasse sozinho. Com outros workers rodando, 300ms garante que o sync não monopoliza a quota.

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[003-eventos-logs]] — O que getLogs busca
← [[020-gas-economics]] — EIP-2929 warm/cold access
← [[015-rpc-pool]] — Os endpoints usados
← [[022-web3py-call-patterns]] — Como get_logs() é chamado
