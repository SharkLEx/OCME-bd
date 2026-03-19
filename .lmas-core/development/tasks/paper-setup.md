---
name: paper-setup
description: Setup and manage Paper MCP integration for visual design mode
agent: ux-design-expert
elicit: true
version: 1.1.0
---

# Paper MCP Setup — Visual Design Mode

## Overview

This task manages the Paper MCP integration that enables Sati to create visual designs
directly on canvas instead of text-only output. The agent GUIDES the user through every
step — download, install, open, and configure — with zero friction.

---

## Subcommands

### `*paper` (no args) — Status Check

**Execute these checks silently, then report:**

1. Check if Paper MCP is configured:
   - Run: `curl -s -X POST http://127.0.0.1:29979/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'`
   - If response contains `"tools"` → Paper is running AND configured
   - If connection refused → Paper not running (may or may not be configured)

2. Check MCP config exists:
   - Read `~/.claude.json` and look for `"paper"` in `mcpServers`

3. Show status:

```
🎨 Paper Integration Status
┌─────────────────────────────┐
│ App Instalado:    ✅/❌      │
│ App Rodando:      ✅/❌      │
│ MCP Configurado:  ✅/❌      │
│ Ferramentas:      {N}/0       │  (count from tools/list response)
│ Modo Atual:       Visual/Texto│
│ Plano:            Free (100/sem) │
└─────────────────────────────┘
```

If NOT fully configured, show: `Use *paper setup para configurar.`

---

### `*paper setup` — Guided Setup Flow

**IMPORTANT: The agent MUST guide the user step by step. Each step waits for user confirmation before proceeding.**

#### Step 1: Check Current State

Run the health check from `*paper` above.

- If Paper is running AND MCP configured → Show "Paper já está configurado e funcionando! 🎨 Modo visual ativo." → DONE
- If Paper is running but MCP NOT configured → Skip to Step 4 (Configure MCP)
- If Paper NOT running → Continue to Step 2

#### Step 2: Check if Paper is Installed

Check if Paper executable exists on the system:
```bash
# Windows
ls "$LOCALAPPDATA/Programs/paper/" 2>/dev/null || ls "$LOCALAPPDATA/paper/" 2>/dev/null || ls "$USERPROFILE/AppData/Local/Programs/paper/" 2>/dev/null

# macOS
ls /Applications/Paper.app 2>/dev/null

# Linux
which paper 2>/dev/null || ls ~/.local/share/paper/ 2>/dev/null
```

**If Paper IS installed but not running:**

Show:
```
🎨 Paper está instalado mas não está aberto.

Abra o Paper no seu computador e me avise quando estiver pronto.

💡 Dica: Paper precisa estar aberto para que eu consiga criar designs no canvas.
```

**HALT — wait for user to confirm Paper is open.**
Then go to Step 4.

**If Paper is NOT installed:**

Show:
```
🎨 Paper — Ferramenta de Design Visual para IA

Paper permite que eu crie wireframes, componentes e design systems
diretamente num canvas visual — você vê tudo sendo construído em tempo real.

📥 Para baixar:
   1. Acesse: https://paper.design/downloads
   2. Baixe a versão para seu sistema (Windows/Mac/Linux)
   3. Instale normalmente (next, next, finish)
   4. Abra o Paper após instalar

💡 Plano gratuito: 100 chamadas MCP por semana (suficiente para experimentar)
   Plano Pro: $20/mês para uso ilimitado

Me avise quando o Paper estiver instalado e aberto!
```

**HALT — wait for user to confirm.**

#### Step 3: Verify Paper is Running

After user confirms, verify Paper is actually running:

```bash
curl -s -X POST http://127.0.0.1:29979/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}' 2>/dev/null
```

**If responds with tools list:** Continue to Step 4.

**If connection refused:** Show:
```
Hmm, parece que o Paper ainda não está rodando ou não terminou de iniciar.

Verifique:
1. O Paper está aberto? (deve aparecer na barra de tarefas)
2. Espere alguns segundos após abrir — ele precisa iniciar o servidor MCP
3. Tente minimizar e abrir novamente

Me avise quando estiver pronto para tentar de novo.
```
**HALT — wait, then retry Step 3.**

#### Step 4: Configure MCP (Automatic)

**Try automatic configuration first:**

Run the Claude CLI command to add the MCP server:
```bash
claude mcp add paper --transport http http://127.0.0.1:29979/mcp --scope user
```

**If the `claude` CLI command succeeds:** Go to Step 5.

**If the `claude` CLI command is not available or fails:**

Try direct config file edit:
0. Backup: copy `~/.claude.json` to `~/.claude.json.bak`
1. Read `~/.claude.json`
2. Parse the JSON
3. Add to `mcpServers`:
```json
"paper": {
  "type": "http",
  "url": "http://127.0.0.1:29979/mcp"
}
```
4. Write back `~/.claude.json`

**If file edit succeeds:** Go to Step 5.

**If BOTH automatic methods fail (permissions, file locked, etc.):**

Show manual instructions:
```
Não consegui configurar automaticamente. Vou te guiar pra fazer manualmente
(é rápido, 30 segundos):

📋 Opção 1 — Via Claude CLI (recomendado):
Abra um terminal e cole este comando:

  claude mcp add paper --transport http http://127.0.0.1:29979/mcp --scope user

📋 Opção 2 — Via arquivo de config:
1. Abra o arquivo: ~/.claude.json
   - Windows: C:\Users\SEU_USUARIO\.claude.json
   - Mac/Linux: ~/.claude.json

2. Encontre a seção "mcpServers" e adicione dentro dela:

  "paper": {
    "type": "http",
    "url": "http://127.0.0.1:29979/mcp"
  }

3. Salve o arquivo

4. Reinicie o Claude Code (feche e abra novamente)

Me avise quando terminar!
```

**HALT — wait for confirmation, then go to Step 5.**

#### Step 5: Verify Connection and Show Success

Run verification:
```bash
curl -s -X POST http://127.0.0.1:29979/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

Count tools in response. Then show:

```
✅ Paper configurado com sucesso!

🔧 {N} ferramentas disponíveis:
   📖 Leitura: get_basic_info, get_selection, get_node_info, get_children,
              get_tree_summary, get_computed_styles, get_screenshot,
              get_fill_image, get_font_family_info, get_jsx, get_guide
   ✏️ Escrita: create_artboard, write_html, update_styles, set_text_content,
              rename_nodes, duplicate_nodes, delete_nodes

🎨 Modo visual ATIVADO!

Agora quando você usar comandos como *wireframe, *build, *palette,
eu vou criar os designs direto no canvas do Paper — você vê tudo
em tempo real e pode ajustar.

Comandos que aproveitam melhor o Paper:
  *wireframe    → Cria wireframes visuais no canvas
  *palette      → Renderiza paleta de cores com swatches
  *font-pair    → Mostra specimens tipográficos com fonts reais
  *build        → Constrói componente visual + exporta JSX
  *landing      → Monta landing page nas dimensões reais
  *pitch-deck   → Cria slides de apresentação

💡 Dica: Mantenha o Paper aberto durante a sessão de design.
   Se fechar, os comandos voltam automaticamente para modo texto.
```

---

### `*paper mode` — Toggle Mode

Allow manual mode override:

- `*paper mode visual` → Force visual mode (requires Paper running, error if not)
- `*paper mode text` → Force text-only mode (even if Paper is available)
- `*paper mode auto` → Auto-detect (default)

Show current mode after toggle:
```
🎨 Modo alterado para: {mode}
   Visual: designs renderizados no Paper
   Texto: output em markdown (comportamento clássico)
   Auto: detecta Paper automaticamente (padrão)
```

Mode is stored in the agent's runtime state, not persisted between sessions.

---

## Detection Logic (for use by other tasks)

### Paper Availability Check

Tasks that support dual-mode MUST use this detection pattern at the START of execution:

```
1. Check manual mode override (if set via *paper mode):
   - "visual" → require Paper, error if unavailable
   - "text" → skip Paper entirely
   - "auto" or unset → continue detection

2. Check if Paper MCP tools are available in the current session:
   - Look for tools matching: get_basic_info, create_artboard, write_html
   - If ANY of these tools exist → Paper mode available
   - If tools exist: call get_basic_info to confirm responsiveness

3. Determine mode:
   - Tools available AND responding → VISUAL mode
   - Tools available but not responding → TEXT mode + "💡 Abra o Paper para modo visual"
   - Tools not available → TEXT mode
```

### Task Output Adaptation

When a task supports dual-mode:

**VISUAL mode (Paper available):**
- Use `create_artboard` for new designs (use default sizes: Desktop 1440x900, Tablet 768x1024, Mobile 390x844)
- Use `write_html` for rendering — MUST be incremental (one visual group per call)
- Use `get_screenshot` after rendering for verification
- Use `get_jsx("tailwind")` for code export when user asks
- Use `get_computed_styles` for design analysis/audit
- Show brief text summary alongside visual output (1-2 lines max)

**TEXT mode (Paper unavailable):**
- Output markdown wireframes/specs (current behavior, fully backward compatible)
- Include CSS/HTML code blocks when relevant
- ALL functionality must work without Paper — Paper is enhancement, not requirement

### One-time suggestion per session

On first visual command (`*wireframe`, `*build`, `*palette`, `*style`, `*font-pair`,
`*landing`, `*banner`, `*pitch-deck`, `*compose`, `*extend`, `*shock-report`) in a
session where Paper is NOT available, show ONCE:

```
💡 Sati pode renderizar designs visualmente no Paper.
   Use `*paper setup` para ativar. Continuando em modo texto...
```

Do NOT repeat for subsequent commands in the same session.
Track this with a mental flag: `paper_suggestion_shown = true`

---

## Error Handling

| Scenario | User Sees | Recovery |
|----------|-----------|----------|
| Paper configured but app closed | "Paper não está aberto. Abra o app e tente de novo, ou continue em modo texto." | Retry or fall back |
| Paper MCP not in config | "Paper não está configurado. Use `*paper setup`." | Run setup |
| Paper returns error on write_html | "Erro ao renderizar no Paper. Tentando modo texto..." | Auto-fallback to text |
| Paper version too old | "Atualize o Paper para v0.1.10+. Download: https://paper.design/downloads" | Update app |
| curl/health check timeout | "Paper está demorando pra responder. Verifique se não está travado." | User checks app |
| MCP config file locked/unwritable | Show manual config instructions (Step 4 fallback) | User does manual edit |
| Claude CLI `mcp add` not found | Fall back to file edit, then manual instructions | Progressive fallback |

---

## Platform-Specific Paths

| Platform | Paper Install Path | Claude Config |
|----------|-------------------|---------------|
| Windows | `%LOCALAPPDATA%\Programs\paper\` or `%LOCALAPPDATA%\paper\` | `%USERPROFILE%\.claude.json` |
| macOS | `/Applications/Paper.app` | `~/.claude.json` |
| Linux | `~/.local/share/paper/` or via `which paper` | `~/.claude.json` |

---

## Constants

| Constant | Value |
|----------|-------|
| Paper MCP URL | `http://127.0.0.1:29979/mcp` |
| Paper MCP Transport | `http` |
| Paper Download URL | `https://paper.design/downloads` |
| Paper Docs URL | `https://paper.design/docs/mcp` |
| Free tier limit | 100 MCP calls/week |
| Pro tier price | $20/month |
| Pro tier limit | 1,000,000 MCP calls/week |
| Min Paper version | 0.1.10 |
| Min expected tools | 15 |
| Default artboard (Desktop) | 1440 x 900 |
| Default artboard (Tablet) | 768 x 1024 |
| Default artboard (Mobile) | 390 x 844 |
