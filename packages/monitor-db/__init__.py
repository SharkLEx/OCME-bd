"""monitor-db — Schema versionado e queries tipadas para o OCME."""
from .migrator import Migrator
from . import queries

__all__ = ["Migrator", "queries"]
