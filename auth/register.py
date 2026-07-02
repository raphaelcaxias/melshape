"""
Melshape — Cadastro de Paciente e Profissional.

Cadastro unificado com validações robustas e fluxo guiado.

Arquitetura:
    Register
    ├── Data Models (RegistrationData, Specialty)
    ├── Constants (mensagens, chaves de sessão, páginas, especialidades)
    ├── RegisterRenderer
    │   ├── Header Section
    │   ├── Patient Form (cadastro de paciente)
    │   ├── Professional Form (cadastro de profissional)
    │   ├── Actions Section (voltar, trocar tipo, login)
    │   └── Footer Section
    └── Main Render

Princípios:
- Segurança: validações robustas, LGPD obrigatório
- Tipagem forte: Protocol, dataclasses, type hints completos
- Validação: reutiliza EmailValidator e PasswordValidator
- Logging: todas as operações são logadas
- Design System: usa classes CSS em vez de inline
- Tratamento de erros: nunca quebra a aplicação
- Constantes: extraídas para o topo do arquivo
- Reutilização: usa componentes já definidos

Fluxo Paciente:
    1. Usuário preenche dados (nome, email, senha, LGPD)
    2. Validação de todos os campos
    3. Cria usuário no banco
    4. Envia email de boas-vindas
    5. Login automático → redireciona para onboarding

Fluxo Profissional:
    1. Usuário preenche dados + registro profissional (CRN/CRM)
    2. Validação de todos os campos
    3. Cria profissional no banco
    4. Envia email de boas-vindas
    5. Login automático → redireciona para pro_dashboard
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

import streamlit as st

import config
from views.auth.forgot_password import EmailValidator, PasswordValidator

logger = logging.getLogger("Melshape.Register")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Validação de nome
_MIN_NAME_LENGTH: int = 2

# Validação de registro profissional
_MIN_LICENSE_LENGTH: int = 3

# Mensagens de erro
_MSG_NAME_REQUIRED: str = "Digite seu nome completo (mínimo 2 caracteres)."
_MSG_EMAIL_INVALID: str = "Digite um email válido."
_MSG_LGPD_REQUIRED: str = "Aceite os Termos de Uso e Política de Privacidade para continuar."
_MSG_LICENSE_REQUIRED: str = "Digite seu número de registro profissional válido."
_MSG_EMAIL_EXISTS: str = "❌ Email já cadastrado. Tente fazer login."
_MSG_EMAIL_EXISTS_HINT: str = "💡 Se você já tem conta, clique em 'Voltar' e faça login."

# Mensagens de sucesso
_MSG_ACCOUNT_CREATED: str = "✅ Conta criada com sucesso!"

# Chaves de sessão
_SESSION_KEY_NAME: str = "reg_name"
_SESSION_KEY_EMAIL: str = "reg_email"
_SESSION_KEY_PASSWORD: str = "reg_password"
_SESSION_KEY_CONFIRM_PASSWORD: str = "reg_confirm_password"
_SESSION_KEY_LGPD: str = "reg_lgpd"
_SESSION_KEY_OBJECTIVE: str = "reg_objective"
_SESSION_KEY_AGE: str = "reg_age"
_SESSION_KEY_SPECIALTY: str = "reg_pro_specialty"
_SESSION_KEY_LICENSE: str = "reg_pro_license"
_SESSION_KEY_USER: str = "user"
_SESSION_KEY_PROFESSIONAL: str = "professional"
_SESSION_KEY_PAGE: str = "page"
_SESSION_KEY_REGISTRATION_SUCCESS: str = "registration_success"

# Páginas de destino
_PAGE_LANDING: str = "landing"
_PAGE_HOME: str = "home"
_PAGE_ONBOARDING: str = "onboarding"
_PAGE_PRO_DASHBOARD: str = "pro_dashboard"
_PAGE_LOGIN: str = "login"
_PAGE_REGISTER: str = "register"
_PAGE_REGISTER_PRO: str = "register_pro"

# Tipos de usuário
_USER_TYPE_PATIENT: str = "patient"
_USER_TYPE_PROFESSIONAL: str = "professional"


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Specialty:
    """
    Representa uma especialidade profissional.
    
    Attributes:
        key: Chave única da especialidade
        label: Label de exibição com emoji
        icon: Ícone visual (emoji)
    
    Example:
        >>> specialty = Specialty("nutritionist", "Nutricionista", "🥗")
        >>> print(specialty.label)
        'Nutricionista'
    """
    
    key: str
    label: str
    icon: str
    
    @property
    def display_label(self) -> str:
        """Retorna label formatado para exibição."""
        return f"{self.icon} {self.label}"


@dataclass
class RegistrationData:
    """
    Dados do cadastro.
    
    Attributes:
        name: Nome completo
        email: Email
        password: Senha
        confirm_password: Confirmação da senha
        lgpd_accepted: Se aceitou os termos
        specialty: Especialidade (profissional)
        license_number: Registro profissional (profissional)
    
    Example:
        >>> data = RegistrationData(name="Maria", email="maria@test.com")
        >>> data.is_valid()
        False
    """
    
    name: str = ""
    email: str = ""
    password: str = ""
    confirm_password: str = ""
    lgpd_accepted: bool = False
    
    # Dados específicos de profissional
    specialty: str = "nutritionist"
    license_number: str = ""
    
    def is_valid(self) -> bool:
        """
        Verifica se todos os campos obrigatórios estão preenchidos.
        
        Returns:
            True se todos os campos obrigatórios estão preenchidos
        
        Example:
            >>> data = RegistrationData(name="Maria", email="maria@test.com", 
            ...                         password="Pass123", confirm_password="Pass123",
            ...                         lgpd_accepted=True)
            >>> data.is_valid()
            True
        """
        return all([
            self.name.strip(),
            self.email.strip(),
            self.password,
            self.confirm_password,
            self.lgpd_accepted
        ])
    
    def is_professional_valid(self) -> bool:
        """
        Verifica campos específicos de profissional.
        
        Returns:
            True se todos os campos (incluindo registro profissional) estão preenchidos
        
        Example:
            >>> data = RegistrationData(name="Dr. Carlos", email="carlos@test.com",
            ...                         password="Pass123", confirm_password="Pass123",
            ...                         lgpd_accepted=True, license_number="CRN-12345")
            >>> data.is_professional_valid()
            True
        """
        return self.is_valid() and bool(self.license_number.strip())


# ─────────────────────────────────────────────────────────────────────────────
# PROTOCOLS
# ─────────────────────────────────────────────────────────────────────────────

class DatabaseService(Protocol):
    """Protocol para serviço de banco de dados."""
    
    def create_user(
        self,
        email: str,
        password: str,
        name: str,
        **kwargs: Any
    ) -> bool:
        """Cria um novo usuário (paciente)."""
        ...
    
    def create_professional(
        self,
        email: str,
        password: str,
        name: str,
        specialty: str,
        license_number: str
    ) -> bool:
        """Cria um novo profissional."""
        ...
    
    def get_user(self, email: str, password: str) -> Any | None:
        """Busca paciente pelo email e senha."""
        ...
    
    def get_professional(self, email: str, password: str) -> Any | None:
        """Busca profissional pelo email e senha."""
        ...


class EmailService(Protocol):
    """Protocol para serviço de email."""
    
    def send_welcome(self, email: str, name: str, trial_days: int) -> bool:
        """Envia email de boas-vindas."""
        ...


class ServicesDict(Protocol):
    """Protocol para dicionário de serviços."""
    
    def __getitem__(self, key: str) -> Any:
        """Obtém um serviço pelo nome."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# ESPECIALIDADES
# ─────────────────────────────────────────────────────────────────────────────

_SPECIALTIES: tuple[Specialty, ...] = (
    Specialty("nutritionist", "Nutricionista", "🥗"),
    Specialty("endocrinologist", "Endocrinologista", "🩺"),
    Specialty("psychologist", "Psicólogo(a)", "🧠"),
    Specialty("personal_trainer", "Personal Trainer", "💪"),
    Specialty("other", "Outro", "👨‍⚕️"),
)

_SPECIALTIES_MAP: dict[str, Specialty] = {s.key: s for s in _SPECIALTIES}

# Opções de objetivo (paciente)
_OBJECTIVES: tuple[str, ...] = (
    "Perda de peso",
    "Ganho muscular",
    "Saúde geral",
    "Pós-bariátrica",
    "GLP-1",
)

# Faixas etárias (paciente)
_AGE_RANGES: tuple[str, ...] = (
    "18-25",
    "26-35",
    "36-45",
    "46-55",
    "56+",
)


# ─────────────────────────────────────────────────────────────────────────────
# REGISTER RENDERER
# ─────────────────────────────────────────────────────────────────────────────

class RegisterRenderer:
    """
    Renderer dedicado para cadastro.
    
    Gerencia cadastro unificado para pacientes e profissionais.
    
    Attributes:
        services: Dicionário de serviços
        db: Serviço de banco de dados
        email_service: Serviço de email
        is_pro: Se está no modo de cadastro profissional
    
    Example:
        >>> renderer = RegisterRenderer(services)
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
            >>> renderer = RegisterRenderer({"db": db, "email_service": email})
        """
        self.services = services
        self.db = services.get("db")
        self.email_service = services.get("email_service")
        self.is_pro = st.session_state.get(_SESSION_KEY_PAGE) == _PAGE_REGISTER_PRO
        
        # Valida serviço obrigatório
        if not self.db:
            logger.error("❌ Serviço 'db' não encontrado")
            raise ValueError("Serviço 'db' é obrigatório")
        
        logger.debug(f"✅ RegisterRenderer inicializado (is_pro={self.is_pro})")
    
    def render(self) -> None:
        """
        Renderiza página de cadastro completa.
        
        Orquestra a renderização de todas as seções:
        1. Header (título e subtítulo)
        2. Formulário específico (paciente ou profissional)
        3. Actions (voltar, trocar tipo, login)
        4. Footer (segurança)
        
        Example:
            >>> renderer.render()
        """
        logger.debug(f"🔄 Renderizando página de cadastro (is_pro={self.is_pro})")
        
        try:
            self._render_header()
            
            # Formulário específico
            if self.is_pro:
                self._render_professional_form()
            else:
                self._render_patient_form()
            
            # Ações secundárias
            self._render_actions()
            self._render_footer()
            
            logger.debug("✅ Página de cadastro renderizada com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao renderizar cadastro: {e}", exc_info=True)
            st.error("Ocorreu um erro ao carregar a página. Por favor, recarregue.")
    
    def _render_header(self) -> None:
        """
        Renderiza cabeçalho da página.
        
        Exibe título e subtítulo centralizados, variando conforme tipo de cadastro.
        
        Example:
            >>> renderer._render_header()
        """
        label = "🏥 Profissional de Saúde" if self.is_pro else "👤 Paciente"
        trial_days = config.PRICING.trial_days
        
        logger.debug(f"🔄 Renderizando header do cadastro ({label})")
        
        st.markdown(
            f"""
            <div class="text-center max-w-lg mx-auto mt-lg">
                <h2 class="text-xl font-extrabold mb-md">
                    📝 Criar conta — {label}
                </h2>
                <p class="text-center text-muted -mt-sm mb-lg">
                    {trial_days} dias grátis • Sem compromisso
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_patient_form(self) -> None:
        """
        Renderiza formulário de cadastro de paciente.
        
        Exibe campos de nome, email, senha, LGPD, objetivo e faixa etária.
        
        Example:
            >>> renderer._render_patient_form()
        """
        logger.debug("🔄 Renderizando formulário de cadastro de paciente")
        
        data = RegistrationData()
        
        with st.form("register_patient_form", clear_on_submit=False):
            col1, col2 = st.columns(2)
            with col1:
                data.name = st.text_input(
                    "Nome completo",
                    placeholder="Ex: Maria Silva",
                    key=_SESSION_KEY_NAME,
                    help="Digite seu nome completo."
                )
                data.email = st.text_input(
                    "Email",
                    placeholder="seu@email.com",
                    key=_SESSION_KEY_EMAIL,
                    help="Usaremos este email para login e comunicações."
                )
            
            with col2:
                data.password = st.text_input(
                    "Senha",
                    type="password",
                    placeholder="Mínimo 8 caracteres",
                    key=_SESSION_KEY_PASSWORD,
                    help="Use uma senha forte com letras, números e símbolos."
                )
                data.confirm_password = st.text_input(
                    "Confirmar senha",
                    type="password",
                    placeholder="Digite a senha novamente",
                    key=_SESSION_KEY_CONFIRM_PASSWORD
                )
            
            # Termos e LGPD
            st.divider()
            data.lgpd_accepted = st.checkbox(
                "📋 Li e aceito os **Termos de Uso** e **Política de Privacidade**",
                key=_SESSION_KEY_LGPD,
                help="Leia os termos antes de aceitar."
            )
            
            # Campos adicionais para análise
            st.divider()
            st.caption("📊 Opcional — para melhor personalização")
            
            col1, col2 = st.columns(2)
            with col1:
                objective = st.selectbox(
                    "Objetivo principal",
                    list(_OBJECTIVES),
                    key=_SESSION_KEY_OBJECTIVE
                )
            with col2:
                age_range = st.selectbox(
                    "Faixa etária",
                    list(_AGE_RANGES),
                    key=_SESSION_KEY_AGE
                )
            
            submitted = st.form_submit_button(
                "Criar conta grátis →",
                type="primary",
                use_container_width=True
            )
        
        if submitted:
            logger.info(f"👆 Formulário de cadastro de paciente submetido para: {data.email}")
            self._handle_patient_registration(data, objective, age_range)
    
    def _render_professional_form(self) -> None:
        """
        Renderiza formulário de cadastro de profissional.
        
        Exibe campos de nome, email, senha, especialidade, registro e LGPD.
        
        Example:
            >>> renderer._render_professional_form()
        """
        logger.debug("🔄 Renderizando formulário de cadastro de profissional")
        
        data = RegistrationData()
        
        with st.form("register_professional_form", clear_on_submit=False):
            col1, col2 = st.columns(2)
            with col1:
                data.name = st.text_input(
                    "Nome completo",
                    placeholder="Ex: Dr. Carlos Santos",
                    key=f"{_SESSION_KEY_NAME}_pro",
                    help="Digite seu nome completo."
                )
                data.email = st.text_input(
                    "Email profissional",
                    placeholder="seu@clinica.com.br",
                    key=f"{_SESSION_KEY_EMAIL}_pro",
                    help="Use seu email profissional."
                )
                data.specialty = st.selectbox(
                    "Especialidade",
                    [s.key for s in _SPECIALTIES],
                    format_func=lambda x: _SPECIALTIES_MAP[x].display_label,
                    key=_SESSION_KEY_SPECIALTY
                )
            
            with col2:
                data.password = st.text_input(
                    "Senha",
                    type="password",
                    placeholder="Mínimo 8 caracteres",
                    key=f"{_SESSION_KEY_PASSWORD}_pro",
                    help="Use uma senha forte."
                )
                data.confirm_password = st.text_input(
                    "Confirmar senha",
                    type="password",
                    placeholder="Digite a senha novamente",
                    key=f"{_SESSION_KEY_CONFIRM_PASSWORD}_pro"
                )
                data.license_number = st.text_input(
                    "CRN / CRM / Registro",
                    placeholder="Ex: CRN-12345",
                    key=_SESSION_KEY_LICENSE,
                    help="Digite seu número de registro profissional."
                )
            
            # Termos e LGPD
            st.divider()
            data.lgpd_accepted = st.checkbox(
                "📋 Li e aceito os **Termos de Uso** e **Política de Privacidade**",
                key=f"{_SESSION_KEY_LGPD}_pro"
            )
            
            submitted = st.form_submit_button(
                "Criar conta profissional →",
                type="primary",
                use_container_width=True
            )
        
        if submitted:
            logger.info(f"👆 Formulário de cadastro profissional submetido para: {data.email}")
            self._handle_professional_registration(data)
    
    def _handle_patient_registration(
        self,
        data: RegistrationData,
        objective: str,
        age_range: str
    ) -> None:
        """
        Processa cadastro de paciente.
        
        Valida dados, cria usuário e completa o registro.
        
        Args:
            data: Dados do cadastro
            objective: Objetivo principal do paciente
            age_range: Faixa etária do paciente
        
        Example:
            >>> renderer._handle_patient_registration(data, "Perda de peso", "26-35")
        """
        logger.info(f"🔄 Processando cadastro de paciente: {data.email}")
        
        # Valida dados
        validation_errors = self._validate_registration(data)
        
        if validation_errors:
            logger.warning(f"⚠️ Erros de validação: {validation_errors}")
            for error in validation_errors:
                st.error(error)
            return
        
        # Cria usuário
        try:
            success = self.db.create_user(
                data.email.lower(),
                data.password,
                data.name.strip(),
                objective=objective,
                age_range=age_range
            )
            
            if success:
                logger.info(f"✅ Paciente criado com sucesso: {data.email}")
                self._complete_registration(data, _USER_TYPE_PATIENT)
            else:
                logger.warning(f"⚠️ Email já cadastrado: {data.email}")
                st.error(_MSG_EMAIL_EXISTS)
                st.info(_MSG_EMAIL_EXISTS_HINT)
                
        except Exception as e:
            logger.error(f"❌ Erro ao criar paciente: {e}", exc_info=True)
            st.error("❌ Ocorreu um erro ao criar sua conta. Tente novamente.")
    
    def _handle_professional_registration(self, data: RegistrationData) -> None:
        """
        Processa cadastro de profissional.
        
        Valida dados, cria profissional e completa o registro.
        
        Args:
            data: Dados do cadastro
        
        Example:
            >>> renderer._handle_professional_registration(data)
        """
        logger.info(f"🔄 Processando cadastro de profissional: {data.email}")
        
        # Valida dados
        validation_errors = self._validate_professional_registration(data)
        
        if validation_errors:
            logger.warning(f"⚠️ Erros de validação: {validation_errors}")
            for error in validation_errors:
                st.error(error)
            return
        
        # Cria profissional
        try:
            success = self.db.create_professional(
                data.email.lower(),
                data.password,
                data.name.strip(),
                data.specialty,
                data.license_number.strip()
            )
            
            if success:
                logger.info(f"✅ Profissional criado com sucesso: {data.email}")
                self._complete_registration(data, _USER_TYPE_PROFESSIONAL)
            else:
                logger.warning(f"⚠️ Email já cadastrado: {data.email}")
                st.error(_MSG_EMAIL_EXISTS)
                
        except Exception as e:
            logger.error(f"❌ Erro ao criar profissional: {e}", exc_info=True)
            st.error("❌ Ocorreu um erro ao criar sua conta. Tente novamente.")
    
    def _complete_registration(self, data: RegistrationData, user_type: str) -> None:
        """
        Completa o fluxo de registro.
        
        Envia email de boas-vindas e faz login automático.
        
        Args:
            data: Dados do cadastro
            user_type: Tipo de usuário ("patient" ou "professional")
        
        Example:
            >>> renderer._complete_registration(data, "patient")
        """
        logger.info(f"🔄 Completando registro para: {data.email} ({user_type})")
        
        # Envia email de boas-vindas
        self._send_welcome_email(data)
        
        # Faz login automático
        if user_type == _USER_TYPE_PATIENT:
            self._login_patient(data)
        else:
            self._login_professional(data)
    
    def _send_welcome_email(self, data: RegistrationData) -> None:
        """
        Envia email de boas-vindas.
        
        Não falha o registro por erro de email.
        
        Args:
            data: Dados do cadastro
        
        Example:
            >>> renderer._send_welcome_email(data)
        """
        if not self.email_service:
            logger.warning("⚠️ Serviço de email não disponível")
            return
        
        try:
            trial_days = config.PRICING.trial_days
            success = self.email_service.send_welcome(
                data.email,
                data.name,
                trial_days
            )
            
            if success:
                logger.info(f"📧 Email de boas-vindas enviado para: {data.email}")
            else:
                logger.warning(f"⚠️ Falha ao enviar email de boas-vindas para: {data.email}")
                
        except Exception as e:
            # Não falha o registro por erro de email
            logger.error(f"❌ Erro ao enviar email de boas-vindas: {e}", exc_info=True)
    
    def _login_patient(self, data: RegistrationData) -> None:
        """
        Faz login automático do paciente.
        
        Args:
            data: Dados do cadastro
        
        Example:
            >>> renderer._login_patient(data)
        """
        try:
            user = self.db.get_user(data.email, data.password)
            if user:
                user_data = self._to_dict(user)
                st.session_state[_SESSION_KEY_USER] = user_data
                st.session_state[_SESSION_KEY_PAGE] = _PAGE_ONBOARDING

                # Consome token de convite profissional (se vier de link de convite)
                try:
                    from professional.patient_invite import InviteService
                    token = InviteService.token_da_url()
                    if token:
                        inv_svc = InviteService(self.db)
                        pro_email = inv_svc.consumir(token, data.email)
                        if pro_email:
                            pro_svc = self.services.get("professional")
                            if pro_svc:
                                pro_svc.link_patient(pro_email, data.email)
                            st.session_state[_SESSION_KEY_USER]["professional_email"] = pro_email
                            logger.info(f"✅ Paciente {data.email} vinculado a {pro_email} via convite")
                            st.query_params.clear()
                except Exception as _inv_err:
                    logger.warning(f"Erro ao processar convite: {_inv_err}")

                logger.info(f"✅ Login automático de paciente: {data.email}")
                st.success(_MSG_ACCOUNT_CREATED)
                st.rerun()
            else:
                logger.error(f"❌ Usuário não encontrado após criação: {data.email}")
                st.error("❌ Ocorreu um erro ao fazer login. Tente fazer login manualmente.")
                st.session_state[_SESSION_KEY_PAGE] = _PAGE_LOGIN
                st.rerun()
        except Exception as e:
            logger.error(f"❌ Erro ao fazer login automático: {e}", exc_info=True)
            st.error("❌ Ocorreu um erro ao fazer login. Tente fazer login manualmente.")
    
    def _login_professional(self, data: RegistrationData) -> None:
        """
        Faz login automático do profissional.
        
        Args:
            data: Dados do cadastro
        
        Example:
            >>> renderer._login_professional(data)
        """
        try:
            professional = self.db.get_professional(data.email, data.password)
            if professional:
                professional_data = self._to_dict(professional)
                st.session_state[_SESSION_KEY_PROFESSIONAL] = professional_data
                st.session_state[_SESSION_KEY_PAGE] = _PAGE_PRO_DASHBOARD
                
                logger.info(f"✅ Login automático de profissional: {data.email}")
                st.success(_MSG_ACCOUNT_CREATED)
                st.rerun()
            else:
                logger.error(f"❌ Profissional não encontrado após criação: {data.email}")
                st.error("❌ Ocorreu um erro ao fazer login. Tente fazer login manualmente.")
                st.session_state[_SESSION_KEY_PAGE] = _PAGE_LOGIN
                st.rerun()
        except Exception as e:
            logger.error(f"❌ Erro ao fazer login automático: {e}", exc_info=True)
            st.error("❌ Ocorreu um erro ao fazer login. Tente fazer login manualmente.")
    
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
    
    def _validate_registration(self, data: RegistrationData) -> list[str]:
        """
        Valida dados de cadastro.
        
        Args:
            data: Dados do cadastro
        
        Returns:
            Lista de mensagens de erro (vazia se válido)
        
        Example:
            >>> errors = renderer._validate_registration(data)
            >>> if errors:
            ...     for error in errors:
            ...         st.error(error)
        """
        errors: list[str] = []
        
        # Nome
        if not data.name or len(data.name.strip()) < _MIN_NAME_LENGTH:
            errors.append(_MSG_NAME_REQUIRED)
        
        # Email
        email_validation = EmailValidator.validate(data.email)
        if not email_validation.is_valid:
            errors.append(_MSG_EMAIL_INVALID)
        
        # Senha
        password_validation = PasswordValidator.validate(data.password, data.confirm_password)
        if not password_validation.is_valid:
            errors.append(password_validation.error_message or "Senha inválida.")
        
        # LGPD
        if not data.lgpd_accepted:
            errors.append(_MSG_LGPD_REQUIRED)
        
        return errors
    
    def _validate_professional_registration(self, data: RegistrationData) -> list[str]:
        """
        Valida dados de cadastro de profissional.
        
        Args:
            data: Dados do cadastro
        
        Returns:
            Lista de mensagens de erro (vazia se válido)
        
        Example:
            >>> errors = renderer._validate_professional_registration(data)
            >>> if errors:
            ...     for error in errors:
            ...         st.error(error)
        """
        errors = self._validate_registration(data)
        
        # Registro profissional
        if not data.license_number or len(data.license_number.strip()) < _MIN_LICENSE_LENGTH:
            errors.append(_MSG_LICENSE_REQUIRED)
        
        return errors
    
    def _render_actions(self) -> None:
        """
        Renderiza ações secundárias.
        
        Exibe botões para voltar, trocar tipo de cadastro e link para login.
        
        Example:
            >>> renderer._render_actions()
        """
        logger.debug("🔄 Renderizando ações secundárias")
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Voltar", use_container_width=True, key="reg_back"):
                logger.info("👆 Botão 'Voltar' clicado")
                st.session_state[_SESSION_KEY_PAGE] = _PAGE_LANDING
                st.rerun()
        
        with col2:
            label = "🏥 Sou profissional" if not self.is_pro else "👤 Sou paciente"
            target_page = _PAGE_REGISTER_PRO if not self.is_pro else _PAGE_REGISTER
            
            if st.button(label, use_container_width=True, key="reg_toggle"):
                logger.info(f"👆 Botão '{label}' clicado → {target_page}")
                st.session_state[_SESSION_KEY_PAGE] = target_page
                st.rerun()
        
        # Link para login
        st.markdown(
            """
            <div class="text-center mt-md text-base text-muted">
                Já tem conta? <strong class="text-primary cursor-pointer">Faça login</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_footer(self) -> None:
        """
        Renderiza rodapé da página.
        
        Exibe mensagem de segurança.
        
        Example:
            >>> renderer._render_footer()
        """
        logger.debug("🔄 Renderizando footer do cadastro")
        
        st.markdown(
            """
            <div class="text-center mt-md text-xs text-faint">
                🔒 Dados protegidos • 📧 Verificação de email
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
        >>> from views.auth.register import render
        >>> render(services)
    """
    logger.debug("🔄 Renderizando página de cadastro")
    
    try:
        renderer = RegisterRenderer(services)
        renderer.render()
    except Exception as e:
        logger.error(f"❌ Erro crítico ao renderizar cadastro: {e}", exc_info=True)
        st.error("Ocorreu um erro ao carregar a página. Por favor, recarregue.")


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTS
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    "render",
    "RegisterRenderer",
    "RegistrationData",
    "Specialty",
    "DatabaseService",
    "EmailService",
    "ServicesDict",
]
