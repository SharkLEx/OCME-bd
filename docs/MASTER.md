# WEbdEX Protocol — Design System MASTER

> **Fonte da Verdade:** Este documento é o brand book oficial da WEbdEX.
> Todos os assets, templates e tokens devem derivar daqui.
> Última atualização: 2026-03-23

---

## 1. Identidade da Marca

### Posicionamento
**WEbdEX Protocol** é um protocolo DeFi de monitoramento on-chain.
O bot **bdZinho (OCME_bd)** traz dados reais da Polygon diretamente ao usuário — via Telegram e Discord.

**Tagline:** "Informação é poder. Na WEbdEX, ela vem até você."
**Sub-tagline:** "Ainda em beta? Sim. Parando? Nunca."

### Tom de Voz
- Direto e técnico — sem rodeios
- Confiante — dados reais, em tempo real
- Celebratório em wins (🟢), analítico em losses (🔴)
- Didático com novatos, preciso com experts
- Nunca condescendente. Sempre útil.

---

## 2. Paleta de Cores

### Brand Core

| Token           | Hex       | Uso principal                              |
|-----------------|-----------|--------------------------------------------|
| `--black`       | `#000000` | Background principal — base de tudo        |
| `--dark`        | `#131313` | Superfícies, cards, painéis                |
| `--pink`        | `#FB0491` | Accent primário — ícone, CTAs, bdZinho     |
| `--red`         | `#D90048` | Accent secundário — urgência, novo holder  |
| `--white`       | `#FFFFFF` | Texto principal                            |
| `--gray`        | `#888888` | Texto secundário / muted                   |

### Semânticos

| Token           | Hex       | Uso                                        |
|-----------------|-----------|--------------------------------------------|
| `--success`     | `#00FFB2` | P&L positivo, win, PRO ativa               |
| `--warning`     | `#FF8800` | Atenção, P&L negativo / loss               |
| `--error`       | `#FF4455` | Crítico, anomalia severa                   |
| `--pro-purple`  | `#E040FB` | Tier PRO — exclusivo assinantes            |
| `--cyan`        | `#00D4FF` | Gráficos, visualizações de dados           |

### Mapa de Contexto (Discord Embeds)

```python
EMBED_COLORS = {
    "brand":       0xFB0491,   # identidade geral
    "status":      0x00FFB2,   # /status, resumo
    "chart":       0x00D4FF,   # /grafico, visualizações
    "milestone":   0xFB0491,   # milestones TVL, holders
    "ciclo_win":   0x00FFB2,   # ciclo 21h P&L positivo
    "ciclo_loss":  0xFF8800,   # ciclo 21h P&L negativo
    "alert":       0xD90048,   # alertas do protocolo
    "anomalia":    0xFF4455,   # anomalia crítica
    "pro":         0xE040FB,   # ações PRO
    "gm":          0xFB0491,   # ritual 7h
    "new_holder":  0xD90048,   # novo holder
    "default":     0x131313,   # fallback neutro
}
```

---

## 3. Tipografia

### Hierarquia

| Papel          | Fonte             | Pesos          | Uso                                    |
|----------------|-------------------|----------------|----------------------------------------|
| **Logo/Pixel** | Press Start 2P    | Regular (400)  | Wordmark "WEbdEX", versão "v3.0", IDs  |
| **UI Primary** | Syne              | 400, 600, 700, 800 | Todo texto da interface            |
| **Code**       | monospace (system)| —              | Endereços, hashes, valores on-chain    |

> **Nota:** O Manual da Marca original especifica "B1 5X5 Regular" para o logo pixel.
> Em ambiente web, "Press Start 2P" (Google Fonts) é o substituto oficial aprovado.

### Escala Tipográfica (CSS)

```css
/* Logo wordmark */
font-family: 'Press Start 2P', monospace;
font-size: 26px;

/* Hero title */
font-family: 'Syne', sans-serif;
font-size: 96px;
font-weight: 800;
line-height: 1.0;
letter-spacing: -2px;

/* Hero tagline */
font-family: 'Syne', sans-serif;
font-size: 38px;
font-weight: 800;

/* Body / Feature */
font-family: 'Syne', sans-serif;
font-size: 24px;
font-weight: 400;
line-height: 1.4;

/* Badge / Label */
font-family: 'Syne', sans-serif;
font-size: 18-20px;
font-weight: 700;
letter-spacing: 2-4px;
text-transform: uppercase;
```

---

## 4. Logotipo

### Ícone (Logo Mark)

```css
/* Logo icon — spec completa */
width: 72px;
height: 72px;
border-radius: 18px;
background: linear-gradient(135deg, #FB0491 0%, #D90048 100%);
font-family: 'Press Start 2P', monospace;
font-size: 22px;
color: #FFFFFF;
letter-spacing: -2px;
content: "bd";
```

Variante footer (48px):
```css
width: 48px; height: 48px;
border-radius: 12px;
font-size: 14px;
```

### Wordmark

```
WE[bd]EX
```
- "WE" e "EX" em `#FFFFFF`
- "bd" em `#FB0491`
- Font: Press Start 2P

### Gradiente de Marca

```css
/* Brand gradient — usar em ícones, CTAs, destaques premium */
background: linear-gradient(135deg, #FB0491 0%, #D90048 100%);

/* Glow pink — efeito de brilho de fundo */
background: radial-gradient(circle, rgba(251,4,145,0.18) 0%, transparent 70%);

/* Glow cyan — efeito secundário */
background: radial-gradient(circle, rgba(0,212,255,0.10) 0%, transparent 70%);
```

### URL do Avatar (bdZinho)
```
https://i.ibb.co/MkcqbvLb/post-149-operador-da-tecnologia-01.jpg
```

---

## 5. Espaçamento

Escala baseada em múltiplos de 8px:

| Token | Value | Uso |
|-------|-------|-----|
| `space-1` | `8px`  | gap mínimo, padding icon |
| `space-2` | `12px` | gap entre elementos inline |
| `space-3` | `16px` | gap padrão, margin-bottom labels |
| `space-4` | `20px` | gap entre logo e texto |
| `space-5` | `24px` | gap entre cards |
| `space-6` | `28px` | gap feature icon + content |
| `space-7` | `32px` | margin-bottom antes de títulos |
| `space-8` | `40px` | padding footer |
| `space-9` | `44px` | padding feature cards horizontal |
| `space-10`| `48px` | padding header, seções internas |
| `space-12`| `60px` | padding coming-soon bottom |
| `space-16`| `64px` | padding lateral padrão (1080px canvas) |
| `space-20`| `80px` | padding hero top |

---

## 6. Border Radius

| Token | Value | Uso |
|-------|-------|-----|
| `radius-sm` | `12px` | logo icon footer |
| `radius-md` | `18px` | logo icon header |
| `radius-lg` | `20px` | cards |
| `radius-pill` | `999px` | badges, pills |

---

## 7. Separadores (Telegram)

```python
SEP_LINHA   = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"  # título de seção
SEP_FINA    = "─────────────────────────"            # subsecção
SEP_ITEM    = "  ├─"   # item de lista
SEP_ULTIMO  = "  └─"   # último item de lista
SEP_RECUO   = "  "     # indentação
```

---

## 8. Emojis por Categoria

### Status / Resultado
| Emoji | Contexto |
|-------|---------|
| 🟢 | P&L positivo, ciclo verde |
| 🔴 | P&L negativo, ciclo vermelho |
| ⚪ | Neutro, sem dados |

### Financeiro
| Emoji | Contexto |
|-------|---------|
| 💰 | Capital, USDT, saldo |
| ✅ | Lucros, ganhos |
| ❌ | Perdas, loss |
| ⛽ | Gas consumido |
| 💎 | Receita do protocolo, BD |
| 🏦 | Período de receita |
| 📦 | Acumulado, supply total |

### Dados / Analytics
| Emoji | Contexto |
|-------|---------|
| 📊 | Gráfico, trades, dados |
| 📈 | Tendência positiva, ROI |
| 👥 | Traders, holders |
| 💼 | Carteira do usuário |
| 🎟️ | Passe de assinatura |

### Blockchain
| Emoji | Contexto |
|-------|---------|
| ⚡ | Protocolo ao vivo |
| 🔄 | SwapBook, swaps |
| 🔗 | Link Polygonscan |
| 🔷 | Rede Polygon |
| 💎 | Movimentação token WEbdEX |
| 🌱 | Mint de token |
| 👛 | Nova carteira |

### Sistema / Bot
| Emoji | Contexto |
|-------|---------|
| ⚠️ | Aviso |
| 🚨 | Anomalia crítica |
| 💡 | Informação, CTA |
| 🤖 | OCME_bd, bot, IA |

### Conquistas
| Emoji | Contexto |
|-------|---------|
| 🏆 | Melhor trade, milestone |
| 🥇🥈🥉 | Top traders |
| 🎉 | Nova carteira, celebração |

### Tempo / Ciclos
| Emoji | Contexto |
|-------|---------|
| 🌙 | Relatório 21h (noturno) |
| 🗓️ | Data do ciclo |
| ⏰ | Hora, tempo real |
| ☀️ | Good morning, ritual 7h |

---

## 9. Padrões de Card (CSS)

### Feature Card
```css
.feature-card {
  background: #131313;
  border-radius: 20px;
  padding: 36px 44px;
  border-left: 4px solid [accent-color];
  /* Overlay sutil com cor do accent */
  background: linear-gradient(135deg, rgba([r],[g],[b],0.06) 0%, transparent 60%);
}
```

### Badge / Pill
```css
.badge {
  background: rgba([r],[g],[b], 0.15);
  border: 1px solid rgba([r],[g],[b], 0.4);
  color: [accent-color];
  padding: 8px 20px;
  border-radius: 999px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
}
```

### Divider (decorativo)
```css
.divider {
  height: 1px;
  background: linear-gradient(90deg,
    transparent 0%,
    rgba(251,4,145,0.3) 30%,
    rgba(251,4,145,0.3) 70%,
    transparent 100%
  );
}
```

---

## 10. Formatos de Canvas (Assets Visuais)

| Formato | Dimensão | Uso |
|---------|---------|-----|
| Story/Post vertical | 1080×1920px | bdZinho announcements, ciclo 21h |
| Post quadrado | 1080×1080px | Milestones, stats |
| Banner horizontal | 1200×628px | OG image, link preview |
| Miniatura | 400×400px | Avatar, ícone |

---

## 11. Headings de Mensagem (Telegram HTML)

```python
# Relatório noturno
"🌙 <b>RELATÓRIO DO CICLO 21H — WEbdEX PROTOCOL</b>\n"

# Relatório pessoal
"📊 <b>mybdBook — WEbdEX</b>\n"

# Protocolo ao vivo
"⚡ <b>PROTOCOLO WEbdEX — AO VIVO · {hora}</b>\n"

# SwapBook
"🔄 <b>SWAPBOOK WEbdEX — {hora}</b>\n"

# Token WEbdEX
"📊 <b>TOKEN WEbdEX — RELATÓRIO DE CRESCIMENTO</b>\n"
```

---

## 12. Footer Padrão

```
WEbdEX Protocol · bdZinho
```

Telegram HTML:
```html
<a href="https://t.me/OCME_bd">Ativar OCME_bd — Beta Gratuito</a>
```

---

## 13. Fontes de Verdade por Plataforma

| Plataforma | Arquivo | Status |
|------------|---------|--------|
| Discord | `packages/orchestrator/discord/design_tokens.py` | ✅ Produção |
| Telegram | `packages/monitor-engine/telegram_design_tokens.py` | ✅ Produção |
| Web/HTML | `media/bdzinho_v3_announcement.html` | 🔄 Template |
| Unificado | `docs/MASTER.md` (este arquivo) | ✅ Fonte da verdade |

---

## 14. Anti-Patterns (O que NÃO fazer)

- ❌ Fundo branco ou claro — a WEbdEX vive no escuro
- ❌ Fontes sem-serif genéricas (Arial, Roboto) — sempre Syne
- ❌ Cores fora da paleta sem aprovação — especialmente cores pastéis
- ❌ Logo sem o ícone quadrado + gradiente
- ❌ "bd" fora do highlight em `#FB0491` no wordmark
- ❌ Texto de sistema sem separadores ━━━ / ─────
- ❌ Emojis fora do mapeamento semântico

---

*WEbdEX Protocol · Design System v1.0 · 2026-03-23*
*Mantido por: @ux-design-expert (Sati)*
