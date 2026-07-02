"""
Melshape — Validadores de Autenticação.

Usados por login.py, register.py e forgot_password.py via:
    from views.auth.forgot_password import EmailValidator, PasswordValidator

Os validadores vivem aqui para facilitar import direto. O forgot_password.py
re-exporta ambas as classes para compatibilidade com os imports existentes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

_EMAIL_REGEX: str = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
_EMAIL_MAX_LENGTH: int = 254
_MIN_PASSWORD_LENGTH: int = 8
_MAX_PASSWORD_LENGTH: int = 128


# ─────────────────────────────────────────────────────────────────────────────
# RESULTADO
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ValidationResult:
    """Resultado de uma validação."""
    is_valid: bool
    error_message: str | None = None

    @classmethod
    def valid(cls) -> "ValidationResult":
        return cls(is_valid=True)

    @classmethod
    def invalid(cls, message: str) -> "ValidationResult":
        return cls(is_valid=False, error_message=message)


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATORS
# ─────────────────────────────────────────────────────────────────────────────

class EmailValidator:
    """Validador de endereço de e-mail."""

    @staticmethod
    def validate(email: str) -> ValidationResult:
        """Valida formato de e-mail.

        Args:
            email: Endereço a ser validado.

        Returns:
            ValidationResult com is_valid e error_message.

        Example:
            >>> result = EmailValidator.validate("user@example.com")
            >>> result.is_valid
            True
        """
        if not email or not email.strip():
            return ValidationResult.invalid("E-mail não pode estar vazio.")

        email = email.strip()

        if len(email) > _EMAIL_MAX_LENGTH:
            return ValidationResult.invalid(
                f"E-mail muito longo (máximo {_EMAIL_MAX_LENGTH} caracteres)."
            )

        if not re.match(_EMAIL_REGEX, email):
            return ValidationResult.invalid(
                "E-mail inválido. Use o formato: nome@dominio.com"
            )

        return ValidationResult.valid()


class PasswordValidator:
    """Validador de senha com confirmação."""

    @staticmethod
    def validate(password: str, confirm_password: str) -> ValidationResult:
        """Valida nova senha e confirmação.

        Args:
            password: Senha desejada.
            confirm_password: Confirmação da senha.

        Returns:
            ValidationResult com is_valid e error_message.
        """
        if not password:
            return ValidationResult.invalid("Senha não pode estar vazia.")

        if len(password) < _MIN_PASSWORD_LENGTH:
            return ValidationResult.invalid(
                f"A senha deve ter no mínimo {_MIN_PASSWORD_LENGTH} caracteres."
            )

        if len(password) > _MAX_PASSWORD_LENGTH:
            return ValidationResult.invalid(
                f"A senha é muito longa (máximo {_MAX_PASSWORD_LENGTH} caracteres)."
            )

        if not any(c.isupper() for c in password):
            return ValidationResult.invalid(
                "A senha deve conter pelo menos uma letra maiúscula."
            )

        if not any(c.islower() for c in password):
            return ValidationResult.invalid(
                "A senha deve conter pelo menos uma letra minúscula."
            )

        if not any(c.isdigit() for c in password):
            return ValidationResult.invalid(
                "A senha deve conter pelo menos um número."
            )

        if password != confirm_password:
            return ValidationResult.invalid("As senhas não coincidem.")

        return ValidationResult.valid()
