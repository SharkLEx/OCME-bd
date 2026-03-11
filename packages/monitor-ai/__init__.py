"""monitor-ai — IA Contextual do OCME Engine.

AIEngine: responde perguntas com dados reais on-chain do usuário.
ContextBuilder: agrega capital, trades, subcontas, inatividade do DB.

Standalone: sem dependência do monolito webdex_*.py.
"""
from .ai_engine import AIEngine, _pretty_ai_text
from .context_builder import ContextBuilder

__all__ = ["AIEngine", "ContextBuilder", "_pretty_ai_text"]
