"""Melshape — Segurança: hash, validação, LGPD."""
import hashlib
import re
import logging
from datetime import datetime

logger = logging.getLogger("Melshape.Security")


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    return hash_password(plain) == hashed


def validate_email(email: str) -> tuple:
    if not email or not email.strip():
        return False, "Email é obrigatório."
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email.strip()):
        return False, "Email inválido. Use o formato: seu@email.com"
    return True, ""


def validate_password(password: str) -> tuple:
    if not password:
        return False, "Senha é obrigatória."
    if len(password) < 6:
        return False, "A senha deve ter pelo menos 6 caracteres."
    return True, ""


def validate_name(name: str) -> tuple:
    if not name or len(name.strip()) < 2:
        return False, "Nome deve ter pelo menos 2 caracteres."
    return True, ""


def sanitize_string(value: str, max_length: int = 500) -> str:
    if not value:
        return ""
    return str(value).strip()[:max_length]


def lgpd_consent_text() -> str:
    return (
        "Ao criar sua conta, você concorda com os "
        "[Termos de Uso](https://melshape.com.br/termos) e a "
        "[Política de Privacidade](https://melshape.com.br/privacidade). "
        "Seus dados de saúde são protegidos conforme a LGPD."
    )


def record_lgpd_consent(email: str) -> str:
    ts = datetime.utcnow().isoformat()
    logger.info(f"LGPD aceite: {email} em {ts}")
    return ts
