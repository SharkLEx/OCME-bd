---
type: knowledge
id: "001"
title: "Consenso Distribuído"
layer: L1-fundamentos
tags: [blockchain, fundamentos, consenso]
links: ["002-smart-contracts", "005-finality-blocos"]
---

# 001 — Consenso Distribuído

> **Ideia central:** Milhares de máquinas concordam sobre o mesmo estado sem precisar confiar umas nas outras.

---

## O Conceito

Numa rede centralizada, existe uma fonte da verdade: o servidor.
Numa blockchain, **não existe servidor**. Existe consenso.

Cada nó da rede mantém uma cópia completa do histórico. Para que uma transação seja "real", a **maioria dos nós precisa concordar** que ela aconteceu — usando regras matemáticas, não confiança humana.

```
BANCO TRADICIONAL         BLOCKCHAIN
──────────────────        ────────────────────
   [Servidor]             [Nó] [Nó] [Nó]
       │                   │    │    │
  [Você confia]            └────┴────┘
                           todos concordam
                           via matemática
```

---

## Por que isso é revolucionário

**Problema antigo:** Como dois desconhecidos podem trocar valor sem intermediário?

**Resposta blockchain:** O código é o intermediário. As regras são públicas, verificáveis, imutáveis.

Isso elimina:
- Risco de contraparte (a outra parte pode dar calote)
- Risco de custódia (o banco pode congelar sua conta)
- Risco de censura (ninguém pode bloquear sua transação)

---

## No contexto WEbdEX

O WEbdEX não pede para você **confiar** na empresa. O protocolo existe on-chain: qualquer pessoa pode verificar que as subcontas existem, que o capital está lá, que as operações aconteceram.

> *"Não confie em nós. Verifique você mesmo."*

Endereço do contrato SubAccounts (bd_v5): `0x6995077c49d920D8516AF7b87a38FdaC5E2c957C`
Qualquer um pode checar no PolygonScan agora mesmo.

---

## Perguntas para aprofundar

- Como o Polygon alcança consenso? → Proof of Stake, validadores com tokens staked
- O que é "51% attack"? → Quando um ator controla a maioria dos validadores
- Por que isso importa para o OCME? → [[005-finality-blocos]]

---

## Links

← [[MOC-Blockchain-Intelligence]]
→ [[002-smart-contracts]] — O que o consenso executa
→ [[005-finality-blocos]] — Quando o consenso é final
