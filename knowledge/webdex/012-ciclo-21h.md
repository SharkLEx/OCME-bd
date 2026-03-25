---
type: knowledge
id: "012"
title: "Ciclo 21h — O Relatório Diário"
layer: L3-webdex
tags: [webdex, ocme, ciclo, relatório, transparência]
links: ["018-janela-temporal-fechada", "016-protocol-ops", "007-tvl"]
---

# 012 — Ciclo 21h

> **Ideia central:** Todo dia às 21h BRT, o protocolo WEbdEX presta contas. Não porque é obrigado — porque os dados estão on-chain e qualquer um pode verificar.

---

## O que é o Ciclo 21h

Um ciclo fechado de 24 horas:
```
Ontem 21:00 BRT → Hoje 21:00 BRT
```

O OCME agrega todas as operações desse período e gera um relatório com:
- P&L bruto do protocolo
- WinRate (operações vencedoras / total)
- Número de traders ativos
- Liquidez total (TVL)
- Top 5 traders do ciclo
- Fees em BD coletadas

---

## Por que 21h e não meia-noite?

Convenção escolhida para o contexto brasileiro (horário de Brasília). Cria um ritual — toda noite às 21h, a comunidade recebe o "boletim" do dia.

---

## A Janela Fechada — Por que isso importa

**Bug histórico:** O sistema usava `ts >= agora` (janela aberta).
**Problema:** Captava operações do ciclo **atual**, não do ciclo **fechado**.
**Fix aplicado:** `ts >= ontem_21h AND ts < hoje_21h` (janela fechada).

```sql
-- ERRADO: janela aberta (captava ciclo em aberto)
WHERE ts >= _ciclo_21h_since()

-- CORRETO: janela fechada (ciclo completo e encerrado)
WHERE ts >= dt_lim AND ts < dt_fim
```

O relatório agora representa um ciclo **completo e imutável**.

→ [[018-janela-temporal-fechada]] — Análise profunda do bug e fix

---

## Conversão UTC vs BRT

On-chain, todos os timestamps são UTC. BRT = UTC - 3.

```python
# 21h BRT → 00h UTC do dia seguinte
ciclo_inicio_brt = datetime(2026, 3, 22, 21, 0)  # BRT
ciclo_inicio_utc = ciclo_inicio_brt + timedelta(hours=3)
# = datetime(2026, 3, 23, 0, 0)  UTC

# SQL query usa UTC
WHERE ts >= '2026-03-23 00:00:00' AND ts < '2026-03-24 00:00:00'
```

---

## O Ciclo 22/03 → 23/03 (dados reais)

```
Ciclo:    22/03 21h → 23/03 21h BRT
Traders:  336
Trades:   57.585
WinRate:  74.6%  (42.933 wins)
P&L:      +$14.773,04 🟢
Liquidez: ~$2.25M
BD fees:  554,54 BD
```

Esses dados são **verificáveis on-chain**. Não são projeção.

---

## O Race Condition

Antes do fix, o worker às vezes consultava antes do último batch de operações ser commitado no banco:

```
21:00:00 — agendador_21h inicia
21:00:01 — consulta banco (proto_sync ainda commitando)
21:00:15 — proto_sync commita últimas 200 ops
→ relatório estava incompleto
```

Fix: `time.sleep(300)` — aguarda 5 minutos para o `proto_sync` fechar o batch.

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[010-triade-risco-responsabilidade-retorno]] — O que o ciclo mede
← [[016-protocol-ops]] — De onde vêm os dados
→ [[018-janela-temporal-fechada]] — O bug e o fix
→ [[007-tvl]] — A liquidez no relatório
