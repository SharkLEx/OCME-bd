---
type: knowledge
id: "054"
title: "Subscription Tiers — Free / Pro / Institutional"
layer: L4-business
tags: [webdex, subscription, monetização, tiers, pro, free, institutional]
links: ["032-modelo-negocio-webdex", "034-unit-economics", "013-token-bd"]
created: 2026-03-25
---

# 054 — Subscription Tiers WEbdEX

> **Ideia central:** Três níveis de acesso criam uma escada de valor: Free prova o produto, Pro monetiza o engajado, Institutional escala o revenue.

---

## Os 3 Tiers

### 🆓 Free
**Para quem:** Qualquer um com Discord — sem carteira necessária

| Feature | Limite |
|---------|--------|
| Perguntas para bdZinho | 36 msgs/dia |
| Cards Discord | Acesso visual (sem dados ao vivo personalizados) |
| Ciclo 21h broadcast | Sim (canal público) |
| Dados on-chain | Leitura básica via comandos |
| Proactive nudge | Não |
| Perfil individual | Não |

**Objetivo:** Conversão → mostrar valor, criar hábito, levar ao Pro

---

### 💎 Pro — 36.9 BD/mês
**Para quem:** Trader ativo que usa WEbdEX como ferramenta de gestão

| Feature | Limite |
|---------|--------|
| Perguntas para bdZinho | Ilimitado (rate limit global 10/hora) |
| Proactive nudge pós-ciclo | Sim — insight personalizado |
| Perfil individual | Sim — bdz_user_profiles |
| Histórico de posições | Sim — por subconta |
| Vision (foto → análise) | Sim — Gemini Flash |
| Alertas personalizados | Sim |
| Cards ao vivo | Todos os 8 |
| Suporte prioritário | Via /suporte |

**Preço:** 36.9 BD/mês (pagamento on-chain, verificado por `is_subscribed()`)

---

### 🏦 Institutional (planejado — Epic 14)
**Para quem:** Fundos, gestoras, traders profissionais

| Feature | Limite |
|---------|--------|
| Multi-wallet | Sim — gestão de portfólio |
| API access | Sim — REST endpoints |
| White-label reports | Sim — PDF/CSV |
| Dedicated support | Sim — SLA |
| Custom alerts | Volume/threshold customizável |
| On-chain analytics deep | Arbitragem histórica, MEV detection |
| Dashboards privados | Sim — Epic 13 |

**Preço:** Negociado (staking BD ou pagamento USDC)

---

## O Mecanismo de Verificação

```python
# subscription.py
def is_subscribed(wallet: str) -> bool:
    # Lê contrato on-chain 0x6481d77f...
    # Verifica se wallet tem tokens staked ou pagamento ativo
    return bool
```

```python
# bot.py
wallet = get_user_wallet(user_id)  # PostgreSQL → Discord user → wallet
is_pro = wallet and is_subscribed(wallet)
```

**Fluxo do usuário Free → Pro:**
1. `/conectar-wallet` — vincula Discord ↔ wallet Polygon
2. Adquire 36.9 BD (swap via protocolo)
3. `/assinar` — transação on-chain staking/pagamento
4. `is_subscribed(wallet)` → True → features desbloqueadas

---

## Métricas Alvo (2026)

| Métrica | Q2 2026 | Q4 2026 |
|---------|---------|---------|
| Free users | 500 | 2.000 |
| Pro subscribers | 50 | 300 |
| Institutional | 2 | 10 |
| MRR (BD) | 1.845 BD | 11.070 BD |

---

## Decisões de Design dos Tiers

### Por que cobrar em BD?
- Cria demanda estrutural pelo token (cada assinatura = compra)
- Alinha incentivos: usuário tem interesse em valorização do BD
- Verificável on-chain — transparência total

### Por que 36 msgs/dia free?
- "36" é o número do token BD (branding) — 36.9 BD/mês, 36 msgs/dia
- Suficiente para ver valor, insuficiente para substituir o Pro
- Não causa burn de API — limite saudável para custo marginal

### Por que Pro antes de Institutional?
- Pro valida o modelo com volume (price discovery)
- Institutional precisa do dashboard (Epic 13) para ser viável
- Sequência: Free → Pro → (Epic 13 live) → Institutional
