---
type: knowledge
id: "009"
title: "Tokenomics — Design Econômico de Tokens"
layer: L2-defi
tags: [defi, tokenomics, economia, incentivos, flywheel]
links: ["006-liquidity-pools", "007-tvl", "013-token-bd", "008-arbitragem-triangular"]
---

# 009 — Tokenomics: Design Econômico de Tokens

> **Ideia central:** Tokenomics é a ciência de projetar sistemas de incentivos usando tokens. Um bom design cria um flywheel — cada ação positiva amplifica a próxima. Um design ruim cria espirais de morte.

---

## Os 4 Pilares do Tokenomics

```
1. SUPPLY     — Quantos tokens existem e como são distribuídos
2. DEMAND     — Por que alguém quer o token
3. UTILITY    — O que o token permite fazer
4. VELOCITY   — Com que frequência o token circula
```

**BD:** supply fixo (369M), demanda por fees, utility em 6 cápsulas, velocity alta (0,00963 por operação).

---

## Supply Design: Inflacionário vs Deflacionário

| Modelo | Exemplo | Risco |
|--------|---------|-------|
| Inflacionário | Emite novos tokens para recompensar | Diluição constante |
| Deflacionário | Supply cai com queima | Deflação pode travar economia |
| **Fixo** | **BD: 369.369.369 para sempre** | **Escassez programada** |

Supply fixo significa que se demand aumenta → preço aumenta (não há mais tokens para emitir).

---

## Velocity: O Problema do "Hold"

Alta velocity = tokens circulam muito = cada token "faz mais trabalho" na economia.
Baixa velocity = todo mundo segura = preço sobe mas utilidade diminui.

**BD tem alta velocity por design:** cada operação queima 0,00963 BD em fee. Quem opera precisa ter BD disponível → incentivo para circular, não só segurar.

---

## O Flywheel WEbdEX

```
Protocolo tem bom WinRate (74.6%)
    ↓
Usuários depositam mais capital
    ↓
TVL cresce → mais arbitragem possível
    ↓
Mais operações → mais fees em BD coletadas
    ↓
Demanda por BD aumenta (precisa para fees)
    ↓
Supply fixo → preço BD sobe
    ↓
BD valorizado → retorno em BD vale mais USD
    ↓
Mais usuários atraídos pelo retorno
    ↓ (volta ao início)
```

---

## Espiral de Morte (o que evitar)

```
Performance ruim → usuários saem → TVL cai →
menos arbitragem → menos fees → menos demanda por BD →
preço BD cai → retornos em USD caem → mais usuários saem
```

É por isso que manter WinRate > 70% é existencial para o protocolo.

---

## Links

← [[MOC-Blockchain-Intelligence]]
→ [[013-token-bd]] — Como o BD implementa estes princípios
→ [[014-filosofia-369]] — A filosofia de design por trás do supply 369M
→ [[006-liquidity-pools]] — O papel das pools no flywheel
→ [[007-tvl]] — TVL como termômetro do flywheel
