# bdZinho — Design Bible v1.0
> Referência canônica para geração de imagens via Nano Banana (MATRIX 3.7+)

## Identidade Visual do Personagem

### Anatomia
- **Formato geral:** robô 3D estilo vinyl/Funko, proporções cute (cabeça grande, corpo compacto)
- **Cabeça:** capacete oval/redondo, branco-creme, com DOIS CHIFRES brancos pontudos no topo
- **Face:** painel frontal rosa-quente (#FF2D78), oval arredondado, levemente afundado no capacete
- **Olhos:** variações — oval brancos (amigável/gentil) | pontos pretos/ovais (foco/sério) | óculos escuros (cool/confiante)
- **Sorriso:** arco simples e suave — sempre presente exceto variante "agressiva"
- **Logo bd:** badge no peito — letras "bd" em branco, fundo #FF2D78, cantos arredondados
- **Articulações:** esférica, braços e pernas bem definidos com juntas visíveis
- **Pés:** botas arredondadas, sem detalhes excessivos

### Paleta de Cores Principal
```
Rosa principal:  #FF2D78  (face, badge, acentos)
Creme/branco:   #F5E6D8  (corpo base)
Rosa escuro:    #CC1060  (sombras, profundidade)
Vinho escuro:   #1A0010  (fundo padrão Telegram)
Preto profundo: #050505  (fundo premium/Discord)
```

### Paleta Alternativa (variante all-pink)
```
Body principal: #FF2D78 (corpo inteiro rosa)
Detalhes:       #CC1060 (sombras)
Olhos/sorriso:  #CC1060 ou relevo branco
```

---

## Expressões Mapeadas

| Expressão | Descrição visual | Quando usar no bot |
|-----------|-----------------|-------------------|
| **FELIZ_APONTANDO** | Braço estendido apontando, sorriso largo | Chamada para ação, notificação positiva |
| **CELEBRANDO** | Braços levantados ou joinha, postura expansiva | Resultado positivo, ganho, win rate alto |
| **ESPECIALISTA** | Mão aberta sustentando orbe/objeto tech | Explicando DeFi, apresentando dado |
| **CONFIANTE_COOL** | Óculos escuros, jaqueta, postura relaxada | Resposta sobre tokens, trading, dicas |
| **PROFISSIONAL** | Terno, braços cruzados, postura ereta | Relatório 21h, análise formal |
| **PENSANDO_IDEIA** | Dedo apontado para cima, lâmpada acesa | Insight, dica, sugestão |
| **ANALISANDO** | Segurando tablet/tela | Relatório, dashboard, análise de dados |
| **SEGURANCA** | Segurando cadeado cyber holográfico | Contrato, segurança, auditoria |
| **PROVOCANDO** | Apontando direto pro usuário, postura desafiadora | Engajamento, provocação amigável |
| **NEUTRO_BASE** | Braços cruzados, sem adereços | Resposta padrão |
| **PREOCUPADO** | Postura recolhida, olhos menores | Alerta, drawdown, risco |
| **BRASIL** | Segurando bandeira do Brasil | Contexto nacional, comunidade |

---

## Prompts Base por Contexto

### Template Universal
```
bdZinho robot mascot 3D render, vinyl toy style, cream white rounded robot body,
hot pink face panel (#FF2D78), two white pointed horns on head, white oval eyes
with gentle smile, "bd" logo badge on chest in hot pink, articulated joints,
rounded boots, {POSE_DESCRIPTION}, {BACKGROUND}, soft studio lighting with
subtle pink rim light, Funko-like proportions, high detail, sharp render,
cinematic quality, WEbdEX DeFi protocol mascot
```

### Backgrounds por Contexto
```
Telegram geral:   dark wine background #1A0010, subtle pink bokeh
Discord relatório: deep black #050505, cinematic lighting
Celebração:       dark background with golden/pink particles floating
Alerta:           dark red vignette, subtle orange glow
Análise:          dark background with holographic blue data overlay
```

---

## Regras de Consistência (OBRIGATÓRIAS nos prompts)

1. **SEMPRE mencionar:** `two white pointed horns`, `hot pink face panel`, `"bd" logo badge on chest`
2. **SEMPRE mencionar:** `cream white body`, `rounded vinyl toy style`, `articulated joints`
3. **NUNCA:** remover os chifres (são o elemento mais icônico)
4. **NUNCA:** trocar o badge "bd" por outro texto
5. **Proporções:** cabeça ~40% da altura total (cute ratio)
6. **Iluminação:** sempre tem rim light rosa suave no lado direito

---

## Variantes de Personagem

### bdZinho Padrão (mais usado)
- Corpo creme/branco, face pink
- Expressão amigável
- Contexto: maioria das interações Telegram

### bdZinho All-Pink (modo agressivo/focado)
- Corpo inteiro #FF2D78
- Olhos menores/mais focados
- Contexto: alertas, ciclos negativos, modo "séria"
- Referência: Bot_WEbdEX_dupla.png (figura da direita)

### bdZinho Executivo (modo formal)
- Terno preto, gravata, badge bd na lapela
- Expressão séria mas acolhedora
- Contexto: relatórios formais, análises maiores

### bdZinho Cool (modo descolado)
- Óculos escuros grandes, jaqueta de couro
- Postura relaxada, mãos abertas com tokens
- Contexto: dicas de trading, conteúdo social

---

## Mapeamento Bot → Imagem

| Situação no bot | Expressão | Variante |
|----------------|-----------|---------|
| Usuário pergunta sobre lucro | CELEBRANDO | Padrão |
| Relatório 21h positivo | PROFISSIONAL + partículas douradas | Executivo |
| Relatório 21h negativo | PREOCUPADO | All-Pink |
| Explicando protocolo | ESPECIALISTA + blockchain orb | Padrão |
| Dica de trading | CONFIANTE_COOL | Cool |
| Insight proativo (MATRIX 4.1) | PENSANDO_IDEIA | Padrão |
| Segurança/contrato | SEGURANCA | Padrão |
| Dashboard/análise | ANALISANDO | Padrão |
| Boas-vindas novo usuário | FELIZ_APONTANDO | Padrão |
| Alerta de drawdown | PREOCUPADO | All-Pink |
| Criação de imagem pelo usuário | livre | Padrão |

---

*Design Bible v1.0 — extraído de 13+ renders oficiais — 2026-03-25*
*Arquivos fonte: Documents/Imagens_bdZinho/logo-20260325T014054Z-3-001/Imagens-logo/*
