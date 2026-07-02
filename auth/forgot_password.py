"""
Melshape — Recuperação de Senha.

Gerencia fluxo completo de reset de senha com token seguro.

Arquitetura:
    ForgotPassword
    ├── Data Models (ResetFlowState, ValidationResult)
    ├── Validators (PasswordValidator, EmailValidator)
    ├── PasswordResetRenderer
    │   ├── Request Form (solicitação de reset)
    │   ├── Reset Form (nova senha com token)
    │   └── Success/Error States
    └── Main Render

Princípios:
- Segurança: nunca informa se email existe ou não
- Tipagem forte: Protocol, dataclasses, type hints completos
- Validação: separada em classes dedicadas
- Logging: todas as operações são logadas
- Design System: usa classes CSS em vez de inline
- Tratamento de erros: nunca quebra a aplicação
- Constantes: extraídas para o topo do arquivo

Fluxo:
    1. Usuário solicita reset → email enviado
    2. Usuário clica no link → token validado
    3. Usuário cria nova senha → token consumido
    4. Usuário redirecionado para login
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

import streamlit as st

import config

logger = logging.getLogger("Melshape.ForgotPassword")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Validação de email
_EMAIL_REGEX: str = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
_EMAIL_MAX_LENGTH: int = 254

# Validação de senha
_MIN_PASSWORD_LENGTH: int = 8
_MAX_PASSWORD_LENGTH: int = 128

# Token
_TOKEN_EXPIRATION_MINUTES: int = 15

# Mensagens
_MSG_EMAIL_SENT: str = "Link enviado! Verifique sua caixa de entrada e spam."
_MSG_TOKEN_EXPIRED: str = "Link inválido ou expirado."
_MSG_PASSWORD_UPDATED: str = "Senha redefinida com sucesso!"
_MSG_INVALID_EMAIL: str = "Por favor, insira um email válido."
_MSG_PASSWORDS_DONT_MATCH: str = "As senhas não coincidem."

# Chaves de sessão
_SESSION_KEY_RESET_STATE: str = "reset_state"
_SESSION_KEY_PAGE: str = "page"
_SESSION_KEY_EMAIL: str = "reset_email"
_SESSION_KEY_NEW_PASSWORD: str = "new_password"
_SESSION_KEY_CONFIRM_PASSWORD: str = "confirm_password"


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ResetFlowState:
    """
    Gerencia estado do fluxo de recuperação de senha.
    
    Attributes:
        email_sent: Se o email de reset foi enviado
        token_valid: Se o token atual é válido
        email: Email do usuário em recuperação
    
    Example:
        >>> state = ResetFlowState()
        >>> state.email_sent = True
        >>> state.email = "user@example.com"
    """
    
    email_sent: bool = False
    token_valid: bool = False
    email: str | None = None
    
    def reset(self) -> None:
        """
        Reseta o estado para valores padrão.
        
        Example:
            >>> state = ResetFlowState(email_sent=True, email="test@test.com")
            >>> state.reset()
            >>> print(state.email_sent)
            False
        """
        self.email_sent = False
        self.token_valid = False
        self.email = None


@dataclass(frozen=True)
class ValidationResult:
    """
    Resultado de uma validação.
    
    Attributes:
        is_valid: Se a validação passou
        error_message: Mensagem de erro (None se válido)
    
    Example:
        >>> result = ValidationResult(True, None)
        >>> if result.is_valid:
        ...     print("Válido!")
    """
    
    is_valid: bool
    error_message: str | None = None
    
    @classmethod
    def valid(cls) -> ValidationResult:
        """Cria resultado de validação válida."""
        return cls(is_valid=True, error_message=None)
    
    @classmethod
    def invalid(cls, message: str) -> ValidationResult:
        """Cria resultado de validação inválida."""
        return cls(is_valid=False, error_message=message)


# ─────────────────────────────────────────────────────────────────────────────
# PROTOCOLS
# ─────────────────────────────────────────────────────────────────────────────

class EmailService(Protocol):
    """Protocol para serviço de email."""
    
    def request_password_reset(self, email: str, name: str, base_url: str) -> bool:
        """Solicita reset de senha via email."""
        ...
    
    def validate_reset_token(self, email: str, token: str) -> bool:
        """Valida token de reset."""
        ...
    
    def consume_reset_token(self, email: str, token: str) -> bool:
        """Consome token e atualiza senha."""
        ...


class DatabaseService(Protocol):
    """Protocol para serviço de banco de dados."""
    
    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Busca usuário pelo email."""
        ...
    
    def update_user_password(self, email: str, new_password: str) -> bool:
        """Atualiza senha do usuário."""
        ...


class ServicesDict(Protocol):
    """Protocol para dicionário de serviços."""
    
    def __getitem__(self, key: str) -> Any:
        """Obtém um serviço pelo nome."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATORS
# ─────────────────────────────────────────────────────────────────────────────

class EmailValidator:
    """
    Validador de email.
    
    Example:
        >>> validator = EmailValidator()
        >>> result = validator.validate("user@example.com")
        >>> if result.is_valid:
        ...     print("Email válido!")
    """
    
    @staticmethod
    def validate(email: str) -> ValidationResult:
        """
        Valida formato de email.
        
        Args:
            email: Email a ser validado
        
        Returns:
            ValidationResult com is_valid e error_message
        
        Example:
            >>> result = EmailValidator.validate("test@test.com")
            >>> result.is_valid
            True
        """
        if not email or not email.strip():
            return ValidationResult.invalid("Email não pode estar vazio.")
        
        email = email.strip()
        
        if len(email) > _EMAIL_MAX_LENGTH:
            return ValidationResult.invalid(
                f"Email muito longo (máximo {_EMAIL_MAX_LENGTH} caracteres)."
            )
        
        if not re.match(_EMAIL_REGEX, email):
            return ValidationResult.invalid(_MSG_INVALID_EMAIL)
        
        return ValidationResult.valid()


class PasswordValidator:
    """
    Validador de senha.
    
    Example:
        >>> validator = PasswordValidator()
        >>> result = validator.validate("StrongPass123", "StrongPass123")
        >>> if result.is_valid:
        ...     print("Senha válida!")
    """
    
    @staticmethod
    def validate(password: str, confirm_password: str) -> ValidationResult:
        """
        Valida nova senha e confirmação.
        
        Args:
            password: Nova senha
            confirm_password: Confirmação da senha
        
        Returns:
            ValidationResult com is_valid e error_message
        
        Example:
            >>> result = PasswordValidator.validate("StrongPass123", "StrongPass123")
            >>> result.is_valid
            True
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
            return ValidationResult.invalid(_MSG_PASSWORDS_DONT_MATCH)
        
        return ValidationResult.valid()


# ─────────────────────────────────────────────────────────────────────────────
# PASSWORD RESET RENDERER
# ─────────────────────────────────────────────────────────────────────────────

class PasswordResetRenderer:
    """
    Renderer dedicado para fluxo de recuperação de senha.
    
    Attributes:
        services: Dicionário de serviços
        db: Serviço de banco de dados
        email_service: Serviço de email
    
    Example:
        >>> renderer = PasswordResetRenderer(services)
        >>> renderer.render()
    """
    
    def __init__(self, services: ServicesDict) -> None:
        """
        Inicializa o renderer.
        
        Args:
            services: Dicionário de serviços (deve conter "db" e "email_service")
        
        Raises:
            ValueError: Se serviços obrigatórios não estiverem presentes
        
        Example:
            >>> renderer = PasswordResetRenderer({"db": db, "email_service": email})
        """
        self.services = services
        self.db = services.get("db")
        self.email_service = services.get("email_service")
        
        # Valida serviços obrigatórios
        if not self.db:
            logger.error("❌ Serviço 'db' não encontrado")
            raise ValueError("Serviço 'db' é obrigatório")
        
        if not self.email_service:
            logger.error("❌ Serviço 'email_service' não encontrado")
            raise ValueError("Serviço 'email_service' é obrigatório")
        
        self._init_session_state()
        logger.debug("✅ PasswordResetRenderer inicializado")
    
    def _init_session_state(self) -> None:
        """
        Inicializa estado da sessão para reset.
        
        Cria ResetFlowState se não existir.
        
        Example:
            >>> renderer._init_session_state()
        """
        if _SESSION_KEY_RESET_STATE not in st.session_state:
            st.session_state[_SESSION_KEY_RESET_STATE] = ResetFlowState()
            logger.debug("🔄 Estado de reset inicializado")
    
    def render(self) -> None:
        """
        Ponto de entrada principal do renderer.
        
        Verifica se é callback de reset (com token) ou formulário de solicitação.
        
        Example:
            >>> renderer.render()
        """
        logger.debug("🔄 Renderizando recuperação de senha")
        
        try:
            params = st.query_params
            
            # Verifica se é callback de reset
            if "reset_token" in params and "email" in params:
                logger.info("🔑 Callback de reset detectado")
                self._render_reset_form(params["email"], params["reset_token"])
                return
            
            # Renderiza formulário de solicitação
            logger.debug("📧 Renderizando formulário de solicitação")
            self._render_request_form()
            
        except Exception as e:
            logger.error(f"❌ Erro ao renderizar recuperação de senha: {e}", exc_info=True)
            st.error("Ocorreu um erro ao carregar a página. Por favor, recarregue.")
    
    def _render_request_form(self) -> None:
        """
        Renderiza formulário de solicitação de reset.
        
        Exibe formulário para usuário inserir email e solicitar link de reset.
        
        Example:
            >>> renderer._render_request_form()
        """
        state: ResetFlowState = st.session_state[_SESSION_KEY_RESET_STATE]
        
        # Cabeçalho
        self._render_header(
            "🔒 Recuperar Senha",
            "Enviaremos um link para seu email com instruções."
        )
        
        # Estado de sucesso
        if state.email_sent:
            logger.info(f"✅ Email de reset enviado para: {state.email}")
            self._render_success_state()
            return
        
        # Formulário principal
        with st.form("forgot_password_form", clear_on_submit=False):
            email = st.text_input(
                "Email cadastrado",
                placeholder="seu@email.com",
                key=_SESSION_KEY_EMAIL,
                help="Digite o email usado no cadastro."
            )
            
            submitted = st.form_submit_button(
                "Enviar link de recuperação →",
                type="primary",
                use_container_width=True
            )
        
        if submitted:
            logger.info(f"👆 Formulário de reset submetido para: {email}")
            self._handle_reset_request(email)
        
        # Ações secundárias
        st.divider()
        self._render_back_button("← Voltar ao login", "login")
        self._render_footer()
    
    def _handle_reset_request(self, email: str) -> None:
        """
        Processa solicitação de reset.
        
        Valida email, busca usuário e envia email de reset.
        Por segurança, sempre mostra sucesso (mesmo se email não existir).
        
        Args:
            email: Email inserido pelo usuário
        
        Example:
            >>> renderer._handle_reset_request("user@example.com")
        """
        # Validação
        validation = EmailValidator.validate(email)
        if not validation.is_valid:
            logger.warning(f"⚠️ Email inválido: {email}")
            st.error(validation.error_message)
            return
        
        email = email.strip().lower()
        
        # Verifica se usuário existe (segurança: não informa se existe ou não)
        user = self.db.get_user_by_email(email)
        
        if user:
            logger.info(f"✅ Usuário encontrado: {email}")
            try:
                base_url = config.ENV.app_url
                user_name = user.get("name", "Usuário")
                
                success = self.email_service.request_password_reset(
                    email,
                    user_name,
                    base_url
                )
                
                if success:
                    logger.info(f"📧 Email de reset enviado para: {email}")
                else:
                    logger.warning(f"⚠️ Falha ao enviar email para: {email}")
                    
            except Exception as e:
                # Log do erro sem expor ao usuário
                logger.error(f"❌ Erro ao enviar email de reset: {e}", exc_info=True)
        else:
            logger.info(f"ℹ️ Usuário não encontrado: {email} (segurança: não informado)")
        
        # Sempre mostra sucesso por segurança
        state: ResetFlowState = st.session_state[_SESSION_KEY_RESET_STATE]
        state.email_sent = True
        state.email = email
        st.rerun()
    
    def _render_reset_form(self, email: str, token: str) -> None:
        """
        Renderiza formulário de nova senha.
        
        Exibe formulário para usuário criar nova senha com token válido.
        
        Args:
            email: Email do usuário
            token: Token de reset
        
        Example:
            >>> renderer._render_reset_form("user@example.com", "abc123")
        """
        # Cabeçalho
        self._render_header(
            "🔑 Criar Nova Senha",
            f"Redefinindo senha para: **{email}**"
        )
        
        # Valida token
        if not self._validate_token(email, token):
            logger.warning(f"⚠️ Token inválido para: {email}")
            self._render_invalid_token()
            return
        
        logger.info(f"✅ Token válido para: {email}")
        
        # Formulário de nova senha
        with st.form("new_password_form", clear_on_submit=False):
            st.markdown(f"**Redefinindo senha para:** `{email}`")
            
            new_password = st.text_input(
                "Nova senha",
                type="password",
                placeholder="Mínimo 8 caracteres",
                key=_SESSION_KEY_NEW_PASSWORD,
                help="Use uma senha forte com letras, números e símbolos."
            )
            
            confirm_password = st.text_input(
                "Confirmar nova senha",
                type="password",
                placeholder="Digite a senha novamente",
                key=_SESSION_KEY_CONFIRM_PASSWORD
            )
            
            submitted = st.form_submit_button(
                "Salvar nova senha →",
                type="primary",
                use_container_width=True
            )
        
        if submitted:
            logger.info(f"👆 Formulário de nova senha submetido para: {email}")
            self._handle_password_update(email, token, new_password, confirm_password)
        
        self._render_footer()
    
    def _handle_password_update(
        self,
        email: str,
        token: str,
        new_password: str,
        confirm_password: str
    ) -> None:
        """
        Processa atualização de senha.
        
        Valida nova senha, consome token e atualiza senha no banco.
        
        Args:
            email: Email do usuário
            token: Token de reset
            new_password: Nova senha
            confirm_password: Confirmação da nova senha
        
        Example:
            >>> renderer._handle_password_update("user@example.com", "abc123", "NewPass123", "NewPass123")
        """
        # Validações
        validation = PasswordValidator.validate(new_password, confirm_password)
        if not validation.is_valid:
            logger.warning(f"⚠️ Validação de senha falhou: {validation.error_message}")
            st.error(validation.error_message)
            return
        
        logger.info("✅ Validação de senha passou")
        
        # Consome token e atualiza senha
        try:
            if self.email_service.consume_reset_token(email, token):
                logger.info(f"✅ Token consumido para: {email}")
                
                if self.db.update_user_password(email, new_password):
                    logger.info(f"✅ Senha atualizada para: {email}")
                    
                    # Limpa query params e mostra sucesso
                    st.query_params.clear()
                    st.success(f"✅ {_MSG_PASSWORD_UPDATED}")
                    st.info("Agora você pode fazer login com sua nova senha.")
                    
                    # Mostra botão para login
                    if st.button("Ir para login →", type="primary"):
                        logger.info("👆 Botão 'Ir para login' clicado")
                        st.session_state[_SESSION_KEY_PAGE] = "login"
                        st.rerun()
                    return
                else:
                    logger.error(f"❌ Falha ao atualizar senha para: {email}")
            else:
                logger.warning(f"⚠️ Falha ao consumir token para: {email}")
                
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar senha: {e}", exc_info=True)
        
        st.error("❌ Não foi possível redefinir a senha. Solicite um novo link.")
    
    def _validate_token(self, email: str, token: str) -> bool:
        """
        Valida token de reset.
        
        Args:
            email: Email do usuário
            token: Token a ser validado
        
        Returns:
            True se token é válido, False caso contrário
        
        Example:
            >>> if renderer._validate_token("user@example.com", "abc123"):
            ...     print("Token válido!")
        """
        try:
            return self.email_service.validate_reset_token(email, token)
        except Exception as e:
            logger.error(f"❌ Erro ao validar token: {e}", exc_info=True)
            return False
    
    def _render_header(self, title: str, subtitle: str) -> None:
        """
        Renderiza cabeçalho estilizado.
        
        Args:
            title: Título do cabeçalho
            subtitle: Subtítulo do cabeçalho
        
        Example:
            >>> renderer._render_header("🔒 Recuperar Senha", "Enviaremos um link...")
        """
        st.markdown(
            f"""
            <div class="text-center max-w-md mx-auto mt-xl">
                <h2 class="text-xl font-extrabold text-center">
                    {title}
                </h2>
                <p class="text-center text-muted mb-lg">
                    {subtitle}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_success_state(self) -> None:
        """
        Renderiza estado de sucesso após envio de email.
        
        Exibe mensagem de sucesso e botão para voltar ao login.
        
        Example:
            >>> renderer._render_success_state()
        """
        state: ResetFlowState = st.session_state[_SESSION_KEY_RESET_STATE]
        
        st.success(
            f"""
            ✅ **{_MSG_EMAIL_SENT}**
            
            O link expira em **{_TOKEN_EXPIRATION_MINUTES} minutos**.
            
            Se não receber o email em alguns minutos, verifique se digitou 
            corretamente e tente novamente.
            """
        )
        
        if st.button("← Voltar ao Login", use_container_width=True):
            logger.info("👆 Botão 'Voltar ao Login' clicado")
            state.reset()
            st.session_state[_SESSION_KEY_PAGE] = "login"
            st.rerun()
    
    def _render_invalid_token(self) -> None:
        """
        Renderiza estado de token inválido.
        
        Exibe mensagem de erro e opções para solicitar novo link ou voltar ao login.
        
        Example:
            >>> renderer._render_invalid_token()
        """
        st.error(f"❌ {_MSG_TOKEN_EXPIRED}")
        st.warning(
            f"""
            **O que fazer?**
            - Solicite um novo link de recuperação
            - Verifique se o email está correto
            - O link expira após {_TOKEN_EXPIRATION_MINUTES} minutos por segurança
            """
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Solicitar novo link", use_container_width=True):
                logger.info("👆 Botão 'Solicitar novo link' clicado")
                st.query_params.clear()
                st.session_state[_SESSION_KEY_PAGE] = "forgot_password"
                st.rerun()
        with col2:
            if st.button("Voltar ao login", use_container_width=True):
                logger.info("👆 Botão 'Voltar ao login' clicado")
                st.query_params.clear()
                st.session_state[_SESSION_KEY_PAGE] = "login"
                st.rerun()
    
    def _render_back_button(self, label: str, target_page: str) -> None:
        """
        Renderiza botão de voltar.
        
        Args:
            label: Texto do botão
            target_page: Página de destino
        
        Example:
            >>> renderer._render_back_button("← Voltar", "login")
        """
        if st.button(label, use_container_width=True):
            logger.info(f"👆 Botão '{label}' clicado → {target_page}")
            st.session_state[_SESSION_KEY_PAGE] = target_page
            st.rerun()
    
    def _render_footer(self) -> None:
        """
        Renderiza rodapé da página.
        
        Exibe mensagem de segurança.
        
        Example:
            >>> renderer._render_footer()
        """
        st.markdown(
            """
            <div class="text-center mt-lg text-xs text-faint">
                🔒 Segurança em primeiro lugar • Dados criptografados
            </div>
            """,
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN RENDER
# ─────────────────────────────────────────────────────────────────────────────

def render(services: ServicesDict) -> None:
    """
    Função principal de renderização.
    
    Interface compatível com o sistema existente.
    
    Args:
        services: Dicionário de serviços (deve conter "db" e "email_service")
    
    Example:
        >>> render({"db": db, "email_service": email_service})
    
    Raises:
        ValueError: Se serviços obrigatórios não estiverem presentes
    
    Example:
        >>> from views.auth.forgot_password import render
        >>> render(services)
    """
    logger.debug("🔄 Renderizando página de recuperação de senha")
    
    try:
        renderer = PasswordResetRenderer(services)
        renderer.render()
    except Exception as e:
        logger.error(f"❌ Erro crítico ao renderizar recuperação de senha: {e}", exc_info=True)
        st.error("Ocorreu um erro ao carregar a página. Por favor, recarregue.")


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTS
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    "render",
    "PasswordResetRenderer",
    "ResetFlowState",
    "ValidationResult",
    "EmailValidator",
    "PasswordValidator",
    "EmailService",
    "DatabaseService",
    "ServicesDict",
]
