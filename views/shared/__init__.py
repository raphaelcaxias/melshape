"""
views.shared — Alias para o pacote ``shared``.
"""

import sys
import importlib

# Força a importação do módulo shared real, independente de onde esteja
try:
    # Tenta importar o módulo shared (que fica na raiz)
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
    # Se o módulo shared existe, importa sidebar.render
    from shared.sidebar import render as sidebar
except ImportError:
    # Se o arquivo shared/sidebar.py não existe, define uma função placeholder
    def sidebar(*args, **kwargs):
        """Placeholder para a sidebar."""
        pass

# Exporta a função sidebar
__all__ = ["sidebar"]
