"""Melshape — Validadores de entrada."""
from core.security import validate_email, validate_password, validate_name


def validate_registration(name: str, email: str,
                           password: str, lgpd_accepted: bool) -> list:
    errors = []
    ok, msg = validate_name(name)
    if not ok:
        errors.append(msg)
    ok, msg = validate_email(email)
    if not ok:
        errors.append(msg)
    ok, msg = validate_password(password)
    if not ok:
        errors.append(msg)
    if not lgpd_accepted:
        errors.append("Aceite os Termos de Uso e Política de Privacidade.")
    return errors


def validate_weight(weight: float) -> tuple:
    if weight < 30 or weight > 300:
        return False, "Peso deve estar entre 30 e 300 kg."
    return True, ""


def validate_height(height: int) -> tuple:
    if height < 100 or height > 250:
        return False, "Altura deve estar entre 100 e 250 cm."
    return True, ""


def validate_age(age: int) -> tuple:
    if age < 12 or age > 110:
        return False, "Idade deve estar entre 12 e 110 anos."
    return True, ""
