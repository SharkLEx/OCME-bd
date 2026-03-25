---
type: knowledge
id: "021"
title: "Polygon: Bor + Heimdall — Arquitetura Dual Layer"
layer: L1-fundamentos
tags: [polygon, bor, heimdall, arquitetura, pos, finality]
links: ["001-consenso-distribuido", "005-finality-blocos", "020-gas-economics", "015-rpc-pool"]
fonte: https://docs.polygon.technology/pos/architecture/
---

# 021 — Polygon: Bor + Heimdall (Dual Layer)

> **Ideia central:** Polygon separa responsabilidades em duas camadas: Bor produz blocos rápido (2s), Heimdall garante finality publicando checkpoints no Ethereum a cada ~256 blocos. O WEbdEX vive no Bor — velocidade. A segurança vem do Heimdall.

---

## A Arquitetura em 3 Camadas

```
┌─────────────────────────────────────────────────────┐
│  ETHEREUM MAINNET                                   │
│  Contratos de staking de POL                        │
│  Checkpoints do Heimdall (finality absoluta)        │
├─────────────────────────────────────────────────────┤
│  HEIMDALL (Validation Layer)                        │
│  Valida blocos do Bor                               │
│  Publica Merkle root no Ethereum a cada ~256 blocos │
│  Baseado em Cosmos SDK + CometBFT                   │
├─────────────────────────────────────────────────────┤
│  BOR (Block Production Layer)                       │
│  Produz blocos a cada ~2 segundos                   │
│  Compatível com EVM (Ethereum bytecode roda aqui)   │
│  Validadores rodam ambas as camadas simultaneamente │
└─────────────────────────────────────────────────────┘
```

---

## Bor: Onde o WEbdEX vive

Bor é a camada EVM-compatível do Polygon. Cada contrato WEbdEX deployado aqui executa o mesmo bytecode que rodaria no Ethereum — mas com:

- **Bloco time:** ~2 segundos (vs ~12s no Ethereum)
- **Gas price:** em POL (~$0.20) vs ETH (~$3000)
- **Throughput:** ~65.000 TPS teórico (vs ~15 TPS Ethereum)

Para o OCME, bloco a cada 2s significa que cada `getLogs` em 2000 blocos cobre ~66 minutos de histórico.

---

## Heimdall: Onde a Finality vem

A cada ~256 blocos do Bor (~8.5 minutos), o Heimdall:
1. Agrega todos os blocos Bor em um Merkle tree
2. Publica o root hash no Ethereum mainnet
3. Validadores assinam o checkpoint

**Duas formas de finality no Polygon:**

| Tipo | Quando | Confiança |
|------|--------|-----------|
| **Bor probabilística** | ~128 blocos (~4 min) | Alta — reorg improvável |
| **Heimdall checkpoint** | ~256 blocos (~8.5 min) | Absoluta — escrita no Ethereum |
| **Ethereum finality** | ~15 min total | Matemática — imutável para sempre |

O OCME usa **finality Bor (128 blocos)** — suficiente para dados de relatório.

---

## Por que não Ethereum Mainnet?

```
Ethereum:  12s/bloco  | gas $5-50/tx    | TPS ~15
Polygon:    2s/bloco  | gas $0.001/tx   | TPS ~65.000
```

Operação de arbitragem WEbdEX:
- Margem: ~0.1% do capital
- Gas no Ethereum: ~$1.00 por operação → impossível com capital < $1000
- Gas no Polygon: ~$0.001 por operação → viável com qualquer capital

**Trade-off aceito:** Menos descentralizado que o Ethereum (menos validadores), mas suficientemente seguro para DeFi.

---

## Implicação para o OCME: Block Time de 2s

```python
# Em webdex_workers.py — o sentinela verifica a cada 30s
time.sleep(30)

# Em 30 segundos, ~15 novos blocos foram produzidos
# O OCME está sempre "perto" da ponta da cadeia
```

O sync worker processa 2000 blocos por batch. Com 2s/bloco:
- 2000 blocos = ~66 minutos de histórico
- Em modo backfill: gap > 200.000 blocos = >111 horas atrasado

---

## Conexão não-óbvia: Heimdall e o OCME

O OCME não usa o Heimdall diretamente — mas se beneficia dele. O Heimdall garante que os dados que o OCME lê via Bor jamais serão reescritos no Ethereum.

Se um evento aparece nos logs do Bor **E** já passou um checkpoint Heimdall, esse evento existe permanentemente no registro histórico do Ethereum. O relatório 21h, portanto, é garantido pelo Ethereum — não apenas pelo Polygon.

---

## Validadores: POL Staking no Ethereum

Validadores fazem stake de POL nos contratos Ethereum (não no Polygon). Isso cria um sistema onde:
- A segurança do Polygon é ancorada no Ethereum
- Para atacar o Polygon, você precisaria controlar validadores que têm POL em risco no Ethereum

Para o WEbdEX: o capital dos usuários é protegido por esse mecanismo de segurança em camadas.

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[001-consenso-distribuido]] — Como o consenso funciona genericamente
← [[005-finality-blocos]] — Os tipos de finality em detalhe
← [[020-gas-economics]] — Por que gas é barato no Polygon
→ [[015-rpc-pool]] — Como o OCME acessa o Bor via RPC
