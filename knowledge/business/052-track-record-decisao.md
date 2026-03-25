---
type: knowledge
id: "052"
title: "Track Record — Por que Win Rate > Streak como métrica principal"
layer: L4-business
tags: [webdex, conquistas, track-record, win-rate, streak, decisão]
links: ["016-protocol-ops", "034-unit-economics", "036-posicionamento"]
created: 2026-03-25
---

# 052 — Track Record: A Decisão por Win Rate

> **Ideia central:** Win Rate (% de ciclos lucrativos) é mais defensável e persuasivo do que Streak (ciclos consecutivos) porque reflete consistência estrutural, não sorte temporal.

---

## O Contexto da Decisão

O card `#conquistas` do Discord exibe 4 métricas de performance do protocolo. A posição de destaque (topo-direita, cor principal) foi objeto de decisão em março 2026.

**Candidatos:**
- **Streak** — ciclos positivos consecutivos (mais emocional, fácil de romper)
- **Win Rate** — % de ciclos lucrativos sobre total (mais estatístico, permanente)

---

## Por que Win Rate Ganhou

### 1. Resistência ao ciclo negativo único
Um ciclo negativo destrói o streak (vai a zero). Mas o win rate cai apenas marginalmente:
```
100 ciclos, 77 positivos → Win Rate = 77%
101 ciclos, 77 positivos → Win Rate = 76,2%  ← queda de 0,8%
Streak = ZERO ← queda de 100%
```

### 2. Histórico permanente vs estado momentâneo
- Streak reflete o estado **agora** — é amnésico
- Win Rate reflete **toda a história** do protocolo — é cumulativo

### 3. Comparável com outros instrumentos financeiros
- Traders avaliam estratégias por win rate (60%+ é considerado bom)
- 77% win rate é **objetivamente melhor que a maioria dos fundos ativos** (média: 45-55%)
- Permite benchmark direto: WEbdEX vs trader manual vs fundo hedge

### 4. Mais honesto em momentos de adversidade
Quando o protocolo tem um ciclo ruim (mercado volátil, liquidez baixa), o streak vai a zero mas o win rate permanece alto. Isso é **confiança estrutural** vs euforia momentânea.

---

## A Hierarquia das 4 Métricas (no card)

| Posição | Métrica | Cor | Propósito |
|---------|---------|-----|-----------|
| Topo-esquerda | 🏆 Streak | Gold | Emoção — "quantos ciclos seguidos?" |
| **Topo-direita** | **💯 Win Rate** | **Pink** | **Persuasão — "% de acerto histórico"** |
| Baixo-esquerda | 📈 P&L Total | Green | Prova — "quanto gerou em $?" |
| Baixo-direita | 🎯 Record Ciclo | Cyan | Potencial — "teto possível" |

**Win Rate ocupa o destaque** porque é o argumento mais difícil de contestar.

---

## O Argumento de Venda

> "77% dos ciclos do WEbdEX foram lucrativos. Isso é verificável on-chain. Não há fundo de gestão ativa no Brasil com esse histórico público."

---

## Implementação

- Fonte: tabela `protocol_ops` no SQLite — `COUNT(*) WHERE profit > 0 / COUNT(*)`
- Card HTML: `data-live="win_rate"` → preenchido pelo `card_server.py` → `data_conquistas()`
- Atualização: tempo real (a cada reload do card)

---

## Lição para próximas decisões de produto

**Prefira métricas cumulativas a métricas de estado** quando o objetivo é construir confiança a longo prazo. Streak é marketing de curto prazo. Win Rate é credibilidade estrutural.
