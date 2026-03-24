# Epic 19 — Monitor v4 Subaccount + Canal Discord

**Status:** 🟢 Ready for Review
**Criado:** 2026-03-23
**Branch:** feat/epic-19-v4-subaccount-monitor

## Objetivo

Monitorar o subaccount v4 do protocolo WEbdEX na Polygon, rastreando movimentações de
USDT e LOOP. Reportar via canal Discord dedicado com relatórios a cada 2 horas.

## Contratos

| Role       | Endereço                                     | Chain   |
|------------|----------------------------------------------|---------|
| Manager    | `0x9b4314878f58C3Ca53EC0087AcC8c9A30DF773E0` | Polygon |
| Subaccount | `0x7c5241688eCd253ca3D13172620be22902a4414c` | Polygon |

## Tokens Monitorados

| Token | Endereço                                     | Decimals |
|-------|----------------------------------------------|----------|
| USDT  | `0xc2132D05D31c914a87C6611C10748AEb04B58e8F` | 6        |
| LOOP  | `0xc4CF5093676e8a61404f51bC6Ceaec5279Ce8645` | 9        |

## Stories

| Story  | Título                                    | Status      |
|--------|-------------------------------------------|-------------|
| 19.1   | Schema v4_events + v4_reports             | InProgress  |
| 19.2   | Worker polling on-chain v4                | InProgress  |
| 19.3   | Relatório 2h → Discord webhook            | InProgress  |
| 19.4   | Canal Discord + webhook config (VPS)      | Todo        |

## Decisões de Arquitetura

- **Worker:** sync `while True` + `time.sleep()` — padrão do monitor-engine
- **Polling interval:** 5 min (checa eventos), flush relatório a cada 2h exatas
- **Discord:** webhook dedicado `DISCORD_WEBHOOK_V4_SUB` — melhor opção (simples, robusto)
- **Arquivo novo:** `webdex_v4_monitor.py` — isolado do core para não poluir workers.py
- **Schema:** tabelas `v4_events` + `v4_reports` no SQLite existente
- **Threshold:** só envia relatório se houver ≥1 evento no período (evita spam)
