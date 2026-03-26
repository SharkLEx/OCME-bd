#!/usr/bin/env python3
"""
bdZinho Discord Channel Knowledge Injector — v3 Launch
Injeta conhecimento sobre os canais do Discord WEbdEX e identidade visual
para que o bdZinho possa referenciar e guiar usuários nos canais certos.

Categorias injetadas:
  • discord_channels — propósito e conteúdo de cada canal
  • design_system    — paleta, fontes, cards visuais do WEbdEX
  • bdzinho_v3       — features do bdZinho Intelligence v3
"""

import os
import psycopg2
from datetime import datetime, timezone

DATABASE_URL = os.environ.get("DATABASE_URL", "")

DISCORD_KNOWLEDGE = [
    # ── CANAIS DISCORD ────────────────────────────────────────────────────────

    ("discord_channels", "canal_webdex_on_chain",
     "Canal #webdex-on-chain: publica eventos on-chain em tempo real na Polygon. "
     "Detecta anomalias (volumes fora do padrão, grandes movimentações), monitora atividade "
     "do protocolo WEbdEX, holders ativos e transações. Bot notifica automaticamente via webhook. "
     "Webhook: DISCORD_WEBHOOK_ONCHAIN. Cor do canal: cyan #00D4FF. "
     "Ideal para: traders que querem saber o que está acontecendo agora na blockchain.",
     "discord_v3_launch_2026", 0.95),

    ("discord_channels", "canal_token_bd",
     "Canal #token-bd: relatório automático a cada 2 horas sobre o token BD. "
     "Inclui supply circulante, top holders, market cap, movimentações de baleias. "
     "Webhook: DISCORD_WEBHOOK_TOKEN_BD. Cor do canal: green #00FFB2. "
     "Publicado pelo monitor engine (função get_token_metrics). "
     "Ideal para: holders do token BD que acompanham o desempenho.",
     "discord_v3_launch_2026", 0.95),

    ("discord_channels", "canal_conquistas",
     "Canal #conquistas: celebra milestones do protocolo WEbdEX. "
     "Publica quando um novo holder se junta, quando metas são batidas, recordes históricos. "
     "Webhook: DISCORD_WEBHOOK_CONQUISTAS. Cor do canal: pink #fb0491. "
     "Tom: celebratório, energético. bdZinho usa persona 'wins' aqui — exclamações, emojis. "
     "Ideal para: comunidade que quer acompanhar o crescimento do protocolo.",
     "discord_v3_launch_2026", 0.95),

    ("discord_channels", "canal_operacoes",
     "Canal #operações: log de operações do protocolo — novas carteiras conectadas, "
     "interações com contratos, confirmações de transações. "
     "Webhook: DISCORD_WEBHOOK_OPERACOES. Cor do canal: red #d90048. "
     "Tom: técnico, preciso. Cada entrada é um evento real do protocolo. "
     "Ideal para: desenvolvedores e usuários avançados que querem rastreabilidade.",
     "discord_v3_launch_2026", 0.95),

    ("discord_channels", "canal_swaps",
     "Canal #swaps: notifica Create Swap e Swap Tokens em tempo real. "
     "Inclui par de tokens, volume, taxa de câmbio média. "
     "Webhook: DISCORD_WEBHOOK_SWAPS. Cor do canal: cyan #00D4FF. "
     "Monitorado pela função SwapBook do monitor engine. "
     "Ideal para: traders que querem ver o fluxo de swaps do protocolo.",
     "discord_v3_launch_2026", 0.95),

    ("discord_channels", "canal_relatorio_diario",
     "Canal #relatório-diário: publicação automática às 21h com o resumo do ciclo de 24h. "
     "Inclui: atividade on-chain, holders ativos, volume de swaps, PnL do protocolo, "
     "tendência para o próximo ciclo. Webhook: DISCORD_WEBHOOK_RELATORIO. "
     "Cor do canal: pink #fb0491. Tom: analítico, completo, com dados reais. "
     "Ideal para: todos os membros — é o 'jornal diário' do WEbdEX.",
     "discord_v3_launch_2026", 0.95),

    ("discord_channels", "canal_gm_wagmi",
     "Canal #gm-wagmi: ritual diário às 7h. bdZinho publica GM + manchetes do mercado Web3 "
     "mais relevantes, sentimento do mercado (bull/bear), meta do dia para a comunidade. "
     "Webhook: DISCORD_WEBHOOK_GM. Cor do canal: pink+green. "
     "Tom: energético, motivacional, Web3-nativo. 'We're all gonna make it.' "
     "Ideal para: todos os membros que começam o dia no Discord.",
     "discord_v3_launch_2026", 0.95),

    ("discord_channels", "canal_bdzinho_ia",
     "Canal #bdzinho-ia (ID: 1483299104653316208): canal de chat direto com o bdZinho. "
     "Usuários perguntam sobre DeFi, Web3, analisam carteiras, aprendem Solidity. "
     "bdZinho tem memória persistente — lembra do histórico do usuário entre sessões. "
     "Adapta tom: didático para iniciantes, técnico para avançados (Persona Engine). "
     "Acessa dados reais da Polygon via Tool Use On-Chain. Cor: pink #fb0491. "
     "É o coração do produto — interação direta com a IA do protocolo.",
     "discord_v3_launch_2026", 0.98),

    # ── DESIGN SYSTEM WEBDEX ─────────────────────────────────────────────────

    ("design_system", "webdex_paleta_cores",
     "Paleta oficial WEbdEX: "
     "Pink #fb0491 (cor primária, identidade bdZinho), "
     "Red #d90048 (ação, urgência, operações), "
     "Green #00FFB2 (sucesso, tokens, ganhos), "
     "Cyan #00D4FF (on-chain, dados, tech), "
     "Black #000000 (fundo), Dark #111111 (cards), "
     "White #ffffff (texto principal), Gray #888888 (texto secundário). "
     "Nunca usar mais de 2 cores de destaque por peça.",
     "discord_v3_launch_2026", 0.90),

    ("design_system", "webdex_fontes",
     "Fontes WEbdEX: Syne 800 (títulos, wordmark, hierarquia principal — import Google Fonts). "
     "Press Start 2P (versão, números especiais, elementos retrô/crypto — import Google Fonts). "
     "Tamanhos padrão: hero-title 88px, hero-tagline 38px, feature-name 19px, feature-desc 22px. "
     "Letter-spacing negativo nos títulos (-3px) para peso visual.",
     "discord_v3_launch_2026", 0.90),

    ("design_system", "webdex_personagem_bdzinho",
     "bdZinho: robô 3D rosa com cabeça arredondada e dois chifres, logo 'bd' no peito. "
     "Expressões: bot-hero (corpo inteiro, apontando), bot-smart (óculos + terno), "
     "bot-face (close-up, moletom azul), bot-blockchain (segurando orb blockchain), "
     "bot-brasil (bandeira BR), bot-authority (terno preto, braços cruzados), "
     "bot-defi (óculos escuros + tokens), bot-wallet (carteira + Bitcoin), "
     "bot-point (apontando para o viewer), bot-dupla (dois robôs). "
     "Drop-shadow rosa: filter: drop-shadow(0 0 60px rgba(251,4,145,0.35)).",
     "discord_v3_launch_2026", 0.92),

    ("design_system", "webdex_cards_anuncio",
     "Cards de anúncio WEbdEX: formato 1080×1920px (Instagram Stories / Discord media). "
     "Estrutura: header (logo+badge) → hero (título+tagline) → bot visual → divider → features (4 cards) → quote → CTA → footer. "
     "Base CSS compartilhada em base.css. 10 variações de lançamento (v1 a v10) + 8 cards por canal. "
     "Servidor local porta 8766 para renderização via Playwright. "
     "Pasta: media/ no repositório principal.",
     "discord_v3_launch_2026", 0.88),

    # ── BDZINHO V3 FEATURES ───────────────────────────────────────────────────

    ("bdzinho_features", "v3_memoria_persistente",
     "bdZinho v3 — Memória Persistente: histórico completo de conversas por usuário. "
     "Armazenado na tabela user_memory no PostgreSQL. "
     "Permite continuidade entre sessões — o bot lembra do nível do usuário, "
     "perguntas anteriores, carteiras analisadas. "
     "Funciona nos canais Discord e Telegram.",
     "discord_v3_launch_2026", 0.95),

    ("bdzinho_features", "v3_tool_use_onchain",
     "bdZinho v3 — Tool Use On-Chain: acessa dados reais da Polygon durante a conversa. "
     "Pede dados de TVL, preço, carteiras, transações em tempo real. "
     "Integrado ao monitor engine via function calling da API Anthropic. "
     "Não inventa dados — sempre busca on-chain antes de responder sobre métricas.",
     "discord_v3_launch_2026", 0.95),

    ("bdzinho_features", "v3_streaming",
     "bdZinho v3 — Streaming: usuário vê a resposta sendo gerada em tempo real. "
     "Implementado via API Anthropic streaming. "
     "Melhora percepção de velocidade e engajamento.",
     "discord_v3_launch_2026", 0.90),

    ("bdzinho_features", "v3_persona_engine",
     "bdZinho v3 — Persona Engine: adapta o tom automaticamente. "
     "Modo iniciante: didático, explicativo, sem jargão. "
     "Modo avançado: técnico, conciso, assume conhecimento. "
     "Modo celebração (wins): entusiasmado, emojis, parabéns. "
     "Modo análise (losses): analítico, calmo, foco em aprendizado. "
     "Detecção automática baseada no histórico e perfil do usuário.",
     "discord_v3_launch_2026", 0.95),
]

def inject_knowledge(conn):
    cur = conn.cursor()
    inserted = 0
    skipped = 0

    for category, key, content, source, confidence in DISCORD_KNOWLEDGE:
        try:
            cur.execute("""
                INSERT INTO bdz_knowledge (category, key, content, source, confidence, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (key) DO UPDATE SET
                    content = EXCLUDED.content,
                    source = EXCLUDED.source,
                    confidence = EXCLUDED.confidence,
                    created_at = EXCLUDED.created_at
            """, (category, key, content, source, confidence,
                  datetime.now(timezone.utc)))
            inserted += 1
        except Exception as e:
            print(f"  ⚠️  Erro em {key}: {e}")
            skipped += 1

    conn.commit()
    cur.close()
    return inserted, skipped


def main():
    print("🤖 bdZinho Discord Channel Knowledge Injector")
    print(f"   {len(DISCORD_KNOWLEDGE)} itens para injetar\n")

    if not DATABASE_URL:
        print("❌ DATABASE_URL não configurado")
        print("   Rode: export DATABASE_URL='postgresql://...'")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        print("✅ Conectado ao PostgreSQL\n")

        inserted, skipped = inject_knowledge(conn)

        print(f"\n📊 Resultado:")
        print(f"   ✅ Inseridos/atualizados: {inserted}")
        print(f"   ⚠️  Pulados: {skipped}")
        print(f"   📦 Total processado: {len(DISCORD_KNOWLEDGE)}")

        conn.close()
        print("\n🎯 bdZinho agora conhece os canais do Discord WEbdEX!")

    except Exception as e:
        print(f"❌ Erro de conexão: {e}")


if __name__ == "__main__":
    main()
