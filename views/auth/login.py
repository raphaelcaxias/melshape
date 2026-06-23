"""
Melshape — Tela de Login.

Login unificado para pacientes e profissionais.

Arquitetura:
    Login
    ├── Constants (validação, mensagens, chaves de sessão)
    ├── LoginRenderer
    │   ├── Header Section
    │   ├── Messages Section (success/info)
    │   ├── Login Form
    │   ├── Actions Section (voltar, esqueci senha, criar conta)
    │   └── Footer Section
    └── Main Render

Princípios:
- Segurança: erro genérico para credenciais inválidas
- Tipagem forte: Protocol, type hints completos
- Validação: reutiliza EmailValidator do forgot_password
- Logging: todas as operações são logadas
- Design System: usa classes CSS em vez de inline
- Tratamento de erros: nunca quebra a aplicação
- Constantes: extraídas para o topo do arquivo
- Reutilização: usa componentes já definidos

Fluxo:
    1. Usuário insere email e senha
    2. Validação de formato
    3. Tenta login como profissional
    4. Se falhar, tenta login como paciente
    5. Se falhar, mostra erro genérico
    6. Redireciona para dashboard apropriado
"""
from __future__ import annotations

import logging
from typing import Any, Protocol

import streamlit as st

import config
from views.auth.forgot_password import EmailValidator

logger = logging.getLogger("Melshape.Login")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Mensagens de erro
_MSG_EMAIL_REQUIRED: str = "Por favor, digite seu email."
_MSG_PASSWORD_REQUIRED: str = "Por favor, digite sua senha."
_MSG_INVALID_EMAIL: str = "Por favor, digite um email válido."
_MSG_INVALID_CREDENTIALS: str = "❌ Email ou senha incorretos."
_MSG_CHECK_CREDENTIALS: str = "💡 Verifique se você digitou corretamente ou crie uma conta."

# Mensagens de sucesso
_MSG_PASSWORD_RESET_SUCCESS: str = "✅ Senha redefinida com sucesso! Faça login."
_MSG_REGISTRATION_SUCCESS: str = "✅ Conta criada com sucesso! Faça login."

# Chaves de sessão
_SESSION_KEY_EMAIL: str = "login_email"
_SESSION_KEY_PASSWORD: str = "login_password"
_SESSION_KEY_REMEMBER_ME: str = "remember_me"
_SESSION_KEY_USER: str = "user"
_SESSION_KEY_PROFESSIONAL: str = "professional"
_SESSION_KEY_PAGE: str = "page"
_SESSION_KEY_PASSWORD_RESET_SUCCESS: str = "password_reset_success"
_SESSION_KEY_REGISTRATION_SUCCESS: str = "registration_success"

# Páginas de destino
_PAGE_LANDING: str = "landing"
_PAGE_HOME: str = "home"
_PAGE_ONBOARDING: str = "onboarding"
_PAGE_PRO_DASHBOARD: str = "pro_dashboard"
_PAGE_FORGOT_PASSWORD: str = "forgot_password"
_PAGE_REGISTER: str = "register"


# ─────────────────────────────────────────────────────────────────────────────
# PROTOCOLS
# ─────────────────────────────────────────────────────────────────────────────

class DatabaseService(Protocol):
    """Protocol para serviço de banco de dados."""
    
    def get_user(self, email: str, password: str) -> Any | None:
        """Busca paciente pelo email e senha."""
        ...
    
    def get_professional(self, email: str, password: str) -> Any | None:
        """Busca profissional pelo email e senha."""
        ...


class ServicesDict(Protocol):
    """Protocol para dicionário de serviços."""
    
    def __getitem__(self, key: str) -> Any:
        """Obtém um serviço pelo nome."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN RENDERER
# ─────────────────────────────────────────────────────────────────────────────

class LoginRenderer:
    """
    Renderer dedicado para página de login.
    
    Gerencia login unificado para pacientes e profissionais.
    
    Attributes:
        services: Dicionário de serviços
        db: Serviço de banco de dados
    
    Example:
        >>> renderer = LoginRenderer(services)
        >>> renderer.render()
    """
    
    def __init__(self, services: ServicesDict) -> None:
        """
        Inicializa o renderer.
        
        Args:
            services: Dicionário de serviços (deve conter "db")
        
        Raises:
            ValueError: Se serviço 'db' não estiver presente
        
        Example:
            >>> renderer = LoginRenderer({"db": db})
        """
        self.services = services
        self.db = services.get("db")
        
        # Valida serviço obrigatório
        if not self.db:
            logger.error("❌ Serviço 'db' não encontrado")
            raise ValueError("Serviço 'db' é obrigatório")
        
        logger.debug("✅ LoginRenderer inicializado")
    
    def render(self) -> None:
        """
        Renderiza página de login completa.
        
        Orquestra a renderização de todas as seções:
        1. Header (título e subtítulo)
        2. Messages (sucesso após reset/registro)
        3. Login Form (email e senha)
        4. Actions (voltar, esqueci senha, criar conta)
        5. Footer (segurança)
        
        Example:
            >>> renderer.render()
        """
        logger.debug("🔄 Renderizando página de login")
        
        try:
            self._render_header()
            self._render_messages()
            self._render_login_form()
            self._render_actions()
            self._render_footer()
            
            logger.debug("✅ Página de login renderizada com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao renderizar login: {e}", exc_info=True)
            st.error("Ocorreu um erro ao carregar a página. Por favor, recarregue.")
    
    def _render_header(self) -> None:
        """
        Renderiza cabeçalho da página.
        
        Exibe título e subtítulo centralizados.
        
        Example:
            >>> renderer._render_header()
        """
        logger.debug("🔄 Renderizando header do login")
        
        st.markdown(
            f"""
            <div class="text-center max-w-md mx-auto mt-xl">
                <h2 class="text-xl font-extrabold mb-lg">
                    🔥 Entrar no {config.APP_NAME}
                </h2>
                <p class="text-center text-muted -mt-sm mb-lg">
                    Acesse sua jornada de transformação
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_messages(self) -> None:
        """
        Renderiza mensagens de sucesso/informação.
        
        Verifica se há mensagens de sucesso após reset de senha ou registro.
        Remove as mensagens após exibir (one-time messages).
        
        Example:
            >>> renderer._render_messages()
        """
        logger.debug("🔄 Verificando mensagens de sucesso")
        
        # Mensagem após reset de senha
        if st.session_state.get(_SESSION_KEY_PASSWORD_RESET_SUCCESS):
            logger.info("✅ Mostrando mensagem de sucesso de reset de senha")
            st.success(_MSG_PASSWORD_RESET_SUCCESS)
            del st.session_state[_SESSION_KEY_PASSWORD_RESET_SUCCESS]
        
        # Mensagem após registro
        if st.session_state.get(_SESSION_KEY_REGISTRATION_SUCCESS):
            logger.info("✅ Mostrando mensagem de sucesso de registro")
            st.success(_MSG_REGISTRATION_SUCCESS)
            del st.session_state[_SESSION_KEY_REGISTRATION_SUCCESS]
    
    def _render_login_form(self) -> None:
        """
        Renderiza formulário de login.
        
        Exibe campos de email e senha, opção "lembrar-me" e botão de submit.
        
        Example:
            >>> renderer._render_login_form()
        """
        logger.debug("🔄 Renderizando formulário de login")
        
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input(
                "Email",
                placeholder="seu@email.com",
                key=_SESSION_KEY_EMAIL,
                help="Digite o email cadastrado."
            )
            
            password = st.text_input(
                "Senha",
                type="password",
                placeholder="Digite sua senha",
                key=_SESSION_KEY_PASSWORD,
                help="Mínimo 8 caracteres."
            )
            
            # Opção "lembrar-me" (visual apenas)
            col1, col2 = st.columns([3, 1])
            with col1:
                st.checkbox("Lembrar-me", key=_SESSION_KEY_REMEMBER_ME)
            with col2:
                st.caption("🔒 Seguro")
            
            submitted = st.form_submit_button(
                "Entrar →",
                type="primary",
                use_container_width=True
            )
        
        if submitted:
            logger.info(f"👆 Formulário de login submetido para: {email}")
            self._handle_login(email, password)
    
    def _handle_login(self, email: str, password: str) -> None:
        """
        Processa tentativa de login.
        
        Valida email e senha, tenta login como profissional ou paciente.
        Se falhar, mostra erro genérico por segurança.
        
        Args:
            email: Email inserido pelo usuário
            password: Senha inserida pelo usuário
        
        Example:
            >>> renderer._handle_login("user@example.com", "password123")
        """
        # Validações iniciais
        if not email or not email.strip():
            logger.warning("⚠️ Email não fornecido")
            st.error(_MSG_EMAIL_REQUIRED)
            return
        
        if not password or not password.strip():
            logger.warning("⚠️ Senha não fornecida")
            st.error(_MSG_PASSWORD_REQUIRED)
            return
        
        email = email.strip().lower()
        
        # Valida formato de email
        email_validation = EmailValidator.validate(email)
        if not email_validation.is_valid:
            logger.warning(f"⚠️ Email inválido: {email}")
            st.error(_MSG_INVALID_EMAIL)
            return
        
        logger.info(f"🔐 Tentando login para: {email}")
        
        # Tenta login como profissional
        professional = self.db.get_professional(email, password)
        if professional:
            logger.info(f"✅ Login de profissional bem-sucedido: {email}")
            self._login_professional(professional)
            return
        
        # Tenta login como paciente
        user = self.db.get_user(email, password)
        if user:
            logger.info(f"✅ Login de paciente bem-sucedido: {email}")
            self._login_user(user)
            return
        
        # Falha no login - erro genérico por segurança
        logger.warning(f"❌ Login falhou para: {email}")
        st.error(_MSG_INVALID_CREDENTIALS)
        st.info(_MSG_CHECK_CREDENTIALS)
    
    def _login_professional(self, professional: Any) -> None:
        """
        Realiza login de profissional.
        
        Converte profissional para dict, configura session state e redireciona.
        
        Args:
            professional: Objeto do profissional (dataclass ou dict)
        
        Example:
            >>> renderer._login_professional(professional)
        """
        user_data = self._to_dict(professional)
        
        st.session_state[_SESSION_KEY_PROFESSIONAL] = user_data
        st.session_state[_SESSION_KEY_PAGE] = _PAGE_PRO_DASHBOARD
        
        logger.info(f"✅ Profissional logado: {user_data.get('email', 'N/A')}")
        st.rerun()
    
    def _login_user(self, user: Any) -> None:
        """
        Realiza login de paciente.
        
        Converte usuário para dict, configura session state e redireciona
        para home (se onboarding completo) ou onboarding (se não).
        
        Args:
            user: Objeto do usuário (dataclass ou dict)
        
        Example:
            >>> renderer._login_user(user)
        """
        user_data = self._to_dict(user)
        
        st.session_state[_SESSION_KEY_USER] = user_data
        
        # Determina página de destino
        onboarding_done = user_data.get("onboarding_done", False)
        target_page = _PAGE_HOME if onboarding_done else _PAGE_ONBOARDING
        
        st.session_state[_SESSION_KEY_PAGE] = target_page
        
        logger.info(
            f"✅ Paciente logado: {user_data.get('email', 'N/A')} → {target_page}"
        )
        st.rerun()
    
    def _to_dict(self, obj: Any) -> dict[str, Any]:
        """
        Converte objeto para dicionário.
        
        Suporta dataclass (com método to_dict), dict ou outro tipo.
        
        Args:
            obj: Objeto a ser convertido
        
        Returns:
            Dicionário com dados do objeto
        
        Example:
            >>> user_dict = renderer._to_dict(user)
            >>> print(user_dict["email"])
        """
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if isinstance(obj, dict):
            return obj
        return {"id": str(obj)}
    
    def _render_actions(self) -> None:
        """
        Renderiza ações secundárias.
        
        Exibe botões para voltar, esqueci senha e criar conta.
        
        Example:
            >>> renderer._render_actions()
        """
        logger.debug("🔄 Renderizando ações secundárias")
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Voltar", use_container_width=True, key="login_back"):
                logger.info("👆 Botão 'Voltar' clicado")
                st.session_state[_SESSION_KEY_PAGE] = _PAGE_LANDING
                st.rerun()
        
        with col2:
            if st.button("Esqueci a senha", use_container_width=True, key="login_forgot"):
                logger.info("👆 Botão 'Esqueci a senha' clicado")
                st.session_state[_SESSION_KEY_PAGE] = _PAGE_FORGOT_PASSWORD
                st.rerun()
        
        st.markdown(
            """
            <div class="text-center mt-md text-base text-muted">
                Não tem conta? <strong class="text-primary cursor-pointer">Crie grátis</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        if st.button("Criar conta grátis →", use_container_width=True, key="login_register"):
            logger.info("👆 Botão 'Criar conta grátis' clicado")
            st.session_state[_SESSION_KEY_PAGE] = _PAGE_REGISTER
            st.rerun()
    
    def _render_footer(self) -> None:
        """
        Renderiza rodapé da página.
        
        Exibe mensagem de segurança.
        
        Example:
            >>> renderer._render_footer()
        """
        logger.debug("🔄 Renderizando footer do login")
        
        st.markdown(
            """
            <div class="text-center mt-lg text-xs text-faint">
                🔒 Todos os dados são criptografados
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
        services: Dicionário de serviços (deve conter "db")
    
    Raises:
        ValueError: Se serviço 'db' não estiver presente
    
    Example:
        >>> from views.auth.login import render
        >>> render(services)
    """
    logger.debug("🔄 Renderizando página de login")
    
    try:
        renderer = LoginRenderer(services)
        renderer.render()
    except Exception as e:
        logger.error(f"❌ Erro crítico ao renderizar login: {e}", exc_info=True)
        st.error("Ocorreu um erro ao carregar a página. Por favor, recarregue.")


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTS
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    "render",
    "LoginRenderer",
    "DatabaseService",
    "ServicesDict",
]
