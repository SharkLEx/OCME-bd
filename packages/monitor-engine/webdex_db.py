# compat stub — Story 7.3 (Epic 7: modularização monolito)
# Conteúdo movido para core/db.py
# Remover após Epic 7 completo e todos os consumers migrados
# __dict__.update exporta TODOS os nomes incluindo underscore-prefixed
import core.db as _mod
import sys as _sys
_this = _sys.modules[__name__]
for _k, _v in vars(_mod).items():
    setattr(_this, _k, _v)
del _mod, _sys, _this, _k, _v
