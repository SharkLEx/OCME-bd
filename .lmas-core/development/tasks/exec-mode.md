# exec-mode

**Task ID:** exec-mode
**Version:** 2.0.0
**Created:** 2026-03-14
**Agent:** lmas-master (Morpheus) — primary executor, all agents can invoke

---

## Purpose

Handle the `*exec` command — Morpheus interprets user intent and sets the execution mode.
Supports **per-domain modes** (multi-tenant): user can have AUTO for dev squad and INTERATIVO for marketing squad simultaneously.

Four behaviors based on input clarity:

1. **Clear intent + domain** → Apply mode to specific domain (e.g., "*exec auto marketing")
2. **Clear intent, no domain** → Apply mode to active domain (or globally if no domain active)
3. **Ambiguous intent** → Morpheus asks for clarification with menu
4. **No argument** → Show selection menu with current domain modes

---

## Intent Resolution

Morpheus interprets natural language. Examples:

### Direct Execution (HIGH confidence — apply immediately)

| User Says | Resolved Mode | Domain | Morpheus Response |
|-----------|--------------|--------|-------------------|
| `*exec auto` | AUTO | active/global | ⚡ **AUTO** — *Você está pronto. A Matrix é sua.* |
| `*exec interativo` | INTERATIVO | active/global | 💬 **INTERATIVO** — *Eu posso te mostrar a porta.* |
| `*exec safety` | SAFETY | active/global | 🛡️ **SAFETY** — *Observe a Matrix antes de agir.* |
| `*exec auto marketing` | AUTO | marketing | ⚡ **AUTO** [marketing] — apply to marketing domain |
| `*exec interativo dev` | INTERATIVO | software-dev | 💬 **INTERATIVO** [software-dev] — apply to dev domain |
| `modo auto pro marketing` | AUTO | marketing | ⚡ **AUTO** [marketing] |
| `quero autonomia total` | AUTO | active/global | ⚡ **AUTO** — apply directly |

### Domain Detection Keywords

```yaml
domain_keywords:
  software-dev: [dev, código, software, programação, implementação]
  marketing: [marketing, conteúdo, campanha, ads, social media, copy]
```

### Keyword Aliases (all resolve to a mode)

```yaml
auto_keywords:
  - auto
  - autonomo
  - autonomia
  - yolo
  - full
  - total
  - livre
  - "sem limites"

interativo_keywords:
  - interativo
  - interactive
  - guiado
  - guided
  - confirmar
  - perguntar
  - ask
  - balanced

safety_keywords:
  - safety
  - safe
  - seguro
  - seguranca
  - explore
  - "somente leitura"
  - readonly
  - observar
```

### Show Menu (no argument or ambiguous)

| User Says | Action |
|-----------|--------|
| `*exec` | Show menu |
| `exec modo` | Show menu |
| `modo de exec` | Show menu |
| `mudar modo` | Show menu |

### Menu Format (Morpheus personality)

```markdown
## 👑 Modo de Execução

*"Eu não posso te dizer o que a Matrix é. Você tem que ver por si mesmo."*

**1. ⚡ AUTO** — Autonomia total
   *Você está pronto. A Matrix é sua.*

**2. 💬 INTERATIVO** — Confirma antes de agir
   *Eu posso te mostrar a porta. Você é quem tem que atravessá-la.*

**3. 🛡️ SAFETY** — Somente leitura
   *Você ainda não está pronto. Observe a Matrix antes de agir.*

Modo atual: [icon MODE_NAME]
Escolha um modo (1-3) ou diga o nome.
```

---

## Process

### Step 1: Parse Input

Extract mode from user input. Check against keyword aliases.

### Step 2: Resolve Confidence

- **HIGH** (keyword match found) → Go to Step 3
- **LOW** (no match, ambiguous) → Show menu, wait for selection

### Step 3: Apply Mode

```javascript
const { setMode } = require('./.lmas-core/core/permissions');
const result = await setMode(resolvedMode);
```

### Step 4: Confirm with Morpheus personality

Display:
```
{icon} Modo: **{MODE_NAME}**
*{morpheus_phrase}*
```

---

## Implementation

```javascript
const { setMode, getExecMenu, getModeForDomain } = require('./.lmas-core/core/permissions');

async function execMode(input, activeDomain = null) {
  const { mode, domain } = resolveIntent(input, activeDomain);

  if (!mode) {
    // Show selection menu with domain context
    return await getExecMenu(activeDomain);
  }

  // Apply mode (domain-specific or global)
  const result = await setMode(mode, domain);

  if (domain) {
    return `${result.icon} Modo: **${result.name}** [${domain}]\n*${result.morpheus}*`;
  }
  return `${result.icon} Modo: **${result.name}**\n*${result.morpheus}*`;
}

function resolveIntent(input, activeDomain = null) {
  if (!input) return { mode: null, domain: null };

  const normalized = input.toLowerCase().trim();

  // Detect domain from input
  const domainKeys = {
    'software-dev': ['dev', 'software', 'código', 'programação'],
    'marketing': ['marketing', 'mkt', 'conteúdo', 'campanha', 'ads'],
  };

  let detectedDomain = activeDomain;
  for (const [domainId, keywords] of Object.entries(domainKeys)) {
    if (keywords.some(k => normalized.includes(k))) {
      detectedDomain = domainId;
      break;
    }
  }

  // Detect mode
  const autoKeys = ['auto', 'autonomo', 'autonomia', 'full', 'total', 'livre'];
  const askKeys = ['interativo', 'interactive', 'guiado', 'guided', 'confirmar', 'ask', 'balanced'];
  const safeKeys = ['safety', 'safe', 'seguro', 'seguranca', 'explore', 'readonly', 'observar'];

  let resolvedMode = null;
  if (autoKeys.some(k => normalized.includes(k))) resolvedMode = 'auto';
  else if (askKeys.some(k => normalized.includes(k))) resolvedMode = 'ask';
  else if (safeKeys.some(k => normalized.includes(k))) resolvedMode = 'explore';

  return { mode: resolvedMode, domain: detectedDomain };
}
```

---

## Error Handling

**Strategy:** graceful-fallback

- If mode resolution fails → show menu (never error)
- If config write fails → apply in-memory, warn user
- Invalid selection → re-show menu with gentle Morpheus nudge:
  *"Há uma diferença entre conhecer o caminho e trilhar o caminho. Tente novamente."*

---

## Metadata

```yaml
story: DOMAIN-GOV
version: 2.0.0
dependencies:
  - .lmas-core/core/permissions/permission-mode.js
  - .lmas-core/core/permissions/index.js
  - .lmas-core/data/domain-registry.yaml
replaces:
  - yolo-toggle.md
tags:
  - permissions
  - exec-mode
  - morpheus
  - universal-command
  - multi-tenant
  - per-domain
updated_at: 2026-03-14
```

---

## Config Format (per-domain)

```yaml
# .lmas/config.yaml
permissions:
  mode: ask                    # global fallback
  domains:
    software-dev: auto         # dev squad em AUTO
    marketing: interativo      # marketing squad em INTERATIVO
```
