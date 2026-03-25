---
type: moc
title: "MOC — Blockchain Intelligence"
cssclasses:
  - moc-note
tags:
  - moc
  - blockchain
  - knowledge
  - webdex
---

# 🧠 Blockchain Intelligence — Mapa do Conhecimento

> Sistema Zettelkasten: cada nota = um átomo de pensamento.
> Leia em qualquer ordem — os links criam o entendimento.
> **Einstein não decorava. Ele conectava.**

---

## 🗺️ Caminho de Aprendizado

```
FUNDAMENTOS → DEFI → WEBDEX → OCME
    L1           L2      L3      L4
```

Cada nível pressupõe o anterior. Mas você pode entrar em qualquer ponto e seguir os links.

---

## L1 — Fundamentos Blockchain

| Nota | Conceito Central | Por que importa |
|------|-----------------|-----------------|
| [[001-consenso-distribuido]] | Nenhuma entidade controla o estado | Base de tudo |
| [[002-smart-contracts]] | Código como lei executável | WEbdEX é código |
| [[003-eventos-logs]] | Histórico imutável indexável | OCME lê isso |
| [[004-gas-transacoes]] | Custo computacional de execução | Afeta performance |
| [[005-finality-blocos]] | Quando uma tx é irreversível | Segurança de dados |
| [[019-evm-state-machine]] | S→T→S': determinismo absoluto | Por que relatórios são verificáveis |
| [[020-gas-economics]] | call() grátis, transact() pago | OCME lê blockchain de graça |
| [[021-polygon-bor-heimdall]] | Bor 2s/bloco + Heimdall checkpoint | Por que Polygon é rápido e barato |

---

## L2 — DeFi (Finanças Descentralizadas)

| Nota | Conceito Central | Por que importa |
|------|-----------------|-----------------|
| [[006-liquidity-pools]] | Liquidez provida por usuários, não bancos | TVL do WEbdEX |
| [[007-tvl]] | Total Value Locked — termômetro do protocolo | Métrica principal |
| [[008-arbitragem-triangular]] | Lucro de ineficiências de preço | Motor do WEbdEX |
| [[009-tokenomics]] | Economia do token como sistema de incentivos | Token BD |

---

## L3 — Protocolo WEbdEX

| Nota | Conceito Central | Por que importa |
|------|-----------------|-----------------|
| [[010-triade-risco-responsabilidade-retorno]] | A filosofia que guia tudo | Identidade do protocolo |
| [[011-subcontas]] | Segregação de capital por usuário | Non-custodial real |
| [[012-ciclo-21h]] | Relatório diário como prova on-chain | Transparência radical |
| [[013-token-bd]] | BD como unidade de governança e fee | Flywheel econômico |
| [[014-filosofia-369]] | A arquitetura 3·6·9 do protocolo | Por que tudo tem esses números |

---

## L4 — OCME Intelligence

| Nota | Conceito Central | Por que importa |
|------|-----------------|-----------------|
| [[015-rpc-pool]] | Redundância de acesso on-chain | Sem ponto único de falha |
| [[016-protocol-ops]] | Tabela de verdade das operações | Fonte dos relatórios |
| [[017-snapshot-tvl]] | Foto do TVL a cada 30min | Série temporal |
| [[018-janela-temporal-fechada]] | Por que ciclos abertos geram erro | O bug que corrigimos |
| [[022-web3py-call-patterns]] | call() vs transact() vs get_logs() | O DNA técnico do OCME |
| [[023-getLogs-batch-efficiency]] | 2000 blocos = sweet spot de eficiência | EIP-2929 + Alchemy CU |

---

## 🔗 Conexões Cruzadas Não-Óbvias

```
[[005-finality-blocos]] ←→ [[018-janela-temporal-fechada]]
    "quando é seguro ler"      "quando fechar a janela"

[[008-arbitragem-triangular]] ←→ [[016-protocol-ops]]
    "o que o protocolo faz"         "como medimos"

[[009-tokenomics]] ←→ [[013-token-bd]] ←→ [[011-subcontas]]
    "teoria econômica"     "implementação"   "execução"

[[006-liquidity-pools]] ←→ [[007-tvl]] ←→ [[017-snapshot-tvl]]
    "o que é liquidez"    "como medir"    "como capturar"
```

---

## 🧪 Perguntas para Expandir o Pensamento

> Estas perguntas não têm notas ainda — são o próximo nível.

- [ ] Por que o Polygon foi escolhido e não Ethereum mainnet?
- [ ] O que acontece com os dados do OCME se houver um reorg de bloco?
- [ ] Como a arbitragem triangular cria valor sem extrair de usuários?
- [ ] Por que 369.369.369 de supply e não 1.000.000?
- [ ] Qual a relação entre assertividade 74% e math de Kelly Criterion?

---

## 🔗 Links Relacionados

- [[MOC-Agentes]] — Os agentes que operam sobre este conhecimento
- [[bdPro]] — Especialista do protocolo
- [[framework/agents/MOC-Agentes|MOC Agentes LMAS]]
