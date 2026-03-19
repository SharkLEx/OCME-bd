# AGENTS.md - LMAS

Este arquivo configura o comportamento esperado de agentes no Codex CLI neste repositorio.

## Constitution

Siga `.lmas-core/constitution.md` como fonte de verdade:
- CLI First
- Agent Authority
- Story-Driven Development
- No Invention
- Quality First
- Absolute Imports

## Workflow Obrigatorio

1. Inicie por uma story em `docs/stories/`
2. Implemente apenas o que os acceptance criteria pedem
3. Atualize checklist (`[ ]` -> `[x]`) e file list
4. Execute quality gates antes de concluir

## Quality Gates

```bash
npm run lint
npm run typecheck
npm test
```

## Estrutura Principal

- Core framework: `.lmas-core/`
- CLI: `bin/`
- Pacotes: `packages/`
- Testes: `tests/`
- Documentacao: `docs/`

## IDE/Agent Sync

- Sincronizar regras/agentes: `npm run sync:ide`
- Validar drift: `npm run sync:ide:check`
- Rodar paridade multi-IDE (Claude/Codex/Gemini): `npm run validate:parity`
- Sync Claude Code: `npm run sync:ide:claude`
- Sincronizar Gemini CLI: `npm run sync:ide:gemini`
- Validar Codex sync/integration: `npm run validate:codex-sync && npm run validate:codex-integration`
- Gerar skills locais do Codex: `npm run sync:skills:codex`
- Este repositorio usa **local-first**: prefira `.codex/skills` versionado no projeto
- Use `sync:skills:codex:global` apenas para testes fora deste repo

## Agent Shortcuts (Codex)

Preferencia de ativacao no Codex CLI:
1. Use `/skills` e selecione `lmas-<agent-id>` vindo de `.codex/skills` (ex.: `lmas-architect`)
2. Se preferir, use os atalhos abaixo (`@architect`, `/architect`, etc.)

Quando a mensagem do usuario for um atalho de agente, carregue o arquivo correspondente em `.lmas-core/development/agents/` (fallback: `.codex/agents/`), renderize o greeting via `generate-greeting.js` e assuma a persona ate receber `*exit`.

Atalhos aceitos por agente:
- `@lmas-master`, `/lmas-master`, `/lmas-master.md` -> `.lmas-core/development/agents/lmas-master.md`
- `@analyst`, `/analyst`, `/analyst.md` -> `.lmas-core/development/agents/analyst.md`
- `@architect`, `/architect`, `/architect.md` -> `.lmas-core/development/agents/architect.md`
- `@data-engineer`, `/data-engineer`, `/data-engineer.md` -> `.lmas-core/development/agents/data-engineer.md`
- `@dev`, `/dev`, `/dev.md` -> `.lmas-core/development/agents/dev.md`
- `@devops`, `/devops`, `/devops.md` -> `.lmas-core/development/agents/devops.md`
- `@pm`, `/pm`, `/pm.md` -> `.lmas-core/development/agents/pm.md`
- `@po`, `/po`, `/po.md` -> `.lmas-core/development/agents/po.md`
- `@qa`, `/qa`, `/qa.md` -> `.lmas-core/development/agents/qa.md`
- `@sm`, `/sm`, `/sm.md` -> `.lmas-core/development/agents/sm.md`
- `@squad-creator`, `/squad-creator`, `/squad-creator.md` -> `.lmas-core/development/agents/squad-creator.md`
- `@ux-design-expert`, `/ux-design-expert`, `/ux-design-expert.md` -> `.lmas-core/development/agents/ux-design-expert.md`

Resposta esperada ao ativar atalho:
1. Confirmar agente ativado
2. Mostrar 3-6 comandos principais (`*help`, etc.)
3. Seguir na persona do agente

---

<!-- LMAS-MANAGED SECTIONS -->
<!-- These sections are managed by LMAS. Edit content between markers carefully. -->
<!-- Your custom content above will be preserved during updates. -->

<!-- LMAS-MANAGED-START: core -->
## Core Rules

1. Siga a Constitution em `.lmas-core/constitution.md`
2. Priorize `CLI First -> Observability Second -> UI Third`
3. Trabalhe por stories em `docs/stories/`
4. Nao invente requisitos fora dos artefatos existentes
<!-- LMAS-MANAGED-END: core -->

<!-- LMAS-MANAGED-START: quality -->
## Quality Gates

- Rode `npm run lint`
- Rode `npm run typecheck`
- Rode `npm test`
- Atualize checklist e file list da story antes de concluir
<!-- LMAS-MANAGED-END: quality -->

<!-- LMAS-MANAGED-START: codebase -->
## Project Map

- Core framework: `.lmas-core/`
- CLI entrypoints: `bin/`
- Shared packages: `packages/`
- Tests: `tests/`
- Docs: `docs/`
<!-- LMAS-MANAGED-END: codebase -->

<!-- LMAS-MANAGED-START: commands -->
## Common Commands

- `npm run sync:ide`
- `npm run sync:ide:check`
- `npm run sync:skills:codex`
- `npm run sync:skills:codex:global` (opcional; neste repo o padrao e local-first)
- `npm run validate:structure`
- `npm run validate:agents`
<!-- LMAS-MANAGED-END: commands -->

<!-- LMAS-MANAGED-START: shortcuts -->
## Agent Shortcuts

Preferencia de ativacao no Codex CLI:
1. Use `/skills` e selecione `lmas-<agent-id>` vindo de `.codex/skills` (ex.: `lmas-architect`)
2. Se preferir, use os atalhos abaixo (`@architect`, `/architect`, etc.)

Interprete os atalhos abaixo carregando o arquivo correspondente em `.lmas-core/development/agents/` (fallback: `.codex/agents/`), renderize o greeting via `generate-greeting.js` e assuma a persona ate `*exit`:

- `@architect`, `/architect`, `/architect.md` -> `.lmas-core/development/agents/architect.md`
- `@dev`, `/dev`, `/dev.md` -> `.lmas-core/development/agents/dev.md`
- `@qa`, `/qa`, `/qa.md` -> `.lmas-core/development/agents/qa.md`
- `@pm`, `/pm`, `/pm.md` -> `.lmas-core/development/agents/pm.md`
- `@po`, `/po`, `/po.md` -> `.lmas-core/development/agents/po.md`
- `@sm`, `/sm`, `/sm.md` -> `.lmas-core/development/agents/sm.md`
- `@analyst`, `/analyst`, `/analyst.md` -> `.lmas-core/development/agents/analyst.md`
- `@devops`, `/devops`, `/devops.md` -> `.lmas-core/development/agents/devops.md`
- `@data-engineer`, `/data-engineer`, `/data-engineer.md` -> `.lmas-core/development/agents/data-engineer.md`
- `@ux-design-expert`, `/ux-design-expert`, `/ux-design-expert.md` -> `.lmas-core/development/agents/ux-design-expert.md`
- `@squad-creator`, `/squad-creator`, `/squad-creator.md` -> `.lmas-core/development/agents/squad-creator.md`
- `@lmas-master`, `/lmas-master`, `/lmas-master.md` -> `.lmas-core/development/agents/lmas-master.md`
<!-- LMAS-MANAGED-END: shortcuts -->
