# Epic 10 — WEbdEX Design System: Telegram + Monitor Engine

**Status:** 🟡 In Progress
**Data de início:** 2026-03-19
**Criado por:** @pm (Morgan)
**Contexto:** Delegado por @lmas-master (Morpheus) após revisão adversarial @smith

---

## 🎯 Visão

Estender o Design System WEbdEX (iniciado no Epic 9 para Discord) para o **Telegram** e concluir a **migração de cores hardcoded** no monitor-engine — tornando toda a identidade visual da marca consistente em todos os canais.

O código já foi implementado localmente pelo @dev. Este epic formaliza as stories para que os commits sejam rastreáveis e o deploy ao VPS seja coordenado.

## 📋 Contexto

O Epic 9 entregou design tokens + embed builder para Discord. Paralelamente, o @dev implementou:

- `telegram_design_tokens.py` — sistema completo de tokens para Telegram (HTML parse mode)
- `metrics_worker.py` — worker de snapshot PostgreSQL + notificação 21h Discord
- Melhorias em `webdex_workers.py`, `webdex_discord_sync.py`, `notification_engine.py`
- Utilitários operacionais: `broadcast_start.py`, `check_db.py`, `check_users.py`, `check_wallets.py`

**Todos os arquivos estão uncommitted** — precisam de stories formais antes do commit + push + deploy.

---

## 📦 Stories

| Story | Título | Status | Dependências |
|-------|--------|--------|-------------|
| 10.1 | Telegram Design Tokens + 21h Report | 🟡 In Progress | Epic 9 |
| 10.2 | Monitor Engine Color Migration | ⬜ Backlog | 10.1 |
| 10.3 | Metrics Worker + Discord 21h Notification | ⬜ Backlog | Epic 9, 10.1 |
| 10.4 | Operational Utilities | ⬜ Backlog | — |

**Ordem recomendada:** 10.1 → 10.2 + 10.4 (paralelo) → 10.3

---

## 🎨 Design System Extension

### Telegram (HTML parse_mode)
```python
# Estrutura telegram_design_tokens.py
EMOJI   — namespace de emojis organizados por categoria semântica
SEP     — separadores (━━━ linha, ─── fina, ├─ item, └─ último)
HDR     — headers de seção (ciclo_21h, mybdBook, protocolo_ao_vivo, swapbook, token_bd)
MSG     — textos recorrentes fixos
FOOTER_TEXT = "WEbdEX Protocol · bdZinho"

# Formatadores
format_currency(), format_pct(), format_pol(), format_bd()
format_webdex(), format_int(), format_wallet(), format_tx()
progress_bar(), winrate_bar(), ops_bar()

# Blocos pré-montados
bloco_pnl_traders(), bloco_gas(), bloco_receita()
bloco_top_traders(), bloco_mybdbook()
bloco_operacoes(), bloco_swapbook(), bloco_token_bd()
cta_ocme()
```

### Discord (tokens já migrados via Epic 9)
- `design_tokens.py` (orchestrator): PINK_LIGHT, SUCCESS, CHART_BLUE, etc.
- `monitor-engine`: migração via `webdex_discord_sync.py` (Epic 10.2)

---

## 📁 Arquivos por Story

| Arquivo | Story | Status |
|---------|-------|--------|
| `packages/monitor-engine/telegram_design_tokens.py` | 10.1 | ⬜ Uncommitted |
| `packages/monitor-engine/webdex_workers.py` (+88L) | 10.1 | ⬜ Uncommitted |
| `packages/monitor-engine/webdex_discord_sync.py` (+54L) | 10.2 | ⬜ Uncommitted |
| `packages/monitor-engine/notification_engine.py` (+94L) | 10.2 | ⬜ Uncommitted |
| `packages/monitor-engine/webdex_anomaly.py` (+10L) | 10.2 | ⬜ Uncommitted |
| `packages/monitor-engine/metrics_worker.py` | 10.3 | ⬜ Uncommitted |
| `packages/monitor-engine/broadcast_start.py` | 10.4 | ⬜ Uncommitted |
| `packages/monitor-engine/check_db.py` | 10.4 | ⬜ Uncommitted |
| `packages/monitor-engine/check_users.py` | 10.4 | ⬜ Uncommitted |
| `packages/monitor-engine/check_wallets.py` | 10.4 | ⬜ Uncommitted |

---

## 🏗️ Deploy Target

| Container | Ação | Story |
|-----------|------|-------|
| `ocme-monitor` (76.13.100.67) | restart após scp + docker cp | 10.1, 10.2, 10.3, 10.4 |

Deploy pattern: `scp → docker cp → docker restart ocme-monitor`
