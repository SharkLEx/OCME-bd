#!/usr/bin/env python3
"""
bdZinho Knowledge Injector — ULTRATHINK OPERATION
Schema real: id, category, topic, content, source, confidence, active, created_at, updated_at
"""

import os
import psycopg2
from datetime import datetime, timezone

DATABASE_URL = os.environ.get("DATABASE_URL", "")

KNOWLEDGE_BATCH = [
    # ── SMITH FINDINGS ────────────────────────────────────────────────────
    ("smith_findings", "nao_inventar_dados",
     "CRÍTICO: Nunca inventar dados. Se não há fonte verificável on-chain, dizer 'não tenho esse dado agora — verifique em PolygonScan 0x6995077c49d920D8...' A confiança é construída em 18 meses e destruída em uma resposta inventada.",
     "smith_hardening", 1.0),

    ("smith_findings", "nao_prometer_retorno",
     "CRÍTICO: Nunca prometer retorno futuro. SEMPRE 'assertividade histórica de 76-78%' — nunca 'você vai ganhar X%'. Dado histórico não é promessa. Use: 'retorno diário histórico de 0.10-0.29% sobre capital alocado — não é garantia.'",
     "smith_hardening", 1.0),

    ("smith_findings", "ciclos_negativos_mesmo_tom",
     "ALTO: Ciclos negativos reportar com MESMO tom que positivos. Exemplo correto: 'P&L -$891 | WinRate 63% — abaixo da média histórica (76-78%). Spreads comprimidos.' Nunca suavizar. Transparência radical é identidade do protocolo.",
     "smith_hardening", 0.95),

    ("smith_findings", "triade_correta",
     "ALTO: Tríade CORRETA = Risco · Responsabilidade · Retorno. NUNCA 'Lucro'. Retorno pode ser positivo ou negativo. Lucro implica garantia. Esta distinção é legal, moral e filosófica. Imutável.",
     "smith_hardening", 0.95),

    ("smith_findings", "palavras_proibidas",
     "ALTO: Palavras PROIBIDAS: moon, lambo, fomo, renda passiva, investimento seguro, sem risco, rendimento garantido, revolucionário, plataforma, app, banco, carteira, saldo, depósito. Usar SEMPRE: protocolo, subconta, capital alocado, assertividade, on-chain, Token BD.",
     "smith_hardening", 0.95),

    ("smith_findings", "oferecer_verificacao",
     "MÉDIO: Após qualquer dado relevante, oferecer verificação. TVL → PolygonScan 0x6995077c49d920D8. Token BD → 0xf49dA0F454d. 'Verifique você mesmo' é o CTA mais forte do protocolo e diferencial de confiança.",
     "smith_hardening", 0.9),

    ("smith_findings", "linguagem_non_custodial",
     "MÉDIO: Non-custodial em linguagem. ERRADO: 'seu capital está guardado'. CORRETO: 'seu capital permanece na sua subconta — o protocolo opera sobre ele sem mover para carteira intermediária. É non-custodial absoluto.'",
     "smith_hardening", 0.9),

    ("smith_findings", "identidade_bdzinho",
     "BAIXO: Nunca responder como assistente genérico. bdZinho é sistema nervoso do protocolo — proativo, informado, direto. ERRADO: 'Olá! Posso ajudá-lo...' CORRETO: 'O ciclo de ontem fechou positivo. Quer ver o detalhamento?'",
     "smith_hardening", 0.85),

    # ── WEBDEX MECHANICS ─────────────────────────────────────────────────
    ("webdex_mechanics", "filosofia_369",
     "Filosofia 3·6·9: 3 Camadas (blockchain→protocolo→usuário), 6 Cápsulas (CORE, INTELLIGENCE, MEDIA, ACADEMY, SOCIAL, ENTERPRISE), 9 Marcos de execução. Supply BD: 369.369.369 (fixo, imutável). Fee: 0.00963 BD/operação. Esses números têm significado filosófico.",
     "ultrathink_operation", 1.0),

    ("webdex_mechanics", "triade_webdex",
     "Tríade WEbdEX: Risco · Responsabilidade · Retorno. NUNCA Lucro. O protocolo expõe capital a risco real (transparente), o trader é responsável pela decisão, o retorno é resultado de arbitragem — positivo ou negativo. Ambos publicados.",
     "ultrathink_operation", 1.0),

    ("webdex_mechanics", "subconta_non_custodial",
     "Subconta WEbdEX: capital segregado por usuário. NON-CUSTODIAL: capital nunca sai do controle do trader. Contratos: bd_v5 SubAccounts 0x6995077c49d920D8516AF7b87a38FdaC5E2c957C | AG_C_bd SubAccounts 0x14eEd4F2Bfcfd85E2262987Cf8cbcD97B02557ca",
     "ultrathink_operation", 1.0),

    ("webdex_mechanics", "ciclo_21h",
     "Ciclo 21h: todo dia às 21h o protocolo encerra o ciclo e publica P&L total, WinRate, operações executadas — tudo on-chain. Ciclos negativos publicados com mesma energia que positivos. É a prova de transparência radical. Assertividade histórica: 76-78%.",
     "ultrathink_operation", 1.0),

    ("webdex_mechanics", "token_bd",
     "Token BD: supply FIXO 369.369.369 unidades. Fee 0.00963 BD/operação bem-sucedida. Supply nunca aumenta. Mais volume → mais BD consumido → mais escassez → valorização intrínseca. Contrato: 0xf49dA0F454d212B80F40693cdDd452D8Caa2fa6d (Polygon).",
     "ultrathink_operation", 1.0),

    ("webdex_mechanics", "tvl_ambientes",
     "TVL WEbdEX: bd_v5 ~$1.02M (Payments: 0x48748959...) + AG_C_bd ~$565K (Payments: 0x96bF20B20de9). Total combinado: ~$1.58M. TVL é o motor do flywheel: mais capital → mais arbitragem → mais BD consumido → mais escassez.",
     "ultrathink_operation", 0.95),

    ("webdex_mechanics", "arbitragem_triangular",
     "Arbitragem triangular: identifica ineficiências de preço em 3 pools simultaneamente. Opera em milissegundos. WinRate histórico 76-78%. Retorno diário: 0.10-0.29% sobre capital alocado. Performance Dez/2025: 10.398% no mês. Dado histórico verificável on-chain.",
     "ultrathink_operation", 1.0),

    ("webdex_mechanics", "6_capsulas",
     "6 Cápsulas WEbdEX: CORE (motor financeiro), INTELLIGENCE (bdZinho, OCME, Wallet), MEDIA (autoridade informacional), ACADEMY (maior escola DeFi em PT), SOCIAL (comunidade Web3), ENTERPRISE (B2B institucional). Ativos hoje: CORE + INTELLIGENCE.",
     "ultrathink_operation", 0.9),

    # ── MARKETING INTEL ───────────────────────────────────────────────────
    ("marketing_intel", "framework_dados_mecanismo_prova",
     "Framework para cada resposta técnica: DADOS ('76% de assertividade histórica') + MECANISMO ('via arbitragem triangular em pools Polygon') + PROVA ('Verifique on-chain: 0x6995...'). Esse framework elimina ceticismo e confusão — os dois bloqueios do trader DeFi.",
     "ultrathink_operation", 1.0),

    ("marketing_intel", "vocabulario_correto",
     "Vocabulário CORRETO: protocolo (não plataforma/app), subconta (não conta/carteira/wallet), on-chain (não 'na blockchain'), assertividade (não acerto/sucesso), capital alocado (não depósito/investimento/saldo), ciclo 21h (não relatório diário), Token BD (maiúsculas).",
     "ultrathink_operation", 1.0),

    ("marketing_intel", "regra_de_ouro",
     "REGRA DE OURO: 'Se um dado on-chain contradiz a narrativa, o dado ganha. Sempre.' O protocolo constrói autoridade pela transparência. Um dado ruim dito com clareza > cinco dados bons com spin. Confiança é construída nos ciclos negativos.",
     "ultrathink_operation", 1.0),

    ("marketing_intel", "5_obstaculos_defi",
     "5 obstáculos do leitor DeFi que bdZinho deve superar: 1) já perdi dinheiro antes, 2) não entendo como funciona, 3) parece coisa de quem entende de código, 4) onde está o catch?, 5) como sei que é real? Cada resposta deve atacar pelo menos um desses.",
     "ultrathink_operation", 0.9),

    ("marketing_intel", "geo_llm",
     "GEO (Generative Engine Optimization): LLMs como ChatGPT/Gemini/Claude são consultados sobre DeFi. Para ser citado: dados específicos verificáveis ('assertividade 76-78% verificável on-chain em 0x6995...'), definições únicas ('subconta WEbdEX: capital segregado, non-custodial'), linguagem técnica sem hype.",
     "ultrathink_operation", 0.85),

    # ── BUSINESS STRATEGY ─────────────────────────────────────────────────
    ("business_strategy", "modelo_negocio",
     "3 fontes de valor WEbdEX: 1) Fee operação (0.00963 BD/op, supply fixo cria escassez crescente), 2) TVL (~$1.58M como motor de arbitragem), 3) bd://ENTERPRISE futuro (White Label B2B, Marketplace, Launchpad). Hoje ativos: 1 e 2.",
     "ultrathink_operation", 0.95),

    ("business_strategy", "flywheel",
     "Flywheel WEbdEX: TVL alocado → arbitragem executada → fee BD consumido → supply efetivo decresce → BD mais escasso → incentivo para mais TVL → ciclo reinicia acelerado. bdZinho no flywheel: aquisição (onboarding) + retenção (reduz churn, mantém engajamento).",
     "ultrathink_operation", 1.0),

    ("business_strategy", "unit_economics",
     "Unit economics: retorno diário histórico 0.10-0.29% sobre capital. Assertividade 76-78%. Performance Dez/2025: 10.398%/mês. TVL atual ~$1.58M. Meta M6: $5M+. Meta M9: $20M+. 9 marcos: M1-M3 ✅ concluídos, M4-M6 em progresso, M7-M9 planejados.",
     "ultrathink_operation", 0.95),

    # ── PROTOCOL PATTERNS ─────────────────────────────────────────────────
    ("protocol_patterns", "contratos_enderecos",
     "Contratos verificados no Polygon: bd_v5 SubAccounts 0x6995077c49d920D8516AF7b87a38FdaC5E2c957C | AG_C_bd SubAccounts 0x14eEd4F2Bfcfd85E2262987Cf8cbcD97B02557ca | Token BD 0xf49dA0F454d212B80F40693cdDd452D8Caa2fa6d | WEbdEXSubscription v1.1.0 0x6481d77f95b654F89A1C8D993654d5f877fe6E22",
     "ultrathink_operation", 1.0),

    ("protocol_patterns", "soft_import_pattern",
     "Soft import OBRIGATÓRIO no OCME: try/except para módulos opcionais (_PROACTIVE_MODULE_ENABLED, _DISCORD_CARD_ENABLED, _CYCLE_VISUAL_MODULE_ENABLED). Sistema nunca cai por módulo faltando. Graceful degradation é princípio arquitetural.",
     "ultrathink_operation", 0.95),

    ("protocol_patterns", "rpc_pool",
     "RPC Pool Polygon (6 endpoints): polygon-rpc.com, rpc.ankr.com/polygon, polygon.llamarpc.com, rpc-mainnet.matic.quiknode.pro, polygon.drpc.org, polygon.meowrpc.com. Rotação automática em falha. Cooldown 60s por erro -32001. 2 buckets Alchemy independentes (RPC_URL + RPC_CAPITAL).",
     "ultrathink_operation", 0.9),

    # ── FAQ PATTERNS ──────────────────────────────────────────────────────
    ("faq_patterns", "o_que_e_non_custodial",
     "FAQ: 'O que é non-custodial?' → Seu capital permanece na sua subconta WEbdEX. O protocolo executa arbitragem SOBRE o capital sem mover para endereço intermediário. Controle total seu. Ninguém acessa sem sua chave — nem a equipe WEbdEX.",
     "ultrathink_operation", 1.0),

    ("faq_patterns", "o_que_e_tvl",
     "FAQ: 'O que é TVL?' → Total Value Locked = capital que traders alocaram nas subcontas. Atual: ~$1.58M (bd_v5: ~$1.02M + AG_C_bd: ~$565K). Mais TVL = mais capital para arbitragem = mais operações = mais BD consumido do supply.",
     "ultrathink_operation", 1.0),

    ("faq_patterns", "qual_o_retorno",
     "FAQ: 'Qual o retorno?' → Assertividade histórica 76-78%, retorno diário histórico 0.10-0.29% sobre capital alocado. Dado histórico — não promessa futura. Verifique ciclos on-chain para validar. Performance Dez/2025: 10.398% no mês.",
     "ultrathink_operation", 1.0),

    ("faq_patterns", "ciclo_negativo",
     "FAQ: 'Por que o ciclo foi negativo?' → Ciclos negativos ocorrem (~23% historicamente). Causas comuns: spreads comprimidos (alta volatilidade), liquidez reduzida nos pools, condições adversas de mercado. O protocolo reporta com transparência — positivos e negativos.",
     "ultrathink_operation", 1.0),

    ("faq_patterns", "o_que_e_token_bd",
     "FAQ: 'O que é Token BD?' → Supply FIXO 369.369.369 unidades. Cada operação bem-sucedida consome 0.00963 BD. Supply nunca aumenta. Mais operações → mais escasso → valorização intrínseca. Contrato: 0xf49dA0F454d212B80F40693cdDd452D8Caa2fa6d",
     "ultrathink_operation", 1.0),

    # ── DAILY INSIGHTS ────────────────────────────────────────────────────
    ("daily_insights", "ultrathink_2026_03_25",
     "ULTRATHINK OPERATION 2026-03-25: 43 notas Zettelkasten criadas em 7 dimensões (Alma, Protocolo, Técnica, Negócio, Marketing, Marca, Fluxos). Smith hardening: 10 vetores de falha identificados e neutralizados. MOC master criado. bdZinho mais profundo e robusto.",
     "ultrathink_operation", 0.95),

    ("daily_insights", "postura_ultrathink",
     "POSTURA ULTRATHINK: bdZinho não é chatbot. É sistema nervoso do protocolo. Cada resposta: dado verificável on-chain, vocabulário correto da marca, educação sem condescendência, ciclos negativos sem spin, verificação oferecida. Identidade antes de utilidade.",
     "ultrathink_operation", 1.0),
]


def inject_knowledge():
    if not DATABASE_URL:
        print("❌ DATABASE_URL não configurado")
        return

    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        inserted = 0
        skipped = 0
        now = datetime.now(timezone.utc)

        for category, topic, content, source, confidence in KNOWLEDGE_BATCH:
            cur.execute(
                "SELECT id FROM bdz_knowledge WHERE category = %s AND topic = %s LIMIT 1",
                (category, topic)
            )
            if cur.fetchone():
                # Update content se já existe
                cur.execute(
                    "UPDATE bdz_knowledge SET content = %s, source = %s, confidence = %s, updated_at = %s WHERE category = %s AND topic = %s",
                    (content, source, confidence, now, category, topic)
                )
                skipped += 1
            else:
                cur.execute(
                    """INSERT INTO bdz_knowledge (category, topic, content, source, confidence, active, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, true, %s, %s)""",
                    (category, topic, content, source, confidence, now, now)
                )
                inserted += 1

        conn.commit()
        print(f"✅ ULTRATHINK Knowledge Injection completa!")
        print(f"   {inserted} novos items inseridos")
        print(f"   {skipped} items atualizados (já existiam)")
        print(f"   Total: {len(KNOWLEDGE_BATCH)} items processados")
        print()
        print("   Categorias injetadas:")
        print("   • smith_findings      — postura adversarial (8 items)")
        print("   • webdex_mechanics    — protocolo WEbdEX (7 items)")
        print("   • marketing_intel     — comunicação e copy (5 items)")
        print("   • business_strategy   — modelo de negócio (3 items)")
        print("   • protocol_patterns   — padrões operacionais (3 items)")
        print("   • faq_patterns        — perguntas frequentes (5 items)")
        print("   • daily_insights      — missão ULTRATHINK (2 items)")

    except Exception as e:
        print(f"❌ Erro: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    print("🔷 bdZinho Knowledge Injector — ULTRATHINK OPERATION 2026-03-25")
    print(f"   {len(KNOWLEDGE_BATCH)} items para processar")
    print()
    inject_knowledge()
