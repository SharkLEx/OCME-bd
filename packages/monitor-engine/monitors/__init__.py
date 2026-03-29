"""
monitors/ — Módulos de monitoramento on-chain e off-chain.

Regra: importa apenas de core/. Nunca de handlers/ ou services/.
Todos são loops infinitos (while True: sleep(N)) — stateless em relação à lógica de negócio.

Módulos:
    chain        — Cache de blockchain + health check
    chain_health — Health monitor da chain
    vigia        — Monitor principal on-chain (webdex_monitor)
    v4           — Monitor subconta v4
    socios       — Monitor sócios (pagamentos USDT)
    network_dash — Dashboard de network fees
    network_notify — Notificações de network
    anomaly      — Detecção de anomalias de preço

Story 7.3 — Epic 7: modularização do monolito Python

NOTA: Wildcard imports removidos — causavam circular import via stubs.
Importe módulos individualmente: from monitors.vigia import X
"""
