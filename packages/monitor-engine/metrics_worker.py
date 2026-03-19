"""
metrics_worker.py — Worker assíncrono que faz snapshot do protocolo no PostgreSQL
e envia notificações proativas para o canal #bdzinho-ia.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from protocol_context import get_status_embed_data
import db_handler
import discord

logger = logging.getLogger("webdex.metrics")

_INTERVAL_S     = 10 * 60   # snapshot a cada 10 minutos
_NOTIFY_CHECK_S = 5  * 60   # verifica notificação 21h a cada 5 minutos

# Canal bdzinho-ia
_BDZINHO_CHANNEL_ID = 1483299104653316208

# Hora do ciclo em UTC: 21h BRT = 00h UTC (dia seguinte)
_CICLO_UTC_HOUR = 0
_CICLO_MIN_MIN  = 10   # dispara a partir de 00:10 UTC (21:10 BRT)
_CICLO_MIN_MAX  = 59   # e até 00:59 UTC


# ── Snapshot ────────────────────────────────────────────────────────────────

def _save_snapshot(data: dict) -> None:
    """Persiste snapshot no PostgreSQL."""
    try:
        tvl_rows = data.get("tvl_rows", [])
        tvl_ag = next((r[1] for r in tvl_rows if r[0] == "AG_C_bd"), 0)
        tvl_bd = next((r[1] for r in tvl_rows if r[0] == "bd_v5"), 0)

        conn = db_handler._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO protocol_snapshots
                   (tvl_total, tvl_ag, tvl_bd, ops_count, ops_profit,
                    cap_wallets, cap_total, positions)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    data.get("tvl_total", 0),
                    tvl_ag, tvl_bd,
                    data.get("ops_count", 0),
                    data.get("ops_profit", 0),
                    data.get("cap_wallets", 0),
                    data.get("cap_total", 0),
                    0,
                )
            )
            conn.commit()
        logger.info("[metrics] Snapshot protocolo salvo: TVL=$%.0f", data.get("tvl_total", 0))
    except Exception as e:
        logger.warning("[metrics] Falha ao salvar snapshot: %s", e)


async def metrics_worker_loop() -> None:
    """Loop assíncrono — aguarda 60s no boot, depois roda a cada 10 min."""
    logger.info("[metrics] Worker iniciado — aguardando 60s...")
    await asyncio.sleep(60)

    while True:
        try:
            data = get_status_embed_data()
            if data:
                _save_snapshot(data)
        except Exception as e:
            logger.warning("[metrics] Erro no ciclo: %s", e)
        await asyncio.sleep(_INTERVAL_S)


# ── Notificação proativa 21h ────────────────────────────────────────────────

def _get_ciclo_delta() -> dict | None:
    """
    Retorna dados do ciclo desde 21h BRT de ontem (= 00h UTC de hoje).
    Compara snapshot mais recente com snapshot de ~24h atrás.
    """
    try:
        conn = db_handler._get_conn()
        now_utc = datetime.now(timezone.utc)

        # Início do ciclo = 00:00 UTC de hoje (= 21:00 BRT ontem)
        ciclo_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

        with conn.cursor() as cur:
            # Snapshot mais recente
            cur.execute(
                """SELECT tvl_total, ops_count, ops_profit, cap_wallets, cap_total
                   FROM protocol_snapshots ORDER BY ts DESC LIMIT 1"""
            )
            latest = cur.fetchone()

            # Snapshot mais próximo do início do ciclo
            cur.execute(
                """SELECT tvl_total, ops_count, ops_profit
                   FROM protocol_snapshots
                   WHERE ts <= %s ORDER BY ts DESC LIMIT 1""",
                (ciclo_start,)
            )
            start = cur.fetchone()

        if not latest:
            return None

        tvl_now    = float(latest[0] or 0)
        ops_now    = int(latest[1] or 0)
        profit_now = float(latest[2] or 0)
        wallets    = int(latest[3] or 0)
        cap_total  = float(latest[4] or 0)

        ops_start    = int(start[1] or 0) if start else 0
        profit_start = float(start[2] or 0) if start else 0.0

        return {
            "tvl":          tvl_now,
            "ops_delta":    max(0, ops_now - ops_start),
            "profit_delta": profit_now - profit_start,
            "wallets":      wallets,
            "cap_total":    cap_total,
        }
    except Exception as e:
        logger.error("[ciclo_21h] Erro ao buscar delta: %s", e)
        return None


# Controle in-memory de dias já notificados (sobrevive dentro do processo)
_notified_days: set[str] = set()


def _already_sent_today() -> bool:
    """Verifica se a notificação 21h já foi enviada hoje."""
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if hoje in _notified_days:
        return True
    # Verifica também no PostgreSQL (evita duplicata após restart na janela)
    try:
        conn = db_handler._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id FROM platform_events
                   WHERE event_type = 'ciclo_21h_notificado'
                     AND content = %s
                   LIMIT 1""",
                (hoje,)
            )
            row = cur.fetchone()
        if row:
            _notified_days.add(hoje)
            return True
    except Exception:
        pass
    return False


def _mark_sent_today() -> None:
    """Marca que a notificação 21h já foi enviada (memory + PostgreSQL)."""
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _notified_days.add(hoje)
    try:
        conn = db_handler._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO platform_events
                   (platform, event_type, external_id, sender_id, channel_id, content, payload, processed)
                   VALUES ('discord', 'ciclo_21h_notificado', %s, 'system', 'bdzinho-ia', %s, '{}', true)""",
                (hoje, hoje)
            )
            conn.commit()
    except Exception as e:
        logger.warning("[ciclo_21h] Falha ao persistir flag: %s", e)


async def ciclo_21h_worker(bot: discord.Client) -> None:
    """
    Notifica o canal #bdzinho-ia após o ciclo 21h BRT.
    Dispara entre 00:10–00:59 UTC (21:10–21:59 BRT), uma vez por dia.
    """
    logger.info("[ciclo_21h] Worker iniciado — aguardando janela 21h BRT...")
    await asyncio.sleep(90)  # deixa o bot subir primeiro

    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            in_window = (
                now_utc.hour == _CICLO_UTC_HOUR
                and _CICLO_MIN_MIN <= now_utc.minute <= _CICLO_MIN_MAX
            )

            if in_window and not _already_sent_today():
                data = _get_ciclo_delta()
                if data and data["ops_delta"] > 0:
                    await _send_ciclo_notification(bot, data, now_utc)
                elif data:
                    logger.info("[ciclo_21h] Sem operações no ciclo — notificação pulada")
                    _mark_sent_today()

        except Exception as e:
            logger.error("[ciclo_21h] Erro no worker: %s", e)

        await asyncio.sleep(_NOTIFY_CHECK_S)


async def _send_ciclo_notification(
    bot: discord.Client,
    data: dict,
    now_utc: datetime,
) -> None:
    """Envia embed de resumo do ciclo 21h no canal #bdzinho-ia."""
    from chart_handler import generate_chart

    channel = bot.get_channel(_BDZINHO_CHANNEL_ID)
    if channel is None:
        logger.warning("[ciclo_21h] Canal #bdzinho-ia não encontrado")
        _mark_sent_today()
        return

    hoje_br = (now_utc - timedelta(hours=3)).strftime("%d/%m/%Y")
    profit  = data["profit_delta"]
    ops     = data["ops_delta"]
    tvl     = data["tvl"]
    wallets = data["wallets"]
    cap     = data["cap_total"]

    emoji  = "🟢" if profit >= 0 else "🔴"
    color  = 0x00FF88 if profit >= 0 else 0xFF4444
    sinal  = f"+${profit:.4f}" if profit >= 0 else f"-${abs(profit):.4f}"

    embed = discord.Embed(
        title=f"{emoji} Ciclo 21h Encerrado — {hoje_br}",
        description="Resumo do dia do **WEbdEX Protocol** na Polygon",
        color=color,
    )
    embed.add_field(name="💎 P&L do Ciclo",
                    value=f"`{sinal}`",
                    inline=True)
    embed.add_field(name="⚡ Operações",
                    value=f"`{ops:,}` trades",
                    inline=True)
    embed.add_field(name="📊 TVL Atual",
                    value=f"**${tvl:,.0f}**",
                    inline=True)
    if wallets:
        embed.add_field(name="💰 Capital Usuários",
                        value=f"`{wallets}` carteiras · **${cap:,.0f}**",
                        inline=False)
    embed.add_field(
        name="📈 Gráficos disponíveis",
        value="Use `/grafico` para ver TVL, P&L ou Operações (24h / 7d / 30d)",
        inline=False,
    )
    embed.set_footer(text="WEbdEX Protocol · Ciclo começa às 21h BR · Polygon")

    # Attach gráfico TVL
    chart_file = None
    try:
        chart_file = await asyncio.get_event_loop().run_in_executor(
            None, lambda: generate_chart("tvl", 24)
        )
    except Exception as e:
        logger.warning("[ciclo_21h] Falha ao gerar gráfico TVL: %s", e)

    try:
        if chart_file:
            await channel.send(embed=embed, file=chart_file)
        else:
            await channel.send(embed=embed)
        logger.info("[ciclo_21h] Notificação 21h enviada ao #bdzinho-ia")
        _mark_sent_today()

        # Gerar vídeo Creatomate (graceful degradation — falha não afeta o ciclo)
        try:
            from creatomate_worker import gerar_video_ciclo
            hoje_str = (now_utc - timedelta(hours=3)).strftime("%d.%m.%Y")
            video_bytes = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: gerar_video_ciclo({
                    "profit":    profit,
                    "ops_count": ops,
                    "tvl_total": tvl,
                    "data_str":  hoje_str,
                })
            )
            if video_bytes:
                import io
                video_file = discord.File(io.BytesIO(video_bytes), filename="ciclo_21h.mp4")
                await channel.send(file=video_file)
                logger.info("[ciclo_21h] Vídeo Creatomate enviado no Discord")
        except Exception as ve:
            logger.warning("[ciclo_21h] Vídeo Creatomate ignorado: %s", ve)

    except Exception as e:
        logger.error("[ciclo_21h] Falha ao enviar notificação: %s", e)
