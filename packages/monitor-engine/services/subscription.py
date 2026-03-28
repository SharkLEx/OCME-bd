"""
services/subscription.py — Subscription Service

Story 7.4 — Epic 7: modularização monolito Python
Desbloqueia: Epic 14 (Subscription Flow Free/Pro/Institutional)

Interface limpa para verificação de tier e gate de features.
Consulta tabela `subscriptions` + coluna `users.subscription_expires` no SQLite.

Tiers:
    "free"          — sem subscription ativa (default)
    "pro"           — subscription on-chain ativa (expires_at > now)
    "institutional" — subscription com tier='institutional' (futuro — Epic 14)

Uso no Epic 14:
    from services.subscription import can_use_feature, get_user_tier

    if not can_use_feature(chat_id, "image_gen"):
        await bot.send_message(chat_id, "Upgrade para Pro para usar /criar_imagem")
        return
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal, Optional

logger = logging.getLogger(__name__)

# ── Feature → Tier mínimo necessário ─────────────────────────────────────────
# Mapeamento de features para o tier mínimo exigido.
# Epic 14 pode sobrescrever este mapa via config da DB.
_FEATURE_TIERS: dict[str, str] = {
    # Free (qualquer usuário)
    "ask":              "free",
    "monitor":          "free",
    "rank":             "free",
    "holders":          "free",
    "tvl":              "free",
    "price":            "free",
    "socios":           "free",
    # Pro (subscription ativa)
    "vision":           "pro",
    "image_gen":        "pro",
    "proactive":        "pro",
    "vault_search":     "pro",
    "deep_analysis":    "pro",
    "custom_alerts":    "pro",
    "card":             "pro",
    # Institutional (futuro — Epic 14)
    "api_access":       "institutional",
    "white_label":      "institutional",
    "priority_support": "institutional",
}

# Ordem de tiers para comparação
_TIER_ORDER: dict[str, int] = {
    "free":          0,
    "pro":           1,
    "institutional": 2,
}


def get_user_tier(chat_id: int) -> Literal["free", "pro", "institutional"]:
    """
    Retorna o tier atual do usuário.

    Lógica:
    1. Verifica subscriptions.tier + status='active' + expires_at > now WHERE chat_id=?
    2. Se encontrado → retorna o tier da subscription
    3. Verifica users.subscription_expires > now como fallback
    4. Se nenhum → retorna "free"

    Returns:
        Literal["free", "pro", "institutional"]
    """
    try:
        from webdex_db import DB_LOCK, conn
        now_iso = datetime.now(timezone.utc).isoformat()

        with DB_LOCK:
            # Primeiro: tabela subscriptions (mais precisa — inclui tier)
            row = conn.execute(
                """SELECT tier FROM subscriptions
                   WHERE chat_id = ?
                     AND status = 'active'
                     AND (expires_at IS NULL OR expires_at > ?)
                   ORDER BY expires_at DESC LIMIT 1""",
                (chat_id, now_iso),
            ).fetchone()

        if row:
            tier = row[0] or "pro"
            if tier in _TIER_ORDER:
                return tier  # type: ignore[return-value]

        # Fallback: coluna subscription_expires em users
        with DB_LOCK:
            row2 = conn.execute(
                "SELECT subscription_expires FROM users WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()

        if row2 and row2[0] and row2[0] > now_iso:
            return "pro"

        return "free"

    except Exception as e:
        logger.warning("[subscription] get_user_tier error (chat_id=%s): %s", chat_id, e)
        return "free"  # graceful degradation — não bloqueia por erro de DB


def can_use_feature(chat_id: int, feature: str) -> bool:
    """
    Verifica se o usuário pode usar a feature.

    Args:
        chat_id: ID do usuário no Telegram
        feature: Nome da feature (ver _FEATURE_TIERS acima)

    Returns:
        True se o tier do usuário >= tier mínimo da feature
        True se feature não está mapeada (features desconhecidas são permitidas)
    """
    required_tier = _FEATURE_TIERS.get(feature, "free")
    if required_tier == "free":
        return True  # shortcut — free features não precisam de DB check

    user_tier = get_user_tier(chat_id)
    return _TIER_ORDER.get(user_tier, 0) >= _TIER_ORDER.get(required_tier, 0)


def get_rate_limit_config(chat_id: int) -> dict:
    """
    Retorna configuração de rate limit baseada no tier do usuário.

    Usado pelo services/rate_limit.py e ai/chat.py para determinar limites.

    Returns:
        dict com keys: chat, vision, image_gen, proactive (msgs/hora)
    """
    tier = get_user_tier(chat_id)

    configs = {
        "free": {
            "chat":      5,
            "vision":    0,
            "image_gen": 0,
            "proactive": 1,
        },
        "pro": {
            "chat":      8,
            "vision":    3,
            "image_gen": 2,
            "proactive": 1,
        },
        "institutional": {
            "chat":      20,
            "vision":    10,
            "image_gen": 5,
            "proactive": 3,
        },
    }
    return configs.get(tier, configs["free"])


def is_subscription_active(chat_id: int) -> bool:
    """Atalho: retorna True se o usuário tem tier > free."""
    return get_user_tier(chat_id) != "free"


def get_subscription_expiry(chat_id: int) -> Optional[str]:
    """
    Retorna a data de expiração da subscription ativa, ou None.

    Returns:
        ISO 8601 string ou None se não tem subscription ativa
    """
    try:
        from webdex_db import DB_LOCK, conn
        now_iso = datetime.now(timezone.utc).isoformat()

        with DB_LOCK:
            row = conn.execute(
                """SELECT expires_at FROM subscriptions
                   WHERE chat_id = ?
                     AND status = 'active'
                     AND (expires_at IS NULL OR expires_at > ?)
                   ORDER BY expires_at DESC LIMIT 1""",
                (chat_id, now_iso),
            ).fetchone()

        return row[0] if row else None

    except Exception as e:
        logger.warning("[subscription] get_subscription_expiry error (chat_id=%s): %s", chat_id, e)
        return None
