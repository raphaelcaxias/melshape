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
    sys.modules["views.shared"] = _real
except ImportError:
    # Se shared não existir, cria um módulo vazio
    import types
    _real = types.ModuleType("shared")
    sys.modules["shared"] = _real
    sys.modules["views.shared"] = _real

# Agora, tenta importar a função render do arquivo sidebar dentro do módulo shared
try:
    from shared.sidebar import render as sidebar
except ImportError:
    # Se o arquivo shared/sidebar.py não existe, define uma função placeholder
    def sidebar(*args, **kwargs):
        """Placeholder para a sidebar."""
        pass

# Exporta a função sidebar
__all__ = ["sidebar"]
