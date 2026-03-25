---
type: knowledge
id: "005"
title: "Finality de Blocos"
layer: L1-fundamentos
tags: [blockchain, finality, blocos, segurança]
links: ["001-consenso-distribuido", "018-janela-temporal-fechada", "015-rpc-pool"]
---

# 005 — Finality de Blocos

> **Ideia central:** Uma transação não é "definitiva" no momento em que aparece. É definitiva quando blocos suficientes foram minerados após ela — tornando um revert matematicamente impossível.

---

## O Problema

Imagine que você lê um dado no bloco 67.834.521. Segundos depois, a rede faz um **reorg**: a cadeia "reescreve" os últimos 3 blocos porque uma cadeia alternativa tinha mais trabalho acumulado.

O dado que você leu agora não existe mais.

---

## Finality no Polygon

| Confirmações | Status | Uso recomendado |
|-------------|--------|----------------|
| 0-1 blocos | Pendente | Não usar |
| 3-10 blocos | Provável | UI / notificações |
| ~64 blocos | Checkpoint | Dados confiáveis |
| **128 blocos** | **Final** | **Dados críticos** |
| 256+ blocos | Ultra-seguro | Dados históricos |

Polygon: ~2 segundos por bloco → 128 blocos ≈ 4 minutos de espera.

---

## Como o OCME lida com isso

O `_protocol_ops_sync_worker` sincroniza continuamente, mas as consultas do relatório 21h usam dados que já têm centenas de blocos de confirmação — efetivamente finais.

```python
# A janela do relatório é sempre do passado
# ontem 21h → hoje 21h = mínimo 3+ horas atrás
# 3 horas = 3*3600/2 = 5400 blocos de confirmação
# Muito além dos 128 necessários para finality
```

---

## Reorg e o OCME

**Risco identificado (Smith):** Se o OCME sincronizar dados muito recentes (< 64 blocos), um reorg pode invalidar dados já gravados no `protocol_ops`.

**Mitigação atual:** O sync trabalha em batches e há um delay natural entre a ocorrência on-chain e o processamento. Na prática, os dados do relatório têm confirmação suficiente.

**Mitigação ideal (ainda não implementada):** Adicionar `block_number` em cada linha da `protocol_ops` e verificar se o bloco ainda está na cadeia canônica antes de incluir no relatório.

---

## A Metáfora

Blockchain é como cimento:
- **0 blocos**: ainda líquido — pode mudar
- **10 blocos**: endurecendo — improvável mudar
- **128 blocos**: sólido — impossível mudar
- **1000 blocos**: pedra — parte da história permanente

O OCME trabalha sempre com cimento já endurecido.

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[001-consenso-distribuido]] — O que cria a finality
→ [[018-janela-temporal-fechada]] — Por que usamos janelas fechadas
→ [[015-rpc-pool]] — Como acessamos os dados com segurança
