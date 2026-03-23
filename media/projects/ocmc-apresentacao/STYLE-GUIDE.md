# Style Guide — Série OCME_bd Apresentação

> Alinhado com `docs/MASTER.md` (fonte da verdade de design).
> Última atualização: 2026-03-23

---

## ⚠️ Correções Necessárias neste Projeto

### 1. Nomenclatura
- **README diz:** `OCMC_bd`
- **Sistema real diz:** `OCME_bd` (bot ativo em `t.me/OCME_bd`)
- **Ação:** Atualizar todos os scripts e o README para `OCME_bd` antes da produção.

### 2. Cores (divergência com MASTER.md)

| Elemento | README (desatualizado) | MASTER.md (correto) |
|----------|----------------------|---------------------|
| Primário | `#E91E8C` | `#FB0491` |
| Cyan | `#00E5FF` | `#00D4FF` |
| Background | `#0A0A0F` | `#000000` |

**Usar sempre os valores do MASTER.md.**

---

## Paleta para os Vídeos

```css
:root {
  /* Backgrounds */
  --bg-main:    #000000;   /* fundo principal dos cards */
  --bg-surface: #131313;   /* painéis e overlays */

  /* Brand */
  --pink:  #FB0491;   /* elementos primários, título, destaques */
  --red:   #D90048;   /* alertas, urgência */
  --cyan:  #00D4FF;   /* dados, gráficos, tech */
  --green: #00FFB2;   /* sucesso, P&L positivo, wins */

  /* Texto */
  --white: #FFFFFF;
  --gray:  #888888;   /* texto secundário */
}
```

---

## Tipografia

```css
/* Títulos de impacto (ex: "MONITORAMENTO 24/7") */
font-family: 'Syne', sans-serif;
font-weight: 800;
font-size: 72-96px;
text-transform: uppercase;
letter-spacing: -2px;

/* Subtítulos */
font-family: 'Syne', sans-serif;
font-weight: 700;
font-size: 32-40px;

/* Labels e badges */
font-family: 'Syne', sans-serif;
font-weight: 700;
font-size: 18-22px;
letter-spacing: 3-4px;
text-transform: uppercase;

/* Logo / bdZinho ID */
font-family: 'Press Start 2P', monospace;
font-size: 20-26px;
```

---

## Layout Base (1080×1920px — Reels/TikTok/Stories)

```
┌─────────────────────────────────┐
│  HEADER: Logo WEbdEX + badge    │  ~120px
├─────────────────────────────────┤
│                                 │
│  CENA CENTRAL                   │
│  bdZinho + elementos visuais    │  ~900px
│  contexto do vídeo              │
│                                 │
├─────────────────────────────────┤
│  TEXTO PRINCIPAL                │  ~400px
│  linha 1 (impacto)              │
│  linha 2 (detalhamento)         │
│  linha 3 (CTA / benefício)      │
├─────────────────────────────────┤
│  FOOTER: Logo + seta CTA        │  ~100px
└─────────────────────────────────┘
```

---

## Template HTML Base (para Creatomate)

Todos os 5 vídeos derivam deste template. Apenas o conteúdo da cena central muda.

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=1080">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Press+Start+2P&display=swap" rel="stylesheet">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  :root {
    --black: #000000; --dark: #131313;
    --pink: #FB0491; --red: #D90048;
    --green: #00FFB2; --cyan: #00D4FF;
    --white: #ffffff; --gray: #888888;
  }
  body {
    width: 1080px; height: 1920px;
    background: var(--black);
    font-family: 'Syne', sans-serif;
    color: var(--white);
    overflow: hidden;
  }
  /* Glow de fundo */
  body::before {
    content: '';
    position: absolute;
    top: -100px; right: -100px;
    width: 600px; height: 600px;
    background: radial-gradient(circle, rgba(251,4,145,0.15) 0%, transparent 70%);
    pointer-events: none;
  }
  .header {
    display: flex; align-items: center;
    justify-content: space-between;
    padding: 48px 64px;
    border-bottom: 1px solid rgba(251,4,145,0.2);
  }
  .logo-icon {
    width: 64px; height: 64px;
    border-radius: 16px;
    background: linear-gradient(135deg, #FB0491 0%, #D90048 100%);
    display: flex; align-items: center; justify-content: center;
    font-family: 'Press Start 2P', monospace;
    font-size: 18px; color: white;
    letter-spacing: -2px;
  }
  .logo-text {
    font-family: 'Press Start 2P', monospace;
    font-size: 20px; margin-left: 16px;
  }
  .logo-text span { color: var(--pink); }
  .scene-area {
    height: 900px;
    display: flex; align-items: center; justify-content: center;
    position: relative;
    /* Slot para bdZinho + elementos contextuais */
  }
  .text-area {
    padding: 0 64px;
    flex: 1;
  }
  .text-eyebrow {
    font-size: 20px; font-weight: 700;
    color: var(--pink); letter-spacing: 4px;
    text-transform: uppercase; margin-bottom: 24px;
  }
  .text-main {
    font-size: 80px; font-weight: 800;
    line-height: 1.0; letter-spacing: -2px;
    margin-bottom: 32px;
  }
  .text-main .accent { color: var(--pink); }
  .text-sub {
    font-size: 32px; font-weight: 400;
    color: rgba(255,255,255,0.75);
    line-height: 1.4;
  }
  .footer {
    position: absolute; bottom: 0; left: 0; right: 0;
    padding: 32px 64px;
    border-top: 1px solid rgba(251,4,145,0.15);
    display: flex; align-items: center; justify-content: space-between;
    background: rgba(0,0,0,0.9);
  }
  .footer-brand { font-family: 'Press Start 2P', monospace; font-size: 12px; color: var(--gray); }
  .footer-brand span { color: var(--pink); }
  .footer-cta {
    font-size: 20px; font-weight: 700;
    color: var(--pink); letter-spacing: 1px;
  }
</style>
</head>
<body>
  <div class="header">
    <div style="display:flex;align-items:center;">
      <div class="logo-icon">bd</div>
      <div class="logo-text">WE<span>bd</span>EX</div>
    </div>
    <div style="color:var(--pink);font-weight:700;letter-spacing:3px;font-size:18px;">OCME_bd</div>
  </div>

  <!-- CENA CENTRAL — personalizar por vídeo -->
  <div class="scene-area">
    <!-- bdZinho image + elementos do contexto aqui -->
  </div>

  <!-- TEXTO PRINCIPAL — personalizar por vídeo -->
  <div class="text-area">
    <div class="text-eyebrow">/* eyebrow aqui */</div>
    <div class="text-main">/* título aqui */</div>
    <div class="text-sub">/* subtítulo aqui */</div>
  </div>

  <div class="footer">
    <div class="footer-brand">WE<span>bd</span>EX Protocol</div>
    <div class="footer-cta">t.me/OCME_bd →</div>
  </div>
</body>
</html>
```

---

## Mapa de Conteúdo por Vídeo

| Vídeo | Eyebrow | Título principal | Accent | Cor extra |
|-------|---------|-----------------|--------|-----------|
| V01 | "APRESENTANDO" | O OCME_bd | "bd" em pink | cyan glow |
| V02 | "24/7 · SEM PARAR" | MONITORAMENTO EM TEMPO REAL | "REAL" em green | green glow |
| V03 | "SEUS DADOS" | NA PALMA DA MÃO | "MÃO" em pink | pink glow |
| V04 | "DOIS AMBIENTES" | UMA VISÃO COMPLETA | "COMPLETA" em cyan | orange + blue |
| V05 | "CICLO 21H" | RESULTADOS REAIS | "REAIS" em green | green particles |

---

## Cores de Glow por Vídeo

```css
/* V01 — Brand/Apresentação */
radial-gradient(circle, rgba(251,4,145,0.18) 0%, transparent 70%)

/* V02 — Monitoramento (urgência) */
radial-gradient(circle, rgba(0,255,178,0.15) 0%, transparent 70%)

/* V03 — Dados pessoais (confiança) */
radial-gradient(circle, rgba(251,4,145,0.18) 0%, transparent 70%)

/* V04 — Dois ambientes */
left: radial-gradient(rgba(255,136,0,0.12)...)
right: radial-gradient(rgba(0,212,255,0.12)...)

/* V05 — Resultados (performance) */
radial-gradient(circle, rgba(0,255,178,0.15) 0%, transparent 70%)
```

---

## Checklist Antes da Produção

- [ ] Confirmar nomenclatura: `OCME_bd` em todos os scripts (não OCMC)
- [ ] Obter assets bdZinho (imagens 3D do robô) de `C:\Users\Alex\Documents\Imagens_bdZinho\`
- [ ] Criar templates Creatomate para cada vídeo (V01–V05)
- [ ] Validar cores contra MASTER.md
- [ ] Testar renderização 1080×1920px via Creatomate API

---

*WEbdEX Protocol · Série OCME_bd · Style Guide v1.0 · 2026-03-23*
