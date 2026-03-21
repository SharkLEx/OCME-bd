# Project Checkpoint

> Ultima atualizacao: 2026-03-21 (auto-refresh)

## Contexto Ativo

**Sessão 2026-03-21 (tarde 2) — Story 15.3 ✅ + Docker API Proxy VPS ✅ + Traefik HTTPS ✅**
Branch: `feat/epic-7-monitor-engine`
Status: 15.3 Ready for Review. Docker API proxy v1.24→v1.47 resolveu Traefik vs Docker 29.3.0. Routing interno OK (200), HTTPS 520 pendente Cloudflare dashboard.
Pendente: Cloudflare SSL → "Full" (não strict) | Discord RESUME | commit + push

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
| 8.8.story | Unknown |
| 8.9.story | InProgress |
| epic-10 | Unknown |
| epic-12 | Unknown |
| epic-16 | Unknown |
| epic-17 | Unknown |
| epic-18 | Unknown |
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

- [ ] Alex: Cloudflare dashboard → SSL mode "Full" para webdex.app (resolve 520)
- [ ] commit + push: Dockerfile, 15.3.story.md, PROJECT-CHECKPOINT.md
- [ ] Discord RESUME investigation (orchestrator-discord py-cord config)
- [ ] Continuar roadmap stories (Epic 17 X/TikTok, Epic 18 LiteLLM, ou outra prioridade)

## Git Recente
(nenhum commit encontrado)
Arquivos modificados: 0

## Ambiente Detectado

Keys: DEEPSEEK_API_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, EXA_API_KEY, CONTEXT7_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, GITHUB_TOKEN, CLICKUP_API_KEY, N8N_API_KEY, N8N_WEBHOOK_URL, SENTRY_DSN, RAILWAY_TOKEN, VERCEL_TOKEN, NODE_ENV, LMAS_VERSION
