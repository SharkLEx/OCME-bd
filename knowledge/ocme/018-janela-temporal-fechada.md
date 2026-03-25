---
type: knowledge
id: "018"
title: "Janela Temporal Fechada"
layer: L4-ocme
tags: [ocme, bug, fix, sql, ciclo, determinismo]
links: ["012-ciclo-21h", "003-eventos-logs", "005-finality-blocos"]
---

# 018 — Janela Temporal Fechada

> **Ideia central:** Um relatório só é confiável se representa um período fixo e imutável. Janela aberta = resultado que muda conforme o tempo passa. Janela fechada = resultado determinístico.

---

## O Bug

```python
# VERSÃO BUGADA — janela aberta
cursor.execute("""
    SELECT COUNT(*) FROM protocol_ops
    WHERE ts >= ?           # desde ontem 21h...
""", (ciclo_inicio,))       # ...até AGORA (muda todo segundo!)
```

**Problema:** Se você roda o relatório às 21h01, você pega ops de 21h00 até 21h01.
Se rodar às 21h05, pega até 21h05. O resultado muda conforme o tempo passa.

Isso é **não-determinístico** — dois runs do mesmo script produzem resultados diferentes.

---

## O Fix

```python
# VERSÃO CORRIGIDA — janela fechada
ciclo_fim   = _ciclo_21h_since()              # hoje 21h BRT (fixed)
ciclo_inicio = ciclo_fim - timedelta(hours=24) # ontem 21h BRT (fixed)

cursor.execute("""
    SELECT COUNT(*) FROM protocol_ops
    WHERE ts >= ? AND ts < ?   # intervalo FECHADO, imutável
""", (ciclo_inicio_utc, ciclo_fim_utc))
```

**Agora:** Não importa quando você roda. O resultado é sempre o mesmo para aquele ciclo.

---

## Idempotência

Este é o princípio de **idempotência**: rodar a mesma operação N vezes produz o mesmo resultado.

```
Run 1 às 21h00: traders=336, trades=57585 ✅
Run 2 às 21h05: traders=336, trades=57585 ✅
Run 3 às 22h00: traders=336, trades=57585 ✅
```

Isso é crucial para:
- **Auditoria**: qualquer um pode verificar o relatório
- **Retry**: se o envio falhar, reenviar não muda os dados
- **Confiança**: o número é uma foto, não um vídeo em tempo real

---

## A Conversão UTC

`protocol_ops.ts` está em UTC. O ciclo é definido em BRT. Conversão:

```
BRT = UTC - 3h
→ 21h BRT = 00h UTC do dia seguinte

Ciclo 22/03 21h → 23/03 21h BRT
= 23/03 00h UTC → 24/03 00h UTC

SQL:
WHERE ts >= '2026-03-23 00:00:00' AND ts < '2026-03-24 00:00:00'
```

---

## O Race Condition paralelo

Mesmo com janela fechada, havia outro problema:

```
21:00:00 BRT — agendador_21h consulta banco
21:00:12 BRT — proto_sync commita últimos 200 eventos
→ relatório perdia ~200 operações do final do ciclo
```

Fix: `time.sleep(300)` antes da query — dá 5 minutos para o `proto_sync` fechar.

---

## Conexão Einstein

Este bug é um caso clássico de **temporal coupling** — dois sistemas (agendador e sync) que precisam se coordenar no tempo mas não têm mecanismo explícito para isso.

A solução correta de longo prazo seria um **handshake**: o sync sinaliza "batch do ciclo N está fechado", o agendador espera por esse sinal.

O `sleep(300)` é uma solução pragmática — funciona na prática porque o sync é muito mais rápido que 5 minutos.

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[012-ciclo-21h]] — O contexto do relatório
← [[003-eventos-logs]] — De onde vêm os dados da query
← [[005-finality-blocos]] — Por que timestamps on-chain são confiáveis
