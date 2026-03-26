---
type: knowledge
title: "Dev — Discord Bot: IA, Tools e Streaming"
tags:
  - dev
  - discord
  - ai-handler
  - tool-use
  - streaming
created: 2026-03-26
source: neo-sensei
---

# Discord Bot: IA, Tools e Streaming

> Módulo 03 de 10 — Professor: Neo
> Como o bdZinho pensa e responde no Discord.

---

## ai_handler.py — O Cérebro

Toda resposta do bdZinho passa por `ai_handler.py`:

```python
# Fluxo de stream_ai_response()
async def stream_ai_response(user_message, username, channel_name, user_id, user_env):
    # 1. Contexto ao vivo
    protocol_ctx = get_protocol_context()        # TVL, win rate
    knowledge_ctx = get_knowledge_context()       # bdz_knowledge (90+ itens)

    # 2. Memória de longa duração
    history = _mem_get(user_id)                   # PostgreSQL ai_conversations

    # 3. Monta mensagens
    messages = [system] + history + [user_msg]

    # 4. Streaming com tool use (máx 3 iterações)
    async for chunk in client.chat.completions.stream(
        model=_MODEL,  # anthropic/claude-sonnet-4-6
        messages=messages,
        tools=DISCORD_TOOLS   # buscar_vault, consulta_protocolo, etc.
    ):
        yield chunk.text
```

---

## Tool Use — Como Funciona

O bdZinho pode chamar tools durante a resposta:

```python
# webdex_tools_discord.py — lista de tools disponíveis
DISCORD_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consulta_protocolo",
            "description": "Consulta métricas ao vivo: TVL, win rate, P&L, operações",
            "parameters": { "type": "object", "properties": {
                "metrica": {"type": "string"}
            }}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_vault",
            "description": "Busca no vault de conhecimento (59+ notas Obsidian sobre WEbdEX, DeFi, Token BD)",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}
            }}
        }
    }
    # + notificar_operacao, get_subconta_balance, etc.
]
```

**Como adicionar uma nova tool:**
1. Adicionar definição em `DISCORD_TOOLS` (webdex_tools_discord.py)
2. Implementar `_impl_minha_tool(**args) -> str`
3. Adicionar no dispatcher: `elif name == "minha_tool": result = _impl_minha_tool(**args)`
4. Adicionar timeout: `_TOOL_TIMEOUTS["minha_tool"] = 5`

---

## Rate Limiting

```python
# Dois níveis de rate limit:

# 1. Free tier: 36 msgs/24h por usuário (bot.py)
_FREE_LIMIT = 36
_FREE_WINDOW = 86400  # 24h em segundos

# 2. IA rate limit: 10 msgs/hora (ai_handler.py)
_RATE_WINDOW = 3600  # 1 hora
# PRO subscribers: sem limite de msgs/dia, mas ainda 10/hora para IA
```

---

## Memória — PostgreSQL + Fallback

```python
# Salvar mensagem
_mem_add(user_id, "user", "minha pergunta")
_mem_add(user_id, "assistant", "minha resposta")

# Recuperar histórico
history = _mem_get(user_id)
# → [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]

# Apagar (LGPD)
mem_delete_user(user_id)  # deleta tudo no PostgreSQL

# Tabela: ai_conversations (PostgreSQL)
# Colunas: chat_id, role, content, platform='discord', created_at
```

---

## Sistema de Botões (ia_buttons.py)

O menu do canal `#bdzinho-ia` é gerenciado por `BdZinhoMenuView`:

```python
class BdZinhoMenuView(discord.ui.View):
    # Botão: 🔗 Conectar Wallet → ConectarWalletModal
    # Botão: 💎 Assinar PRO → embed com instrução de pagamento
    # Botão: 📊 Minha Assinatura → status da assinatura
    # Botão: 🤖 Iniciar Chat → cria thread privada
    # Botão: 🧠 Modo Dev → ativa pensamento estendido (96.3 BD/mês)
```

Para adicionar novo botão:
```python
@discord.ui.button(label="🆕 Meu Botão", style=discord.ButtonStyle.secondary,
                   custom_id="btn_meu_botao")
async def btn_meu(self, interaction: discord.Interaction, button: discord.ui.Button):
    await interaction.response.send_message("...", ephemeral=True)
```

---

## Subscription Gate (subscription.py)

```python
# Verificar se usuário tem PRO ativo
from subscription import is_subscribed, days_remaining
wallet = get_user_wallet(discord_user_id)
if wallet and is_subscribed(wallet):
    # PRO: mensagens ilimitadas
    pass

# Contrato: 0x6481d77f95b654F89A1C8D993654d5f877fe6E22 (Polygon)
# Token BD: 0xf49dA0F454d212B80F40693cdDd452D8Caa2fa6d
# Preço PRO: 36.9 BD/mês
# Preço Dev: 96.3 BD/mês (inclui extended thinking)
```

---

## voice_discord.py — SYSTEM_PROMPT

O `SYSTEM_PROMPT` define a personalidade do bdZinho. Modificar com cuidado:
- Nunca remover identidade WEbdEX
- Adicionar novas capacidades no final do prompt
- `build_prompt()` injeta contexto dinâmico (protocolo, ambiente do usuário)

---

## Design Tokens

```python
# design_tokens.py
PRO_PURPLE = 0x7C3AED   # cor para assinantes PRO
SUCCESS    = 0x10B981   # confirmações
WARNING    = 0xF59E0B   # alertas
ERROR      = 0xEF4444   # erros
PINK_LIGHT = 0xFB0491   # brand WEbdEX

# Sempre usar esses tokens — nunca hardcodar cores nos embeds
embed = discord.Embed(color=SUCCESS)
```
