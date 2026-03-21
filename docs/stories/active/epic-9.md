# Epic 9 — bdZinho Discord v2: Visual Identity & Intelligence

**Status:** ✅ Done
**Data de início:** 2026-03-18
**Criado por:** @sm + @ux-design-expert (Sati)

---

## 🎯 Visão

Transformar o bdZinho de "bot funcional" em **mascote on-brand com identidade visual consistente** no Discord — embeds com cores da marca, personalidade animada, gráficos interativos e notificações proativas.

## 📋 Contexto

Após o Epic 8 (infraestrutura base do Orchestrator + Discord bot), o bdZinho está operacional mas visualmente genérico. A Sati analisou:
- Manual da Marca WEbdEX (2024-07-18) — tokens oficiais extraídos
- 33 imagens Instagram do bdZinho — identidade visual mapeada
- Código existente (`bot.py`, `ia_buttons.py`, `commands.py`, `chart_handler.py`)

O Epic 9 consolida essa identidade em código.

---

## 📦 Stories

| Story | Título | Status | Dependências |
|-------|--------|--------|-------------|
| 9.1 | Design Tokens + Embed Builder | ✅ Done | — |
| 9.2 | Slash Command /grafico | ✅ Done | 9.1 |
| 9.3 | Motor de Notificações Proativas | ✅ Done | 9.1 |
| 9.4 | bdZinho Personalidade v2 | ✅ Done | — |

**Ordem recomendada:** 9.1 → 9.4 (paralelo) → 9.2 + 9.3

---

## 🎨 Design System (Sati)

### Tokens Oficiais

```python
# Brand — Manual da Marca WEbdEX
PINK_LIGHT  = 0xFB0491   # accent primário
RED_LIGHT   = 0xD90048   # accent secundário
BLACK       = 0x000000   # background
DARK        = 0x131313   # superfícies
WHITE       = 0xFFFFFF   # texto

# Semânticos
SUCCESS     = 0x00FFB2   # P&L positivo
WARNING     = 0xFF8800   # atenção
ERROR       = 0xFF4455   # crítico
PRO_PURPLE  = 0xE040FB   # tier PRO
CHART_BLUE  = 0x00D4FF   # gráficos
```

### Identidade bdZinho
- Robô 3D, rosto rosa/pink, corpo preto, chifres de diabo, logo "bd" no peito
- Tom: animado, direto, celebrativo em wins, analítico em losses
- Tipografia: Syne (UI), B1 5X5 (logo pixel font)

---

## 📁 Arquivos Criados/Modificados

| Arquivo | Story | Status |
|---------|-------|--------|
| `packages/orchestrator/discord/design_tokens.py` | 9.1 | ✅ Done |
| `packages/orchestrator/discord/embed_builder.py` | 9.1 | ✅ Done |
| `packages/orchestrator/discord/chart_views.py` | 9.2 | ✅ Done |
| `packages/orchestrator/discord/voice_discord.py` | 9.4 | ✅ Done |
| `packages/monitor-engine/notification_engine.py` | 9.3 | ✅ Done |
| `packages/orchestrator/discord/commands.py` | 9.1, 9.2 | ✅ Done |
| `packages/orchestrator/discord/ia_buttons.py` | 9.1 | ✅ Done |
| `packages/monitor-engine/webdex_discord_animate.py` | 9.1 | ✅ Done |
| `packages/monitor-engine/webdex_workers.py` | 9.3 | ✅ Done |
