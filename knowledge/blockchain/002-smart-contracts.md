---
type: knowledge
id: "002"
title: "Smart Contracts"
layer: L1-fundamentos
tags: [blockchain, smart-contracts, fundamentos]
links: ["001-consenso-distribuido", "003-eventos-logs", "011-subcontas"]
---

# 002 — Smart Contracts

> **Ideia central:** Um programa que existe on-chain e executa automaticamente quando condições são atendidas. Sem servidor, sem empresa, sem intermediário.

---

## O Conceito

Um smart contract é código deployado na blockchain. Uma vez publicado:
- **Não pode ser alterado** (exceto se projetado para upgrade)
- **Executa automaticamente** quando chamado
- **Resultado é público** — qualquer um pode verificar

```python
# Analogia: um contrato de aluguel tradicional
# vs um smart contract

# TRADICIONAL: você assina papel, confia no cartório
# SMART CONTRACT: você chama uma função, a blockchain executa

# Exemplo simplificado
def depositar(valor, wallet):
    if valor > 0:
        saldo[wallet] += valor
        emit Deposito(wallet, valor)  # evento on-chain
```

---

## ABI — A Interface do Contrato

ABI (Application Binary Interface) é o "manual" do contrato: define quais funções existem e o que cada uma recebe/retorna.

```json
{
  "name": "balanceOf",
  "inputs": [{"name": "account", "type": "address"}],
  "outputs": [{"type": "uint256"}],
  "stateMutability": "view"
}
```

**`stateMutability: "view"`** → leitura apenas, sem gas, sem modificação de estado.

---

## Call vs Transaction

| Tipo | Modifica estado? | Gasta gas? | Resultado |
|------|-----------------|-----------|-----------|
| **Call** | Não | Não | Imediato |
| **Transaction** | Sim | Sim | Confirmado em ~2s (Polygon) |

O OCME faz predominantemente **calls** (leitura) — mais barato e mais rápido.

```python
# O que o OCME faz
saldo = contract.functions.balanceOf(wallet).call()  # call — sem gas

# O que um usuário faz ao depositar
tx = contract.functions.depositar(valor).transact()  # transaction — gas
```

---

## No contexto WEbdEX

O WEbdEX tem múltiplos contratos por ambiente:

| Contrato | Função |
|----------|--------|
| **SubAccounts** | Guarda capital dos usuários (non-custodial) |
| **Payments** | Processa fees em USDT0 |
| **Token BD** | ERC-20 padrão, supply fixo |

O OCME lê esses contratos constantemente via `web3.py`:
```python
# webdex_chain.py — o que o OCME realmente faz
contract.functions.balanceOf(wallet).call(block_identifier=block_number)
```

---

## Conexão não-óbvia

Smart contracts geram **eventos** quando executam. Esses eventos são a fonte de dados do OCME.

→ [[003-eventos-logs]] — Como o OCME lê o histórico de contratos

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[001-consenso-distribuido]] — O que torna o contrato confiável
→ [[003-eventos-logs]] — O que o contrato emite
→ [[011-subcontas]] — O contrato mais importante do WEbdEX
