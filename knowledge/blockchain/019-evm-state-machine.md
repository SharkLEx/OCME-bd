---
type: knowledge
id: "019"
title: "EVM — Máquina de Estados Determinística"
layer: L1-fundamentos
tags: [evm, estado, determinismo, fundamentos]
links: ["001-consenso-distribuido", "002-smart-contracts", "018-janela-temporal-fechada", "022-web3py-call-patterns"]
fonte: https://ethereum.org/en/developers/docs/evm/
---

# 019 — EVM: Máquina de Estados Determinística

> **Ideia central:** A EVM não é um banco de dados. É uma função matemática: `Y(S, T) = S'`. Dado um estado S e uma transação T, **sempre** produz o mesmo novo estado S'. Sem aleatoriedade, sem exceções.

---

## A Equação Fundamental

```
Y(S, T) = S'

S  = Estado atual (todos os saldos, código, storage de todos os contratos)
T  = Transação (instruções assinadas)
S' = Novo estado após executar T
```

Isso é **determinismo absoluto**. Qualquer nó do mundo, dado o mesmo S e T, chega ao mesmo S'.

---

## Implicação 1: Por que o relatório 21h é verificável

O OCME gera um relatório: "57.585 operações, WinRate 74.6%, P&L +$14.773".

Como verificar? Execute a mesma query contra o mesmo range de blocos on-chain. O resultado será **idêntico** — porque a EVM é determinística. Os dados não mudam, o passado é imutável.

```python
# Qualquer um pode rodar isso e confirmar o relatório
logs = web3.eth.get_logs({
    'fromBlock': 67_834_521,   # bloco do início do ciclo
    'toBlock':   67_877_234,   # bloco do fim do ciclo
    'address':   CONTRATO_WEBDEX,
    'topics':    [TOPIC_OPENPOSITION]
})
# O resultado será sempre o mesmo para esses blocos
```

→ [[018-janela-temporal-fechada]] — Por que janela fechada = resultado determinístico

---

## Implicação 2: O Estado como Merkle Patricia Trie

O estado global (S) é armazenado como uma **Merkle Patricia Trie** — uma árvore onde cada folha é um valor e cada nó interno é o hash dos filhos.

```
       [Root Hash]
      /           \
  [Hash AB]     [Hash CD]
  /    \         /    \
[A]   [B]     [C]    [D]
```

O Root Hash do bloco N **captura o estado completo do mundo** naquele bloco.

**Para o OCME:** Quando chamamos `balanceOf(wallet, block_identifier=67_834_521)`, estamos navegando a trie do bloco 67.834.521 — lendo o estado exato do passado.

```python
# OCME lê o estado histórico com precisão cirúrgica
saldo_passado = contract.functions.balanceOf(wallet).call(
    block_identifier=67_834_521  # ← pino no estado histórico
)
```

---

## Implicação 3: Stack Machine com 256-bit Words

A EVM é uma **stack machine** (não registradores) com:
- Profundidade máxima: 1024 elementos
- Tamanho de cada elemento: 256 bits (32 bytes)

Por que 256 bits? Porque keccak256 (o hash usado em tudo) produz 256 bits. Os endereços Ethereum são 160 bits (últimos 20 bytes de um hash de 256 bits).

**Para o OCME:** O endereço de wallet que lemos nos logs é esses 160 bits. O `topics[1]` vem zero-padded para 256 bits:
```
topics[1] = 0x000000000000000000000000 + endereço_20_bytes
```

O decode correto:
```python
wallet = '0x' + log['topics'][1].hex()[-40:]  # últimos 40 chars hex = 20 bytes
```

---

## Implicação 4: Revert — Tudo ou Nada

Se uma transação falhar (gas insuficiente, condição não atendida, REVERT explícito), **todo o estado volta ao ponto anterior**. Não existe "transação parcialmente executada".

**Para o protocolo WEbdEX:** Uma operação de arbitragem que falha no meio não deixa o usuário com posição aberta. Ou executa completa, ou volta ao estado original. Isso é segurança por design.

**Na protocol_ops:** Operações com `profit < 0` são operações que executaram (gas foi pago) mas o spread foi insuficiente. Não são reverts — são execuções legítimas com resultado negativo.

---

## Conexões Einstein

**EVM determinismo ↔ Blockchain como source of truth:**
O WEbdEX pode afirmar "nossa performance é X%" porque X% é uma função determinística dos dados on-chain. Ninguém pode contestar — qualquer pessoa pode recalcular.

**Merkle Trie ↔ Time Travel:**
`block_identifier` é literalmente viagem no tempo. Você "visita" o estado exato do blockchain em qualquer momento passado. O OCME usa isso para construir série histórica de capital.

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[001-consenso-distribuido]] — O que garante que todos chegam ao mesmo S'
← [[002-smart-contracts]] — O código que a EVM executa
→ [[018-janela-temporal-fechada]] — Determinismo aplicado aos relatórios
→ [[022-web3py-call-patterns]] — Como o OCME usa block_identifier na prática
→ [[020-gas-economics]] — O custo de cada operação na EVM
