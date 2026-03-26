---
type: knowledge
title: "Dev — Knowledge System: Vault RAG, bdz_knowledge e Knowledge Loop"
tags:
  - dev
  - vault
  - rag
  - knowledge
  - bdz_knowledge
created: 2026-03-26
source: neo-sensei
---

# Knowledge System: Vault RAG, bdz_knowledge e Knowledge Loop

> Módulo 07 de 10 — Professor: Neo
> Como o bdZinho aprende e busca conhecimento.

---

## Dois Sistemas de Conhecimento

| Sistema | Arquivo | Fonte | Atualização |
|---------|---------|-------|-------------|
| **Vault RAG** | `vault_reader.py` | Notas Obsidian `.md` | Automático (Nightly Trainer) |
| **bdz_knowledge** | `bdz_knowledge_discord.py` | PostgreSQL `bdz_knowledge` | Manual + Market Intelligence |

---

## Vault RAG — vault_reader.py

O vault indexa notas Obsidian e responde a buscas semânticas por scoring:

```python
# Scoring de relevância
def _score(note: dict, query: str) -> float:
    score = 0.0
    query_lower = query.lower()
    tokens = query_lower.split()

    # Título = 10 pontos por token encontrado
    title_lower = note["title"].lower()
    for token in tokens:
        if token in title_lower:
            score += 10.0

    # Tags = 3 pontos por tag que faz match
    for tag in note.get("tags", []):
        for token in tokens:
            if token in tag.lower():
                score += 3.0

    # Body = 0.5 por ocorrência no conteúdo
    body_lower = note.get("body", "").lower()
    for token in tokens:
        score += body_lower.count(token) * 0.5

    return score
```

### Cache com TTL (thread-safe)

```python
class _VaultIndex:
    def __init__(self):
        self._notes: list[dict] = []
        self._last_load: float = 0.0
        self._ttl: float = float(os.getenv("VAULT_CACHE_MINUTES", "60")) * 60
        self._lock = threading.Lock()       # protege leituras
        self._load_lock = threading.Lock()  # serializa reloads

    def ensure_loaded(self):
        """C-1 fix: double-check pattern evita reload duplo."""
        now = time.time()
        if now - self._last_load < self._ttl:
            return
        with self._load_lock:
            if time.time() - self._last_load < self._ttl:
                return  # outro thread já carregou
            self._reload()
```

### Buscar no vault

```python
from vault_reader import search_vault, vault_status

# Retorna lista de dicts com title, tags, excerpt, score
resultados = search_vault("tokenomia WEbdEX")

# Status do vault
info = vault_status()
# → {"total": 59, "vault_path": "/ocme_data/vault", "cache_age_min": 12.3}
```

---

## bdz_knowledge — PostgreSQL

Base de conhecimento estruturada com 90+ itens injetada no SYSTEM_PROMPT:

```python
# bdz_knowledge_discord.py
def get_knowledge_context() -> str:
    """Retorna todos os itens bdz_knowledge como contexto."""
    rows = _load_knowledge()  # cache 1h
    if not rows:
        return ""
    lines = ["## Base de Conhecimento:\n"]
    for row in rows:
        lines.append(f"### {row['title']} [{row['category']}]")
        lines.append(row['content'])
        lines.append("")
    return "\n".join(lines)
```

### Categorias do bdz_knowledge

| Categoria | Descrição | Exemplos |
|-----------|-----------|---------|
| `protocol` | WEbdEX, contratos, TVL | "Como funciona o protocolo" |
| `market` | DeFi, mercado, tendências | "Yield atual no Polygon" |
| `faq` | Perguntas frequentes | "O que é subconta?" |
| `defi` | Conceitos DeFi | "O que é impermanent loss?" |
| `tokenomia` | Token BD, supply, fee | "Supply: 369.369.369 BD" |

### Adicionar novo conhecimento

```sql
-- PostgreSQL: inserir via psql ou código
INSERT INTO bdz_knowledge (category, title, content, priority)
VALUES ('protocol', 'Nova Feature X', 'Descrição completa...', 10);

-- Após inserir, o cache expira em 1h automaticamente
-- Para forçar reload imediato:
SELECT * FROM bdz_knowledge WHERE title LIKE '%Feature X%';
```

---

## Knowledge Loop (O Ciclo Completo)

```
Conversa Discord
    ↓
bdZinho aprende
    ↓
Nightly Trainer (00:00 BRT)
    ↓
vault_writer.py (ocme-monitor)
    → escreve nota em /app/data/vault/learned/
    ↓
Docker volume compartilhado
    ↓
vault_reader.py (orchestrator-discord)
    → indexa automaticamente (TTL 60min)
    ↓
bdZinho lê na próxima busca
```

### Por que o loop funciona

O volume Docker `monitor-engine_monitor_data` é montado em DOIS containers:
- `ocme-monitor` → `/app/data/` (leitura + **escrita**)
- `orchestrator-discord` → `/ocme_data/` (leitura)

Então `/app/data/vault/learned/nota.md` = `/ocme_data/vault/learned/nota.md`

---

## Como Adicionar Notas ao Vault

### Via deploy manual

```bash
# 1. Criar nota localmente
# 2. Copiar para VPS
scp -i ~/.ssh/ocme_vps_key minha-nota.md root@76.13.100.67:/tmp/

# 3. Injetar no volume (via ocme-monitor que tem acesso rw)
ssh -i ~/.ssh/ocme_vps_key root@76.13.100.67 \
  "docker cp /tmp/minha-nota.md ocme-monitor:/app/data/vault/dev/minha-nota.md"

# 4. Forçar reload do cache se precisar imediato
ssh -i ~/.ssh/ocme_vps_key root@76.13.100.67 \
  "docker exec orchestrator-discord python3 -c \
  'import vault_reader; vault_reader._index._last_load=0; vault_reader._index.ensure_loaded(); \
   print(vault_reader.vault_status())'"
```

### Via Nightly Trainer (automático)

O Nightly Trainer escreve em `/app/data/vault/learned/` automaticamente.
Formato do arquivo gerado:

```markdown
---
type: learned
title: "Insight: {tema}"
tags:
  - learned
  - auto
  - {data}
created: {data}
source: nightly-trainer
---

# {título}

{conteúdo aprendido das conversas}
```

---

## Estrutura do Vault em Produção

```
/app/data/vault/  (= /ocme_data/vault/ via Docker volume)
├── knowledge/          ← Documentação do protocolo
│   ├── dev/            ← Este currículo (001-010)
│   └── ...
├── bdzinho/            ← Identidade e Design Bible
├── learned/            ← Notas auto-aprendidas pelo Nightly Trainer
└── backups/            ← não é vault, é do SQLite
```

---

## Padrão de Frontmatter para Notas do Vault

```yaml
---
type: knowledge        # knowledge | learned | bdzinho | protocol
title: "Título claro"
tags:
  - categoria1
  - categoria2
created: 2026-03-26
source: nome-do-autor  # neo-sensei | nightly-trainer | manual
---
```

**Por que importa:** O vault_reader usa `tags` para scoring. Notas sem tags têm score mais baixo.
