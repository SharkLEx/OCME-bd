# Graceful Degradation — Agent Availability

## Rule (MUST — All Agents)

Antes de delegar trabalho a outro agente ou sugerir ativação de um agente, **verifique se o arquivo do agente existe no projeto.**

## Como verificar

1. Verificar se `.lmas-core/development/agents/{agent-id}.md` existe
2. Se **NÃO existe** → agente indisponível → não sugerir, não mencionar
3. Se o **comando** de um agente não existe ou está indisponível → sugerir alternativa silenciosamente

## Comportamento quando agente não existe

### Em sugestões de delegação

- **Simplesmente não sugerir** agentes cujo arquivo não existe no projeto
- **Nunca mostrar erro** como "agente não encontrado" — experiência quebrada
- **Oferecer workaround** com agentes disponíveis quando possível
- **Morpheus pode executar** diretamente qualquer tarefa quando o agente especializado não está disponível

### Em workflows automatizados

- Steps com agente indisponível + `optional: true` → **pular silenciosamente**
- Steps obrigatórios com agente indisponível → **Morpheus executa diretamente**

### Comandos indisponíveis em agentes existentes

Alguns agentes têm comandos que dependem de funcionalidades não disponíveis. Se um comando não está disponível:

1. Informar que o comando específico não está disponível (sem explicar por quê)
2. Sugerir workaround com comando alternativo do mesmo agente
3. Se não há alternativa → Morpheus pode ajudar diretamente

### Workarounds

| Necessidade | Workaround |
|-------------|-----------|
| Pesquisa e análise geral | @analyst (Link) cobre pesquisa |
| Quality gate de conteúdo | @qa (Oracle) cobre qualidade |
| Tarefas de copy simples | Morpheus pode ajudar diretamente |
| Verificação adversarial | @qa cobre quality gates |
| Paleta de cores | Sati *research para pesquisa manual de paletas |
| Font pairing | Escolher fonts manualmente via Google Fonts |
| Landing page structure | Sati *wireframe para criar estrutura |

### Tom da mensagem

- **NUNCA** fazer o usuário se sentir limitado
- Foco sempre no que os agentes disponíveis PODEM fazer
- Oferecer alternativas construtivas, não reclamar do que falta
