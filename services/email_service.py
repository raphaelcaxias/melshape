"""
Melshape — Serviço de email via Resend.
Gratuito: 3.000 emails/mês, 100/dia.
https://resend.com
"""
import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional

import streamlit as st

logger = logging.getLogger("Melshape.Email")

# ── Tokens de recuperação de senha (em memória / Supabase) ────────────────────
# Estrutura: { email: { "token": str, "expires_at": datetime } }
_RESET_TOKENS: dict = {}


# ─────────────────────────────────────────────────────────────────────────────
# CLIENTE RESEND
# ─────────────────────────────────────────────────────────────────────────────
def _get_resend_client():
    """Retorna cliente Resend se API key configurada, None caso contrário."""
    try:
        import resend
        api_key = st.secrets.get("RESEND_API_KEY", "")
        if not api_key:
            logger.warning("RESEND_API_KEY não configurado — emails desativados.")
            return None
        resend.api_key = api_key
        return resend
    except ImportError:
        logger.warning("Pacote 'resend' não instalado. Execute: pip install resend")
        return None


def _send(to: str, subject: str, html: str) -> bool:
    """Envia email via Resend. Retorna True se enviado."""
    client = _get_resend_client()
    if not client:
        logger.info(f"[MOCK EMAIL] Para: {to} | Assunto: {subject}")
        return True  # Simula sucesso em modo offline

    try:
        from_address = st.secrets.get("RESEND_FROM", "Melshape <noreply@melshape.com.br>")
        params = {
            "from": from_address,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        client.Emails.send(params)
        logger.info(f"Email enviado para {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar email para {to}: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATES HTML
# ─────────────────────────────────────────────────────────────────────────────
_BASE_STYLE = """
<div style="font-family:'DM Sans',Arial,sans-serif;max-width:560px;margin:0 auto;
background:#fafaf8;border-radius:16px;overflow:hidden;border:1px solid #e8e0d0;">
  <div style="background:linear-gradient(135deg,#C9A84C,#a8862e,#3D5A73);
  padding:2rem;text-align:center;">
    <div style="font-size:2rem;">🔥</div>
    <div style="font-family:Sora,Arial,sans-serif;font-weight:800;font-size:1.4rem;
    color:white;">Melshape</div>
    <div style="font-size:0.8rem;color:rgba(255,255,255,0.85);">
    Para quem está mudando de verdade.</div>
  </div>
  <div style="padding:1.75rem 2rem;">
    {content}
  </div>
  <div style="background:#f1ebe0;padding:1rem 2rem;text-align:center;
  font-size:0.72rem;color:#94a3b8;">
    © 2025 Melshape · <a href="https://melshape.com.br/privacidade"
    style="color:#C9A84C;">Política de Privacidade</a> ·
    <a href="https://melshape.com.br/termos" style="color:#C9A84C;">Termos de Uso</a>
  </div>
</div>
"""


def _wrap(content: str) -> str:
    return _BASE_STYLE.format(content=content)


# ─────────────────────────────────────────────────────────────────────────────
# EMAILS TRANSACIONAIS
# ─────────────────────────────────────────────────────────────────────────────
def send_welcome(to: str, name: str, trial_days: int = 10) -> bool:
    """Email de boas-vindas após cadastro."""
    content = f"""
    <h2 style="font-family:Sora,sans-serif;color:#1C1C1E;margin:0 0 0.75rem;">
      Olá, {name}! 🎉
    </h2>
    <p style="color:#4a4a4a;line-height:1.6;">
      Bem-vindo ao <b>Melshape</b>! Sua conta foi criada com sucesso e você tem
      <b>{trial_days} dias de acesso completo</b> ao plano Pro — sem cartão.
    </p>
    <div style="background:#fffbeb;border:1px solid #fcd34d;border-left:4px solid #C9A84C;
    border-radius:8px;padding:1rem;margin:1rem 0;">
      <b style="color:#78350f;">⏳ Seu trial expira em {trial_days} dias.</b><br>
      <span style="font-size:0.88rem;color:#92400e;">
        Aproveite para registrar refeições, monitorar peso e configurar seu perfil.
      </span>
    </div>
    <p style="color:#4a4a4a;line-height:1.6;">
      <b>3 coisas para fazer agora:</b><br>
      1️⃣ Complete o onboarding (2 minutos)<br>
      2️⃣ Registre sua primeira refeição<br>
      3️⃣ Configure seu modo de saúde (GLP-1, bariátrico, fitness ou emagrecimento)
    </p>
    <div style="text-align:center;margin:1.5rem 0;">
      <a href="https://melshape.com.br"
      style="background:linear-gradient(135deg,#C9A84C,#a8862e);color:#1C1C1E;
      padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600;
      font-family:Sora,sans-serif;">
        Acessar o Melshape →
      </a>
    </div>
    <p style="font-size:0.8rem;color:#94a3b8;">
      ⚕️ O Melshape é uma ferramenta de apoio nutricional e não substitui orientação médica.
    </p>
    """
    return _send(to, "🔥 Bem-vindo ao Melshape! Seu trial começou.", _wrap(content))


def send_password_reset(to: str, name: str, reset_url: str) -> bool:
    """Email de recuperação de senha com link temporário."""
    content = f"""
    <h2 style="font-family:Sora,sans-serif;color:#1C1C1E;margin:0 0 0.75rem;">
      Redefinir senha
    </h2>
    <p style="color:#4a4a4a;line-height:1.6;">
      Olá, <b>{name}</b>! Recebemos uma solicitação para redefinir a senha da sua conta.
    </p>
    <div style="text-align:center;margin:1.5rem 0;">
      <a href="{reset_url}"
      style="background:linear-gradient(135deg,#C9A84C,#a8862e);color:#1C1C1E;
      padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600;
      font-family:Sora,sans-serif;">
        Redefinir minha senha →
      </a>
    </div>
    <p style="color:#64748b;font-size:0.85rem;text-align:center;">
      ⏰ Este link expira em <b>15 minutos</b>.
    </p>
    <div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;
    padding:0.75rem;margin-top:1rem;">
      <span style="font-size:0.82rem;color:#7f1d1d;">
        🔒 Se você não solicitou a redefinição, ignore este email.
        Sua conta continua segura.
      </span>
    </div>
    """
    return _send(to, "🔒 Redefinição de senha — Melshape", _wrap(content))


def send_meal_reminder(to: str, name: str, streak: int = 0) -> bool:
    """Lembrete para registrar refeição (enviado se sem registro no dia)."""
    streak_msg = (
        f'<div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;'
        f'padding:0.65rem 1rem;margin:0.75rem 0;color:#92400e;font-size:0.88rem;">'
        f'🔥 Você tem uma sequência de <b>{streak} dias</b>! Não perca agora.</div>'
        if streak >= 3 else ""
    )
    content = f"""
    <h2 style="font-family:Sora,sans-serif;color:#1C1C1E;margin:0 0 0.75rem;">
      Oi, {name}! 👋
    </h2>
    <p style="color:#4a4a4a;line-height:1.6;">
      Você ainda não registrou refeições hoje. Manter a consistência é o que
      gera resultados reais.
    </p>
    {streak_msg}
    <div style="text-align:center;margin:1.25rem 0;">
      <a href="https://melshape.com.br"
      style="background:linear-gradient(135deg,#C9A84C,#a8862e);color:#1C1C1E;
      padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600;">
        Registrar agora →
      </a>
    </div>
    <p style="font-size:0.78rem;color:#94a3b8;text-align:center;">
      Para cancelar estes lembretes, acesse Perfil → Preferências.
    </p>
    """
    return _send(to, "🍽️ Lembre-se de registrar suas refeições hoje", _wrap(content))


def send_trial_expiring(to: str, name: str, days_remaining: int) -> bool:
    """Aviso quando trial está prestes a expirar."""
    urgency_color = "#dc2626" if days_remaining <= 1 else "#f59e0b"
    content = f"""
    <h2 style="font-family:Sora,sans-serif;color:#1C1C1E;margin:0 0 0.75rem;">
      Seu trial expira em {days_remaining} dia(s) ⏳
    </h2>
    <div style="background:{urgency_color}10;border:2px solid {urgency_color}40;
    border-radius:10px;padding:1rem;text-align:center;margin:1rem 0;">
      <span style="font-size:1.5rem;font-weight:700;color:{urgency_color};">
        {days_remaining} dia(s) restante(s)
      </span>
    </div>
    <p style="color:#4a4a4a;line-height:1.6;">
      Olá, <b>{name}</b>! Seu trial do Melshape Pro está quase acabando.
      Para continuar com acesso ilimitado, assine o plano Pro por apenas
      <b>R$19,90/mês</b>.
    </p>
    <div style="text-align:center;margin:1.5rem 0;">
      <a href="https://melshape.com.br"
      style="background:linear-gradient(135deg,#C9A84C,#a8862e);color:#1C1C1E;
      padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600;">
        Assinar o Melshape Pro →
      </a>
    </div>
    """
    return _send(to, f"⏰ Seu trial Melshape expira em {days_remaining} dia(s)", _wrap(content))


def send_streak_at_risk(to: str, name: str, streak: int) -> bool:
    """Aviso quando sequência está em risco (sem registro ontem)."""
    content = f"""
    <h2 style="font-family:Sora,sans-serif;color:#dc2626;margin:0 0 0.75rem;">
      🔥 Sua sequência de {streak} dias está em risco!
    </h2>
    <p style="color:#4a4a4a;line-height:1.6;">
      Olá, <b>{name}</b>! Você tem uma sequência incrível de <b>{streak} dias</b>,
      mas não registrou refeições ontem. Registre hoje para manter!
    </p>
    <div style="text-align:center;margin:1.5rem 0;">
      <a href="https://melshape.com.br"
      style="background:linear-gradient(135deg,#C9A84C,#a8862e);color:#1C1C1E;
      padding:0.75rem 2rem;border-radius:8px;text-decoration:none;font-weight:600;">
        Salvar minha sequência →
      </a>
    </div>
    """
    return _send(to, f"🔥 Sequência de {streak} dias em risco!", _wrap(content))


# ─────────────────────────────────────────────────────────────────────────────
# RECUPERAÇÃO DE SENHA
# ─────────────────────────────────────────────────────────────────────────────
def _generate_token(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def request_password_reset(email: str, name: str, base_url: str = "https://melshape.com.br") -> bool:
    """
    Gera token de reset, armazena e envia email.
    Retorna True se email foi enviado com sucesso.
    """
    token     = _generate_token()
    expires   = datetime.utcnow() + timedelta(minutes=15)

    # Armazena token (em produção use Supabase table password_resets)
    _RESET_TOKENS[email.lower()] = {
        "token":      token,
        "expires_at": expires,
        "name":       name,
    }

    reset_url = f"{base_url}/?reset_token={token}&email={email}"
    return send_password_reset(email, name, reset_url)


def validate_reset_token(email: str, token: str) -> bool:
    """Valida se token é válido e não expirou."""
    record = _RESET_TOKENS.get(email.lower())
    if not record:
        return False
    if record["token"] != token:
        return False
    if datetime.utcnow() > record["expires_at"]:
        _RESET_TOKENS.pop(email.lower(), None)
        return False
    return True


def consume_reset_token(email: str, token: str) -> bool:
    """Valida e consome token (remove após uso)."""
    if validate_reset_token(email, token):
        _RESET_TOKENS.pop(email.lower(), None)
        return True
    return False
