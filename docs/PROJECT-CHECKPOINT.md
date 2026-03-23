# Project Checkpoint

> Ultima atualizacao: 2026-03-23 17:55 (pre-compact save)

## Contexto Ativo

**Sessão 2026-03-23 — Design System WEbdEX + OCME_bd Série Visual**
Branch: `feat/epic-7-monitor-engine`
Status: Cards V01–V05 finalizados com imagens reais bdZinho. Prontos para Creatomate render.
Pendente (Alex): Cloudflare SSL "Full" para webdex.app + Discord webhook VPS alerts.

## Decisoes Tomadas

| Decisão | Motivo |
|---------|--------|
| VPS Infra: iptables-persistent (UFW removido) | netfilter-persistent conflita com UFW — UFW chains ainda ativas, sem regressão |
| RPC_FALLBACK → rpc.ankr.com/polygon | polygon-rpc.com retorna 401 — ankr é público sem auth |
| Backup rotation: manter 7 mais recentes | 38 backups acumulados sem política — limpou 31 backups |
| WhatsApp (8.9) → apenas configurar token | Código 100% pronto em stub, sem nova story |
| Instagram (8.8) → bloqueada até Meta aprovar app | Não adianta implementar sem poder testar |
| Twitter/X (17.1) → OAuth 1.0a com hmac stdlib | Evita dependência requests-oauthlib |
| TikTok (17.2) → upload 3-step (init+PUT+poll) | Único fluxo suportado pelo Content Posting API |
| LiteLLM stack → gpt-4o-mini + DeepSeek V3 + Groq | -60% custo, fallback automático via proxy |
| LiteLLM → OpenAI SDK com base_url (não litellm lib) | Menos dependências, mesma funcionalidade |
| Epic 13 (Dashboard) → adiado | Analisar após social media + LiteLLM |

## Status das Stories

| Story | Status |
|-------|--------|
| 15.3.story | Unknown |
| 15.4.story | Unknown |
| 16.1.story | Unknown |
| 16.2.story | Unknown |
| 16.3.story | Unknown |
| 16.4.story | Unknown |
| 17.1.story | Unknown |
| 17.2.story | Unknown |
| 18.1.story | Unknown |
| 19.1.story | Unknown |
| 19.2.story | Unknown |
| 19.3.story | Unknown |
| 8.8.story | Unknown |
| 8.9.story | InProgress |
| epic-10 | Unknown |
| epic-12 | Unknown |
| epic-16 | Unknown |
| epic-17 | Unknown |
| epic-18 | Unknown |
| epic-19 | Unknown |
| epic-7-ocme-bd-monitor-engine | Unknown |
| epic-8-webdex-orchestrator | Unknown |
| epic-9 | Unknown |
| 10.1.story | Unknown |
| 10.2.story | Unknown |
| 10.3.story | Unknown |
| 10.4.story | Unknown |
| 10.5.story | Unknown |
| 11.1.story | Unknown |
| 12.1.story | Unknown |
| 12.2.story | Unknown |
| 12.2b.story | Unknown |
| 12.3.story | Unknown |
| 12.4.story | Unknown |
| 14.3.story | Unknown |
| 15.1.story | Unknown |
| 15.2.story | Unknown |
| 8.1.story | Unknown |
| 8.2.story | Unknown |
| 8.3.story | Unknown |
| 8.4.story | Unknown |
| 8.5.story | Unknown |
| 8.6.story | Unknown |
| 8.7.story | Unknown |
| 9.1.story | Unknown |
| 9.2.story | Unknown |
| 9.3.story | Unknown |
| 9.4.story | Unknown |

## Decisoes Tomadas

(atualizado pelos agentes durante o trabalho)

## Ultimo Trabalho Realizado

### Sessão 2026-03-23 — Cards V01-V05 com imagens reais bdZinho

**Imagens reais integradas nos 5 HTML cards (zero IA externa):**
- V01 ← `post_149_operador-da-tecnologia_01.jpg` (bdZinho arms open, orquestrando)
- V02 ← `post_145_automação_01.jpg` (bdZinho no cockpit, monitorando)
- V03 ← `post_147_SubAccount_story_01.jpg` (bdZinho explicando estrutura blockchain)
- V04 ← `post_148_ambiente-financeiro_01.jpg` (bdZinho entre ambientes, círculo central)
- V05 ← `post_144_historico_01.jpg` (bdZinho com dashboard de performance)
- Imagens copiadas para `assets/`, CSS ajustado com `drop-shadow` glow por cor do card
- Previews gerados via Playwright em `previews/V01-V05-bdzinho-real.png`

Arquivos criados/modificados:
- `media/projects/ocmc-apresentacao/assets/` (5 imagens bdZinho copiadas)
- `media/projects/ocmc-apresentacao/cards/V01..V05.html` (img tags reais)
- `media/projects/ocmc-apresentacao/previews/V01-V05-bdzinho-real.png` (renders)

### Sessão 2026-03-23 — Design System WEbdEX + Série OCME_bd Visual

**Design workflow executado por Sati + Smith (zero IA externa):**
- `docs/MASTER.md` criado — Brand book WEbdEX unificado (14 seções)
- `media/bdzinho_v3_announcement.html` refinado — quote + closing CTA adicionados
- `media/projects/ocmc-apresentacao/STYLE-GUIDE.md` criado — guide V01-V05
- `media/projects/ocmc-apresentacao/cards/V01-V05` criados — 5 HTML cards 1080×1920px
- Fix OCMC_bd → OCME_bd em README + V01/V02/V04/V05 scripts + cores README

Arquivos criados/modificados:
- `docs/MASTER.md` (novo)
- `media/bdzinho_v3_announcement.html` (modificado)
- `media/projects/ocmc-apresentacao/STYLE-GUIDE.md` (novo)
- `media/projects/ocmc-apresentacao/cards/V01..V05.html` (5 novos)
- `media/projects/ocmc-apresentacao/README.md` (fix naming + cores)
- `media/projects/ocmc-apresentacao/scripts/V01,V02,V04,V05.md` (fix naming)

### Sessão 2026-03-23 — Fixes relatório 21h (TVL + ciclo + Smith audit)

**Bugs corrigidos em `webdex_workers.py`:**
- TVL: `lp_usdt_supply + lp_loop_supply` (raw LP) → `SUM(total_usd)` (USD real)
- Ciclo timing: `_ciclo_21h_since()` = início do ciclo NOVO → subtrair 24h = ciclo que fechou
- Smith Fix 1 🔴: guard `_pr[0] is None` → `_pr[2] == 0` (COUNT() nunca retorna NULL)
- Smith Fix 2 🟡: `_ciclo_fim`/`dt_lim` hoistado para fora do loop por-usuário
- Smith Fix 3 🟡: comentário UTC corrigido ("ontem 00h" → "hoje 00h")
- Smith Fix 4 🟡: upper bound `AND data_hora<?` / `AND ts<?` adicionado (anti double-count)

**TVL fix aplicado também em:**
- `protocol_context.py` (get_protocol_context + get_status_embed_data)
- `scripts/test_relatorio_21h.py`

Arquivos modificados:
- `packages/monitor-engine/webdex_workers.py`
- `packages/monitor-engine/protocol_context.py`
- `packages/monitor-engine/scripts/test_relatorio_21h.py`

### Sessão 2026-03-23 — Epic 19 Monitor v4 Subaccount + Discord

**Epic 19 ✅ CONCLUÍDO e deployado em produção:**
- Story 19.1: `webdex_v4_monitor.py` criado (492 linhas) — poll 5min, Transfer events USDT+LOOP, SQLite v4_events/v4_reports/v4_state
- Story 19.2: `v4_subaccount_worker` registrado em `_THREAD_REGISTRY` (webdex_main.py)
- Story 19.3: Relatório 2h Discord — embed rico, threshold 1tx, marca `reported=1`, persiste `discord_sent=1`
- Canal Discord `#sub-v4-monitor` criado, webhook configurado em `.env` VPS e `.env.example`
- Deploy VPS: Dockerfile corrigido (bytes hex fix), `scp webdex_v4_monitor.py`, `docker build + up`
- Fix logger: `webdex.v4_monitor` → `WEbdEX` (logs INFO visíveis)
- **Resultado**: `[v4] Worker iniciado | sub=0x7c52...414c`, `eventos=1 novos=1`

Arquivos modificados:
- `packages/monitor-engine/webdex_v4_monitor.py` (novo)
- `packages/monitor-engine/webdex_main.py` (+import +thread)
- `packages/monitor-engine/Dockerfile` (+webdex_v4_monitor.py)
- `packages/monitor-engine/.env.example` (+DISCORD_WEBHOOK_V4_SUB)
- `docs/stories/active/epic-19.md`, `19.1-19.3.story.md` (criados)

### Sessão 2026-03-21 (tarde) — Smith VPS Infrastructure Audit + Hardening

**Smith Audit INFECTED→ 13 findings resolvidos:**
- C-01 ✅ iptables INPUT: port 3000 (easypanel) + 5174 (Vite) bloqueados do público, RFC1918 aceito, regras persistidas
- C-02 ✅ Swap 4GB criado e ativado (`/swapfile`, swappiness=10, persistido no fstab)
- C-03 ✅ RPC_FALLBACK trocado `polygon-rpc.com→rpc.ankr.com/polygon` + container restart (health=ok)
- H-03 ✅ Backup rotation adicionada ao ocme-update (38→7 backups, -31 arquivos)
- H-04 ✅ Docker image prune (dangling removidos)
- M-01 ✅ Telegram 403 handler já implementado em `webdex_bot_core.py:122-130`
- M-02 ✅ pg_dump orchestrator-postgres adicionado ao ocme-update (com rotation de 5)
- M-03 ✅ Rede orphan já limpa
- M-04 ✅ CPU 9.65%→5.14% (melhora com retry loop reduzido)
- L-02 ✅ Log rotation já configurada (`max-size: 5m`)
- H-02 ✅ Dead container já ausente

- H-05 ✅ Kernel 6.8.0-90 → 6.8.0-106 (reboot executado — 13/13 containers voltaram automático)
- nginx ✅ Host nginx desativado — estava bloqueando Traefik em todo reboot (55d sem reboot mascarou o bug)
- M-07 ✅ `/usr/local/bin/vps-health-alert` cron */15min: disk, RAM, swap, containers, backup age

**Pendente (VPS infra):**
- `DISCORD_WEBHOOK_ALERT` em `/etc/vps-alerts.conf` (Alex fornecer URL webhook Discord)
- Discord RESUME ~3x/7h — investigar orchestrator-discord (py-cord keepalive)
- Cloudflare SSL: mudar para "Full" (não "Full strict") no dashboard Cloudflare para webdex.app

### Sessão 2026-03-21 (manhã) — Epic 16 QA Audit Monitor Engine COMPLETO** (255/255 testes passando):

**Story 16.3 — Handlers (22+20+15=57 testes):**
- `test_user_handlers.py` — touch_user, set_user_active, upsert_user, ai_can_use, LGPD
- `test_admin_handlers.py` — _is_admin, is_admin_chat, _get_admin_chat_ids, esc, barra_progresso
- `test_reports.py` — _ciclo_21h_label, _profit_emoji, formatar_moeda, period_to_hours

**Story 16.4 — Workers (19+20+13=52 testes):**
- `test_subscription_worker.py` — wallet locks, _persist_subscription ON CONFLICT, _get_chat_id_for_wallet
- `test_notification_engine.py` — cooldown, _post_embed, _check_milestones, _check_new_holders
- `test_creatomate_worker.py` — gerar_video_ciclo, poll timeout, graceful degradation

**Fixes aplicados:**
- `_real_wbc()` helper: remove mock webdex_bot_core, importa real + patch ADMIN_USER_IDS=[123456789]
- `_ensure_subscriptions()`: DROP+CREATE com schema correto (wallet_address) + ALTER TABLE ADD COLUMN subscription_expires
- `_safe_unlink()`: gc.collect() antes de os.unlink para Windows PermissionError
- TestTouchUser: adaptado para UPDATE-only (não INSERT) behavior real

Arquivos modificados:
- `packages/monitor-engine/tests/test_user_handlers.py`
- `packages/monitor-engine/tests/test_admin_handlers.py`
- `packages/monitor-engine/tests/test_reports.py`
- `packages/monitor-engine/tests/test_subscription_worker.py`
- `packages/monitor-engine/tests/test_notification_engine.py`
- `packages/monitor-engine/tests/test_creatomate_worker.py`
- `docs/stories/active/16.3.story.md` → ✅ Ready for Review
- `docs/stories/active/16.4.story.md` → ✅ Ready for Review

### Sessão 2026-03-21 (tarde 2) — Story 15.3 + Docker API Proxy + Traefik HTTPS

**Story 15.3 ✅ Ready for Review:**
- Script `test_relatorio_21h.py` atualizado (assinatura nova, BRT→UTC, tvl_usd)
- Dead import `notify_ciclo_report` removido de `webdex_workers.py`
- Dockerfile: `COPY monitor-engine/scripts/ ./scripts/` adicionado
- Script testado via `docker exec ocme-monitor` — relatório Discord enviado, sem crash

**Docker API Proxy (VPS) ✅:**
- Docker 29.3.0 quebra Traefik v3 (Docker SDK usa v1.24, min agora é v1.40)
- Proxy TCP `172.18.0.1:2376` reescreve versão `v1.2x→v1.47` em tempo real
- Systemd service `docker-api-proxy.service` ativo + boot automático
- iptables: porta 2376 protegida (aceita RFC1918, dropa público)

**Traefik orchestrator ✅ (roteamento OK):**
- `entrypoints=websecure→https` e `docker.network=orchestrator_net→easypanel`
- Containers n8n, orchestrator-api, grafana descobertos pelo Traefik
- curl local retorna 200; externo ainda 520 por Cloudflare SSL

**Pendente (Alex faz no dashboard Cloudflare):**
- SSL/TLS mode: "Full strict" → "Full" para webdex.app (ou criar Origin Certificate)

Arquivos locais modificados:
- `packages/monitor-engine/Dockerfile`
- `packages/monitor-engine/scripts/test_relatorio_21h.py`
- `docs/stories/active/15.3.story.md` → ✅ Ready for Review

## Proximos Passos

- [x] HTTPS 520 → RESOLVIDO: subdomínios *.rxuos9.easypanel.host (n8n 200, grafana 200, api 200)
- [x] get_user_portfolio bug → CORRIGIDO no VPS (fl_snapshots sem coluna wallet)
- [ ] commit + push: PROJECT-CHECKPOINT.md (docker-compose/env são VPS-only)
- [ ] Discord RESUME — comportamento normal py-cord, sem ação necessária
- [ ] Continuar roadmap stories (Epic 17 X/TikTok, Epic 18 LiteLLM, ou outra prioridade)
- [ ] Opcional: apontar webdex.app → rxuos9 hosts via Cloudflare redirect/CNAME (quando Alex quiser)

## Git Recente
(nenhum commit encontrado)
Arquivos modificados: 0

## Ambiente Detectado

Keys: DEEPSEEK_API_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, EXA_API_KEY, CONTEXT7_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, GITHUB_TOKEN, CLICKUP_API_KEY, N8N_API_KEY, N8N_WEBHOOK_URL, SENTRY_DSN, RAILWAY_TOKEN, VERCEL_TOKEN, NODE_ENV, LMAS_VERSION
