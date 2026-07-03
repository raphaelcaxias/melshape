"""
views.auth — Alias para o pacote ``auth`` (telas de autenticação).

Este módulo é um proxy: qualquer import de ``views.auth.X``
resolve para ``auth.X``.

Módulos disponíveis
-------------------
landing         Página inicial pública                     (render)
login           Tela de login                              (render)
register        Cadastro de paciente e profissional        (render)
forgot_password Recuperação / reset de senha               (render)
"""

import sys
import importlib

# Garante que views.auth.X → auth.X para qualquer submódulo
_real = importlib.import_module("auth")
sys.modules.setdefault("views.auth", _real)

# Re-exporta os módulos principais para que
# ``from views.auth import login`` funcione diretamente
from auth import forgot_password, landing, login, register  # noqa: E402

__all__ = ["landing", "login", "register", "forgot_password"]
