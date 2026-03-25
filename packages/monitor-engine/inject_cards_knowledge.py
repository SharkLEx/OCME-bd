#!/usr/bin/env python3
"""
bdZinho Cards v3 Knowledge Injector — 8 Cards Animados + Sistema Dados ao Vivo
Ensina o bdZinho sobre o sistema de cards Discord que foi implementado em 2026-03-25.

Executar: DATABASE_URL=... python inject_cards_knowledge.py
"""

import os
import psycopg2
from datetime import datetime, timezone

DATABASE_URL = os.environ.get("DATABASE_URL", "")

CARDS_KNOWLEDGE = [
    # ── SISTEMA DE CARDS ──────────────────────────────────────────────────────
    ("discord_features", "cards_v3_sistema_overview",
     "bdZinho Cards v3: 8 cards animados 1080×1920px enviados ao Discord como WebM. "
     "Cada card corresponde a um canal do servidor: #webdex-on-chain, #token-bd, #conquistas, "
     "#operações, #swaps, #relatório-diário, #gm-wagmi, #bdzinho-ia. "
     "Os cards mostram dados ao vivo do protocolo WEbdEX — não são imagens estáticas. "
     "Animações CSS funcionam porque são gravados como vídeo WebM pelo Playwright/Chrome. "
     "Discord reproduz WebM inline, exibindo as animações para todos os usuários.",
     "implementation_cards_v3_2026-03-25", 1.0),

    ("discord_features", "cards_v3_comando_slash",
     "Comando slash /card no Discord: gera e envia um card animado com dados ao vivo. "
     "Uso: /card → dropdown com 8 opções (On-Chain, Token BD, Conquistas, Operações, Swaps, "
     "Relatório Diário, GM WAGMI, bdZinho IA). "
     "O bot grava o card em tempo real via render_card.js e envia como arquivo WebM. "
     "Timeout de 60 segundos. Disponível para qualquer membro do servidor.",
     "implementation_cards_v3_2026-03-25", 1.0),

    ("discord_features", "cards_v3_dados_por_canal",
     "Dados ao vivo injetados em cada card: "
     "token-bd → supply BD, holders totais, market cap estimado; "
     "webdex-onchain → anomalias detectadas, volume 24h, holders ativos, eventos no ciclo; "
     "conquistas → texto do próximo milestone, novas carteiras hoje; "
     "operacoes → últimas 4 operações (tipo + subconta); "
     "swaps → CreateSwap count, SwapTokens count, volume em USD; "
     "relatorio-diario → % atividade on-chain, % holders ativos, % volume swaps (barras animadas); "
     "gm-wagmi → hora atual e data; "
     "bdzinho-ia → usuários com IA, total de perguntas, perguntas hoje.",
     "implementation_cards_v3_2026-03-25", 1.0),

    # ── ARQUITETURA TÉCNICA ───────────────────────────────────────────────────
    ("technical_architecture", "card_server_py",
     "card_server.py: servidor Python puro (zero dependências externas — só stdlib). "
     "Roda na porta 8766 no VPS. Endpoints: /api/data/{card-name} retorna JSON com dados ao vivo. "
     "Lê diretamente do banco SQLite webdex_v5_final.db (mesmo banco do monitor-engine). "
     "Iniciar no VPS: python card_server.py ou DB_PATH=/caminho/db python card_server.py. "
     "Funciona sem instalar pip/virtualenv — apenas Python 3.x padrão.",
     "implementation_cards_v3_2026-03-25", 0.99),

    ("technical_architecture", "live_data_js",
     "live-data.js: script JS genérico de data-binding declarativo. "
     "Elementos HTML com data-live='campo' têm textContent atualizado via fetch da API. "
     "data-live-prop='style.width' atualiza propriedades CSS (usado nas barras do relatório). "
     "Graceful degradation: se card_server.py não estiver rodando, conteúdo estático permanece. "
     "Uso: <script src='live-data.js' data-card='token-bd'></script>",
     "implementation_cards_v3_2026-03-25", 0.99),

    ("technical_architecture", "render_card_js",
     "render_card.js: grava um card animado com dados ao vivo usando Playwright/Chrome headless. "
     "Comandos: node render_card.js token-bd (grava + envia webhook); "
     "node render_card.js token-bd --no-send (só grava, usado pelo bot Discord); "
     "node render_card.js all (todos os 8 cards). "
     "Requer card_server.py rodando em localhost:8766. "
     "Chrome path: C:/Program Files/Google/Chrome/Application/chrome.exe. "
     "Grava 5 segundos de WebM 1080×1920 a 1 DPR.",
     "implementation_cards_v3_2026-03-25", 0.99),

    # ── CANAIS E WEBHOOKS ─────────────────────────────────────────────────────
    ("discord_channels", "cards_v3_mapa_canais",
     "Mapa de cards para canais Discord WEbdEX: "
     "webdex-onchain → #webdex-on-chain (cor #00D4FF); "
     "token-bd → #token-bd (cor #00FFB2); "
     "conquistas → #conquistas (cor #fb0491); "
     "operacoes → #operações (cor #d90048); "
     "swaps → #swaps (cor #00D4FF); "
     "relatorio-diario → #relatório-diário (cor #fb0491); "
     "gm-wagmi → #gm-wagmi (cor #fb0491); "
     "bdzinho-ia → #bdzinho-ia (cor #fb0491). "
     "Variáveis de ambiente dos webhooks: DISCORD_WEBHOOK_ONCHAIN, DISCORD_WEBHOOK_TOKEN_BD, "
     "DISCORD_WEBHOOK_CONQUISTAS, DISCORD_WEBHOOK_OPERACOES, DISCORD_WEBHOOK_SWAPS, "
     "DISCORD_WEBHOOK_RELATORIO, DISCORD_WEBHOOK_GM.",
     "implementation_cards_v3_2026-03-25", 0.98),

    # ── COMO RESPONDER SOBRE OS CARDS ─────────────────────────────────────────
    ("response_patterns", "responder_sobre_cards_discord",
     "Quando perguntarem sobre os cards animados do Discord ou como ver dados ao vivo: "
     "Os cards mostram dados em tempo real do protocolo WEbdEX — supply do token BD, TVL, operações, "
     "swaps e muito mais. Use /card no Discord para gerar qualquer card na hora. "
     "Cada canal (#token-bd, #swaps, #operações etc.) tem um card animado dedicado. "
     "Os dados são puxados diretamente da blockchain Polygon via nosso monitor engine.",
     "implementation_cards_v3_2026-03-25", 0.99),

    ("response_patterns", "responder_sobre_dados_tempo_real",
     "bdZinho pode fornecer dados em tempo real do protocolo através de: "
     "1) cards animados via /card (visual, 1080×1920, WebM); "
     "2) comando /status (embed texto com TVL, operações, capital); "
     "3) gráficos via /grafico (TVL histórico, P&L, operações). "
     "Os dados vêm do webdex_v5_final.db que o monitor-engine atualiza continuamente. "
     "A fonte é sempre on-chain — sem intermediários, sem estimativas manuais.",
     "implementation_cards_v3_2026-03-25", 0.99),
]


def main():
    if not DATABASE_URL:
        print("❌ DATABASE_URL não configurada.")
        print("   Uso: DATABASE_URL=postgresql://... python inject_cards_knowledge.py")
        return

    conn = None
    inserted = 0
    updated = 0
    now = datetime.now(timezone.utc)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        for category, topic, content, source, confidence in CARDS_KNOWLEDGE:
            cur.execute(
                "SELECT id FROM bdz_knowledge WHERE category = %s AND topic = %s LIMIT 1",
                (category, topic)
            )
            if cur.fetchone():
                cur.execute(
                    "UPDATE bdz_knowledge SET content = %s, source = %s, confidence = %s, updated_at = %s "
                    "WHERE category = %s AND topic = %s",
                    (content, source, confidence, now, category, topic)
                )
                updated += 1
            else:
                cur.execute(
                    """INSERT INTO bdz_knowledge (category, topic, content, source, confidence, active, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, true, %s, %s)""",
                    (category, topic, content, source, confidence, now, now)
                )
                inserted += 1

        conn.commit()
        print("✅ bdZinho Cards v3 Knowledge injetado com sucesso!")
        print(f"   {inserted} novos items inseridos")
        print(f"   {updated} items atualizados")
        print(f"   Total: {len(CARDS_KNOWLEDGE)} items processados")
        print()

        cur.execute("SELECT COUNT(*) FROM bdz_knowledge WHERE active = true")
        total = cur.fetchone()[0]
        print(f"   📊 Total bdz_knowledge ativo: {total} items")
        print()
        print("   bdZinho agora sabe sobre:")
        print("   • Sistema de 8 cards animados Discord (WebM 1080×1920)")
        print("   • Comando /card com dados ao vivo")
        print("   • Arquitetura: card_server.py + live-data.js + render_card.js")
        print("   • Mapa de canais Discord e webhooks")
        print("   • Como responder perguntas sobre dados ao vivo")

    except Exception as e:
        print(f"❌ Erro: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
