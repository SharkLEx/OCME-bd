---
type: knowledge
id: "011"
title: "Subcontas — Non-Custodial Real"
layer: L3-webdex
tags: [webdex, subcontas, non-custodial, smart-contract, capital]
links: ["002-smart-contracts", "008-arbitragem-triangular", "010-triade-risco-responsabilidade-retorno", "016-protocol-ops"]
---

# 011 — Subcontas: Non-Custodial Real

> **Ideia central:** Cada usuário do WEbdEX tem uma subconta separada no smart contract. O protocolo opera sobre esse capital, mas o usuário mantém controle on-chain a qualquer momento.

---

## O que é Non-Custodial

**Custodial (exchange centralizada):** Você deposita, a exchange guarda. Você confia que eles não vão sumir.

**Non-custodial (WEbdEX):** Seu capital está num smart contract. O protocolo tem permissão para **usar** esse capital para arbitragem, mas não pode **transferir** para outra carteira.

```
Contrato SubAccounts (bd_v5): 0x6995077c49d920D8516AF7b87a38FdaC5E2c957C
Contrato SubAccounts (AG_C_bd): 0x14eEd4F2Bfcfd85E2262987Cf8cbcD97B02557ca
```

Qualquer um pode verificar no PolygonScan que o capital existe no contrato.

---

## Estrutura On-Chain da Subconta

```solidity
mapping(address => SubAccount) public subAccounts;

struct SubAccount {
    uint256 balance_usdt;      // capital disponível para operar
    uint256 balance_loop;      // capital em LP
    bool active;               // operações habilitadas
    uint256 cumulative_profit; // lucro acumulado histórico
    uint256 cumulative_fee;    // fees BD pagas
}
```

O OCME lê esses dados continuamente.

---

## Como o OCME rastreia as subcontas

```python
# webdex_workers.py — _capital_snapshot_worker
users = cursor.execute(
    "SELECT chat_id, wallet, env, rpc FROM users WHERE wallet<>'' AND active=1"
).fetchall()

for chat_id, wallet, env, rpc in users:
    # Lê saldo diretamente do contrato (call — sem gas)
    usdt_balance = subaccounts.functions.getBalance(wallet).call()
    lp_balance = lp_contract.functions.balanceOf(wallet).call()

    total_usd = usdt_balance + (lp_balance × lp_price_per_unit)

    # Salva snapshot local
    cursor.execute("INSERT INTO capital_cache VALUES (?, ?, ?, ?)",
                   (chat_id, wallet, total_usd, now()))
```

---

## Os Dois Ambientes

| Ambiente | SubAccounts | TVL aprox | Perfil |
|----------|-------------|-----------|--------|
| **bd_v5** | `0x6995...7C` | ~$1.02M | Principal, maior volume |
| **AG_C_bd** | `0x14eE...ca` | ~$397K | Alternativo |

O usuário escolhe o ambiente ao se cadastrar. O OCME rastreia ambos.

---

## Responsabilidade Distribuída na Prática

```
Usuário deposita USDT no contrato SubAccounts
     ↓
Protocolo detecta novo capital disponível
     ↓
Motor de arbitragem usa o capital para operações
     ↓
Lucro ou perda é creditado na subconta
     ↓
Usuário pode sacar a qualquer momento (sem lock)
```

Em nenhum momento o protocolo "segura" o dinheiro fora do contrato on-chain.

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[002-smart-contracts]] — O smart contract onde as subcontas vivem
← [[008-arbitragem-triangular]] — O que o protocolo faz com o capital
→ [[010-triade-risco-responsabilidade-retorno]] — Responsabilidade aplicada
→ [[016-protocol-ops]] — Como cada operação é registrada
