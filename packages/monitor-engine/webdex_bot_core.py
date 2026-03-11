from __future__ import annotations
# ==============================================================================
# webdex_bot_core.py — WEbdEX Monitor Engine (extraído de WEbdEX_V30_24_SPEED_PATCH_FIXED.py)
# Linhas fonte: ~1220-1560 (bot init, notif queue, send helpers, admin checks)
# ==============================================================================

import os, time, re, queue, html
from typing import Any, Dict, List

import telebot
from telebot import types
from decimal import Decimal

from webdex_config import (
    logger, log_error, TELEGRAM_TOKEN, ADMIN_USER_IDS, Web3,
    ABI_ERC20_META, TOKEN_CONFIG, TOKENS_TO_WATCH,
)
from webdex_db import (
    DB_LOCK, cursor, conn, set_user_active, now_br, get_config, set_config,
    normalize_txhash,
)
from webdex_chain import obter_preco_pol

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io

# ==============================================================================
# 🤖 BOT INIT
# ==============================================================================
if not TELEGRAM_TOKEN or (":" not in TELEGRAM_TOKEN):
    logger.error("❌ TELEGRAM_TOKEN inválido. Defina TELEGRAM_TOKEN no .env.")
    raise SystemExit(1)

class _TelebotExceptionHandler(telebot.ExceptionHandler):
    def handle(self, exception):
        err = str(exception)
        if "502" in err or "Bad Gateway" in err:
            logger.warning("🌐 Telegram 502 (Bad Gateway) — aguardando 10s e reconectando...")
            time.sleep(10)
            return True
        if "429" in err or "Too Many Requests" in err:
            wait = 10
            try:
                m = re.search(r"retry after (\d+)", err, re.IGNORECASE)
                if m:
                    wait = int(m.group(1)) + 1
            except Exception:
                pass
            logger.warning(f"⏳ Telegram 429 (Rate limit) — aguardando {wait}s...")
            time.sleep(wait)
            return True
        if any(x in err for x in ["ConnectionReset", "RemoteDisconnected", "ReadTimeout",
                                   "ConnectionError", "ConnectTimeout", "ProtocolError"]):
            logger.warning(f"🔌 Telegram network error — aguardando 8s: {err[:120]}")
            time.sleep(8)
            return True
        return False

bot = telebot.TeleBot(
    TELEGRAM_TOKEN,
    parse_mode="HTML",
    exception_handler=_TelebotExceptionHandler(),
)

# ==============================================================================
# 🔔 Notification Queue
# ==============================================================================
NOTIF_QUEUE: "queue.Queue[tuple]" = queue.Queue(maxsize=5000)

_TG_SAFE_LIMIT = 3500

def _send(chat_id: int, text: str, reply_markup=None):
    return _tg_send_with_retry(bot.send_message, chat_id, text, reply_markup=reply_markup)

def _send_long(chat_id: int, text: str, reply_markup=None, limit: int = _TG_SAFE_LIMIT):
    text = text or ""
    if len(text) <= limit:
        return _send(chat_id, text, reply_markup=reply_markup)
    lines = text.splitlines(True)
    chunk = ""
    first = True
    for ln in lines:
        if len(chunk) + len(ln) > limit and chunk:
            _send(chat_id, chunk, reply_markup=(reply_markup if first else None))
            first = False
            chunk = ""
        chunk += ln
    if chunk:
        _send(chat_id, chunk, reply_markup=(reply_markup if first else None))

def _is_tg_blocked_error(e) -> bool:
    s = str(e)
    if "Forbidden: bot was blocked by the user" in s:
        return True
    if getattr(e, "error_code", None) == 403:
        return True
    try:
        rj = getattr(e, "result_json", None) or {}
        if isinstance(rj, dict) and rj.get("error_code") == 403:
            return True
    except Exception:
        pass
    return False

def _tg_send_with_retry(fn, *args, **kwargs):
    chat_id = None
    if args:
        chat_id = args[0]
    chat_id = kwargs.get("chat_id", chat_id)
    backoff = 1.0
    last_err = None
    for _ in range(5):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_err = e
            if _is_tg_blocked_error(e):
                try:
                    logger.warning(f"Telegram 403 (blocked) -> desativando chat_id={chat_id}")
                except Exception:
                    pass
                try:
                    if chat_id is not None:
                        set_user_active(int(chat_id), 0)
                except Exception:
                    pass
                return None
            try:
                logger.warning(f"Telegram send retry: {e}")
            except Exception:
                pass
            err_str = str(e)
            if "400" in err_str and ("parse" in err_str.lower() or "entities" in err_str.lower()):
                last_err = e
                break
            if "429" in err_str or "Too Many Requests" in err_str:
                try:
                    m = re.search(r"retry after (\d+)", err_str, re.IGNORECASE)
                    wait = int(m.group(1)) + 1 if m else backoff
                except Exception:
                    wait = backoff
                time.sleep(wait)
                backoff = min(wait + 1, 15.0)
            else:
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 15.0)
    try:
        logger.error(f"Telegram send failed after retries: {last_err}")
    except Exception:
        pass
    err_str = str(last_err)
    if "400" in err_str and ("parse" in err_str.lower() or "entities" in err_str.lower()):
        try:
            def _strip_html(t):
                t = re.sub(r"<[^>]+>", "", str(t))
                import html as _html
                return _html.unescape(t)
            clean_args = list(args)
            if len(clean_args) >= 2 and isinstance(clean_args[1], str):
                clean_args[1] = _strip_html(clean_args[1])[:3500]
            clean_kwargs = {k: v for k, v in kwargs.items() if k != "parse_mode"}
            fn(*clean_args, **clean_kwargs)
            logger.warning("Telegram fallback: mensagem reenviada como texto puro (HTML inválido)")
        except Exception as _fe:
            logger.error(f"Telegram fallback também falhou: {_fe}")
    return None

def _notif_worker():
    while True:
        item = NOTIF_QUEUE.get()
        try:
            kind = item[0]
            if kind == "html":
                chat_id, text_msg, disable_preview = item[1], item[2], item[3]
                _tg_send_with_retry(
                    bot.send_message,
                    chat_id,
                    text_msg,
                    parse_mode="HTML",
                    disable_web_page_preview=disable_preview,
                )
            elif kind == "photo":
                chat_id, photo_bytes, caption = item[1], item[2], item[3]
                _tg_send_with_retry(bot.send_photo, chat_id, photo_bytes, caption=caption)
            elif kind == "doc":
                chat_id, doc_bytes, filename, caption = item[1], item[2], item[3], item[4]
                _tg_send_with_retry(bot.send_document, chat_id, doc_bytes, visible_file_name=filename, caption=caption)
        except Exception as e:
            try:
                logger.error(f"notif_worker erro: {e}")
            except Exception:
                pass
        finally:
            try:
                NOTIF_QUEUE.task_done()
            except Exception:
                pass

def _tg_split_text(text: str, limit: int = _TG_SAFE_LIMIT):
    if not text:
        return [""]
    text = str(text)
    if len(text) <= limit:
        return [text]
    parts = []
    buf = ""
    for line in text.split("\n"):
        add = (line + "\n")
        if len(buf) + len(add) <= limit:
            buf += add
        else:
            if buf:
                parts.append(buf.rstrip("\n"))
                buf = ""
            while len(add) > limit:
                parts.append(add[:limit])
                add = add[limit:]
            buf = add
    if buf:
        parts.append(buf.rstrip("\n"))
    return [p for p in parts if p is not None and p != ""]

def _get_admin_chat_ids():
    try:
        return list(sorted({int(x) for x in ADMIN_USER_IDS}))
    except Exception:
        return []

SUPPORT_HEADER = "Você fala com a <b>IA da WEbdEX</b>. Caso precise, vamos atualizá-lo da nossa conversa."

def send_html(chat_id: int, text: str, **kwargs):
    disable_preview = kwargs.get("disable_web_page_preview", True)
    try:
        chunks = _tg_split_text(str(text), _TG_SAFE_LIMIT)
        for ch in chunks:
            NOTIF_QUEUE.put_nowait(("html", int(chat_id), str(ch), bool(disable_preview)))
    except Exception:
        try:
            bot.send_message(int(chat_id), str(text)[:_TG_SAFE_LIMIT], parse_mode="HTML", disable_web_page_preview=bool(disable_preview))
        except Exception:
            pass

def send_support(chat_id: int, text: str, **kwargs):
    msg = f"{SUPPORT_HEADER}\n\n{text}\n\n{SUPPORT_HEADER}"
    return send_html(chat_id, msg, **kwargs)

# ==============================================================================
# 🖼️ LOGO WEbdEX — envia com file_id cacheado (upload único)
# ==============================================================================
import pathlib as _pathlib

_LOGO_PATH = str(_pathlib.Path(__file__).parent / "webdex_logo.jpeg")
_LOGO_FILE_ID_KEY = "webdex_logo_file_id"
_TG_CAPTION_LIMIT  = 1024

def send_logo_photo(chat_id: int, caption: str = "", reply_markup=None) -> bool:
    """
    Envia a logo WEbdEX como foto.
    - Primeira vez: faz upload do arquivo local e salva o file_id no DB.
    - Demais vezes: reutiliza o file_id (zero re-upload).
    - Se caption > 1024 chars: envia foto sem caption + texto separado.
    - Retorna True se enviou com sucesso, False caso contrário.
    """
    try:
        cached_fid = get_config(_LOGO_FILE_ID_KEY, "")

        # Caption do Telegram: máx 1024 chars
        cap_safe  = (caption or "")[:_TG_CAPTION_LIMIT]
        cap_long  = len(caption or "") > _TG_CAPTION_LIMIT
        mk        = reply_markup

        def _do_send(photo_src):
            return bot.send_photo(
                chat_id, photo_src,
                caption=cap_safe if not cap_long else "",
                parse_mode="HTML",
                reply_markup=mk if not cap_long else None,
            )

        if cached_fid:
            try:
                msg = _do_send(cached_fid)
            except Exception:
                # file_id inválido ou expirado — re-faz upload
                set_config(_LOGO_FILE_ID_KEY, "")
                cached_fid = ""

        if not cached_fid:
            if not _pathlib.Path(_LOGO_PATH).exists():
                return False
            with open(_LOGO_PATH, "rb") as f:
                msg = _do_send(f)
            # Salva o file_id para reutilização
            try:
                fid = msg.photo[-1].file_id
                set_config(_LOGO_FILE_ID_KEY, fid)
            except Exception:
                pass

        # Se caption era longa, manda o texto completo em seguida
        if cap_long and caption:
            send_html(chat_id, caption, reply_markup=mk)

        return True
    except Exception as _e:
        logger.warning("[send_logo_photo] %s", _e)
        return False

def _clear_pending_steps(chat_id: int):
    try:
        bot.clear_step_handler_by_chat_id(chat_id)
    except Exception:
        pass

def _clear_pending(chat_id: int):
    return _clear_pending_steps(chat_id)

def _is_admin(chat_id: int) -> bool:
    return (chat_id in ADMIN_USER_IDS) if ADMIN_USER_IDS else False

def is_admin_chat(chat_id) -> bool:
    try:
        return _is_admin(int(chat_id))
    except Exception:
        return False

def is_admin(chat_id, *args, **kwargs) -> bool:
    return is_admin_chat(chat_id)

# ==============================================================================
# 🎨 UTILS
# ==============================================================================
def esc(s: Any) -> str:
    import html as _html
    return _html.escape(str(s), quote=False)

def code(text: Any) -> str:
    return f"<code>{esc(text)}</code>"

def barra_progresso(wins: int, total: int) -> str:
    if total <= 0:
        return "⬜" * 10
    perc = wins / total
    blocos = int(perc * 10)
    return "🟩" * blocos + "🔴" * (10 - blocos)

def get_token_meta(addr: str) -> Dict[str, Any]:
    import json as _json
    from webdex_config import ABI_ERC20_META, TOKEN_CONFIG
    from webdex_chain import web3
    t_chk = Web3.to_checksum_address(addr)
    if t_chk in TOKEN_CONFIG:
        return TOKEN_CONFIG[t_chk]
    try:
        c = web3.eth.contract(address=t_chk, abi=_json.loads(ABI_ERC20_META))
        return {"dec": int(c.functions.decimals().call()), "sym": str(c.functions.symbol().call()), "icon": "🪙"}
    except Exception:
        return {"dec": 18, "sym": "UNK", "icon": "🔵"}

def formatar_moeda(valor: Any, decimais: int) -> float:
    try:
        return float(Decimal(int(valor)) / Decimal(10 ** int(decimais)))
    except Exception:
        try:
            return float(valor) / (10 ** int(decimais))
        except Exception:
            return 0.0

def gerar_grafico(rows):
    if not rows:
        return None
    rows.sort(key=lambda x: x[0])
    dates, equity = [], []
    acc = 0.0
    for r in rows:
        if str(r[1]) != "Trade":
            continue
        try:
            acc += (float(r[4]) - float(r[5]))
            from datetime import datetime
            dates.append(datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S"))
            equity.append(acc)
        except Exception:
            pass
    if not dates:
        return None
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 5))
    cor = "#00ff9d" if acc >= 0 else "#ff4d4d"
    ax.plot(dates, equity, color=cor, linewidth=2, marker=".", markersize=4)
    ax.fill_between(dates, equity, color=cor, alpha=0.15)
    ax.set_title(f"Equity Curve (Liq: {acc:+.4f} USD)", color="white")
    ax.grid(True, linestyle=":", alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    buf = io.BytesIO()
    buf.name = "dre.png"
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=110)
    buf.seek(0)
    plt.close(fig)
    return buf
