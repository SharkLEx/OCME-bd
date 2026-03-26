# Project Checkpoint

> Ultima atualizacao: 2026-03-26 (auto-refresh)

## Contexto Ativo

**Sessão 2026-03-26 noite — VAULT ATIVO + BUGS CORRIGIDOS ✅**

### Entregues nesta sessão:

**BUG 2 — Botão 🔌 Conectar para novos usuários ✅**
- `main_kb()` agora mostra "🔌 Conectar" condicionalmente para usuários sem wallet
- Usuários conectados NÃO veem o botão (comportamento correto)

**BUG 3 — NameError em auto_resume_notify ✅**
- `main_kb(m.chat.id)` → `main_kb(cid)` — `m` não existia no escopo
- Deployado via docker cp + docker restart ocme-monitor

**Vault Obsidian ATIVO ✅**
- Descoberta: vault existe em `/ocme_data/vault/` (Docker volume) + `/opt/vault/` (host)
- Sync automático criado: `/opt/sync_vault.sh` — cron `0 * * * *` (cada hora)
- `056-dai-integration.md` sincronizada e confirmada no Discord bot
- `vault_reader.search_vault('DAI integração')` → 3 resultados ✅
- bdZinho Discord pode usar tool `buscar_vault` com knowledge completo

**Docker-compose atualizados (local):**
- `orchestrator/docker-compose.yml`: volume `/opt/vault:/app/vault:ro` + `VAULT_PATH`
- `monitor-engine/docker-compose.yml`: volume `/opt/vault:/app/vault` + `VAULT_LOCAL_PATH`

**Verificações:**
- Ciclo 21h: 5821 trades, 27/29 wallets — FUNCIONANDO ✅
- Filtros: lógica OK — query/handler corretos ✅
- Container ocme-monitor: UP healthy após restart ✅

---

**Sessão 2026-03-26 tarde — DAI MONITORING DEPLOYADO ✅**

### DAI adicionado ao monitor v4 ✅
- `TOKEN_DAI = 0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063` (18 decimals, Polygon)
- Loop de polling: `[TOKEN_USDT, TOKEN_LOOP, TOKEN_DAI]`
- Relatório 2h + diário: campos 🟡 DAI in/out, líquido = USDT+DAI
- Deploy: `docker cp` + `docker restart` — container healthy, v4 worker ativo
- Capital_cache: DAI já aparece no breakdown real de usuário (AG_C_bd $18.414)
- **Próximo:** commit + push via @devops

**Sessão 2026-03-26 tarde — OCME CRASH RESOLVIDO E DEPLOYADO ✅**

### Incidente ocme-monitor — FECHADO ✅

**Causa raiz (2 bugs simultâneos):**
1. `webdex_db.py`: cursor global compartilhado entre 20 threads → SIGSEGV em Python 3.12
2. Container rodava imagem OLD (INSERT 11 colunas) vs source com 15 cols vs tabela com 17 cols

**Fixes deployados (commits `0f29bab` + `82174b4` — branch feat/epic-7-monitor-engine):**
- `webdex_db.py`: `_ConnProxy` + `_CursorProxy` com `threading.local()` — cada thread tem sua própria conexão SQLite
- `webdex_monitor.py`: INSERT atualizado para 17 colunas (inclui `contract_address`, `gas_pol`)
- `webdex_observability.py`: `check_same_thread=False` em ambos os `sqlite3.connect()`
- Docker image rebuiltada e force-recreated com os fixes

**Status pós-fix:**
- Container: `Up 8+ min (healthy)` — RestartCount=0
- anomaly_worker: ✅ rodando com 4492 subcontas (era o gatilho do segfault)
- VIGIA lag: recuperando (10014 → 7937 blocos, ~15min para realtime)
- Operações: 105.163 registradas, trades chegando normalmente

**Pendências restantes:**
1. 🟡 Push do branch `feat/epic-7-monitor-engine` para remote (quando Alex quiser)
2. 🟡 Watchdog externo via n8n (pingar healthcheck a cada 5min)
3. 🟡 Merge do branch de fix para main no VPS

**Sessão 2026-03-26 — Vault RAG + Smith audit CLEAN ✅ DEPLOYADO**

Commits deployados no submodule orchestrator:
- `c2b912d` fix(vault): C-1 race condition + C-2 prompt injection + H-2 size limit + H-3 memory leak

Entregas desta sessão:
- **vault_reader.py** (NOVO): RAG completo — indexa 59+ notas Obsidian, busca por relevância
- **webdex_tools_discord.py** (MODIFICADO): tool `buscar_vault` adicionada — bdZinho lê o vault em tempo real
- **webdex_vault_writer.py** (NOVO, monitor-engine): Nexo escreve notas aprendidas no vault (fecha o loop)
- **webdex_ai.py** (MODIFICADO): remove circulação sem fonte (Smith LOW)
- **bdzinho_v3_announcement.html** (REESCRITO): logo circular + cards TVL/win rate/vault/token
- **Smith audit**: 4 findings resolvidos → INFECTED → CLEAN
  - C-1: race condition em _load() → _load_lock + double-check
  - C-2: prompt injection via vault → _sanitize_excerpt() aplicado
  - H-2: notas >50KB ignoradas (proteção de memória)
  - H-3: _rate_data cresce sem evicção → evict periódico a cada hora
- Bot WEbdEX#7787 online e saudável após restart

**M-4 RESOLVIDO ✅**: vault compartilhado via `monitor-engine_monitor_data` Docker volume
- `ocme-monitor` escreve em `/app/data/vault/` (rw)
- `orchestrator-discord` lê de `/ocme_data/vault/` (ro) — mesmo volume
- Nexo aprende → escreve `.md` → bdZinho lê na próxima query. Loop fechado.
- 59 notas migradas, vault_status: available=true, notes_count=59

**Sessão 2026-03-26 — bdPro ULTRATHINK DeFi Avançado + Playground Foundry ✅**

Notas Obsidian criadas (curriculum bdPro — Dimensão 10):
- `knowledge/solidity-dev/013-agregadores-defi.md` — 1inch (Router V5 + API), 0x Protocol, Paraswap, routing de liquidez, execução on-chain, segurança, Python off-chain (OCME)
- `knowledge/solidity-dev/014-chainlink-oracles.md` — AggregatorV3Interface, feeds Polygon (MATIC/USD, ETH/USD, USDT/USD), validações staleness/roundIncomplete, TWAP Uniswap V3 via tickCumulatives, integração WEbdEXSubscription V2
- `knowledge/solidity-dev/015-permit2-aprovacoes.md` — EIP-712 domain separator, EIP-2612 Permit (OZ ERC20Permit), Uniswap Permit2 (0x000...22D4), SignatureTransfer vs AllowanceTransfer, frontend ethers v6, WEbdEXSubscription com 3 métodos
- `knowledge/solidity-dev/016-webdex-contracts-playground.md` — Documentação do playground Foundry real (sol-016)

Playground Foundry criado: `packages/webdex-contracts/`
- `src/WEbdEXSubscriptionV2.sol` — contrato com 3 métodos: classic/EIP-2612/Permit2 + Chainlink oracle
- `src/interfaces/` — IPermit2, IAggregatorV3, I1inchRouter
- `test/SubscriptionV2.t.sol` — testes unitários completos (mocks + fuzz)
- `test/ForkTest.t.sol` — testes fork Polygon Mainnet (USDT real + Chainlink real + Permit2 real)
- `script/Deploy.s.sol` — deploy Amoy + Mainnet com verificação PolygonScan
- `foundry.toml` — config completo + remappings OZ v5 + Chainlink

Smith audit: todas as notas (sol-013 a sol-016) CLEAN ✅
Status total: 71 notas Obsidian / 10 dimensões

**Sessão 2026-03-25 madrugada (Token BD ULTRATHINK) — CONCLUÍDA ✅**

Commits deployados:
- `7a5ee01` feat(ultrathink): Token BD ULTRATHINK — Obsidian `016-token-bd-knowledge.md` + voice_discord.py atualizado
- `8fa8632` feat(tokenomia): Token BD knowledge completo no system prompt bdZinho (submodule)

**Token BD ULTRATHINK ✅ DEPLOYADO:**
- Nota Obsidian: `knowledge/webdex/016-token-bd-knowledge.md` (supply, distribuição, ICM, Swapbook, V.A.L.T., casos de uso)
- bdZinho Discord: seção TOKEN BD de 5→15 linhas com tokenomia completa
- Container orchestrator-discord: healthy, bot WEbdEX#7787 online

**Sessão 2026-03-25 noite (OCME Infra Hardening v2 + #conquistas) — CONCLUÍDA ✅**

Commits deployados no VPS:
- `b4497f0` OOM fix: docker-compose memory 768M → 1536M
- `9464ea5` #conquistas redesign + cursor bug fix em webdex_milestones
- `ffc7226` **CRÍTICO: webdex_db.py thread-local connections** — elimina segfault SQLite

**Causa raiz dos crashes "toda hora" ENCONTRADA E CORRIGIDA:**
- `dmesg` revelou: segfault em `_sqlite3.cpython-312.so` — 20+ threads, 1 conexão SQLite
- Fix: `_ConnProxy` + `_CursorProxy` com `threading.local()` em webdex_db.py
- Container: Restarts=0 desde 21:43, MEM=44%, logs CLEAN

**#conquistas Discord:** canal = feed saúde do protocolo (nova_carteira + daily summary)
**Próximo:** Epic 13 (Dashboard Externo Next.js+SIWE)

**Sessão 2026-03-25 madrugada — CONCLUÍDA ✅**

Entregas (commit `d0685ae` pushado + deployado VPS):
- Notas Obsidian 052-055 — Dimensão 9 criada (55 notas totais)
- Dashboard Público (Gap #1) LIVE: `https://track-ocme.rxuos9.easypanel.host/dashboard-publico.html`
- `/api/data/public-dashboard`: win_rate 77%, P&L $933K, 4.37M ciclos, histórico 60
- card_server auto-inicia com bot, DB correto `/ocme_data/webdex_v5_final.db`, imagem rebuilded ✅
- Próximo: Gap #2 DeCripto; Epic 13; sincronizar git VPS

**Sessão 2026-03-25 noite — CONCLUÍDA ✅**

Entregas desta sessão (commits pushados + deployados VPS):
- `1e5585d` feat(conquistas): Track Record v2 — gold theme, win_rate, dados reais
- `1f04db8` fix(card_server): OCME_DB_PATH → TODOS os cards agora com dados reais!
- `22f01dd` chore: bump root

**#conquistas Track Record ✅ LIVE — dados reais confirmados via API:**
- 🏆 Streak: 3 ciclos positivos consecutivos
- 💯 Win Rate: 77% dos ciclos lucrativos
- 📈 P&L Total: $932.795 acumulado
- 🎯 Record Ciclo: $4,35

**BUG CRÍTICO CORRIGIDO: card_server DB_PATH ✅**
- Todos os 8 cards Discord agora usam /ocme_data/webdex_v5_final.db (4.37M rows)

**Vault Obsidian VPS sincronizado ✅ (55 notas)**
- market-intelligence 044-050 adicionadas
- MOC-bdZinho-Learning-Map.md atualizado

**Sessão 2026-03-25 noite (Sprints OCME Telegram) — CONCLUÍDA ✅**
- Sprint 1 Hamann: infra hardening (memory 768M, restart policy, SIGTERM graceful, throttle restart)
- Sprint 2 Kamala: UX redesign (4-button menu + 4 submenus + backward compat)
- Sprint 3 Mifune: bdZinho expressão emocional no ciclo 21h Telegram (timeout 30s, rate limit)
- Smith supervisão: INFECTED → CLEAN após 4 correções (BD-01 timeout, UX-01/02/05 menu fixes)
- Arquivos modificados: docker-compose.yml, webdex_main.py, webdex_handlers/user.py, webdex_workers.py

**Próximas sessões:**
- Deploy para VPS: SCP 4 arquivos + docker compose build + up ocme-monitor
- Deploy trainer fix (webdex_ai_trainer.py Nexo fixes já copiado via docker cp)
- Epic 13 (Dashboard Externo Next.js)

## Contexto Ativo (anterior)

**bdZinho Cards v3 ✅ 100% DEPLOYADO NO VPS** (2026-03-25 15:00)
- card_server.py: auto-inicia com o bot via `_start_card_server()` no `on_ready`
- Node.js v24 + Playwright + Chromium headless instalados no container orchestrator-discord
- render_card.js versão Linux — token-bd.webm 740KB gerado e testado no VPS
- `/card` slash command: 10 comandos Discord sincronizados (era 9)
- bdz_knowledge: **99 items ativos** (+9 sobre sistema de cards)
- Obsidian vault VPS: nota 051 criada em knowledge/webdex/
- VPS host: Node.js v18 + Chromium 146 também disponíveis

**Commits locais (aguardando push pelo @devops):**
- `767cbe5` chore: bump orchestrator (auto-start card_server)
- `4932feb` fix: render_card_linux.js + path fix container
- `8b6a7a3` feat(cards-v3): 8 cards + sistema dados ao vivo

**Market Intelligence WEbdEX Q1/Q2 2026 ✅ INJETADA E DEPLOYADA** (2026-03-25)
- Pesquisa extensiva: 7 temas, 18+ fontes, dados Q1 2026
- Arquivo fonte: `knowledge/webdex/015-market-intelligence-Q1Q2-2026.md`
- 7 notas Obsidian criadas: `knowledge/market-intelligence/044–050` (8ª dimensão do vault)
- **34 items injetados** (V1: 23 + V2: 11) — total: **90 items ativos** (era 56)
- Cache Discord invalidado — bdZinho recarrega 90 items na próxima resposta
- Achados V1: TVL DeFi $130-140B; Polygon ATH $3,28B; Brasil 5° adoção; VASP Fev/26; DeCripto Jul/26; ciclo 21h ≠ MEV bots
- Achados V2 (3 agentes): **Katana** (chain DeFi Mar/2026); yield-bearing stablecoins (narrativa #1 2026); DeFAI $1.3B market cap; "hash trap" DeCripto; dashboard público como gap prioritário
- 5 gaps: **Dashboard público** (#1 urgente+fácil), DeCripto educação (#2), Token BD staking (#3), Copy trading (#4), USDC rotas (#5)

**ULTRATHINK OPERATION ✅ 100% CONCLUÍDA — AMBOS CONTAINERS** (2026-03-25)
- 43 notas Zettelkasten L5 criadas (7 dimensões do conhecimento bdZinho)
- MOC-bdZinho-Learning-Map.md: mapa total com conexões cruzadas no Obsidian
- Smith hardening: 10 vetores de falha identificados e neutralizados (027-smith-hardening-bdzinho.md)
- 34 items injetados no bdz_knowledge VPS (7 categorias)
- **Telegram** `webdex_ai.py` v3: identidade bdZinho completa, vocab obrigatório, DADOS→MECANISMO→PROVA, Regra de Ouro
- **Discord** `voice_discord.py` v3: Smith-hardened, 10 vetores, vocab, Pro subscriber awareness — Bot online ✅
- Regra gravada: Discord é primário (Pro subscription), mas SEMPRE atualizar os 2

**Rename Interno MATRIX → bdZinho ✅ CONCLUÍDO** (2026-03-25 | commit `7afe3f6`)
- Variáveis, logs e docstrings: toda referência `MATRIX-X.X` removida do código Python
- `_MATRIX36/41/44_ENABLED` → `_DISCORD_CARD/PROACTIVE_MODULE/CYCLE_VISUAL_MODULE_ENABLED`
- Comando admin `/matrix3_stats` → `/bdz_stats`
- Deploy VPS `{"status": "ok"}` confirmado

**bdZinho Cycle Visual ✅ DEPLOYADO** (2026-03-25 | commit `d06af3d`)
- bdZinho com expressão emocional pós-ciclo: CELEBRANDO/PROFISSIONAL/NEUTRO
- Posta imagem no Discord após cada ciclo 21h

**bdZinho Vision ✅ DEPLOYADO** (2026-03-25 | commit `d06af3d`)
- Usuário envia foto → bdZinho analisa via Gemini Flash Vision
- Personalizado com perfil individual do trader

**MATRIX 4.1 — Proactive Mode ✅ DEPLOYADO** (2026-03-25 | commit `88b07e2`)
- `webdex_ai_proactive.py`: post_cycle_nudge() dispara pós-ciclo 21h
- LLM DeepSeek gera insight personalizado por trader (perfil MATRIX 4.0 + dados ciclo)
- Rate limit 24h/user, máx 15 usuários/ciclo, fallback sem LLM
- Hook em `webdex_workers.py` agendador_21h após broadcast Telegram
- VPS: `{"status": "ok"}` | MATRIX 4.0 ATIVO confirmado

**MATRIX 4.0 — Individual Memory ✅ DEPLOYADO** (2026-03-25 | commit `07644d6`)

**MATRIX 3.0→3.6 Smith Hardening ✅ CONCLUÍDO** (2026-03-25 | commit `e03d7a6`)
- 10 findings corrigidos: 3 HIGH + 7 MEDIUM — veredito final CLEAN
- HIGH-01: guard `pending:` MATRIX-3.6 antes do daemon thread (anti double-post)
- HIGH-02: connection leak trainer corrigido (try/finally)
- HIGH-03: prompt injection — XML isolation + truncate 300 chars no conteúdo de usuários
- Deployado VPS: `{"status": "ok"}` | commit pushado `66986ef..e03d7a6`

**MATRIX 3.7 — Nano Banana Image Gen ✅ DEPLOYADO** (2026-03-25 | commit `6d31c9e`)
- `webdex_ai_image_gen.py`: geração via OpenRouter Gemini (google/gemini-2.5-flash-image)
- Handler Telegram `🎨 Criar Imagem` no main_kb + next_step + rate limit 30s
- VPS: `{"status": "ok"}` — porta 9090, uptime confirmado

**MATRIX 4.0 — Individual Memory ✅ DEPLOYADO** (2026-03-25 | commit `07644d6`)
- `webdex_ai_user_profile.py`: tabela `bdz_user_profiles`, perfil por trader (facts JSONB + summary)
- `webdex_ai.py`: `profile_build_context()` injetado no brain prompt + `profile_touch()` assíncrono
- `webdex_ai_trainer.py`: 4o agente Profile Updater roda toda meia-noite
- VPS: módulos `profile module OK` + `profile_updater: True` confirmados

**MATRIX 3.6 → 3.0 stack completo e operacional em produção**

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
| epic-7-ocme-bd-monitor-engine | Unknown |

## Decisoes Tomadas

(atualizado pelos agentes durante o trabalho)

## Ultimo Trabalho Realizado

(nenhum commit encontrado)

Arquivos modificados (nao commitados): 0

## Proximos Passos

(atualizado pelos agentes durante o trabalho)

## Git Recente
(nenhum commit encontrado)
Arquivos modificados: 0

## Ambiente Detectado

Keys: DEEPSEEK_API_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, EXA_API_KEY, CONTEXT7_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, GITHUB_TOKEN, CLICKUP_API_KEY, N8N_API_KEY, N8N_WEBHOOK_URL, SENTRY_DSN, RAILWAY_TOKEN, VERCEL_TOKEN, NODE_ENV, LMAS_VERSION, OBSIDIAN_API_KEY
