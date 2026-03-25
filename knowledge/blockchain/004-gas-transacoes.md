---
type: knowledge
id: "004"
title: "Gas e Transações — O Custo Computacional"
layer: L1-fundamentos
tags: [blockchain, gas, transações, fundamentos]
links: ["020-gas-economics", "002-smart-contracts", "021-polygon-bor-heimdall"]
---

# 004 — Gas e Transações

> **Ideia central:** Gas é o combustível da EVM. Cada operação tem um preço em gas. Você paga gas × gas_price em ETH/POL. Leituras são gratuitas; escritas custam.

---

## Gas = Unidade de Medida Computacional

```
Gas ≠ POL/ETH

Gas = quanto "trabalho" a EVM faz
Gas price = quanto você paga por unidade de trabalho
Custo total = Gas usado × Gas price
```

Por que separar as duas coisas? Para que o custo computacional (gas) seja estável enquanto o preço da moeda (POL/ETH) flutua.

---

## Custos Base de Operações Comuns

| Operação | Gas | O que faz |
|----------|-----|-----------|
| Transferência ETH/POL | 21.000 | Mover valor entre contas |
| SLOAD (ler storage) cold | 2.100 | Ler variável do contrato |
| SLOAD (ler storage) warm | 100 | Ler variável já acessada |
| SSTORE (escrever storage) | 20.000 | Modificar variável |
| Criar contrato | 32.000+ | Deploy novo smart contract |
| LOG (emitir evento) | 375 + 8×bytes | Emitir evento no bloco |

O evento `OpenPosition` do WEbdEX custa ~375 + 8×(dados) gas.

---

## No WEbdEX: Quem paga o gas?

```
Operação de arbitragem (transação on-chain):
  Gas = ~200.000
  Gas price = 30 Gwei = 30×10⁻⁹ POL
  Custo = 200.000 × 30×10⁻⁹ = 0,006 POL ≈ $0,0012

O protocolo desconta o gas da subconta do usuário (gas_pol na protocol_ops)
```

Gas é parte do custo de cada operação — por isso aparece como `gas_pol` nos dados.

---

## Sentinela de Gas Alto

O OCME monitora o preço do gas em tempo real:

```python
# webdex_workers.py — sentinela
gwei = web3.eth.gas_price / 10**9
if gwei > LIMITE_GWEI:
    send_html(cid, f"🔥 GÁS ALTO: {gwei:.0f} Gwei")
```

Quando gas está muito alto, as operações de arbitragem podem se tornar não-lucrativas — o custo supera o spread.

---

## Links

← [[MOC-Blockchain-Intelligence]]
→ [[020-gas-economics]] — Análise profunda do sistema de gas
→ [[002-smart-contracts]] — O código que consome gas
→ [[021-polygon-bor-heimdall]] — Por que Polygon tem gas barato
