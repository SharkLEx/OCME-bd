---
type: knowledge
id: "017"
title: "fl_snapshots — Série Temporal do TVL"
layer: L4-ocme
tags: [ocme, tvl, snapshots, série-temporal, fl]
links: ["007-tvl", "006-liquidity-pools", "016-protocol-ops", "015-rpc-pool"]
---

# 017 — fl_snapshots: Série Temporal do TVL

> **Ideia central:** `fl_snapshots` captura o TVL total do protocolo a cada 30 minutos — criando uma série temporal que permite calcular lucro do protocolo, crescimento de liquidez, e alimentar o relatório 21h com o dado de Liquidez LP.

---

## Estrutura da Tabela

```sql
CREATE TABLE fl_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,         -- timestamp UTC
    env         TEXT NOT NULL,         -- 'bd_v5' ou 'AG_C_bd'
    total_usd   REAL NOT NULL,         -- TVL total em USD
    usdt_balance REAL,                 -- USDT0 nos contratos
    lp_balance  REAL,                  -- LP tokens em circulação
    lp_price    REAL,                  -- preço por LP token (USD)
    block_number INTEGER               -- bloco da leitura
);
```

---

## Como é Populado: fl_snapshot_worker

```python
# webdex_workers.py — roda a cada 30 min
def _fl_snapshot_worker():
    for env_key, contracts in CONTRACTS.items():
        # 1. Ler USDT0 no contrato de pagamentos
        usdt = payments.functions.totalDeposits().call()

        # 2. Ler LP tokens em circulação
        lp_supply = lp_contract.functions.totalSupply().call()

        # 3. Buscar preço LP via DexScreener
        lp_price = _fetch_lp_price_per_unit(web3, lp_addr, lp_dec)

        # 4. Calcular TVL total
        total_usd = (usdt / 10**6) + (lp_supply / 10**18) * lp_price

        # 5. Inserir snapshot
        cursor.execute("""
            INSERT INTO fl_snapshots (ts, env, total_usd, lp_price, block_number)
            VALUES (?, ?, ?, ?, ?)
        """, (now_utc, env_key, total_usd, lp_price, curr_block))
```

---

## O Label "Liquidez LP" no Relatório

```sql
-- Como o relatório 21h calcula o TVL
SELECT ROUND(SUM(f.total_usd), 2)
FROM fl_snapshots f
INNER JOIN (
    SELECT env, MAX(ts) AS max_ts
    FROM fl_snapshots GROUP BY env
) latest ON f.env = latest.env AND f.ts = latest.max_ts
```

Pega o snapshot mais recente de **cada ambiente** e soma. Por isso o label correto é "Liquidez LP" (fonte = fl_snapshots dos LPs) e não "TVL" genérico.

---

## Cache de Preço LP

```python
_lp_price_cache: dict = {}       # limpo a cada ciclo
_lp_price_last_known: dict = {}  # persiste entre ciclos (fallback)

def _fetch_lp_price_per_unit(web3, lp_addr, lp_dec):
    if lp_addr in _lp_price_cache:
        return _lp_price_cache[lp_addr]  # cache do ciclo atual

    # Busca DexScreener
    price = fetch_from_dexscreener(lp_addr)
    if price:
        _lp_price_cache[lp_addr] = price
        _lp_price_last_known[lp_addr] = price  # guarda para fallback
        return price

    # Fallback: último preço válido (não usa 1.0!)
    return _lp_price_last_known.get(lp_addr, None)
```

**Por que não usar 1.0 como fallback?** Um LP token raramente vale exatamente $1. Usar 1.0 geraria TVL incorreto. O OCME prefere omitir o dado a ter dado errado.

---

## Série Temporal: Crescimento de Liquidez

Com snapshots a cada 30 min, é possível calcular:
```sql
-- Crescimento de TVL nos últimos 7 dias
SELECT
    DATE(ts) AS dia,
    MAX(total_usd) AS tvl_max,
    MIN(total_usd) AS tvl_min,
    AVG(total_usd) AS tvl_medio
FROM fl_snapshots
WHERE ts >= datetime('now', '-7 days')
GROUP BY DATE(ts)
ORDER BY dia;
```

Isso alimenta futuramente o dashboard do Epic 13.

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[007-tvl]] — O conceito de TVL
← [[006-liquidity-pools]] — De onde vem o lp_balance
← [[016-protocol-ops]] — A tabela irmã (operações vs TVL)
→ [[015-rpc-pool]] — Como o worker acessa os contratos
