---
type: knowledge
id: "010"
title: "Tríade: Risco · Responsabilidade · Retorno"
layer: L3-webdex
cssclasses: [agent-bdpro]
tags: [webdex, filosofia, triade, protocolo]
links: ["011-subcontas", "013-token-bd", "014-filosofia-369"]
---

# 010 — Tríade: Risco · Responsabilidade · Retorno

> **Ideia central:** Toda decisão no protocolo WEbdEX passa por três filtros simultâneos. Não existe retorno sem responsabilidade. Não existe responsabilidade sem compreender o risco.

---

## A Tríade

```
        RISCO
       /     \
      /       \
RESPONSABILIDADE ─── RETORNO
```

Os três são inseparáveis. Cada vértice define os outros dois.

---

## Risco

**No WEbdEX:** Risco não é evitado — é quantificado e precificado.

Cada operação de arbitragem tem:
- Risco de execução (slippage)
- Risco de gas (preço POL pode subir)
- Risco de timing (janela fecha antes do swap)

O protocolo não promete "sem risco". Promete **gestão de risco** com regras públicas on-chain.

---

## Responsabilidade

**No WEbdEX:** Responsabilidade é distribuída — não centralizada.

O usuário é responsável por:
- Escolher o ambiente (AG_C_bd vs bd_v5)
- Decidir quanto capital depositar
- Entender o que está fazendo

O protocolo é responsável por:
- Executar as regras como especificado no contrato
- Não ter custody do capital (non-custodial)
- Ser transparente via OCME e relatório 21h

**Non-custodial é responsabilidade, não feature.**

---

## Retorno

**No WEbdEX:** Retorno é consequência de executar bem os outros dois.

```
Performance histórica:
  Dezembro 2025: 10.398%
  Assertividade diária: 74-78%
  Retorno diário: 0.10-0.29% sobre capital
```

O retorno não é prometido — é resultado verificável on-chain.

---

## Aplicação Prática

Quando o OCME gera o relatório 21h, ele está medindo os três:

| Métrica | Mede o quê |
|---------|-----------|
| WinRate | Risco de execução |
| P&L bruto | Retorno gerado |
| Traders ativos | Responsabilidade distribuída |
| TVL | Confiança coletiva no protocolo |

---

## A pergunta de Einstein

**Por que "Risco" e não "Lucro" no terceiro vértice?**

Porque lucro é consequência. Risco é condição. Um protocolo que promete lucro sem gestão de risco é produto financeiro, não protocolo DeFi.

A tríade coloca o usuário como agente ativo, não como passageiro.

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[014-filosofia-369]] — A estrutura maior onde a tríade se encaixa
→ [[011-subcontas]] — Responsabilidade aplicada: capital segregado
→ [[013-token-bd]] — Retorno aplicado: fee em BD
→ [[012-ciclo-21h]] — Como medimos os três simultaneamente
