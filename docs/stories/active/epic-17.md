# Epic 17 — Social Media Expansion: X + TikTok + Instagram + WhatsApp

**Status:** 🟡 In Progress
**Criado:** 2026-03-20
**Objetivo:** Distribuir o conteúdo do WEbdEX Protocol OS automaticamente para todos os canais sociais — ciclo 21h, milestones on-chain e alertas de mercado.

---

## Visão: Um evento, quatro canais simultâneos

```
Monitor Engine detecta evento (ciclo 21h / milestone / alerta)
            ↓
    notification_engine.py
     /    |     |      \
Telegram Discord  X    TikTok
 ✅       ✅    17.1   17.2

Meta credentials recebidas → ativa:
Instagram (8.8)   WhatsApp (8.9 ✅ stub pronto)
```

---

## Stories

| Story | Canal | Status | Blocker |
|-------|-------|--------|---------|
| 17.1 | Twitter/X Auto-posting | ⏳ Backlog | Twitter API keys |
| 17.2 | TikTok Auto-posting (vídeo) | ⏳ Backlog | TikTok API keys |
| 8.8 | Instagram Integration | ⏸️ Bloqueada | Meta app approval |
| 8.9 | WhatsApp Integration | ✅ Pronto (stub) | Meta token → ativa sozinho |

---

## Prioridade de Implementação

1. **Twitter/X (17.1)** — API disponível, processo de aprovação simples
2. **TikTok (17.2)** — API disponível, requer conta Business
3. **Instagram (8.8)** — após aprovação Meta
4. **WhatsApp (8.9)** — apenas configurar token quando Meta liberar

---

## Nota sobre WhatsApp

A Story 8.9 está **100% implementada em stub mode**. Quando Alex receber as credenciais Meta:
```bash
# VPS: docker exec orchestrator-api ou orchestrator-discord
export WHATSAPP_TOKEN=<token>
export WHATSAPP_PHONE_NUMBER_ID=<id>
# restart container → ativa automaticamente
```

Não requer nova story — apenas configuração de env var.
