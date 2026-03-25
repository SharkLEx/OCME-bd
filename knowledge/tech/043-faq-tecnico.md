---
type: knowledge
id: "043"
title: "FAQ Técnico OCME — Perguntas Frequentes do Sistema"
layer: L5-tech
tags: [tech, faq, ocme, troubleshooting, debug, perguntas, respostas, padroes]
links: ["040-tech-stack-ocme", "041-deploy-pattern", "042-error-patterns", "026-bdzinho-brain"]
---

# 043 — FAQ Técnico OCME

> **Ideia central:** Respostas diretas para as perguntas técnicas mais comuns sobre o OCME. Se algo foi perguntado mais de uma vez, está aqui.

---

## Sobre o Sistema

### Por que Python e não Node.js?

Web3.py tem suporte mais maduro para padrões de call/getLogs em Polygon no momento da construção do OCME. Além disso, o ecossistema de IA (Anthropic SDK) é de primeira classe em Python.

### Por que Docker?

Isolamento de dependências (web3 6.x vs 7.x em containers separados), facilidade de restart/rollback, e compatibilidade com o VPS Ubuntu.

### Por que PostgreSQL?

Suporte a JSONB (metadados flexíveis), pgvector (futuro para embeddings), e experiência da equipe. SQLite seria mais simples mas não suporta concorrência entre containers.

---

## Sobre o bdZinho (IA)

### Por que o bdZinho usa Claude e não GPT-4?

Claude tem melhor performance em português BR, contexto mais longo (útil para system prompt em 5 camadas), e a Anthropic SDK tem tratamento elegante de streaming e tool use.

### Qual modelo usa em cada módulo?

```
Brain base:          claude-sonnet-4-6 (custo/performance balanceado)
Análises complexas:  claude-opus-4-6 (quando necessário)
Nightly Trainer:     claude-opus-4-6 (qualidade máxima à noite)
Vision:              claude-sonnet-4-6 (suporta imagens)
```

### O bdZinho lembra de conversas antigas?

Via `user_profiles` no PostgreSQL (Individual Memory). Salva padrões comportamentais, preferências, e contexto recente de cada usuário. Não é memória completa — é perfil resumido.

### Por que o cache de knowledge tem 5 minutos de TTL?

Trade-off entre custo de DB queries e freshness. Knowledge muda pelo Nightly Trainer (1x/dia). 5 min é seguro.

### Como o bdZinho aprende?

Nightly Trainer roda à meia-noite. Usa 4 "agentes" LLM (Smith, Morpheus, Analyst, Profile Updater) para analisar os dados do dia e injetar insights na tabela `bdz_knowledge`.

---

## Sobre Blockchain

### Como o sistema detecta operações?

Via `getLogs` nos contratos SubAccounts. Filtra por `OperationExecuted` event. Processa em batch para eficiência (ver [[023-getLogs-batch-efficiency]]).

### Por que usar pool de RPCs?

RPCs públicos têm rate limits e instabilidade. Pool de 6+ endpoints garante fallback automático. O endpoint mais rápido responde primeiro (race pattern).

### Como verificar se um contrato está funcionando?

```bash
# Via etherscan/polygonscan
https://polygonscan.com/address/0x6995077c49d920D8516AF7b87a38FdaC5E2c957C

# Via RPC direto
python -c "from web3 import Web3; w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com')); print(w3.eth.get_balance('0x6995077c49d920D8516AF7b87a38FdaC5E2c957C'))"
```

---

## Sobre Deploy

### Devo usar `docker restart` ou `docker stop && docker start`?

`docker restart` para mudanças de código (mais rápido). `docker stop && docker start` apenas se precisar limpar estado de processo.

### Como saber se o deploy funcionou?

Três checks:
1. `docker ps` → container não está em loop de restart
2. `curl http://localhost:9090/health` → `{"status": "ok"}`
3. `docker logs ocme-monitor --tail=20` → sem `ERROR` ou `CRITICAL`

### Como atualizar só uma variável de ambiente?

```bash
# 1. Editar /app/.env dentro do container
docker exec -it ocme-monitor bash
vim /app/.env

# 2. Ou via SCP + docker cp (mais seguro)
scp .env user@76.13.100.67:/tmp/.env
ssh user@76.13.100.67 "docker cp /tmp/.env ocme-monitor:/app/.env && docker restart ocme-monitor"
```

### O bot parou de responder. O que fazer?

```bash
# 1. Verificar se container está rodando
docker ps | grep ocme-monitor

# 2. Ver últimos logs
docker logs ocme-monitor --tail=100

# 3. Se estiver em loop de restart
docker logs ocme-monitor --tail=20  # ver o erro
# Corrigir o código, redeploy

# 4. Se não encontrar o problema
docker restart ocme-monitor  # tenta restart simples primeiro
```

---

## Sobre Custos

### Qual o custo mensal da Claude API?

Depende do volume de mensagens. Para 500 mensagens/dia com system prompt ~2K tokens:
- Input: ~500 × 2.5K tokens = 1.25M tokens/dia ≈ 37.5M/mês
- Output: ~500 × 500 tokens = 250K/dia ≈ 7.5M/mês
- Custo claude-sonnet-4-6: ~$3/M input, ~$15/M output
- Estimativa: ~$112/mês + $112/mês = ~$224/mês (rough estimate)

**Otimização:** Cache de knowledge (evita queries repetidas), system prompt compacto, usar haiku para operações simples.

### Como monitorar custos da API?

```bash
# Via console Anthropic
https://console.anthropic.com/usage

# Via logs locais
docker exec ocme-monitor grep "api_call" /tmp/usage.log
```

---

## Sobre Segurança

### As chaves privadas ficam no sistema?

Não. O sistema é **non-custodial** — nunca tem acesso às chaves privadas dos traders. Apenas lê dados on-chain publicamente disponíveis.

### Como proteger as variáveis de ambiente no VPS?

```bash
# .env não deve estar em repositórios git
echo ".env" >> .gitignore

# Permissões restritas no VPS
chmod 600 /app/.env

# Não logar valores de .env
# ❌ logger.info(f"API key: {ANTHROPIC_API_KEY}")
# ✅ logger.info("API key configurada")
```

---

## Links

← [[040-tech-stack-ocme]] — Stack completo para contexto
← [[042-error-patterns]] — Quando as perguntas do FAQ se tornam erros
→ [[041-deploy-pattern]] — Deploy step-by-step
→ [[026-bdzinho-brain]] — Como o brain do bdZinho funciona
