---
type: knowledge
title: "Dev — Nightly Trainer: Agentes, Nexo e Aprendizado Automático"
tags:
  - dev
  - nightly-trainer
  - nexo
  - learning
  - workers
created: 2026-03-26
source: neo-sensei
---

# Nightly Trainer: Agentes, Nexo e Aprendizado Automático

> Módulo 08 de 10 — Professor: Neo
> Como o bdZinho aprende e evolui automaticamente toda noite.

---

## O Que É o Nightly Trainer

O Nightly Trainer é um pipeline que roda todo dia às **00:00 BRT** e faz o bdZinho aprender com as conversas do dia anterior.

```
00:00 BRT → agendador_nightly dispara
  ↓
Lê conversas Discord das últimas 24h (PostgreSQL ai_conversations)
  ↓
Agrupa por tema com Claude (análise semântica)
  ↓
Gera insights → escreve notas .md no vault
  ↓
bdZinho lê essas notas nas próximas buscas
```

---

## Arquivo Principal: webdex_nightly.py (ocme-monitor)

```
packages/monitor-engine/
├── webdex_nightly.py         ← Pipeline principal
├── webdex_workers.py         ← Registra agendador_nightly_worker
└── webdex_main.py            ← Inicia a thread
```

### Thread registration

```python
# webdex_main.py
threading.Thread(
    target=agendador_nightly_worker,
    daemon=True,
    name="nightly_trainer"
).start()
```

### Worker loop

```python
# webdex_workers.py
def agendador_nightly_worker():
    logger.info("[nightly_trainer] Iniciado")
    while True:
        try:
            agora = datetime.now(TZ_BRT)
            # Dispara apenas na janela 00:00–00:05 BRT
            if agora.hour == 0 and agora.minute < 5:
                if _ja_executou_hoje():
                    pass
                else:
                    _executar_nightly()
                    _marcar_executado_hoje()
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error("[nightly_trainer] Erro: %s", e, exc_info=True)
        time.sleep(60)  # verifica a cada minuto
```

---

## Os Agentes do Nightly Trainer

O pipeline usa múltiplos "agentes" (chamadas Claude) em sequência:

### Agente 1 — Minerador de Conversas

```python
# Busca perguntas recorrentes nas últimas 24h
prompt = """Analise estas conversas Discord e identifique:
1. Perguntas que apareceram mais de 1x
2. Temas que geraram engajamento
3. Confusões ou mal-entendidos frequentes

Conversas: {conversas_do_dia}

Retorne JSON: {"temas": [...], "perguntas_recorrentes": [...]}"""
```

### Agente 2 — Sintetizador (o Nexo)

O Nexo é o agente central — pega os temas e gera insights acionáveis:

```python
# Nexo: transforma raw insights em conhecimento estruturado
prompt = """Você é Nexo, o sistema nervoso do WEbdEX.
Temas identificados hoje: {temas}

Para cada tema, gere um insight no formato:
- Título claro
- O que os usuários querem saber
- Resposta definitiva baseada nos dados

Retorne JSON: {"insights": [{"titulo": ..., "conteudo": ...}]}"""
```

### Agente 3 — Vault Writer

Converte insights em notas `.md` e salva no vault:

```python
def vault_writer(insights: list[dict]):
    data_hoje = datetime.now(TZ_BRT).strftime("%Y-%m-%d")
    for insight in insights:
        slug = _slugify(insight["titulo"])
        path = f"{VAULT_LEARNED_DIR}/{data_hoje}-{slug}.md"
        conteudo = f"""---
type: learned
title: "{insight['titulo']}"
tags:
  - learned
  - auto
  - {data_hoje}
created: {data_hoje}
source: nightly-trainer
---

# {insight['titulo']}

{insight['conteudo']}
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(conteudo)
        logger.info("[vault_writer] Nota criada: %s", path)
```

---

## Configuração de Ambiente

```bash
# .env do ocme-monitor
VAULT_LOCAL_PATH=/app/data/vault
VAULT_LEARNED_DIR=learned              # subdir dentro de VAULT_LOCAL_PATH
NIGHTLY_MIN_CONVERSATIONS=3            # mínimo de conversas para disparar
NIGHTLY_LOOKBACK_HOURS=24             # janela de conversas a analisar
```

---

## Como Verificar se Está Funcionando

```bash
# Ver logs do nightly trainer
docker logs ocme-monitor --tail=50 | grep nightly

# Ver notas geradas hoje
docker exec ocme-monitor find /app/data/vault/learned -name "$(date +%Y-%m-%d)*"

# Verificar última execução
docker exec ocme-monitor python3 -c "
import sqlite3, os
db = sqlite3.connect(os.environ['DB_PATH'])
print(db.execute(\"SELECT valor FROM config WHERE chave='last_nightly'\").fetchone())
"
```

---

## Adicionar um Novo Agente ao Pipeline

1. Criar a função em `webdex_nightly.py`:
```python
def _agente_novo(dados: dict) -> dict:
    """Agente 4 — Detector de Oportunidades."""
    prompt = f"..."  # seu prompt
    resposta = _call_claude(prompt)  # wrapper interno
    return json.loads(resposta)
```

2. Encadear no pipeline principal:
```python
def _executar_nightly():
    conversas = _buscar_conversas()            # Agente 1
    temas = _agente_minerador(conversas)       # Agente 2
    insights = _agente_nexo(temas)             # Agente 3 (Nexo)
    oportunidades = _agente_novo(insights)     # Agente 4 (novo)
    vault_writer(insights + oportunidades)     # salva tudo
```

---

## Integração com bdZinho

O bdZinho lê as notas aprendidas nas buscas via `buscar_vault` tool:

```python
# Quando usuário pergunta algo no Discord
# Tool: buscar_vault("tokenomia")
# → vault_reader.py busca em TODAS as notas incluindo learned/
# → Retorna notas com maior score (título > tags > body)
# → bdZinho inclui no contexto e responde com o aprendizado
```

**Resultado:** Perguntas que aparecem toda semana → Nexo aprende → bdZinho passa a responder melhor sem intervenção manual.
