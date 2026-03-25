---
type: knowledge
id: "008"
title: "Arbitragem Triangular"
layer: L2-defi
tags: [defi, arbitragem, mecânica, webdex]
links: ["006-liquidity-pools", "011-subcontas", "016-protocol-ops"]
---

# 008 — Arbitragem Triangular

> **Ideia central:** Explorar ineficiências de preço entre três pares de trading para lucrar sem risco direcional. É matemática pura, não especulação.

---

## O Conceito

Arbitragem triangular envolve 3 swaps em sequência que voltam à moeda original com mais do que começou:

```
USDT → Token A → Token B → USDT
          ↑           ↑
     swap 1        swap 3
               swap 2
```

**Por que funciona:** Pools de liquidez diferentes têm preços diferentes para os mesmos tokens. Uma ineficiência de 0.1% em três swaps pode gerar lucro líquido após fees.

---

## A Matemática

Condição de lucro:
```
Preço(USDT→A) × Preço(A→B) × Preço(B→USDT) > 1 + fees_totais

Exemplo:
  1 USDT → 0.5 Token A (pool 1: rate 0.5)
  0.5 A  → 200 Token B (pool 2: rate 400)
  200 B  → 1.002 USDT  (pool 3: rate 0.00501)

  Lucro: 0.002 USDT (0.2%) por operação
```

---

## Por que não é especulação

Especulação = apostar na direção do preço.
Arbitragem = explorar diferença de preço **agora**, fechar posição **agora**.

O WEbdEX não fica com posição aberta. Cada operação abre e fecha no mesmo ciclo.

```
Risco direcional: 0
Risco de execução: existe (slippage, gas, timing)
```

---

## O papel das Subcontas

Cada usuário tem uma subconta separada no protocolo. O capital é segregado — o protocolo usa o capital da subconta do usuário para as operações, mas o usuário mantém controle on-chain.

→ [[011-subcontas]] — Como as subcontas funcionam

---

## O que o OCME vê

Cada operação de arbitragem gera um evento `OpenPosition` on-chain:
```
wallet: 0x4f6e...f0f4
profit: 0.0068 USDT
fee_bd: 0.00963 BD
gas_pol: 0.0003 POL
ts: 2026-03-23 14:32:17
```

O relatório 21h agrega **todas** essas operações do ciclo.

**Ciclo 22/03→23/03:**
- 57.585 operações
- WinRate 74.6% (42.933 wins)
- P&L bruto: +$14.773,04

---

## A pergunta de Einstein

**Por que 74.6% de winrate e não 100%?**

Porque algumas operações tentam a arbitragem mas a janela fecha antes da execução (slippage, competição com outros bots, gas). O protocolo tenta, às vezes perde o spread, paga o gas mesmo assim.

74.6% é excelente. Estratégias de HFT tradicionais ficam em 50-60%.

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[006-liquidity-pools]] — De onde vem a ineficiência de preço
→ [[011-subcontas]] — Onde o capital fica
→ [[016-protocol-ops]] — Como o OCME registra cada operação
