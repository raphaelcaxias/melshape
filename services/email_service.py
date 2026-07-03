"""
Melshape — Email Service.

Serviço de email via Resend (3k/mês grátis) com mock automático
quando RESEND_API_KEY não está configurado.

Princípios:
- Fallback automático: Resend → Mock (logs)
- Tokens seguros: secrets.token_urlsafe para reset de senha
- Templates acolhedores: design consistente com a marca
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para todas as entidades

Arquitetura:
    EmailService
    ├── Client Management
    │   ├── _get_client() -> Resend | None
    │   └── is_configured() -> bool
    ├── Send
    │   ├── send(to, subject, html) -> EmailResult
    │   ├── send_with_template(to, subject, template, context) -> EmailResult
    │   └── send_template_email(to, template_type, context) -> EmailResult
    ├── Templates
    │   ├── render_template(template_type, context) -> str
    │   ├── get_available_templates() -> list[EmailTemplate]
    │   └── preview_template(template_type, context) -> EmailPreview
    ├── Specific Emails
    │   ├── send_welcome(to, name, trial_days) -> EmailResult
    │   ├── send_password_reset(to, name, reset_url) -> EmailResult
    │   ├── send_meal_reminder(to, name, streak) -> EmailResult
    │   ├── send_streak_at_risk(to, name, streak) -> EmailResult
    │   ├── send_trial_expiring(to, name, days_remaining) -> EmailResult
    │   └── send_clinical_action(to, name, titulo, mensagem) -> EmailResult
    ├── Tokens
    │   ├── request_password_reset(email, name, base_url) -> str
    │   ├── validate_reset_token(email, token) -> bool
    │   ├── consume_reset_token(email, token) -> bool
    │   └── clear_expired_tokens() -> int
    └── Utilities
        ├── _wrap(content, tagline) -> str
        ├── _btn(url, label) -> str
        └── _gen_token() -> str
"""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable

import streamlit as st

import config

logger = logging.getLogger("Melshape.Email")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Token configuration
_TOKEN_LENGTH: int = 32
_TOKEN_EXPIRY_MINUTES: int = 15

# Email configuration
_DEFAULT_FROM: str = "Melshape <noreply@melshape.com.br>"
_DEFAULT_APP_URL: str = "https://melshape.com.br"
_PRIVACY_URL: str = "https://melshape.com.br/privacidade"
_TERMS_URL: str = "https://melshape.com.br/termos"

# Email templates base
_BASE_TEMPLATE: str = """
<div style="font-family:'DM Sans',Arial,sans-serif;max-width:560px;margin:0 auto;
background:#fafaf8;border-radius:16px;overflow:hidden;border:1px solid #e8e0d0;">
  <div style="background:linear-gradient(135deg,#C9A84C,#a8862e,#3D5A73);
  padding:2rem;text-align:center;">
    <div style="font-size:2rem;">🔥</div>
    <div style="font-family:Sora,Arial,sans-serif;font-weight:800;
    font-size:1.4rem;color:white;">Melshape</div>
    <div style="font-size:0.8rem;color:rgba(255,255,255,0.85);">
    {tagline}</div>
  </div>
  <div style="padding:1.75rem 2rem;">{content}</div>
  <div style="background:#f1ebe0;padding:1rem 2rem;text-align:center;
  font-size:0.72rem;color:#94a3b8;">
    © {year} Melshape ·
    <a href="{privacy_url}" style="color:#C9A84C;">Privacidade</a> ·
    <a href="{terms_url}" style="color:#C9A84C;">Termos</a>
  </div>
</div>
"""

_BTN_TEMPLATE: str = """
<a href="{url}" style="background:linear-gradient(135deg,#C9A84C,#a8862e);
color:#1C1C1E;padding:0.75rem 2rem;border-radius:8px;
text-decoration:none;font-weight:600;font-family:Sora,sans-serif;
display:inline-block;">{label}</a>
"""


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class EmailTemplateType(str, Enum):
    """Tipos de templates de email disponíveis."""
    WELCOME = "welcome"
    PASSWORD_RESET = "password_reset"
    MEAL_REMINDER = "meal_reminder"
    STREAK_RISK = "streak_risk"
    TRIAL_EXPIRING = "trial_expiring"
    CLINICAL_ACTION = "clinical_action"
    
    @property
    def label(self) -> str:
        """Retorna label do template."""
        labels = {
            "welcome": "Boas-vindas",
            "password_reset": "Reset de Senha",
            "meal_reminder": "Lembrete de Refeição",
            "streak_risk": "Streak em Risco",
            "trial_expiring": "Trial Expirando",
            "clinical_action": "Ação Clínica",
        }
        return labels.get(self.value, self.value)
    
    @property
    def icon(self) -> str:
        """Retorna ícone do template."""
        icons = {
            "welcome": "🎉",
            "password_reset": "🔒",
            "meal_reminder": "🍽️",
            "streak_risk": "🔥",
            "trial_expiring": "⏳",
            "clinical_action": "📋",
        }
        return icons.get(self.value, "📧")
    
    @property
    def default_subject(self) -> str:
        """Retorna assunto padrão do template."""
        subjects = {
            "welcome": "🔥 Bem-vindo ao Melshape!",
            "password_reset": "🔒 Redefinição de senha — Melshape",
            "meal_reminder": "🍽️ Registre suas refeições hoje — Melshape",
            "streak_risk": "🔥 Sequência em risco — Melshape",
            "trial_expiring": "⏰ Trial expirando — Melshape",
            "clinical_action": "📋 Ação clínica — Melshape",
        }
        return subjects.get(self.value, "Melshape")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EmailToken:
    """
    Modelo de token de reset de senha.
    
    Attributes:
        token: Token seguro
        email: Email do usuário
        expires_at: Timestamp de expiração
        name: Nome do usuário
        created_at: Timestamp de criação
    """
    token: str
    email: str
    expires_at: datetime
    name: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def is_expired(self) -> bool:
        """Verifica se o token expirou."""
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Verifica se o token é válido (não expirou)."""
        return not self.is_expired
    
    @property
    def remaining_minutes(self) -> int:
        """Retorna minutos restantes até expirar."""
        if self.is_expired:
            return 0
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds() / 60))
    
    @property
    def remaining_seconds(self) -> int:
        """Retorna segundos restantes até expirar."""
        if self.is_expired:
            return 0
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds()))
    
    @property
    def expiry_label(self) -> str:
        """Retorna label de expiração formatada."""
        minutes = self.remaining_minutes
        if minutes > 60:
            hours = minutes // 60
            return f"{hours}h {minutes % 60}min"
        return f"{minutes}min"


@dataclass(frozen=True)
class EmailResult:
    """
    Resultado do envio de email.
    
    Attributes:
        success: Se o email foi enviado com sucesso
        to: Email do destinatário
        subject: Assunto do email
        error_message: Mensagem de erro (se houver)
        mock: Se foi um envio mock (sem Resend)
        template_type: Tipo de template usado (se aplicável)
        sent_at: Timestamp de envio
        message_id: ID da mensagem (se disponível)
    """
    success: bool
    to: str
    subject: str
    error_message: str = ""
    mock: bool = False
    template_type: str | None = None
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message_id: str = ""
    
    @property
    def is_mock(self) -> bool:
        """Verifica se foi um envio mock."""
        return self.mock
    
    @property
    def is_real(self) -> bool:
        """Verifica se foi um envio real (não mock)."""
        return not self.mock and self.success
    
    @property
    def summary_text(self) -> str:
        """Retorna texto resumido do resultado."""
        if self.success:
            if self.mock:
                return f"[MOCK] Email para {self.to}: {self.subject}"
            return f"✅ Email enviado para {self.to}: {self.subject}"
        return f"❌ Falha ao enviar email para {self.to}: {self.error_message}"
    
    @property
    def status_icon(self) -> str:
        """Retorna ícone do status."""
        if self.success:
            return "📦" if self.mock else "✅"
        return "❌"
    
    @property
    def has_error(self) -> bool:
        """Verifica se há erro."""
        return bool(self.error_message)


@dataclass(frozen=True)
class EmailTemplate:
    """
    Modelo de template de email.
    
    Attributes:
        type: Tipo do template
        label: Nome legível do template
        icon: Ícone representativo
        description: Descrição do template
        required_fields: Campos obrigatórios no contexto
        optional_fields: Campos opcionais no contexto
    """
    type: EmailTemplateType
    label: str
    icon: str
    description: str
    required_fields: list[str] = field(default_factory=list)
    optional_fields: list[str] = field(default_factory=list)
    
    @classmethod
    def from_type(cls, template_type: EmailTemplateType) -> EmailTemplate:
        """Cria um template a partir do tipo."""
        templates = {
            EmailTemplateType.WELCOME: cls(
                type=template_type,
                label="Boas-vindas",
                icon="🎉",
                description="Email de boas-vindas para novos usuários",
                required_fields=["name"],
                optional_fields=["trial_days", "btn_url"],
            ),
            EmailTemplateType.PASSWORD_RESET: cls(
                type=template_type,
                label="Reset de Senha",
                icon="🔒",
                description="Email para redefinição de senha",
                required_fields=["name", "reset_url"],
                optional_fields=[],
            ),
            EmailTemplateType.MEAL_REMINDER: cls(
                type=template_type,
                label="Lembrete de Refeição",
                icon="🍽️",
                description="Lembrete para registrar refeições",
                required_fields=["name"],
                optional_fields=["streak", "btn_url"],
            ),
            EmailTemplateType.STREAK_RISK: cls(
                type=template_type,
                label="Streak em Risco",
                icon="🔥",
                description="Alerta de sequência em risco",
                required_fields=["name", "streak"],
                optional_fields=["btn_url"],
            ),
            EmailTemplateType.TRIAL_EXPIRING: cls(
                type=template_type,
                label="Trial Expirando",
                icon="⏳",
                description="Alerta de trial expirando",
                required_fields=["name", "days_remaining"],
                optional_fields=["btn_url"],
            ),
            EmailTemplateType.CLINICAL_ACTION: cls(
                type=template_type,
                label="Ação Clínica",
                icon="📋",
                description="Comunicação de ação clínica",
                required_fields=["name", "titulo", "mensagem"],
                optional_fields=["btn_url"],
            ),
        }
        return templates.get(template_type, templates[EmailTemplateType.WELCOME])
    
    @property
    def display_text(self) -> str:
        """Retorna texto formatado para exibição."""
        return f"{self.icon} {self.label}"
    
    @property
    def all_fields(self) -> list[str]:
        """Retorna todos os campos (obrigatórios + opcionais)."""
        return self.required_fields + self.optional_fields


@dataclass(frozen=True)
class EmailPreview:
    """
    Preview de um email antes do envio.
    
    Attributes:
        template_type: Tipo do template
        to: Email do destinatário
        subject: Assunto do email
        html: Conteúdo HTML completo
        context: Contexto usado para renderização
        rendered_at: Timestamp de renderização
    """
    template_type: EmailTemplateType
    to: str
    subject: str
    html: str
    context: dict[str, Any]
    rendered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def html_length(self) -> int:
        """Retorna tamanho do HTML em caracteres."""
        return len(self.html)
    
    @property
    def html_size_kb(self) -> float:
        """Retorna tamanho do HTML em KB."""
        return len(self.html.encode("utf-8")) / 1024
    
    @property
    def summary_text(self) -> str:
        """Retorna texto resumido do preview."""
        return f"{self.template_type.icon} {self.template_type.label} para {self.to}"


# ─────────────────────────────────────────────────────────────────────────────
# TOKEN STORE (em memória)
# ─────────────────────────────────────────────────────────────────────────────

class InMemoryTokenStore:
    """
    Armazenamento em memória para tokens de reset.
    
    ⚠️ AVISO: Apenas para desenvolvimento/demo.
    Em produção, use tabela password_resets no Supabase.
    """
    
    def __init__(self) -> None:
        self._tokens: dict[str, EmailToken] = {}
    
    def create(self, email: str, name: str) -> EmailToken:
        """
        Cria um novo token de reset.
        
        Args:
            email: Email do usuário
            name: Nome do usuário
            
        Returns:
            Objeto EmailToken
        """
        token = self._gen_token()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=_TOKEN_EXPIRY_MINUTES)
        
        email_token = EmailToken(
            token=token,
            email=email.lower().strip(),
            expires_at=expires_at,
            name=name,
        )
        
        self._tokens[email.lower().strip()] = email_token
        logger.debug(f"✅ Token criado para {email} (expira em {_TOKEN_EXPIRY_MINUTES}min)")
        return email_token
    
    def get(self, email: str) -> EmailToken | None:
        """
        Busca um token pelo email.
        
        Args:
            email: Email do usuário
            
        Returns:
            Objeto EmailToken ou None
        """
        key = email.lower().strip()
        return self._tokens.get(key)
    
    def validate(self, email: str, token: str) -> bool:
        """
        Valida um token de reset.
        
        Args:
            email: Email do usuário
            token: Token a ser validado
            
        Returns:
            True se o token é válido e não expirou
        """
        key = email.lower().strip()
        stored = self._tokens.get(key)
        
        if not stored:
            logger.debug(f"validate: token não encontrado para {email}")
            return False
        
        if stored.token != token:
            logger.debug(f"validate: token inválido para {email}")
            return False
        
        if stored.is_expired:
            self._tokens.pop(key, None)
            logger.debug(f"validate: token expirado para {email}")
            return False
        
        logger.debug(f"✅ Token válido para {email}")
        return True
    
    def consume(self, email: str, token: str) -> bool:
        """
        Consome um token (valida e remove).
        
        Args:
            email: Email do usuário
            token: Token a ser consumido
            
        Returns:
            True se o token foi consumido com sucesso
        """
        if self.validate(email, token):
            self._tokens.pop(email.lower().strip(), None)
            logger.debug(f"✅ Token consumido para {email}")
            return True
        
        logger.debug(f"❌ Falha ao consumir token para {email}")
        return False
    
    def clear_expired(self) -> int:
        """
        Remove todos os tokens expirados.
        
        Returns:
            Número de tokens removidos
        """
        expired = [
            key for key, stored in self._tokens.items()
            if stored.is_expired
        ]
        
        for key in expired:
            self._tokens.pop(key, None)
        
        if expired:
            logger.debug(f"✅ {len(expired)} tokens expirados removidos")
        
        return len(expired)
    
    def clear_all(self) -> int:
        """
        Remove todos os tokens.
        
        Returns:
            Número de tokens removidos
        """
        count = len(self._tokens)
        self._tokens.clear()
        
        if count > 0:
            logger.debug(f"✅ {count} tokens removidos")
        
        return count
    
    def get_active_count(self) -> int:
        """
        Retorna quantidade de tokens ativos (não expirados).
        
        Returns:
            Número de tokens ativos
        """
        return sum(1 for token in self._tokens.values() if token.is_valid)
    
    def _gen_token(self) -> str:
        """Gera um token seguro."""
        return secrets.token_urlsafe(_TOKEN_LENGTH)


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class EmailService:
    """
    Serviço de email com templates e tokens.
    
    Gerencia envio de emails via Resend com fallback para mock.
    
    Example:
        >>> email_service = EmailService()
        >>> result = email_service.send_welcome("user@example.com", "João")
        >>> print(result.summary_text)
    """

    def __init__(self) -> None:
        """Inicializa o serviço de email."""
        self._token_store = InMemoryTokenStore()
        self._client = self._get_client()
        logger.debug(f"✅ EmailService inicializado (Resend: {self._client is not None})")

    # ─────────────────────────────────────────────────────────────────────────
    # CLIENT MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def _get_client(self) -> Any | None:
        """
        Retorna o cliente Resend (ou None se não configurado).
        
        Returns:
            Cliente Resend ou None
        """
        try:
            import resend
            
            key = st.secrets.get("RESEND_API_KEY", "")
            if not key:
                logger.debug("RESEND_API_KEY não configurado")
                return None
            
            resend.api_key = key
            return resend
            
        except ImportError:
            logger.debug("Resend não instalado")
            return None
        except Exception as e:
            logger.warning(f"Erro ao inicializar Resend: {e}")
            return None

    def is_configured(self) -> bool:
        """
        Verifica se o serviço de email está configurado.
        
        Returns:
            True se Resend está configurado
        """
        return self._client is not None

    # ─────────────────────────────────────────────────────────────────────────
    # SEND
    # ─────────────────────────────────────────────────────────────────────────

    def send(
        self,
        to: str,
        subject: str,
        html: str,
    ) -> EmailResult:
        """
        Envia um email via Resend (ou mock).
        
        Args:
            to: Email do destinatário
            subject: Assunto do email
            html: Conteúdo HTML do email
            
        Returns:
            EmailResult com resultado do envio
        """
        if not to or not subject or not html:
            logger.warning("send: to, subject ou html não informados")
            return EmailResult(
                success=False,
                to=to,
                subject=subject,
                error_message="Parâmetros obrigatórios não informados",
            )
        
        if not self._client:
            logger.info(f"[MOCK] Email para: {to} | Assunto: {subject}")
            return EmailResult(
                success=True,
                to=to,
                subject=subject,
                mock=True,
            )
        
        try:
            from_addr = st.secrets.get("RESEND_FROM", _DEFAULT_FROM)
            
            response = self._client.Emails.send({
                "from": from_addr,
                "to": [to],
                "subject": subject,
                "html": html,
            })
            
            message_id = response.get("id", "") if response else ""
            
            logger.info(f"✅ Email enviado para {to}: {subject}")
            return EmailResult(
                success=True,
                to=to,
                subject=subject,
                message_id=message_id,
            )
            
        except Exception as e:
            logger.error(f"Erro ao enviar email para {to}: {e}")
            return EmailResult(
                success=False,
                to=to,
                subject=subject,
                error_message=str(e),
            )

    def send_with_template(
        self,
        to: str,
        subject: str,
        template: str,
        context: dict[str, Any],
    ) -> EmailResult:
        """
        Envia um email usando um template.
        
        Args:
            to: Email do destinatário
            subject: Assunto do email
            template: Nome do template
            context: Dicionário com variáveis do template
            
        Returns:
            EmailResult com resultado do envio
        """
        if not template or not context:
            logger.warning("send_with_template: template ou context não informados")
            return EmailResult(
                success=False,
                to=to,
                subject=subject,
                error_message="Template ou context não informados",
            )
        
        # Renderiza template
        try:
            html = self._render_template(template, context)
            result = self.send(to, subject, html)
            
            # Adiciona tipo de template ao resultado
            return EmailResult(
                success=result.success,
                to=result.to,
                subject=result.subject,
                error_message=result.error_message,
                mock=result.mock,
                template_type=template,
                sent_at=result.sent_at,
                message_id=result.message_id,
            )
        except Exception as e:
            logger.error(f"send_with_template falhou: {e}")
            return EmailResult(
                success=False,
                to=to,
                subject=subject,
                error_message=str(e),
            )

    def send_template_email(
        self,
        to: str,
        template_type: EmailTemplateType,
        context: dict[str, Any],
        subject: str | None = None,
    ) -> EmailResult:
        """
        Envia um email usando tipo de template.
        
        Args:
            to: Email do destinatário
            template_type: Tipo do template
            context: Dicionário com variáveis do template
            subject: Assunto personalizado (opcional)
            
        Returns:
            EmailResult com resultado do envio
        """
        if not subject:
            subject = template_type.default_subject
        
        return self.send_with_template(
            to=to,
            subject=subject,
            template=template_type.value,
            context=context,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TEMPLATES
    # ─────────────────────────────────────────────────────────────────────────

    def render_template(
        self,
        template_type: EmailTemplateType,
        context: dict[str, Any],
    ) -> str:
        """
        Renderiza um template com o contexto fornecido.
        
        Args:
            template_type: Tipo do template
            context: Dicionário com variáveis
            
        Returns:
            HTML renderizado
        """
        return self._render_template(template_type.value, context)

    def _render_template(self, template: str, context: dict[str, Any]) -> str:
        """
        Renderiza um template com o contexto fornecido.
        
        Args:
            template: Nome do template
            context: Dicionário com variáveis
            
        Returns:
            HTML renderizado
        """
        templates = {
            "welcome": self._template_welcome,
            "password_reset": self._template_password_reset,
            "meal_reminder": self._template_meal_reminder,
            "streak_risk": self._template_streak_risk,
            "trial_expiring": self._template_trial_expiring,
            "clinical_action": self._template_clinical_action,
        }
        
        render_fn = templates.get(template)
        if not render_fn:
            raise ValueError(f"Template desconhecido: {template}")
        
        content = render_fn(context)
        tagline = context.get("tagline", "Para quem está mudando de verdade.")
        
        return _BASE_TEMPLATE.format(
            tagline=tagline,
            content=content,
            year=datetime.now().year,
            privacy_url=_PRIVACY_URL,
            terms_url=_TERMS_URL,
        )

    def get_available_templates(self) -> list[EmailTemplate]:
        """
        Retorna lista de templates disponíveis.
        
        Returns:
            Lista de objetos EmailTemplate
        """
        return [EmailTemplate.from_type(t) for t in EmailTemplateType]

    def get_template_by_type(self, template_type: EmailTemplateType) -> EmailTemplate:
        """
        Retorna template por tipo.
        
        Args:
            template_type: Tipo do template
            
        Returns:
            Objeto EmailTemplate
        """
        return EmailTemplate.from_type(template_type)

    def preview_template(
        self,
        template_type: EmailTemplateType,
        to: str,
        context: dict[str, Any],
        subject: str | None = None,
    ) -> EmailPreview:
        """
        Gera preview de um template sem enviar.
        
        Args:
            template_type: Tipo do template
            to: Email do destinatário
            context: Dicionário com variáveis
            subject: Assunto personalizado (opcional)
            
        Returns:
            Objeto EmailPreview
        """
        if not subject:
            subject = template_type.default_subject
        
        html = self.render_template(template_type, context)
        
        return EmailPreview(
            template_type=template_type,
            to=to,
            subject=subject,
            html=html,
            context=context,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TEMPLATE RENDERERS
    # ─────────────────────────────────────────────────────────────────────────

    def _template_welcome(self, context: dict[str, Any]) -> str:
        """Template de boas-vindas."""
        name = context.get("name", "Paciente")
        trial_days = context.get("trial_days", config.TRIAL_DAYS)
        btn_url = context.get("btn_url", _DEFAULT_APP_URL)
        
        return f"""
        <h2 style="font-family:Sora,sans-serif;color:#1C1C1E;margin:0 0 .75rem;">
          Olá, {name}! 🎉
        </h2>
        <p style="color:#4a4a4a;line-height:1.6;">
          Bem-vindo ao <b>Melshape</b>! Você tem <b>{trial_days} dias de acesso Pro</b>
          — sem cartão, sem compromisso.
        </p>
        <div style="background:#fffbeb;border:1px solid #fcd34d;border-left:4px solid #C9A84C;
             border-radius:8px;padding:1rem;margin:1rem 0;">
          <b style="color:#78350f;">⏳ Trial expira em {trial_days} dias.</b><br>
          <span style="font-size:.88rem;color:#92400e;">
          Registre refeições, monitore peso e configure seu perfil.</span>
        </div>
        <p style="color:#4a4a4a;line-height:1.6;">
          <b>3 coisas para fazer agora:</b><br>
          1️⃣ Complete o onboarding (2 min)<br>
          2️⃣ Registre sua primeira refeição<br>
          3️⃣ Configure seu modo de saúde
        </p>
        <div style="text-align:center;margin:1.5rem 0;">
          {self._btn(btn_url, "Acessar o Melshape →")}
        </div>
        """

    def _template_password_reset(self, context: dict[str, Any]) -> str:
        """Template de reset de senha."""
        name = context.get("name", "Paciente")
        reset_url = context.get("reset_url", "")
        
        return f"""
        <h2 style="font-family:Sora,sans-serif;color:#1C1C1E;margin:0 0 .75rem;">
          🔒 Redefinir senha
        </h2>
        <p style="color:#4a4a4a;line-height:1.6;">
          Olá, <b>{name}</b>! Recebemos uma solicitação de redefinição de senha.
        </p>
        <div style="text-align:center;margin:1.5rem 0;">
          {self._btn(reset_url, "Redefinir minha senha →")}
        </div>
        <p style="color:#64748b;font-size:.85rem;text-align:center;">
          ⏰ Link expira em <b>15 minutos</b>.
        </p>
        <div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;
             padding:.75rem;margin-top:1rem;">
          <span style="font-size:.82rem;color:#7f1d1d;">
          🔒 Se não foi você, ignore este email.</span>
        </div>
        """

    def _template_meal_reminder(self, context: dict[str, Any]) -> str:
        """Template de lembrete de refeição."""
        name = context.get("name", "Paciente")
        streak = context.get("streak", 0)
        btn_url = context.get("btn_url", _DEFAULT_APP_URL)
        
        streak_html = ""
        if streak >= 3:
            streak_html = f"""
            <div style="background:#fffbeb;border:1px solid #fcd34d;
                 border-radius:8px;padding:.65rem 1rem;margin:.75rem 0;
                 color:#92400e;font-size:.88rem;">
              🔥 Sequência de <b>{streak} dias</b>! Não perca agora.
            </div>
            """
        
        return f"""
        <h2 style="font-family:Sora,sans-serif;color:#1C1C1E;margin:0 0 .75rem;">
          Oi, {name}! 👋
        </h2>
        <p style="color:#4a4a4a;line-height:1.6;">
          Você ainda não registrou refeições hoje.
        </p>
        {streak_html}
        <div style="text-align:center;margin:1.25rem 0;">
          {self._btn(btn_url, "Registrar agora →")}
        </div>
        <p style="font-size:.78rem;color:#94a3b8;text-align:center;">
          Para cancelar: Perfil → Preferências.
        </p>
        """

    def _template_streak_risk(self, context: dict[str, Any]) -> str:
        """Template de streak em risco."""
        name = context.get("name", "Paciente")
        streak = context.get("streak", 0)
        btn_url = context.get("btn_url", _DEFAULT_APP_URL)
        
        return f"""
        <h2 style="font-family:Sora,sans-serif;color:#dc2626;margin:0 0 .75rem;">
          🔥 Sequência de {streak} dias em risco!
        </h2>
        <p style="color:#4a4a4a;line-height:1.6;">
          Olá, <b>{name}</b>! Registre hoje para manter sua sequência.
        </p>
        <div style="text-align:center;margin:1.5rem 0;">
          {self._btn(btn_url, "Salvar minha sequência →")}
        </div>
        """

    def _template_trial_expiring(self, context: dict[str, Any]) -> str:
        """Template de trial expirando."""
        name = context.get("name", "Paciente")
        days_remaining = context.get("days_remaining", 0)
        btn_url = context.get("btn_url", _DEFAULT_APP_URL)
        
        cor = "#dc2626" if days_remaining <= 1 else "#f59e0b"
        
        return f"""
        <h2 style="font-family:Sora,sans-serif;color:#1C1C1E;margin:0 0 .75rem;">
          ⏳ Trial expira em {days_remaining} dia(s)
        </h2>
        <div style="background:{cor}10;border:2px solid {cor}40;border-radius:10px;
             padding:1rem;text-align:center;margin:1rem 0;">
          <span style="font-size:1.5rem;font-weight:700;color:{cor};">
          {days_remaining} dia(s) restante(s)
          </span>
        </div>
        <p style="color:#4a4a4a;line-height:1.6;">Olá, <b>{name}</b>!
          Assine o Pro por <b>R$ {config.PRO_PRICE:.2f}/mês</b> para continuar.
        </p>
        <div style="text-align:center;margin:1.5rem 0;">
          {self._btn(btn_url, "Assinar o Melshape Pro →")}
        </div>
        """

    def _template_clinical_action(self, context: dict[str, Any]) -> str:
        """Template de ação clínica."""
        name = context.get("name", "Paciente")
        titulo = context.get("titulo", "Ação clínica")
        mensagem = context.get("mensagem", "")
        btn_url = context.get("btn_url", _DEFAULT_APP_URL)
        
        return f"""
        <h2 style="font-family:Sora,sans-serif;color:#1C1C1E;margin:0 0 .75rem;">
          Olá, {name}! 👋
        </h2>
        <p style="color:#4a4a4a;line-height:1.6;">{mensagem}</p>
        <div style="text-align:center;margin:1.5rem 0;">
          {self._btn(btn_url, "Ver no Melshape →")}
        </div>
        """

    # ─────────────────────────────────────────────────────────────────────────
    # SPECIFIC EMAILS
    # ─────────────────────────────────────────────────────────────────────────

    def send_welcome(
        self,
        to: str,
        name: str,
        trial_days: int = config.TRIAL_DAYS,
    ) -> EmailResult:
        """
        Envia email de boas-vindas.
        
        Args:
            to: Email do destinatário
            name: Nome do destinatário
            trial_days: Dias de trial
            
        Returns:
            EmailResult com resultado do envio
        """
        if not to or not name:
            logger.warning("send_welcome: to ou name não informados")
            return EmailResult(
                success=False,
                to=to,
                subject="Bem-vindo ao Melshape",
                error_message="Parâmetros obrigatórios não informados",
            )
        
        return self.send_template_email(
            to=to,
            template_type=EmailTemplateType.WELCOME,
            context={
                "name": name,
                "trial_days": trial_days,
                "btn_url": st.secrets.get("APP_URL", _DEFAULT_APP_URL),
            },
            subject=f"🔥 Bem-vindo ao Melshape, {name}!",
        )

    def send_password_reset(
        self,
        to: str,
        name: str,
        reset_url: str,
    ) -> EmailResult:
        """
        Envia email de reset de senha.
        
        Args:
            to: Email do destinatário
            name: Nome do destinatário
            reset_url: URL de reset
            
        Returns:
            EmailResult com resultado do envio
        """
        if not to or not name or not reset_url:
            logger.warning("send_password_reset: parâmetros obrigatórios não informados")
            return EmailResult(
                success=False,
                to=to,
                subject="Redefinição de senha",
                error_message="Parâmetros obrigatórios não informados",
            )
        
        return self.send_template_email(
            to=to,
            template_type=EmailTemplateType.PASSWORD_RESET,
            context={
                "name": name,
                "reset_url": reset_url,
            },
        )

    def send_meal_reminder(
        self,
        to: str,
        name: str,
        streak: int = 0,
    ) -> EmailResult:
        """
        Envia lembrete de refeição.
        
        Args:
            to: Email do destinatário
            name: Nome do destinatário
            streak: Streak atual
            
        Returns:
            EmailResult com resultado do envio
        """
        if not to or not name:
            logger.warning("send_meal_reminder: to ou name não informados")
            return EmailResult(
                success=False,
                to=to,
                subject="Lembrete de refeição",
                error_message="Parâmetros obrigatórios não informados",
            )
        
        return self.send_template_email(
            to=to,
            template_type=EmailTemplateType.MEAL_REMINDER,
            context={
                "name": name,
                "streak": streak,
                "btn_url": st.secrets.get("APP_URL", _DEFAULT_APP_URL),
            },
        )

    def send_streak_at_risk(
        self,
        to: str,
        name: str,
        streak: int,
    ) -> EmailResult:
        """
        Envia alerta de streak em risco.
        
        Args:
            to: Email do destinatário
            name: Nome do destinatário
            streak: Streak atual
            
        Returns:
            EmailResult com resultado do envio
        """
        if not to or not name:
            logger.warning("send_streak_at_risk: to ou name não informados")
            return EmailResult(
                success=False,
                to=to,
                subject="Streak em risco",
                error_message="Parâmetros obrigatórios não informados",
            )
        
        return self.send_template_email(
            to=to,
            template_type=EmailTemplateType.STREAK_RISK,
            context={
                "name": name,
                "streak": streak,
                "btn_url": st.secrets.get("APP_URL", _DEFAULT_APP_URL),
            },
            subject=f"🔥 Sequência de {streak} dias em risco — Melshape",
        )

    def send_trial_expiring(
        self,
        to: str,
        name: str,
        days_remaining: int,
    ) -> EmailResult:
        """
        Envia alerta de trial expirando.
        
        Args:
            to: Email do destinatário
            name: Nome do destinatário
            days_remaining: Dias restantes de trial
            
        Returns:
            EmailResult com resultado do envio
        """
        if not to or not name:
            logger.warning("send_trial_expiring: to ou name não informados")
            return EmailResult(
                success=False,
                to=to,
                subject="Trial expirando",
                error_message="Parâmetros obrigatórios não informados",
            )
        
        return self.send_template_email(
            to=to,
            template_type=EmailTemplateType.TRIAL_EXPIRING,
            context={
                "name": name,
                "days_remaining": days_remaining,
                "btn_url": st.secrets.get("APP_URL", _DEFAULT_APP_URL),
            },
            subject=f"⏰ Trial expira em {days_remaining} dia(s) — Melshape",
        )

    def send_clinical_action(
        self,
        to: str,
        name: str,
        titulo: str,
        mensagem: str,
    ) -> EmailResult:
        """
        Envia email de ação clínica (profissional → paciente).
        
        Args:
            to: Email do destinatário
            name: Nome do destinatário
            titulo: Título da ação
            mensagem: Mensagem da ação
            
        Returns:
            EmailResult com resultado do envio
        """
        if not to or not name or not titulo or not mensagem:
            logger.warning("send_clinical_action: parâmetros obrigatórios não informados")
            return EmailResult(
                success=False,
                to=to,
                subject="Ação clínica",
                error_message="Parâmetros obrigatórios não informados",
            )
        
        return self.send_template_email(
            to=to,
            template_type=EmailTemplateType.CLINICAL_ACTION,
            context={
                "name": name,
                "titulo": titulo,
                "mensagem": mensagem,
                "btn_url": st.secrets.get("APP_URL", _DEFAULT_APP_URL),
            },
            subject=f"📋 {titulo} — Melshape",
        )

    # ─────────────────────────────────────────────────────────────────────────
    # TOKENS
    # ─────────────────────────────────────────────────────────────────────────

    def request_password_reset(
        self,
        email: str,
        name: str,
        base_url: str = _DEFAULT_APP_URL,
    ) -> str:
        """
        Gera token de reset e retorna a URL de redefinição.
        
        Args:
            email: Email do usuário
            name: Nome do usuário
            base_url: URL base da aplicação
            
        Returns:
            URL de redefinição de senha
        """
        if not email or not name:
            logger.warning("request_password_reset: email ou name não informados")
            return ""
        
        email_token = self._token_store.create(email, name)
        reset_url = f"{base_url}/?reset_token={email_token.token}&email={email}"
        
        logger.debug(f"✅ Token gerado para {email}: {reset_url[:50]}...")
        return reset_url

    def validate_reset_token(self, email: str, token: str) -> bool:
        """
        Valida um token de reset.
        
        Args:
            email: Email do usuário
            token: Token a ser validado
            
        Returns:
            True se o token é válido e não expirou
        """
        if not email or not token:
            logger.warning("validate_reset_token: email ou token não informados")
            return False
        
        return self._token_store.validate(email, token)

    def consume_reset_token(self, email: str, token: str) -> bool:
        """
        Consome um token de reset (valida e remove).
        
        Args:
            email: Email do usuário
            token: Token a ser consumido
            
        Returns:
            True se o token foi consumido com sucesso
        """
        if not email or not token:
            logger.warning("consume_reset_token: email ou token não informados")
            return False
        
        return self._token_store.consume(email, token)

    def get_token(self, email: str) -> EmailToken | None:
        """
        Busca um token pelo email.
        
        Args:
            email: Email do usuário
            
        Returns:
            Objeto EmailToken ou None
        """
        return self._token_store.get(email)

    def clear_expired_tokens(self) -> int:
        """
        Remove todos os tokens expirados.
        
        Returns:
            Número de tokens removidos
        """
        return self._token_store.clear_expired()

    def clear_all_tokens(self) -> int:
        """
        Remove todos os tokens.
        
        Returns:
            Número de tokens removidos
        """
        return self._token_store.clear_all()

    def get_active_tokens_count(self) -> int:
        """
        Retorna quantidade de tokens ativos.
        
        Returns:
            Número de tokens ativos
        """
        return self._token_store.get_active_count()

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────────────────────

    def _wrap(self, content: str, tagline: str = "") -> str:
        """
        Envolve conteúdo no template base.
        
        Args:
            content: Conteúdo HTML
            tagline: Tagline do header
            
        Returns:
            HTML completo
        """
        if not tagline:
            tagline = "Para quem está mudando de verdade."
        
        return _BASE_TEMPLATE.format(
            tagline=tagline,
            content=content,
            year=datetime.now().year,
            privacy_url=_PRIVACY_URL,
            terms_url=_TERMS_URL,
        )

    def _btn(self, url: str, label: str) -> str:
        """
        Gera HTML de botão.
        
        Args:
            url: URL do botão
            label: Texto do botão
            
        Returns:
            HTML do botão
        """
        return _BTN_TEMPLATE.format(url=url, label=label)


# ─────────────────────────────────────────────────────────────────────────────
# INSTÂNCIA GLOBAL
# ─────────────────────────────────────────────────────────────────────────────

email_service = EmailService()


# ─────────────────────────────────────────────────────────────────────────────
# WRAPPERS PARA COMPATIBILIDADE
# ─────────────────────────────────────────────────────────────────────────────

def send(to: str, subject: str, html: str) -> EmailResult:
    """Wrapper para compatibilidade."""
    return email_service.send(to, subject, html)


def send_with_template(
    to: str,
    subject: str,
    template: str,
    context: dict[str, Any],
) -> EmailResult:
    """Wrapper para compatibilidade."""
    return email_service.send_with_template(to, subject, template, context)


def send_welcome(to: str, name: str, trial_days: int = config.TRIAL_DAYS) -> bool:
    """Wrapper para compatibilidade."""
    result = email_service.send_welcome(to, name, trial_days)
    return result.success


def send_password_reset(to: str, name: str, reset_url: str) -> bool:
    """Wrapper para compatibilidade."""
    result = email_service.send_password_reset(to, name, reset_url)
    return result.success


def send_meal_reminder(to: str, name: str, streak: int = 0) -> bool:
    """Wrapper para compatibilidade."""
    result = email_service.send_meal_reminder(to, name, streak)
    return result.success


def send_streak_at_risk(to: str, name: str, streak: int) -> bool:
    """Wrapper para compatibilidade."""
    result = email_service.send_streak_at_risk(to, name, streak)
    return result.success


def send_trial_expiring(to: str, name: str, days_remaining: int) -> bool:
    """Wrapper para compatibilidade."""
    result = email_service.send_trial_expiring(to, name, days_remaining)
    return result.success


def send_clinical_action(to: str, name: str, titulo: str, mensagem: str) -> bool:
    """Wrapper para compatibilidade."""
    result = email_service.send_clinical_action(to, name, titulo, mensagem)
    return result.success


def request_password_reset(
    email: str,
    name: str,
    base_url: str = _DEFAULT_APP_URL,
) -> str:
    """Wrapper para compatibilidade."""
    return email_service.request_password_reset(email, name, base_url)


def validate_reset_token(email: str, token: str) -> bool:
    """Wrapper para compatibilidade."""
    return email_service.validate_reset_token(email, token)


def consume_reset_token(email: str, token: str) -> bool:
    """Wrapper para compatibilidade."""
    return email_service.consume_reset_token(email, token)


def clear_expired_tokens() -> int:
    """Wrapper para compatibilidade."""
    return email_service.clear_expired_tokens()


def is_email_configured() -> bool:
    """Wrapper para compatibilidade."""
    return email_service.is_configured()


__all__ = [
    # Service
    "EmailService",
    "email_service",
    # Enums
    "EmailTemplateType",
    # Models
    "EmailToken",
    "EmailResult",
    "EmailTemplate",
    "EmailPreview",
    # Send (wrappers)
    "send",
    "send_with_template",
    # Emails (wrappers)
    "send_welcome",
    "send_password_reset",
    "send_meal_reminder",
    "send_streak_at_risk",
    "send_trial_expiring",
    "send_clinical_action",
    # Tokens (wrappers)
    "request_password_reset",
    "validate_reset_token",
    "consume_reset_token",
    # Utilities (wrappers)
    "clear_expired_tokens",
    "is_email_configured",
]
