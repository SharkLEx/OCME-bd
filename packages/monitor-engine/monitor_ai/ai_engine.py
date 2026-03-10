# ==============================================================================
# monitor_ai/ai_engine.py — IA com contexto on-chain real
# OCME bd Monitor Engine — Story 7.4
# ==============================================================================
from __future__ import annotations

import logging
import re
import sqlite3
from typing import Any

import requests

from config import AI_API_KEY, AI_BASE_URL, OPENAI_MODEL
from monitor_ai.context_builder import build_user_context, format_context_for_prompt

logger = logging.getLogger('monitor.ai.engine')

_SYSTEM_BASE = (
    'Você é a IA oficial do OCME bd — sistema de monitoramento DeFi na Polygon. '
    'Responda 100% em PT-BR. Seja direto, claro e técnico quando necessário. '
    'NUNCA peça dados sensíveis (seed phrase, private key, mnemônico). '
    'Se não souber algo, diga claramente.'
)

_SYSTEM_WITH_DATA = (
    _SYSTEM_BASE + '\n\n'
    'Você TEM ACESSO aos dados reais do usuário abaixo. '
    'Use-os para responder com precisão. Não cite fontes externas — esses são dados do sistema.\n\n'
    '{context}'
)

_MD_CLEAN_RE = re.compile(r'(\*\*|\*|`|^#{1,6}\s*)', re.M)


def _pretty(s: str) -> str:
    '''Limpa markdown para texto amigável no Telegram.'''
    if not s:
        return ''
    s = s.replace('\r\n', '\n')
    s = _MD_CLEAN_RE.sub('', s)
    s = re.sub(r'^\s*[-–•]\s+', '• ', s, flags=re.M)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def _call_api(system: str, user_text: str, timeout: int = 45) -> str:
    '''Chama OpenAI ou OpenRouter e retorna texto da resposta.'''
    if not AI_API_KEY:
        return (
            '⚙️ IA não configurada.\n\n'
            'Adicione no .env:\nOPENAI_API_KEY=sua_chave\nOPENAI_MODEL=gpt-4.1-nano'
        )

    headers = {
        'Authorization': f'Bearer {AI_API_KEY}',
        'Content-Type': 'application/json',
    }

    # Tenta endpoint /chat/completions (OpenRouter + OpenAI novo)
    payload: dict[str, Any] = {
        'model': OPENAI_MODEL,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user',   'content': user_text},
        ],
        'max_completion_tokens': 800,
    }

    try:
        url = f'{AI_BASE_URL}/chat/completions'
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        rj = resp.json() if resp.content else {}

        if resp.status_code >= 400:
            err = ''
            if isinstance(rj.get('error'), dict):
                err = rj['error'].get('message', '')
            logger.warning('IA API erro %d: %s', resp.status_code, err)
            return f'IA erro ({resp.status_code}). {err}'.strip()

        # Extrai texto da resposta
        choices = rj.get('choices', [])
        if choices:
            text = (choices[0].get('message') or {}).get('content') or ''
            return _pretty(text) or 'IA não retornou texto.'

        # Fallback para API /responses (OpenAI legado)
        output = rj.get('output_text') or ''
        if not output:
            for item in (rj.get('output') or []):
                for c in (item.get('content') or []):
                    if c.get('type') in ('output_text', 'text') and c.get('text'):
                        output += c['text']
        return _pretty(output) if output else 'IA não retornou texto. Tente novamente.'

    except requests.Timeout:
        return '⏳ IA demorou muito. Tente novamente.'
    except Exception as exc:
        logger.error('_call_api falhou: %s', exc)
        return f'IA falhou: {exc}'


def answer(
    user_text: str,
    conn: sqlite3.Connection | None = None,
    wallet: str | None = None,
    chat_id: int | None = None,
    period_hours: int = 24,
    mode: str = 'community',
) -> str:
    '''
    Responde à pergunta do usuário.
    Se wallet fornecida, injeta contexto real no system prompt.
    '''
    if conn and wallet:
        try:
            ctx = build_user_context(conn, wallet, chat_id=chat_id, period_hours=period_hours)
            ctx_text = format_context_for_prompt(ctx)
            system = _SYSTEM_WITH_DATA.format(context=ctx_text)
        except Exception as exc:
            logger.warning('Falha ao construir contexto: %s', exc)
            system = _SYSTEM_BASE
    else:
        system = _SYSTEM_BASE

    if mode == 'dev':
        system += '\nModo DEV: pode usar termos técnicos avançados sem simplificações.'

    return _call_api(system, user_text)


def answer_inactivity_diagnostic(
    conn: sqlite3.Connection,
    wallet: str,
    minutes: float,
    sigma: float,
    chat_id: int | None = None,
) -> str:
    '''Diagnóstico específico de inatividade com contexto histórico.'''
    ctx = build_user_context(conn, wallet, chat_id=chat_id, period_hours=720)  # 30d
    ctx_text = format_context_for_prompt(ctx)

    prompt = (
        f'O sistema ficou inativo há {minutes:.0f} minutos ({sigma:.1f}σ acima da média histórica). '
        f'Com base nos dados abaixo, explique a causa provável e o que o usuário deve fazer:\n\n'
        f'{ctx_text}\n\n'
        f'Responda em 3-5 linhas, em português, de forma direta e acionável.'
    )

    system = _SYSTEM_WITH_DATA.format(context=ctx_text)
    return _call_api(system, prompt, timeout=30)
