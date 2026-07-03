"""
views.shared — Alias para o pacote ``shared`` (elementos compartilhados).

Módulos disponíveis
-------------------
sidebar         Sidebar de navegação (render)
sidebar_nav     Lógica de itens de menu e navegação
"""

import sys
import importlib

# Tenta importar o módulo shared real
try:
    _real = importlib.import_module("shared")
    sys.modules.setdefault("views.shared", _real)
except ImportError:
    # Fallback: cria um módulo shared vazio para evitar erro
    import types
    _real = types.ModuleType("shared")
    sys.modules["shared"] = _real
    sys.modules["views.shared"] = _real

# Importa a função render do módulo sidebar e a expõe como 'sidebar'
try:
    from shared.sidebar import render as sidebar
except ImportError:
    # Fallback: define uma função placeholder
    def sidebar(*args, **kwargs):
        pass

__all__ = ["sidebar"]
