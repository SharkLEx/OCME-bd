---
type: knowledge
id: "015"
title: "RPC Pool — Redundância de Acesso On-Chain"
layer: L4-ocme
tags: [ocme, rpc, infraestrutura, resiliência]
links: ["003-eventos-logs", "005-finality-blocos"]
---

# 015 — RPC Pool

> **Ideia central:** Um único endpoint RPC é um ponto único de falha. O OCME usa 3 endpoints em rotação — se um falha ou esgota quota, o próximo assume automaticamente.

---

## O Problema

Para ler dados da blockchain, o OCME precisa de um **RPC endpoint** — um servidor que processa as chamadas.

Endpoints gratuitos (como Alchemy free tier) têm:
- **Quota diária de compute units** (~300M CUs/dia na Alchemy)
- **Rate limits** (requisições por segundo)
- **Downtime** ocasional

Se o OCME depende de um único endpoint e ele cai, o bot fica cego.

---

## A Solução: RpcPool

```python
# webdex_chain.py
class RpcPool:
    """Round-robin com cooldown por endpoint"""

    endpoints = [
        RPC_URL,       # Alchemy key 1
        RPC_CAPITAL,   # Alchemy key 2 (quota independente!)
        RPC_FALLBACK,  # 1rpc.io/matic (sem quota)
    ]

    def get(self) -> Web3:
        # tenta cada endpoint em ordem
        # se falhou recentemente → pula (cooldown)
        # retorna o primeiro disponível
```

---

## Quota Independente — A Chave

Duas chaves Alchemy = dois "baldes" de quota **completamente independentes**:

```
Alchemy App 1 (RPC_URL):     300M CUs/dia
Alchemy App 2 (RPC_CAPITAL): 300M CUs/dia
1rpc.io (RPC_FALLBACK):      sem limite (mais lento)
─────────────────────────────────────────
Total efetivo:               600M+ CUs/dia
```

Quando o App 1 esgota às 20h, o App 2 ainda tem 100% da quota intacta.

---

## Por que `--force-recreate` e não `restart`?

```bash
# ERRADO: docker restart usa variáveis de ambiente baked na imagem anterior
docker restart ocme-monitor

# CORRETO: força releitura do .env atual
docker compose up -d --force-recreate
```

`docker restart` não relê o `.env`. `force-recreate` recria o container do zero com as variáveis atuais.

---

## Configuração atual no VPS

```bash
# /opt/ocme-monitor/packages/monitor-engine/.env
RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/q06CVcAAm...    # Alchemy App 1
RPC_CAPITAL=https://polygon-mainnet.g.alchemy.com/v2/KGs-ozO...  # Alchemy App 2
RPC_FALLBACK=https://1rpc.io/matic                               # Fallback público
```

---

## Cooldown Logic

Quando um endpoint falha, ele entra em "cooldown":

```python
if falhou:
    self.cooldown[endpoint] = time.time() + 60  # 60s de cooldown

if time.time() < self.cooldown.get(endpoint, 0):
    continue  # pula este endpoint
```

Isso evita spam de retries para um endpoint que está claramente fora.

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[003-eventos-logs]] — O que o RpcPool acessa
← [[005-finality-blocos]] — Por que ler do bloco correto importa
