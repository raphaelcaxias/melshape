"""
Melshape — Segurança e LGPD.

Gerencia hash de senhas, validações, tokens de reset e consentimento LGPD.
Todas as operações sensíveis de segurança são centralizadas aqui.

Princípios:
- Hash de senha com PBKDF2-HMAC-SHA256 (260.000 iterações)
- Salt de 32 bytes (64 caracteres hex)
- Comparação em tempo constante (hmac.compare_digest)
- Tokens seguros para reset de senha (secrets.token_urlsafe)
- Consentimento LGPD com timestamp auditável
- Validação de email com regex robusto (RFC 5322 simplificado)
- Validação de senha com força mínima (OWASP guidelines)
- Timezone-aware datetimes (evita datetime.utcnow deprecado)

Segurança:
- OWASP Password Storage Cheat Sheet 2025
- NIST SP 800-63B (Digital Identity Guidelines)
- LGPD Lei 13.709/2018 (Art. 7º, 8º e 18)
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final, Protocol, runtime_checkable

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES DE SEGURANÇA
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SecurityConstants:
    """
    Constantes de segurança do sistema.
    
    Baseado em:
    - OWASP Password Storage Cheat Sheet (2025)
    - NIST SP 800-132 (Recommendation for Password-Based Key Derivation)
    """
    # PBKDF2 configuration
    salt_size: Final[int] = 32  # 32 bytes = 256 bits (NIST recommendation)
    iterations: Final[int] = 260_000  # OWASP 2025 recommendation for SHA256
    hash_algo: Final[str] = "sha256"  # SHA-256 (FIPS 180-4 approved)
    
    # Token configuration
    token_length: Final[int] = 32  # 32 bytes = 256 bits of entropy
    token_expiry_minutes: Final[int] = 15  # Short-lived for security
    
    # Password policy (OWASP minimum requirements)
    min_password_length: Final[int] = 8  # Increased from 6 (OWASP 2025)
    require_uppercase: Final[bool] = False  # Optional: complexity requirements
    require_number: Final[bool] = True
    require_special: Final[bool] = False


SECURITY: Final = SecurityConstants()

# Aliases para compatibilidade
SALT_SIZE: Final[int] = SECURITY.salt_size
ITERATIONS: Final[int] = SECURITY.iterations
HASH_ALGO: Final[str] = SECURITY.hash_algo
TOKEN_LENGTH: Final[int] = SECURITY.token_length
TOKEN_EXPIRY_MINUTES: Final[int] = SECURITY.token_expiry_minutes
MIN_PASSWORD_LENGTH: Final[int] = SECURITY.min_password_length

# ─────────────────────────────────────────────────────────────────────────────
# RESULTADOS DE VALIDAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ValidationResult:
    """
    Resultado de uma validação.
    
    Attributes:
        is_valid: True se a validação passou
        message: Mensagem de erro (vazia se válido)
        field: Campo validado (opcional)
    """
    is_valid: bool
    message: str = ""
    field: str = ""
    
    def __bool__(self) -> bool:
        """Permite usar ValidationResult em contextos booleanos."""
        return self.is_valid


# ─────────────────────────────────────────────────────────────────────────────
# HASH DE SENHA (PBKDF2 com 260.000 iterações)
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """
    Gera hash seguro da senha com PBKDF2-HMAC-SHA256.
    
    Args:
        password: Senha em texto puro
        
    Returns:
        String no formato: salt_hex:hash_hex
        
    Exemplo:
        >>> hash_password("minha_senha")
        "a1b2c3d4e5f6...:7890abcdef..."
    
    Segurança:
        - Salt de 32 bytes (256 bits) gerado com os.urandom (CSPRNG)
        - 260.000 iterações (OWASP 2025 recommendation)
        - SHA-256 (FIPS 180-4 approved)
        - Formato armazenável: salt_hex:hash_hex
        
    Notas:
        - PBKDF2 é resistente a ataques de GPU/ASIC
        - Salt único por senha previne ataques de rainbow table
        - Alto número de iterações aumenta custo computacional
    """
    if not password:
        raise ValueError("Password cannot be empty")
    
    # CSPRNG (Cryptographically Secure Pseudo-Random Number Generator)
    salt = os.urandom(SALT_SIZE)
    
    # PBKDF2-HMAC-SHA256
    digest = hashlib.pbkdf2_hmac(
        HASH_ALGO,
        password.encode("utf-8"),
        salt,
        ITERATIONS,
        dklen=None,  # Default: hash length (32 bytes for SHA256)
    )
    
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verifica se a senha confere com o hash armazenado.
    
    Args:
        password: Senha em texto puro
        stored_hash: Hash armazenado (salt:hash)
        
    Returns:
        True se a senha confere, False caso contrário
        
    Segurança:
        - Usa hmac.compare_digest (tempo constante)
        - Protege contra timing attacks
        - Valida formato do hash antes de processar
        
    Exemplo:
        >>> stored = hash_password("minha_senha")
        >>> verify_password("minha_senha", stored)
        True
        >>> verify_password("senha_errada", stored)
        False
    """
    if not password or not stored_hash:
        return False
    
    if ":" not in stored_hash:
        return False
    
    try:
        salt_hex, hash_hex = stored_hash.split(":", 1)
        
        # Valida formato hex
        if len(salt_hex) != SALT_SIZE * 2 or len(hash_hex) != 64:
            return False
        
        salt = bytes.fromhex(salt_hex)
        
        # Recomputa hash com o mesmo salt
        digest = hashlib.pbkdf2_hmac(
            HASH_ALGO,
            password.encode("utf-8"),
            salt,
            ITERATIONS,
        )
        
        # Comparação em tempo constante (previne timing attacks)
        return hmac.compare_digest(digest.hex(), hash_hex)
        
    except (ValueError, TypeError, AttributeError):
        # Falha silenciosa por segurança (não revela formato do hash)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# TOKENS DE RESET DE SENHA
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ResetToken:
    """
    Token de reset de senha.
    
    Attributes:
        token: Token seguro (URL-safe base64)
        email: Email do usuário (lowercase)
        expires_at: Timestamp de expiração (timezone-aware UTC)
        created_at: Timestamp de criação (timezone-aware UTC)
    """
    token: str
    email: str
    expires_at: datetime
    created_at: datetime = None
    
    def __post_init__(self):
        """Define created_at se não fornecido."""
        if self.created_at is None:
            object.__setattr__(self, "created_at", datetime.now(timezone.utc))
    
    def is_expired(self) -> bool:
        """Verifica se o token expirou."""
        return datetime.now(timezone.utc) > self.expires_at


@runtime_checkable
class TokenStoreProtocol(Protocol):
    """
    Protocol para armazenamento de tokens.
    
    Permite diferentes implementações:
    - InMemoryTokenStore (desenvolvimento)
    - DatabaseTokenStore (produção)
    - RedisTokenStore (alta performance)
    """
    
    def create(self, email: str) -> ResetToken:
        """Cria um novo token de reset."""
        ...
    
    def validate(self, email: str, token: str) -> bool:
        """Valida um token de reset."""
        ...
    
    def consume(self, email: str, token: str) -> bool:
        """Consome um token (valida e remove)."""
        ...
    
    def clear_expired(self) -> int:
        """Remove todos os tokens expirados."""
        ...


class InMemoryTokenStore:
    """
    Armazenamento em memória para tokens de reset.
    
    ⚠️ AVISO DE SEGURANÇA:
    Esta implementação é APENAS para desenvolvimento/demo.
    Em produção, use DatabaseTokenStore ou RedisTokenStore.
    
    Limitações:
    - Tokens são perdidos ao reiniciar a aplicação
    - Não funciona em ambientes multi-instância
    - Sem persistência ou auditoria
    """
    
    def __init__(self) -> None:
        self._tokens: dict[str, ResetToken] = {}
    
    def create(self, email: str) -> ResetToken:
        """
        Cria um novo token de reset.
        
        Args:
            email: Email do usuário
            
        Returns:
            ResetToken com token e expiração
            
        Segurança:
            - Token gerado com secrets.token_urlsafe (CSPRNG)
            - 32 bytes de entropia (256 bits)
            - Expira em 15 minutos (curta duração)
        """
        # CSPRNG para geração de token
        token = secrets.token_urlsafe(TOKEN_LENGTH)
        
        # Timezone-aware datetime (evita datetime.utcnow deprecado)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=TOKEN_EXPIRY_MINUTES)
        
        reset_token = ResetToken(
            token=token,
            email=email.lower().strip(),
            expires_at=expires_at,
            created_at=now,
        )
        
        self._tokens[email.lower().strip()] = reset_token
        return reset_token
    
    def validate(self, email: str, token: str) -> bool:
        """
        Valida um token de reset.
        
        Args:
            email: Email do usuário
            token: Token a ser validado
            
        Returns:
            True se o token é válido e não expirou
            
        Segurança:
            - Comparação em tempo constante (hmac.compare_digest)
            - Limpeza automática de tokens expirados
        """
        key = email.lower().strip()
        stored = self._tokens.get(key)
        
        if not stored:
            return False
        
        # Comparação em tempo constante
        if not hmac.compare_digest(stored.token, token):
            return False
        
        # Verifica expiração
        if stored.is_expired():
            self._tokens.pop(key, None)  # Limpa token expirado
            return False
        
        return True
    
    def consume(self, email: str, token: str) -> bool:
        """
        Consome um token (valida e remove).
        
        Args:
            email: Email do usuário
            token: Token a ser consumido
            
        Returns:
            True se o token foi consumido com sucesso
            
        Segurança:
            - Token só é consumido se válido
            - Previne reuso de tokens (one-time use)
        """
        if self.validate(email, token):
            self._tokens.pop(email.lower().strip(), None)
            return True
        return False
    
    def clear_expired(self) -> int:
        """
        Remove todos os tokens expirados.
        
        Returns:
            Número de tokens removidos
        """
        now = datetime.now(timezone.utc)
        expired = [
            key for key, stored in self._tokens.items()
            if stored.is_expired()
        ]
        for key in expired:
            self._tokens.pop(key, None)
        return len(expired)


# Instância global do TokenStore (InMemory para demo)
# Em produção, substitua por DatabaseTokenStore
token_store: TokenStoreProtocol = InMemoryTokenStore()


def request_password_reset(email: str, name: str, base_url: str) -> str:
    """
    Gera token de reset e retorna a URL de redefinição.
    
    Args:
        email: Email do usuário
        name: Nome do usuário (usado no template do email)
        base_url: URL base da aplicação
        
    Returns:
        URL de redefinição de senha
        
    Exemplo:
        >>> request_password_reset("user@example.com", "João", "https://melshape.com.br")
        "https://melshape.com.br/?reset_token=abc123...&email=user@example.com"
    """
    reset_token = token_store.create(email)
    
    # URL encoding para segurança (previne injection)
    from urllib.parse import quote
    encoded_email = quote(email.lower().strip())
    
    return f"{base_url}/?reset_token={reset_token.token}&email={encoded_email}"


def validate_reset_token(email: str, token: str) -> bool:
    """Valida um token de reset."""
    return token_store.validate(email, token)


def consume_reset_token(email: str, token: str) -> bool:
    """Consome um token de reset (valida e remove)."""
    return token_store.consume(email, token)


# ─────────────────────────────────────────────────────────────────────────────
# VALIDAÇÕES
# ─────────────────────────────────────────────────────────────────────────────

# Regex para validação de email (RFC 5322 simplificado)
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
)


def validate_email(email: str) -> ValidationResult:
    """
    Valida formato de email com regex robusto (RFC 5322 simplificado).
    
    Args:
        email: Email a ser validado
        
    Returns:
        ValidationResult com is_valid e message
        
    Exemplos:
        >>> validate_email("user@example.com")
        ValidationResult(is_valid=True, message="")
        >>> validate_email("invalid")
        ValidationResult(is_valid=False, message="Email inválido.")
        
    Notas:
        - Aceita a maioria dos emails válidos
        - Rejeita emails claramente inválidos
        - Não verifica existência do domínio (requer DNS lookup)
    """
    if not email or not email.strip():
        return ValidationResult(False, "Email é obrigatório.", "email")
    
    email_clean = email.strip().lower()
    
    if not EMAIL_REGEX.match(email_clean):
        return ValidationResult(
            False, 
            "Email inválido. Use formato: nome@dominio.com",
            "email"
        )
    
    return ValidationResult(True, "", "email")


def validate_password(password: str) -> ValidationResult:
    """
    Valida força mínima da senha (OWASP guidelines).
    
    Args:
        password: Senha a ser validada
        
    Returns:
        ValidationResult com is_valid e message
        
    Exemplos:
        >>> validate_password("senha123")
        ValidationResult(is_valid=True, message="")
        >>> validate_password("123")
        ValidationResult(is_valid=False, message="Senha deve ter no mínimo 8 caracteres.")
        
    Política (OWASP 2025):
        - Mínimo 8 caracteres
        - Pelo menos uma letra
        - Pelo menos um número
        - (Opcional) Maiúsculas e caracteres especiais
    """
    if not password:
        return ValidationResult(False, "Senha é obrigatória.", "password")
    
    if len(password) < MIN_PASSWORD_LENGTH:
        return ValidationResult(
            False,
            f"Senha deve ter no mínimo {MIN_PASSWORD_LENGTH} caracteres.",
            "password"
        )
    
    # Validações de complexidade
    has_letter = any(c.isalpha() for c in password)
    has_number = any(c.isdigit() for c in password)
    
    if not has_letter:
        return ValidationResult(
            False,
            "Senha deve conter pelo menos uma letra.",
            "password"
        )
    
    if SECURITY.require_number and not has_number:
        return ValidationResult(
            False,
            "Senha deve conter pelo menos um número.",
            "password"
        )
    
    if SECURITY.require_uppercase and not any(c.isupper() for c in password):
        return ValidationResult(
            False,
            "Senha deve conter pelo menos uma letra maiúscula.",
            "password"
        )
    
    if SECURITY.require_special and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return ValidationResult(
            False,
            "Senha deve conter pelo menos um caractere especial.",
            "password"
        )
    
    return ValidationResult(True, "", "password")


def validate_password_confirm(password: str, confirm: str) -> ValidationResult:
    """
    Valida se a senha e a confirmação são iguais e atendem aos critérios.
    
    Args:
        password: Senha
        confirm: Confirmação da senha
        
    Returns:
        ValidationResult com is_valid e message
    """
    if password != confirm:
        return ValidationResult(
            False,
            "As senhas não coincidem.",
            "password_confirm"
        )
    
    return validate_password(password)


# ─────────────────────────────────────────────────────────────────────────────
# LGPD (Lei Geral de Proteção de Dados)
# ─────────────────────────────────────────────────────────────────────────────

def lgpd_consent_text() -> str:
    """
    Retorna o texto padrão de consentimento LGPD.
    
    Returns:
        Texto de consentimento formatado em Markdown
        
    Base Legal:
        - LGPD Lei 13.709/2018 (Art. 7º, 8º e 18)
        - Direitos do titular de dados
    """
    return (
        "_Ao criar sua conta, você concorda com os "
        "[Termos de Uso](https://melshape.com.br/termos) e a "
        "[Política de Privacidade](https://melshape.com.br/privacidade) "
        "do Melshape, incluindo o tratamento dos seus dados de saúde "
        "conforme a Lei Geral de Proteção de Dados (LGPD — Lei 13.709/2018)._\n\n"
        "**Seus direitos (Art. 18 LGPD):**\n"
        "- Acessar seus dados a qualquer momento\n"
        "- Solicitar correção ou exclusão\n"
        "- Revogar o consentimento a qualquer momento\n"
        "- Portabilidade dos dados\n\n"
        "**Responsável:** Melshape · suporte@melshape.com.br"
    )


def record_lgpd_consent(email: str) -> str:
    """
    Registra o timestamp do consentimento LGPD (timezone-aware UTC).
    
    Args:
        email: Email do usuário
        
    Returns:
        Timestamp ISO 8601 do consentimento (UTC)
        
    Exemplo:
        >>> record_lgpd_consent("user@example.com")
        "2026-06-22T14:30:00+00:00"
        
    Notas:
        - Timestamp em UTC para consistência global
        - Formato ISO 8601 para interoperabilidade
        - Deve ser armazenado no banco para auditoria
    """
    # Timezone-aware datetime (UTC)
    now = datetime.now(timezone.utc)
    return now.isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# UTILITÁRIOS DE SEGURANÇA
# ─────────────────────────────────────────────────────────────────────────────

def generate_secure_token(length: int = 32) -> str:
    """
    Gera um token seguro usando CSPRNG.
    
    Args:
        length: Tamanho do token em bytes (padrão: 32 = 256 bits)
        
    Returns:
        Token URL-safe base64
        
    Exemplo:
        >>> generate_secure_token(32)
        "abc123def456..."
    """
    return secrets.token_urlsafe(length)


def sanitize_input(text: str) -> str:
    """
    Sanitiza input do usuário para prevenir XSS e injection.
    
    Args:
        text: Texto a ser sanitizado
        
    Returns:
        Texto sanitizado
        
    Notas:
        - Remove caracteres de controle
        - Strip de espaços em branco
        - Não substitui HTML escaping (faça isso na renderização)
    """
    if not text:
        return ""
    
    # Remove caracteres de controle (ASCII 0-31 e 127)
    sanitized = "".join(
        char for char in text
        if ord(char) >= 32 and ord(char) != 127
    )
    
    return sanitized.strip()


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTS PÚBLICOS
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    # Hash de senha
    "hash_password",
    "verify_password",
    # Tokens
    "ResetToken",
    "TokenStoreProtocol",
    "InMemoryTokenStore",
    "token_store",
    "request_password_reset",
    "validate_reset_token",
    "consume_reset_token",
    # Validações
    "ValidationResult",
    "validate_email",
    "validate_password",
    "validate_password_confirm",
    # LGPD
    "lgpd_consent_text",
    "record_lgpd_consent",
    # Utilitários
    "generate_secure_token",
    "sanitize_input",
    # Constantes
    "SECURITY",
    "SALT_SIZE",
    "ITERATIONS",
    "HASH_ALGO",
    "TOKEN_LENGTH",
    "TOKEN_EXPIRY_MINUTES",
    "MIN_PASSWORD_LENGTH",
]
