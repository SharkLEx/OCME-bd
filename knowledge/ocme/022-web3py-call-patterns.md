---
type: knowledge
id: "022"
title: "web3.py — Padrões de Call do OCME"
layer: L4-ocme
tags: [web3py, ocme, python, contratos, call, getLogs]
links: ["002-smart-contracts", "003-eventos-logs", "019-evm-state-machine", "023-getLogs-batch-efficiency"]
fonte: https://web3py.readthedocs.io/en/stable/web3.contract.html
---

# 022 — web3.py: Padrões de Call do OCME

> **Ideia central:** web3.py é a ponte entre o Python do OCME e a EVM do Polygon. Cada operação tem um padrão específico. Conhecer o padrão correto elimina bugs e maximiza eficiência.

---

## Os 3 Modos de Interação com Contratos

```python
# Instanciar contrato (sempre primeiro)
contract = web3.eth.contract(
    address=Web3.to_checksum_address(ENDERECO),
    abi=ABI_JSON
)

# MODO 1: call() — leitura local, sem gas, resultado imediato
resultado = contract.functions.balanceOf(wallet).call()

# MODO 2: transact() — escreve on-chain, gasta gas, retorna tx_hash
tx_hash = contract.functions.transfer(dest, amount).transact()

# MODO 3: estimate_gas() — simula sem executar, retorna gas necessário
gas_estimado = contract.functions.transfer(dest, amount).estimate_gas()
```

---

## O que o OCME usa: exclusivamente call()

```python
# webdex_chain.py — todos os reads do protocolo

# Saldo ERC-20 do usuário
bd_balance = bd_contract.functions.balanceOf(wallet).call()

# Supply total do token
total_supply = bd_contract.functions.totalSupply().call()

# Com block_identifier — lê estado histórico
saldo_historico = contract.functions.balanceOf(wallet).call(
    block_identifier=67_834_521  # pino no bloco específico
)
```

**Por que block_identifier importa:**
Sem ele, você lê o estado "latest" — que muda a cada 2 segundos.
Com ele, você lê o estado de um bloco específico — imutável para sempre.

→ [[019-evm-state-machine]] — Por que o estado histórico é acessível assim

---

## get_logs(): O Core do Proto Sync

```python
# O padrão exato que _protocol_ops_sync_worker usa
logs = web3.eth.get_logs({
    'fromBlock': from_block,           # início do range
    'toBlock': to_block,               # fim do range (max 2000 blocos no Alchemy)
    'address': CONTRATO_SUBACCOUNTS,   # filtro por contrato
    'topics': [TOPIC_OPENPOSITION]     # filtro por tipo de evento
})

# Decodificar cada log
for log in logs:
    # topics[0] = assinatura do evento (hex)
    # topics[1] = wallet (padded para 32 bytes)
    wallet = Web3.to_checksum_address('0x' + log['topics'][1].hex()[-40:])

    # data = parâmetros não-indexed
    decoded = contract.events.OpenPosition().process_log(log)
    profit = decoded['args']['profit']
    fee_bd = decoded['args']['fee']
    ts = decoded['args']['timestamp']
```

---

## process_receipt() vs process_log()

| Método | Input | Quando usar |
|--------|-------|------------|
| `process_receipt(receipt)` | Receipt de tx enviada | Após transact() — você enviou a tx |
| `process_log(log)` | Log individual de get_logs() | Ao fazer backfill histórico |

O OCME usa `process_log()` — nunca enviou transações, só lê logs históricos.

---

## create_filter() — Alternativa para Monitoramento em Tempo Real

```python
# Criando filtro de eventos (mantém estado no nó RPC)
event_filter = contract.events.OpenPosition.create_filter(
    from_block='latest',
    argument_filters={'wallet': WALLET_ESPECIFICA}  # filtro opcional
)

# Polling do filtro
novos_eventos = event_filter.get_new_entries()
```

**Por que o OCME NÃO usa create_filter():**
- Filtros têm estado no nó RPC — se o nó reinicia, o filtro se perde
- Menos confiável para sistemas de produção
- `get_logs()` com range explícito é idempotente e reprocessável

---

## ABI: O Contrato de Interface

```python
# ABI mínima para ler eventos OpenPosition
ABI = json.loads('[{"anonymous":false,"inputs":[{"indexed":true,"name":"wallet","type":"address"},{"indexed":false,"name":"profit","type":"int256"},{"indexed":false,"name":"fee","type":"uint256"},{"indexed":false,"name":"timestamp","type":"uint256"}],"name":"OpenPosition","type":"event"}]')

# ABI mínima ERC-20 (balanceOf + totalSupply)
ABI_ERC20 = json.loads('[{"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"totalSupply","outputs":[{"type":"uint256"}],"stateMutability":"view","type":"function"}]')
```

O OCME usa ABIs mínimas (só o que precisa) — menos dados para parsear, menos chance de erro.

---

## Checksum Address: Detalhe Crítico

```python
# ERRADO — pode falhar dependendo da versão do web3.py
saldo = contract.functions.balanceOf('0xabc...').call()

# CORRETO — sempre usar checksum
saldo = contract.functions.balanceOf(
    Web3.to_checksum_address('0xabc...')
).call()
```

Checksum address é o endereço com letras maiúsculas/minúsculas que funcionam como checksum (EIP-55). A web3.py v7 é estrita sobre isso.

---

## Conectando ao RPC Pool

```python
# webdex_chain.py — o OCME não usa web3 direto, usa o pool
web3 = rpc_pool.get()  # retorna web3 conectado ao endpoint disponível

# Se o endpoint falha mid-request, a exceção é capturada
# e o próximo endpoint é tentado no próximo ciclo
```

→ [[015-rpc-pool]] — Como o pool gerencia os endpoints

---

## Links

← [[MOC-Blockchain-Intelligence]]
← [[002-smart-contracts]] — O que os contratos expõem
← [[003-eventos-logs]] — Os logs que get_logs() retorna
← [[019-evm-state-machine]] — Por que block_identifier funciona
→ [[023-getLogs-batch-efficiency]] — Otimização do sync worker
