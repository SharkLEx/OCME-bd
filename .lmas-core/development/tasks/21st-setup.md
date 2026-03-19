---
name: 21st-setup
description: Setup 21st.dev Magic MCP for AI-powered component library access
agent: ux-design-expert
elicit: true
version: 1.0.0
---

# 21st.dev Magic MCP Setup — Component Library Integration

## Overview

This task configures the 21st.dev Magic MCP, giving Sati access to thousands of
production-ready React/Tailwind components with advanced effects (3D, shaders,
scroll animations, glassmorphism, etc.).

**Tools unlocked:** `component_builder`, `component_inspiration`, `component_refiner`, `logo_search`

---

## Command: `*21st` (no args) — Status Check

1. Check if `magic` exists in MCP config (`~/.claude.json` → `mcpServers.magic`)
2. Check if magic tools are available in current session (look for `mcp__magic__*` tools)
3. Report:

```
🧩 21st.dev Magic Status
┌──────────────────────────────────┐
│ MCP Configurado:    ✅/❌         │
│ Tools Disponíveis:  4/0          │
│   - component_builder     ✅/❌  │
│   - component_inspiration ✅/❌  │
│   - component_refiner     ✅/❌  │
│   - logo_search           ✅/❌  │
└──────────────────────────────────┘
```

If not configured: `Use *21st setup para configurar.`

---

## Command: `*21st setup` — Guided Setup Flow

### Step 1: Check Current State

- Read `~/.claude.json` and look for `mcpServers.magic`
- If found AND tools working → "21st.dev Magic já está configurado! 🧩 4 ferramentas disponíveis." → DONE
- If found but NOT working → Go to Step 5 (Troubleshoot)
- If NOT found → Continue to Step 2

### Step 2: Explain What 21st.dev Is

Show:
```
🧩 21st.dev Magic — Biblioteca de Componentes IA

21st.dev é uma biblioteca com milhares de componentes React/Tailwind
publicados pela comunidade — inclui efeitos avançados como:
  - Scroll animations com parallax e 3D
  - Shaders WebGL e backgrounds cinematográficos
  - Glassmorphism, spring physics, Framer Motion
  - Hero sections, pricing, testimonials, CTAs prontos
  - Logos SVG de qualquer empresa

É gratuito! Só precisa criar uma conta para gerar sua API key.
Vou abrir a página pra você — leva 30 segundos.
```

### Step 3: Open Browser and Guide Login

**Open the browser automatically:**

```bash
# Windows
start https://21st.dev/magic/console

# macOS
open https://21st.dev/magic/console

# Linux
xdg-open https://21st.dev/magic/console
```

Detect platform from system and use the correct command.

Show:
```
🌐 Abri a página do 21st.dev no seu browser.

Siga estes passos:
  1. Faça login (pode usar GitHub, Google, ou email)
  2. Após logar, você verá sua API Key na página
  3. Copie a API key e cole aqui

Aguardando sua API key...
```

**HALT — wait for user to paste their API key.**

### Step 3b: If Browser Didn't Open

If the user says the browser didn't open, or they can't access:

```
Sem problema! Acesse manualmente:

📋 Cole este link no seu browser:
   https://21st.dev/magic/console

Ou se preferir ir pela home:
  1. Acesse: https://21st.dev
  2. Clique em "Log in" (canto superior direito)
  3. Faça login com GitHub, Google ou email
  4. Após logar, acesse: https://21st.dev/magic/console
  5. Copie a API key que aparece na página

Cole a key aqui quando tiver!
```

**HALT — wait for user.**

### Step 3c: If User Can't Create Account or Login

```
Se está tendo problemas para criar conta:

📧 Via Email:
  1. Clique em "Sign up" ou "Log in"
  2. Digite seu email
  3. Verifique sua caixa de entrada (e spam) para o link de confirmação
  4. Clique no link e volte para https://21st.dev/magic/console

🔗 Via GitHub:
  1. Clique em "Continue with GitHub"
  2. Autorize o app 21st.dev
  3. Pronto — você será redirecionado ao console

🔗 Via Google:
  1. Clique em "Continue with Google"
  2. Escolha sua conta Google
  3. Pronto

Se nenhum método funcionar, pode ser um bloqueio temporário do site.
Tente novamente em alguns minutos ou use outro browser.
```

**HALT — wait for user.**

### Step 3d: If User Can't Find the API Key

```
A API key deve aparecer na página https://21st.dev/magic/console

Se não encontra:
  1. Verifique se está logado (deve ver seu avatar/nome no canto)
  2. A key geralmente aparece num campo de texto ou card na página
  3. Pode haver um botão "Generate Key" ou "Create API Key" — clique nele
  4. A key parece com: a1b2c3d4e5f6a7b8c9d0e1f2...  (texto longo com letras e números)

Se ainda não consegue encontrar, me descreva o que você vê na página
e eu te guio.
```

**HALT — wait for user.**

### Step 4: Configure MCP (Automatic)

Once user provides the API key:

**Validate the key format:**
- Should be a hex string (letters a-f and numbers 0-9)
- Typically 64 characters long
- If format looks wrong, ask user to verify: "Essa key parece diferente do esperado. Tem certeza que copiou toda a chave?"

**Try automatic installation via CLI first:**

```bash
npx @21st-dev/cli@latest install claude --api-key <USER_KEY>
```

**If CLI succeeds:** Go to Step 6 (Verify).

**If CLI fails or is not available, configure manually:**

0. Backup: copy `~/.claude.json` to `~/.claude.json.bak`
1. Read `~/.claude.json`
2. Parse JSON
3. Add to `mcpServers`:

Para Windows:
```json
"magic": {
  "type": "stdio",
  "command": "cmd",
  "args": ["/c", "npx", "-y", "@21st-dev/magic@latest"],
  "env": {
    "API_KEY": "<USER_KEY>"
  }
}
```

Para Mac/Linux:
```json
"magic": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@21st-dev/magic@latest"],
  "env": {
    "API_KEY": "<USER_KEY>"
  }
}
```

Detect platform and use the correct variant automatically.

4. Write back `~/.claude.json`

**If file edit succeeds:** Go to Step 6 (Verify).

**If BOTH automatic methods fail:**

Show manual instructions:
```
Não consegui configurar automaticamente. Vou te dar os passos manuais
(30 segundos):

📋 Opção 1 — Via terminal (mais fácil):
Cole este comando no terminal:

  npx @21st-dev/cli@latest install claude --api-key SUA_KEY_AQUI

Substitua SUA_KEY_AQUI pela key que você copiou.

📋 Opção 2 — Via arquivo de config:
1. Abra: ~/.claude.json
   - Windows: C:\Users\SEU_USUARIO\.claude.json
   - Mac/Linux: ~/.claude.json

2. Encontre "mcpServers": { ... } e adicione dentro:

  Para Windows:
  "magic": {
    "type": "stdio",
    "command": "cmd",
    "args": ["/c", "npx", "-y", "@21st-dev/magic@latest"],
    "env": {
      "API_KEY": "SUA_KEY_AQUI"
    }
  }

  Para Mac/Linux:
  "magic": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@21st-dev/magic@latest"],
    "env": {
      "API_KEY": "SUA_KEY_AQUI"
    }
  }

3. Salve o arquivo
4. Reinicie o Claude Code (feche e abra novamente)

Me avise quando terminar!
```

**HALT — wait for confirmation.**

### Step 5: Troubleshoot (MCP configured but not working)

If the MCP entry exists in config but tools aren't available:

```
O 21st.dev Magic está configurado mas não está funcionando.
Possíveis causas:

1. ❌ API key inválida ou expirada
   → Acesse https://21st.dev/magic/console e gere uma nova key
   → Me passe a nova key que eu atualizo

2. ❌ Node.js não instalado ou versão antiga
   → Verifique: node --version (precisa ser 18+)
   → Se não tem Node: https://nodejs.org

3. ❌ npx não funciona (bloqueio de rede/proxy)
   → Tente rodar: npx -y @21st-dev/magic@latest --help
   → Se der erro de rede, pode ser firewall/proxy corporativo

4. ❌ Claude Code precisa reiniciar
   → Feche e abra o Claude Code novamente
   → O MCP só carrega na inicialização

Qual desses pode ser o caso?
```

**HALT — diagnose based on user response.**

### Step 6: Verify and Show Success

After configuration, verify:
- Check if `mcp__magic__*` tools are now available in the session
- Note: May need Claude Code restart for stdio MCP to load

Show:
```
✅ 21st.dev Magic configurado com sucesso!

🧩 4 ferramentas de componentes disponíveis:
   🔨 component_builder     — Gera componentes React/Tailwind sob demanda
   💡 component_inspiration — Busca componentes existentes para inspiração
   ✨ component_refiner     — Melhora/refina componentes existentes
   🎨 logo_search           — Busca logos SVG de qualquer empresa

Agora quando Sati usa *build, *wireframe ou *landing, ela pode
buscar referências na biblioteca 21st.dev com milhares de componentes
com efeitos avançados (3D, scroll, shaders, glassmorphism).

💡 Dica: Se precisar reiniciar o Claude Code para os tools carregarem,
   feche e abra novamente.
```

If Claude Code needs restart:
```
⚠️ O 21st.dev Magic é um MCP stdio — precisa reiniciar o Claude Code
para carregar. Feche e abra novamente, depois use *21st pra verificar.
```

---

## Detection Logic (for use by other tasks)

### 21st.dev Availability Check

```
1. Check if mcp__magic__21st_magic_component_builder tool exists
   - If yes → 21st.dev available
   - If no → 21st.dev not available

2. No health check needed (stdio MCP — if tool exists, it works)
```

### Task Integration Pattern

When Sati commands can benefit from 21st.dev:

**If 21st.dev available:**
- `*build {component}` → First call `component_inspiration` to find similar components
- `*landing {type}` → Call `component_inspiration` for hero, features, pricing sections
- `*wireframe` → Call `component_inspiration` for layout references
- Any logo needed → Call `logo_search`

**If 21st.dev NOT available:**
- Build from scratch (current behavior)
- On first component build per session, suggest ONCE:
  "💡 Com 21st.dev Magic, Sati pode buscar milhares de componentes prontos como referência. Use `*21st setup` para ativar."

---

## Error Handling

| Scenario | User Sees | Recovery |
|----------|-----------|----------|
| Browser won't open | Manual URL + step-by-step instructions | Step 3b |
| Can't create account | Email/GitHub/Google alternatives | Step 3c |
| Can't find API key | Visual guide to console page | Step 3d |
| Invalid API key format | Ask to re-copy | Validate in Step 4 |
| CLI install fails | File edit fallback → manual instructions | Progressive fallback |
| Tools not loading after config | Restart Claude Code | Step 6 note |
| Node.js not installed | Link to nodejs.org | Step 5 |
| Network/proxy blocking npx | Diagnose + alternatives | Step 5 |

---

## Constants

| Constant | Value |
|----------|-------|
| Console URL | `https://21st.dev/magic/console` |
| Home URL | `https://21st.dev/home` |
| NPM Package | `@21st-dev/magic@latest` |
| CLI Package | `@21st-dev/cli@latest` |
| Config Key | `magic` (in mcpServers) |
| Transport | `stdio` |
| Required: API_KEY | Yes (env var) |
| Windows command | `cmd /c npx -y @21st-dev/magic@latest` |
| Mac/Linux command | `npx -y @21st-dev/magic@latest` |
| Tools count | 4 |
| Pricing | Free (community) |
| Node.js min version | 18+ |
