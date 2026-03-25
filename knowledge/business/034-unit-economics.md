---
type: knowledge
id: "034"
title: "Unit Economics WEbdEX — Os Números de Cada Unidade"
layer: L5-business
tags: [business, unit-economics, metricas, retorno, capital, assertividade, fees, bd]
links: ["032-modelo-negocio-webdex", "033-escalabilidade", "009-tokenomics", "013-token-bd", "012-ciclo-21h"]
---

# 034 — Unit Economics WEbdEX

> **Ideia central:** O WEbdEX tem unit economics verificáveis on-chain. Cada unidade — uma operação, uma subconta, um ciclo — tem números reais. Não projeções. Dados históricos auditáveis.

---

## Unidade 1: Operação Individual

```
Fee por operação:      0.00963 BD
Assertividade histórica: 76-78%
Tempo de ciclo:        21h

Para cada 100 operações:
  ├── ~77 operações lucrativas (assertividade 77%)
  ├── ~23 operações negativas
  └── 0.963 BD consumido do supply
```

**O que 0.963 BD significa no supply:**
- Supply: 369.369.369 BD
- Cada 100 operações: remove ~0.000000261% do supply circulante
- Em escala: 10.000 ops/dia → ~96.3 BD/dia → ~35.000 BD/ano

---

## Unidade 2: Subconta (Capital por Trader)

```
Retorno diário estimado: 0.10-0.29% sobre capital alocado
Variância: depende de spreads disponíveis no ciclo

Exemplo com $10.000 alocado:
  ├── Dia favorável (0.29%): +$29
  ├── Dia médio (0.18%): +$18
  ├── Dia desfavorável (0.10%): +$10
  └── Ciclo negativo raro: P&L negativo (transparente on-chain)
```

**Retorno mensal estimado:**
- Conservador (0.10%/dia × 30): +3.0% ao mês
- Base (0.18%/dia × 30): +5.4% ao mês
- Otimista (0.29%/dia × 30): +8.7% ao mês

⚠️ **Importante:** Não é promessa. É dado histórico. Ciclos negativos existem e são publicados com a mesma transparência.

---

## Unidade 3: Ciclo 21h

```
Por ciclo (21h), agregado do protocolo:
  TVL atual: ~$1.58M
  Operações: variável (depende de spreads)
  P&L típico: $1.500-$4.500 positivos
  P&L negativo: publicado sem spin quando ocorre
```

**Performance documentada Dez/2025:**
- 10.398% no mês (dado on-chain verificável)
- Base TVL: ~$1.58M
- Ciclos positivos: ~77% dos ciclos
- Ciclos negativos: ~23% (transparentemente reportados)

---

## Unidade 4: Token BD

```
Supply fixo:       369.369.369 BD
Fee/operação:      0.00963 BD
Burn/ano (estimado, 100 ops/dia):
  → 0.963 BD/dia × 365 = ~351 BD/ano

Pressão deflacionária:
  → 10.000 ops/dia = 96.3 BD/dia = ~35.145 BD/ano
  → % do supply = 35.145 / 369.369.369 = 0.0095%/ano
```

**Com escala:**
- 100.000 ops/dia → ~3.5M BD/ano removidos do supply
- 1.000.000 ops/dia → ~35M BD/ano
- Em 10 anos a esse nível: ~9.5% do supply removido por utilidade real

---

## Unidade 5: Assinante Pro (Futuro — Epic 14)

```
Free Tier:    acesso básico, relatórios diários
Pro Tier:     ~$49/mês (estimado)
Institutional: ~$299/mês (estimado)

ARPU objetivo:
  ├── Free: $0 (aquisição)
  ├── Pro: $49/mês
  └── Institutional: $299/mês
```

**Mix de receita alvo (M7):**
- 60% fees de operação (BD)
- 25% assinaturas Pro/Institutional
- 15% bd://ENTERPRISE B2B

---

## Custo de Aquisição por Canal

| Canal | CAC estimado | LTV | LTV/CAC |
|-------|-------------|-----|---------|
| Orgânico (SEO+Community) | $0 | Alto | ∞ |
| bdZinho (retention) | $0 (já pago) | ↑↑ | ∞ |
| Twitter/X | $50-150 | Médio | 3-8x |
| YouTube | $100-300 | Alto | 5-15x |
| bd://ACADEMY | $200-500 | Muito alto | 10-25x |

**Insight:** bdZinho como custo de retenção = praticamente $0 incremental. Um trader que fica 6 meses a mais representa $300-1.800 em fees BD geradas.

---

## O Número que Importa

```python
# Unit economics fundamental
TVL = 1_580_000  # USD
retorno_diario = 0.0018  # 0.18% base
receita_diaria = TVL * retorno_diario  # = $2.844/dia

# Escalado para $10M TVL:
receita_diaria_10M = 10_000_000 * 0.0018  # = $18.000/dia

# Fee BD consumido (à taxa atual):
bd_consumido_dia = operacoes_estimadas * 0.00963
```

O modelo é comprovado. O crescimento é matemático. O supply é fixo.

---

## Links

← [[032-modelo-negocio-webdex]] — Como o modelo gera esses números
← [[033-escalabilidade]] — Como os números crescem
← [[012-ciclo-21h]] — De onde vêm os dados do ciclo
→ [[013-token-bd]] — O Token que absorve o valor
→ [[009-tokenomics]] — A teoria por trás dos números
