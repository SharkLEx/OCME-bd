---
type: knowledge
id: "055"
title: "Observability: Por que 'degraded' deve retornar HTTP 200"
layer: L3-ocme
tags: [ocme, observability, healthcheck, docker, incidente, decisão]
links: ["040-tech-stack-ocme", "041-deploy-pattern", "053-pipeline-dado-ao-usuario"]
created: 2026-03-25
---

# 055 — Incidente: ocme-monitor Unhealthy (Degraded ≠ Down)

> **Decisão:** O estado "degraded" do monitor engine é operacionalmente aceitável e deve retornar HTTP 200 no health endpoint — não 503.

---

## O Incidente

**Sintoma:** `docker ps` mostrava `ocme-monitor (unhealthy)` mesmo com o monitor funcionando normalmente e dados chegando ao Discord.

**Causa raiz:**

```python
# webdex_observability.py — ANTES do fix
code = 200 if status["status"] == "ok" else 503
```

O `healthcheck` do Docker usa `urllib.request.urlopen()` que lança exceção em respostas HTTP 4xx/5xx:
```
urllib.error.HTTPError: HTTP Error 503: Service Unavailable
→ Container marcado como unhealthy
→ Restart policy pode reiniciar desnecessariamente
```

**Estado "degraded"** ocorre quando o loop `vigia_webdex` não está rodando mas o servidor HTTP está online. Isso é **normal** em certas condições (startup, restart de componente interno).

---

## O Fix

```python
# webdex_observability.py — APÓS o fix
code = 200 if status["status"] in ("ok", "degraded") else 503
```

**Princípio:** Retornar 503 apenas quando o container está genuinamente incapacitado (crash total, DB inacessível). "Degraded" significa "funcionando com capacidade reduzida" — diferente de "down".

---

## A Analogia

```
Sistema de saúde humana:
  OK       = totalmente saudável
  Degraded = resfriado — funciona, apenas não no pico
  503      = hospitalizado — não pode trabalhar

Docker healthcheck equivalente:
  healthy  = OK
  healthy  = Degraded  ← CORRETO (continua servindo)
  unhealthy = crash/down ← CORRETO
```

---

## Estados do Monitor e seus HTTP codes

| status["status"] | Significado | HTTP code | Docker estado |
|-----------------|-------------|-----------|---------------|
| `"ok"` | Tudo rodando | 200 | healthy |
| `"degraded"` | Vigia parado, HTTP OK | 200 | healthy ✅ |
| `"error"` | Falha crítica interna | 503 | unhealthy |
| Servidor não responde | Container crash | timeout | unhealthy |

---

## Implementação e Deploy

O fix foi aplicado diretamente no container via `docker cp` em 2026-03-25:
```bash
docker cp webdex_observability.py ocme-monitor:/opt/ocme-monitor/packages/monitor-engine/
docker compose restart monitor
```

**Status após fix:** `ocme-monitor (healthy)` ✅

**Pendência:** Push do fix para GitHub (VPS sem credenciais configuradas). O arquivo local está atualizado mas o commit ainda não foi propagado ao remote.

---

## Lição de Infraestrutura

**Healthchecks devem distinguir "degradado" de "down".** Um container que retorna 503 por estar temporariamente degradado pode ser reiniciado desnecessariamente pelo orquestrador — causando mais instabilidade do que o estado degradado original.

**Regra:** HTTP 503 = "não posso servir esta request agora". Se o servidor HTTP está respondendo, o container está vivo.
