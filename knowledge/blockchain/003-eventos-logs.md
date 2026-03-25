---
type: knowledge
id: "003"
title: "Eventos e Logs"
layer: L1-fundamentos
tags: [blockchain, eventos, logs, indexação]
links: ["002-smart-contracts", "016-protocol-ops", "015-rpc-pool"]
---

# 003 — Eventos e Logs

> **Ideia central:** Toda ação relevante num smart contract emite um evento — um registro imutável e indexável que qualquer observador pode ler.

---

## O Conceito

Quando um smart contract executa uma operação importante, ele **emite um evento**:

```solidity
// No contrato Solidity
event OpenPosition(address indexed wallet, uint256 amount, uint256 timestamp);

function abrirPosicao(uint256 valor) external {
    // ... lógica de negócio ...
    emit OpenPosition(msg.sender, valor, block.timestamp);
}
```

Esse evento fica gravado nos **logs do bloco** para sempre. É o ledger imutável.

---

## Como o OCME Lê Eventos

O OCME usa `getLogs` para buscar eventos por range de blocos:

```python
# webdex_chain.py — o coração do OCME
logs = web3.eth.get_logs({
    'fromBlock': bloco_inicio,
    'toBlock': bloco_fim,
    'address': contrato_address,
    'topics': [TOPIC_OPENPOSITION]  # filtro por tipo de evento
})

for log in logs:
    wallet = decode_address(log['topics'][1])
    amount = decode_uint256(log['data'])
    # salva em protocol_ops
```

---

## Topics — O Sistema de Índice

Cada evento tem até 4 `topics`. O primeiro é sempre o hash da assinatura do evento:

```
TOPIC_OPENPOSITION = keccak256("OpenPosition(address,uint256,uint256)")
= 0x3f8456... (hex)
```

Isso permite filtrar só eventos relevantes sem baixar toda a blockchain.

---

## A Estrutura do Dado

```
Log {
  blockNumber: 67834521,        # em qual bloco
  blockHash: "0xabc...",        # hash do bloco
  transactionHash: "0xdef...",  # tx que gerou
  address: "0x6995...",         # contrato que emitiu
  topics: [                     # parâmetros indexed
    "0x3f84...",               # assinatura do evento
    "0x0000...wallet_address"  # wallet (indexed)
  ],
  data: "0x0000...amount"      # parâmetros não-indexed
}
```

---

## Por que isso é poderoso

1. **Imutável** — ninguém pode deletar um log
2. **Verificável** — qualquer um pode confirmar no PolygonScan
3. **Indexável** — getLogs com filtros é eficiente
4. **Histórico completo** — do bloco de deploy até agora

O OCME tem acesso ao histórico **completo desde o dia do deploy** do contrato WEbdEX.

---

## Conexão não-óbvia: Logs → protocol_ops

O fluxo real no OCME:
```
Bloco on-chain
  → getLogs (TOPIC_OPENPOSITION)
    → decode(wallet, amount, timestamp)
      → INSERT INTO protocol_ops
        → SELECT para relatório 21h
          → Telegram + Discord
```

Cada linha da tabela `protocol_ops` veio de um evento on-chain.

→ [[016-protocol-ops]] — A tabela que armazena esses eventos

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[002-smart-contracts]] — O que gera os eventos
→ [[015-rpc-pool]] — Como o OCME se conecta para ler os logs
→ [[016-protocol-ops]] — Onde os eventos são persistidos
→ [[018-janela-temporal-fechada]] — Por que o timestamp importa
