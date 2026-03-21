# Project Checkpoint

> Ultima atualizacao: 2026-03-21 01:34 (pre-compact save)

## Contexto Ativo

**Sessão 2026-03-21 — Stories 15.3 + 15.4 + Smith INFECTED→corrigido ✅**
Branch: `main` (entregas diretamente em main)
Trabalhando: Fixes críticos F-01→F-04 do Smith — deploy VPS confirmado
Próximo: Story 15.4 testes unitários (@qa, F-07 pendente) + F-08 cleanup config table

## Decisoes Tomadas

| Decisão | Motivo |
|---------|--------|
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

### Sessão 2026-03-21

**Epic 16 — QA Audit Monitor Engine COMPLETO** (255/255 testes passando):

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

## Proximos Passos

(atualizado pelos agentes durante o trabalho)

## Git Recente
(nenhum commit encontrado)
Arquivos modificados: 0

## Ambiente Detectado

Keys: DEEPSEEK_API_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, EXA_API_KEY, CONTEXT7_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, GITHUB_TOKEN, CLICKUP_API_KEY, N8N_API_KEY, N8N_WEBHOOK_URL, SENTRY_DSN, RAILWAY_TOKEN, VERCEL_TOKEN, NODE_ENV, LMAS_VERSION
