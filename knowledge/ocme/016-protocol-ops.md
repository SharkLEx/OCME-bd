---
type: knowledge
id: "016"
title: "protocol_ops — A Tabela de Verdade"
layer: L4-ocme
tags: [ocme, database, protocol-ops, sql, eventos]
links: ["003-eventos-logs", "011-subcontas", "012-ciclo-21h", "018-janela-temporal-fechada"]
---

# 016 — protocol_ops: A Tabela de Verdade

> **Ideia central:** `protocol_ops` é a cópia local dos eventos on-chain. É o banco de dados central do OCME — tudo que o relatório 21h calcula vem daqui. É append-only, como a blockchain.

---

## Estrutura da Tabela

```sql
CREATE TABLE protocol_ops (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    block_number INTEGER NOT NULL,     -- bloco on-chain da operação
    tx_hash     TEXT NOT NULL,         -- hash da transação
    wallet      TEXT NOT NULL,         -- endereço do trader
    env         TEXT NOT NULL,         -- 'bd_v5' ou 'AG_C_bd'
    profit      REAL,                  -- lucro líquido em USD
    fee_bd      REAL,                  -- fee paga em BD (0.00963 por op)
    gas_pol     REAL,                  -- gas pago em POL
    ts          TEXT NOT NULL,         -- timestamp UTC do bloco
    created_at  TEXT DEFAULT (datetime('now'))
);

-- Índices para performance
CREATE INDEX idx_protocol_ops_ts ON protocol_ops(ts);
CREATE INDEX idx_protocol_ops_wallet ON protocol_ops(wallet);
CREATE UNIQUE INDEX idx_protocol_ops_tx ON protocol_ops(tx_hash, env);
```

---

## Append-Only: Imitando a Blockchain

A blockchain nunca deleta dados — só adiciona. `protocol_ops` segue o mesmo princípio.

```python
# webdex_workers.py — INSERT OR IGNORE (nunca UPDATE)
cursor.execute("""
    INSERT OR IGNORE INTO protocol_ops
    (block_number, tx_hash, wallet, env, profit, fee_bd, gas_pol, ts)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (block, tx_hash, wallet, env, profit, fee_bd, gas_pol, timestamp))
```

`UNIQUE INDEX` em `(tx_hash, env)` garante **idempotência**: reprocessar o mesmo bloco não duplica dados.

---

## A Query do Relatório 21h

```sql
-- O que o relatório 21h calcula (ciclo fechado)
SELECT
    COUNT(DISTINCT wallet)                            AS traders,
    COUNT(CASE WHEN profit > 0 THEN 1 END)           AS wins,
    COUNT(*)                                          AS total_ops,
    ROUND(SUM(fee_bd), 6)                            AS total_bd,
    ROUND(SUM(CASE WHEN profit > 0 THEN profit
               ELSE 0 END), 4)                       AS pnl_bruto,
    ROUND(SUM(gas_pol), 6)                           AS gas_total
FROM protocol_ops
WHERE ts >= '2026-03-23 00:00:00'   -- início UTC (ontem 21h BRT + 3h)
  AND ts <  '2026-03-24 00:00:00';  -- fim UTC (hoje 21h BRT + 3h)
```

---

## Top 5 Traders

```sql
SELECT
    wallet,
    ROUND(SUM(profit), 4)  AS total_profit,
    ROUND(SUM(fee_bd), 4)  AS total_fee
FROM protocol_ops
WHERE ts >= ? AND ts < ?
GROUP BY wallet
ORDER BY SUM(profit) DESC
LIMIT 5;
```

---

## Crescimento da Tabela

Com ~57.585 ops/ciclo × 365 dias:
```
~21 milhões de linhas/ano

Tamanho estimado por linha: ~200 bytes
= ~4.2 GB/ano
```

Para manter performance, são necessários:
- Índices eficientes (criados)
- Paginação em queries de análise
- Eventual particionamento por data (futura melhoria)

---

## Relação com fl_snapshots

| Tabela | O que guarda | Frequência |
|--------|-------------|-----------|
| `protocol_ops` | Cada operação individual | Contínuo (evento on-chain) |
| `fl_snapshots` | TVL total do protocolo | A cada 30 min |
| `capital_cache` | Capital de cada usuário | A cada 30 min |

`fl_snapshots` é usado para o TVL no relatório (não `protocol_ops`).

→ [[017-snapshot-tvl]] — Como fl_snapshots funciona

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[003-eventos-logs]] — Cada linha veio de um evento on-chain
← [[011-subcontas]] — A wallet em cada linha é uma subconta
→ [[012-ciclo-21h]] — O relatório que usa esta tabela
→ [[018-janela-temporal-fechada]] — O bug de janela afetava esta query
