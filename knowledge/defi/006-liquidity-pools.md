---
type: knowledge
id: "006"
title: "Liquidity Pools — Como funciona a liquidez DeFi"
layer: L2-defi
tags: [defi, liquidity-pools, amm, lp, tvl]
links: ["001-consenso-distribuido", "007-tvl", "008-arbitragem-triangular", "009-tokenomics"]
---

# 006 — Liquidity Pools: Liquidez sem Banco

> **Ideia central:** Em DeFi, não há market makers humanos. Há pools de liquidez — contratos que mantêm dois tokens em reserva e permitem swaps automaticamente, usando uma fórmula matemática.

---

## O Modelo Tradicional vs AMM

```
TRADICIONAL (Order Book):
  Comprador ↔ [Exchange central] ↔ Vendedor
  Precisa de market makers humanos para manter liquidez

DEFI (AMM — Automated Market Maker):
  Usuário ↔ [Smart Contract com reservas de Token A + Token B] ↔ Usuário
  A fórmula matemática É o market maker
```

---

## A Fórmula Invariante (Uniswap v2)

```
x × y = k

x = reserva do Token A
y = reserva do Token B
k = constante (nunca muda, a não ser quando LP adiciona/remove liquidez)
```

**Exemplo:**
```
Pool USDT/BD: x=100.000 USDT, y=50.000 BD, k=5×10⁹

Alguém compra 1.000 BD:
  y' = 50.000 - 1.000 = 49.000
  x' = k / y' = 5×10⁹ / 49.000 = 102.040,8 USDT
  → Preço pago: 102.040,8 - 100.000 = 2.040,8 USDT por 1.000 BD
  → Preço médio: $2.04 por BD (vs $2.00 antes da compra)
```

O preço sobe com a compra — **slippage** automático que protege a pool.

---

## LP Tokens: Recibo de Participação

Quando você deposita liquidez numa pool, recebe **LP tokens** proporcional à sua participação:

```
Você deposita: 10.000 USDT + 5.000 BD
Pool tem: 100.000 USDT + 50.000 BD  (10% é seu)
Você recebe: 1.000 LP tokens (se supply total = 10.000)
```

No WEbdEX, os LP tokens são rastreados pelo OCME em `lp_balance` nas subcontas.

---

## Como o TVL é calculado

```python
# fl_snapshot_worker no OCME
# Valor do LP = TVL da pool × (seu LP / supply total LP)

lp_price_per_unit = tvl_pool / lp_total_supply  # USD por LP token
lp_value_usd = lp_balance × lp_price_per_unit
```

O OCME busca o preço por LP token via DexScreener (sem API key), com fallback para último preço válido.

---

## Impermanent Loss: O Risco do LP

```
Você depositou: 50% USDT + 50% BD (ao preço $2 por BD)
BD sobe para $4: a pool rebalanceia automaticamente
Quando você saca: você tem menos BD (vendeu durante a subida) e mais USDT
vs Ter segurado BD: você teria mais valor

Diferença = Impermanent Loss
```

É "impermanente" porque volta a zero se os preços retornam à proporção original. Se você saca durante a divergência, a perda é realizada.

**Para o WEbdEX:** As fees geradas pela pool compensam o IL quando o protocolo tem bom volume.

---

## Links

← [[MOC-Blockchain-Intelligence]]
→ [[007-tvl]] — Como a liquidez se traduz em TVL
→ [[008-arbitragem-triangular]] — Como as pools criam oportunidades de arb
→ [[009-tokenomics]] — Como o token BD flui pelas pools
