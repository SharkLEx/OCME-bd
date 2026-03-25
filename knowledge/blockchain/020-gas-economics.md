---
type: knowledge
id: "020"
title: "Gas Economics — Por que o OCME lê de graça"
layer: L1-fundamentos
tags: [evm, gas, economia, eficiência, ocme]
links: ["019-evm-state-machine", "002-smart-contracts", "021-polygon-bor-heimdall", "023-getLogs-batch-efficiency"]
fonte: https://evm.codes/about
---

# 020 — Gas Economics: Por que o OCME lê de graça

> **Ideia central:** Gas é o preço computacional da EVM. Operações de LEITURA não modificam estado → não pagam gas. O OCME faz 99% leitura → custo de blockchain = quase zero.

---

## A Estrutura do Gas

```
Custo total de uma tx = base_fee + priority_fee (tip)

base_fee   = determinado pelo protocolo (varia com congestionamento)
priority_fee = gorjeta para o validador (você escolhe)

Gas total consumido = 21.000 (base) + opcodes executados + calldata
```

**Base de 21.000 gas** é o custo mínimo de qualquer transação — só pelo fato de existir.

---

## Call vs Transaction: A Diferença Fundamental

| Operação | Modifica estado? | Gasta gas? | Custo real |
|----------|-----------------|-----------|-----------|
| `call()` | Não | **Não** | $0.00 |
| `transact()` | Sim | **Sim** | ~$0.001-0.01 no Polygon |

O OCME usa `call()` para:
- `balanceOf(wallet)` → saldo do usuário
- `totalSupply()` → supply do token
- Todos os reads de estado do protocolo

O OCME usa `transact()` para: **nada** — ele só lê, nunca escreve.

```python
# webdex_chain.py — leituras sem gas
saldo = contract.functions.balanceOf(wallet).call()           # GRÁTIS
supply = contract.functions.totalSupply().call()               # GRÁTIS

# O que seria uma escrita (o OCME não faz isso)
tx = contract.functions.transfer(dest, amount).transact()     # PAGO
```

---

## Calldata: O Custo de Transmissão

Mesmo em calls gratuitas, há um custo de transmissão (pago pelo RPC provider, não por você):

```
Calldata: 4 gas por byte zero / 16 gas por byte não-zero
```

Uma chamada `balanceOf(address)` tem:
- 4 bytes de selector (assinatura da função) = ~64 gas
- 20 bytes de endereço = ~320 gas

Total: ~384 gas de "calldata" — mas como é call(), você não paga.

---

## Warm vs Cold Access (EIP-2929)

Introduzido no hard fork Berlin (2021). **Primeira vez** que você acessa um endereço ou slot de storage em uma transação:

```
Cold SLOAD (primeiro acesso a um slot): 2.100 gas
Warm SLOAD (acesso subsequente ao mesmo slot): 100 gas
```

**Para o OCME — insight não-óbvio:**

Quando o `_protocol_ops_sync_worker` busca 2000 blocos de logs em um batch, a EVM processa eventos do mesmo contrato repetidamente. Por EIP-2929, após o primeiro acesso ao endereço do contrato, todos os acessos subsequentes são "warm" (100 gas vs 2.100 gas).

Isso significa que batch de 2000 blocos é **21x mais eficiente** em gas por evento do que 2000 chamadas individuais.

→ [[023-getLogs-batch-efficiency]] — Como o OCME maximiza essa eficiência

---

## Gas Refunds: O Detalhe do London Hardfork

Antes do London (2021): refund de até 50% do gas se você deletava storage (SSTORE → 0).
Depois do London: refund limitado a 20% (1/5) do total da tx.

**Para o WEbdEX:** Operações que fazem reset de posições (fechar arbitragem) costumavam ser mais baratas. Pós-London, o protocolo precisa ser mais eficiente em gas.

---

## Memory Expansion: A Armadilha Quadrática

```python
# Custo de expandir memória na EVM
memory_size_word = (memory_byte_size + 31) // 32
memory_cost = (memory_size_word ** 2) // 512 + (3 * memory_size_word)
```

Custo cresce **quadraticamente** com o tamanho da memória. Um getLogs que retorna 10.000 logs usa muito mais memória que 10 requests de 1 log cada — mas o overhead de 10.000 requests separados supera o custo quadrático.

O sweet spot: batches de ~2000 blocos (configuração atual do OCME).

---

## Por que Polygon é barato

Polygon PoS usa **POL** para gas, não ETH. Com POL a ~$0.20:

```
Gas price típico: 30 Gwei = 30 × 10⁻⁹ POL
Operação de 200.000 gas = 200.000 × 30 × 10⁻⁹ POL = 0.006 POL
Em USD: 0.006 × $0.20 = $0.0012

vs Ethereum mainnet com ETH a $3000:
mesma operação = ~$12.00
```

O WEbdEX opera no Polygon justamente porque operações de arbitragem com margem de 0.1% precisam de gas < margem. No mainnet Ethereum, seria inviável.

→ [[021-polygon-bor-heimdall]] — A arquitetura que torna isso possível

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[019-evm-state-machine]] — A máquina que consome gas
→ [[021-polygon-bor-heimdall]] — Por que Polygon tem gas barato
→ [[023-getLogs-batch-efficiency]] — Otimização de gas no OCME
