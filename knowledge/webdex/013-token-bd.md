---
type: knowledge
id: "013"
title: "Token BD — Flywheel Econômico"
layer: L3-webdex
tags: [webdex, token-bd, tokenomics, flywheel, governança]
links: ["009-tokenomics", "007-tvl", "010-triade-risco-responsabilidade-retorno", "011-subcontas"]
---

# 013 — Token BD: O Flywheel Econômico

> **Ideia central:** BD não é só um token — é a unidade de medida de participação no protocolo. Cada operação de arbitragem paga 0,00963 BD de fee. O fluxo de BD conecta todas as 6 cápsulas do protocolo.

---

## Os Números Fundamentais

```
Contrato: 0xf49dA0F454d212B80F40693cdDd452D8Caa2fa6d
Supply:   369.369.369 BD (fixo, nunca inflaciona)
Fee/op:   0,00963 BD por operação executada
```

Por que 369.369.369? A filosofia 3·6·9 do WEbdEX — cada dígito é significativo no sistema numérico do protocolo.

---

## O Flywheel

```
Mais usuários depositam capital
        ↓
Mais operações de arbitragem
        ↓
Mais fees em BD coletadas
        ↓
BD em circulação aumenta
        ↓
Valor do BD sobe (supply fixo + demanda aumentando)
        ↓
BD valorizado atrai mais usuários
        ↓
(volta ao início)
```

Este é o **flywheel de crescimento**: cada componente alimenta o próximo.

---

## BD no Ciclo 22/03→23/03

```
57.585 operações × 0,00963 BD/op = 554,54 BD em fees
```

Em 365 dias (projetado no mesmo ritmo):
```
554,54 BD/dia × 365 = 202.407 BD/ano em fees
```

Com supply de 369.369.369 BD, as fees anuais representam 0,055% do supply circulando como atividade.

---

## ERC-20: O Padrão

BD é um token ERC-20 padrão. Isso significa:
- Compatível com qualquer carteira Ethereum
- Transferível livremente
- Rastreável no PolygonScan
- Usável em qualquer protocolo DeFi que aceite ERC-20

```python
# Como o OCME lê o saldo BD de um usuário
bd_balance = bd_contract.functions.balanceOf(wallet).call()
# Resultado: int em wei (18 casas decimais)
bd_human = bd_balance / 10**18  # converter para unidades BD
```

---

## BD nas 6 Cápsulas

| Cápsula | Papel do BD |
|---------|-------------|
| bd://CORE | Fee por operação de arbitragem |
| bd://INTELLIGENCE | Pass fee (0,00963 BD por acesso ao OCME) |
| bd://ACADEMY | Learn-to-Earn — BD como recompensa |
| bd://SOCIAL | Governança e participação |
| bd://ENTERPRISE | Pagamento B2B em BD |
| bd://MEDIA | Incentivos de conteúdo |

Cada cápsula tem um mecanismo diferente de circulação, mas todas usam o mesmo token.

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[014-filosofia-369]] — Por que 369.369.369 e não outro número
← [[009-tokenomics]] — A teoria por trás do design
← [[007-tvl]] — TVL e valor do BD são correlacionados
→ [[010-triade-risco-responsabilidade-retorno]] — Retorno medido em BD
→ [[011-subcontas]] — Onde as fees são debitadas
