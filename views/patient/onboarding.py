"""
Melshape — Onboarding do Paciente.

Fluxo guiado para configurar perfil, objetivos e preferências.

Arquitetura:
    Onboarding
    ├── Data Models (OnboardingData)
    ├── Constants (opções, mensagens, chaves de sessão, páginas)
    ├── Validators (Step1Validator, Step2Validator, Step3Validator)
    ├── Calculators (calculate_age, estimate_goal_weeks)
    ├── OnboardingRenderer
    │   ├── Progress Bar
    │   ├── Step 1: Dados pessoais
    │   ├── Step 2: Objetivos e metas
    │   ├── Step 3: Hábitos e estilo de vida
    │   ├── Step 4: Restrições alimentares
    │   ├── Step 5: Condições médicas
    │   ├── Step 6: Revisão e finalização
    │   └── Completed State
    └── Main Render

Princípios:
- Fluxo guiado: 6 passos com validação progressiva
- Tipagem forte: Protocol, dataclasses, type hints completos
- Validação: separada em classes dedicadas
- Logging: todas as operações são logadas
- Design System: usa classes CSS em vez de inline
- Tratamento de erros: nunca quebra a aplicação
- Constantes: extraídas para o topo do arquivo
- Separação de responsabilidades: calculators, validators, renderers

Fluxo:
    1. Dados pessoais (nascimento, gênero, altura, peso)
    2. Objetivos (meta principal, peso desejado, ritmo)
    3. Hábitos (exercícios, nível fitness, sono)
    4. Preferências alimentares (restrições, dietas anteriores)
    5. Condições médicas (condições, medicamentos)
    6. Revisão e finalização
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

import streamlit as st

import config

logger = logging.getLogger("Melshape.Onboarding")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Validação de idade
_MIN_AGE: int = 18
_MAX_AGE: int = 100

# Validação de altura
_MIN_HEIGHT_CM: float = 100.0
_MAX_HEIGHT_CM: float = 250.0

# Validação de peso
_MIN_WEIGHT_KG: float = 20.0
_MAX_WEIGHT_KG: float = 350.0
_MAX_WEIGHT_DIFF_KG: float = 100.0

# Validação de sono
_MIN_SLEEP_HOURS: int = 3
_MAX_SLEEP_HOURS: int = 12

# Taxas de perda de peso (kg/semana)
_WEIGHT_LOSS_RATES: dict[str, float] = {
    "light": 0.5,
    "moderate": 1.0,
    "intense": 1.5,
}

# Mensagens de erro
_MSG_BIRTH_DATE_REQUIRED: str = "Por favor, informe sua data de nascimento."
_MSG_MIN_AGE: str = f"Você deve ter pelo menos {_MIN_AGE} anos para usar o {config.APP_NAME}."
_MSG_MAX_AGE: str = "Por favor, verifique sua data de nascimento."
_MSG_GENDER_REQUIRED: str = "Por favor, selecione seu gênero."
_MSG_INVALID_HEIGHT: str = "Altura inválida. Por favor, verifique o valor."
_MSG_INVALID_WEIGHT: str = "Peso inválido. Por favor, verifique o valor."
_MSG_GOAL_REQUIRED: str = "Por favor, selecione um objetivo principal."
_MSG_TARGET_WEIGHT_REQUIRED: str = "Por favor, informe um peso desejado válido."
_MSG_TARGET_WEIGHT_INVALID: str = "Peso desejado inválido."
_MSG_WEIGHT_DIFF_WARNING: str = "⚠️ A diferença entre seu peso atual e desejado é muito grande. Considere metas intermediárias."
_MSG_EXERCISE_REQUIRED: str = "Por favor, informe sua frequência de exercícios."
_MSG_SLEEP_INVALID: str = f"Por favor, informe uma quantidade válida de horas de sono ({_MIN_SLEEP_HOURS}-{_MAX_SLEEP_HOURS})."

# Mensagens de sucesso
_MSG_PROFILE_SAVED: str = "🎉 Perfil configurado com sucesso!"
_MSG_REDIRECTING: str = "Redirecionando para sua página inicial..."
_MSG_ALREADY_COMPLETED: str = "✅ Você já completou seu onboarding!"

# Chaves de sessão
_SESSION_KEY_STEP: str = "onboarding_step"
_SESSION_KEY_DATA: str = "onboarding_data"
_SESSION_KEY_COMPLETED: str = "onboarding_completed"
_SESSION_KEY_USER: str = "user"
_SESSION_KEY_PAGE: str = "page"

# Páginas de destino
_PAGE_HOME: str = "home"

# Total de passos
_TOTAL_STEPS: int = 6


# ─────────────────────────────────────────────────────────────────────────────
# OPÇÕES (constantes)
# ─────────────────────────────────────────────────────────────────────────────

# Gêneros
_GENDERS: tuple[str, ...] = (
    "Feminino",
    "Masculino",
    "Prefiro não informar",
    "Outro",
)

# Objetivos principais
_PRIMARY_GOALS: dict[str, str] = {
    "weight_loss": "🏋️ Perda de peso",
    "muscle_gain": "💪 Ganho muscular",
    "maintenance": "⚖️ Manutenção",
    "post_bariatric": "🔪 Pós-bariátrica",
    "health_improvement": "❤️ Melhora da saúde",
    "glp1_support": "💉 Suporte GLP-1",
}

# Metas semanais
_WEEKLY_GOALS: dict[str, str] = {
    "light": "🐢 Leve (0-2kg/mês)",
    "moderate": "🐇 Moderada (2-4kg/mês)",
    "intense": "🐆 Intensa (4-6kg/mês)",
}

# Níveis de fitness
_FITNESS_LEVELS: dict[str, str] = {
    "beginner": "🌱 Iniciante",
    "intermediate": "🌿 Intermediário",
    "advanced": "🌳 Avançado",
}

# Frequência de exercícios
_EXERCISE_FREQUENCIES: tuple[str, ...] = (
    "Nenhum",
    "1-2 vezes/semana",
    "3-4 vezes/semana",
    "5-6 vezes/semana",
    "Todos os dias",
)

# Restrições alimentares
_DIETARY_RESTRICTIONS: tuple[str, ...] = (
    "🥩 Carnívoro",
    "🐟 Pescetariano",
    "🥬 Vegetariano",
    "🌱 Vegano",
    "🌾 Glúten",
    "🥛 Lactose",
    "🥜 Nozes",
    "🍷 Álcool",
    "☕ Cafeína",
)

# Condições médicas
_MEDICAL_CONDITIONS: tuple[str, ...] = (
    "Diabetes tipo 2",
    "Hipertensão",
    "Colesterol alto",
    "Hipotireoidismo",
    "Síndrome do ovário policístico",
    "Apneia do sono",
    "Refluxo",
    "Gastrite",
    "Ansiedade",
    "Depressão",
    "Lesão muscular",
    "Outro",
)

# Dietas anteriores
_PREVIOUS_DIETS: tuple[str, ...] = (
    "Low carb",
    "Cetogênica",
    "Mediterrânea",
    "DASH",
    "Vegan",
    "Vegetariana",
    "Jejum intermitente",
    "Low fat",
    "Não fiz dieta",
)


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OnboardingData:
    """
    Dados coletados durante o onboarding.
    
    Attributes:
        birth_date: Data de nascimento
        gender: Gênero
        height_cm: Altura em centímetros
        weight_kg: Peso atual em quilogramas
        primary_goal: Objetivo principal
        target_weight_kg: Peso desejado em quilogramas
        weekly_goal: Ritmo de progresso semanal
        dietary_restrictions: Lista de restrições alimentares
        exercise_frequency: Frequência de exercícios
        sleep_hours: Horas de sono por noite
        medical_conditions: Lista de condições médicas
        medications: Lista de medicamentos em uso
        fitness_level: Nível de condicionamento físico
        previous_diets: Lista de dietas anteriores
    
    Example:
        >>> data = OnboardingData()
        >>> data.birth_date = datetime(1990, 1, 1)
        >>> data.gender = "Feminino"
    """
    
    # Dados pessoais
    birth_date: datetime | None = None
    gender: str = ""
    height_cm: float = 0.0
    weight_kg: float = 0.0
    
    # Objetivos
    primary_goal: str = ""
    target_weight_kg: float = 0.0
    weekly_goal: str = "moderate"
    
    # Preferências
    dietary_restrictions: list[str] = field(default_factory=list)
    exercise_frequency: str = ""
    sleep_hours: int = 0
    
    # Condições médicas
    medical_conditions: list[str] = field(default_factory=list)
    medications: list[str] = field(default_factory=list)
    
    # Experiência
    fitness_level: str = "beginner"
    previous_diets: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """
        Converte para dicionário.
        
        Returns:
            Dicionário com todos os dados do onboarding
        
        Example:
            >>> data = OnboardingData()
            >>> data.birth_date = datetime(1990, 1, 1)
            >>> data_dict = data.to_dict()
            >>> print(data_dict["birth_date"])
        """
        return {
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "gender": self.gender,
            "height_cm": self.height_cm,
            "weight_kg": self.weight_kg,
            "primary_goal": self.primary_goal,
            "target_weight_kg": self.target_weight_kg,
            "weekly_goal": self.weekly_goal,
            "dietary_restrictions": self.dietary_restrictions,
            "exercise_frequency": self.exercise_frequency,
            "sleep_hours": self.sleep_hours,
            "medical_conditions": self.medical_conditions,
            "medications": self.medications,
            "fitness_level": self.fitness_level,
            "previous_diets": self.previous_diets,
            "onboarding_completed_at": datetime.now().isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# PROTOCOLS
# ─────────────────────────────────────────────────────────────────────────────

class DatabaseService(Protocol):
    """Protocol para serviço de banco de dados."""
    
    def update_user(self, data: dict[str, Any]) -> bool:
        """Atualiza dados do usuário."""
        ...


class ServicesDict(Protocol):
    """Protocol para dicionário de serviços."""
    
    def __getitem__(self, key: str) -> Any:
        """Obtém um serviço pelo nome."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# CALCULATORS
# ─────────────────────────────────────────────────────────────────────────────

def calculate_age(birth_date: datetime) -> int:
    """
    Calcula idade a partir da data de nascimento.
    
    Args:
        birth_date: Data de nascimento
    
    Returns:
        Idade em anos
    
    Example:
        >>> age = calculate_age(datetime(1990, 1, 1))
        >>> print(age)
        34
    """
    today = datetime.now()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


def estimate_goal_weeks(
    current_weight: float,
    target_weight: float,
    weekly_goal: str,
) -> float | None:
    """
    Estima semanas para atingir meta de peso.
    
    Args:
        current_weight: Peso atual em kg
        target_weight: Peso desejado em kg
        weekly_goal: Ritmo semanal ("light", "moderate", "intense")
    
    Returns:
        Número de semanas estimado, ou None se não aplicável
    
    Example:
        >>> weeks = estimate_goal_weeks(80.0, 70.0, "moderate")
        >>> print(weeks)
        10.0
    """
    if current_weight <= 0 or target_weight <= 0:
        return None
    
    if current_weight <= target_weight:
        return None
    
    diff = current_weight - target_weight
    rate = _WEIGHT_LOSS_RATES.get(weekly_goal, 1.0)
    
    if rate <= 0:
        return None
    
    return diff / rate


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATORS
# ─────────────────────────────────────────────────────────────────────────────

class Step1Validator:
    """
    Validador do passo 1 (dados pessoais).
    
    Example:
        >>> validator = Step1Validator()
        >>> is_valid = validator.validate(data)
    """
    
    @staticmethod
    def validate(data: OnboardingData) -> bool:
        """
        Valida dados do passo 1.
        
        Args:
            data: Dados do onboarding
        
        Returns:
            True se válido, False caso contrário
        
        Example:
            >>> is_valid = Step1Validator.validate(data)
        """
        if not data.birth_date:
            logger.warning("⚠️ Data de nascimento não informada")
            st.error(_MSG_BIRTH_DATE_REQUIRED)
            return False
        
        age = calculate_age(data.birth_date)
        if age < _MIN_AGE:
            logger.warning(f"⚠️ Idade inválida: {age}")
            st.error(_MSG_MIN_AGE)
            return False
        
        if age > _MAX_AGE:
            logger.warning(f"⚠️ Idade muito alta: {age}")
            st.error(_MSG_MAX_AGE)
            return False
        
        if not data.gender:
            logger.warning("⚠️ Gênero não informado")
            st.error(_MSG_GENDER_REQUIRED)
            return False
        
        if data.height_cm < _MIN_HEIGHT_CM or data.height_cm > _MAX_HEIGHT_CM:
            logger.warning(f"⚠️ Altura inválida: {data.height_cm}")
            st.error(_MSG_INVALID_HEIGHT)
            return False
        
        if data.weight_kg < _MIN_WEIGHT_KG or data.weight_kg > _MAX_WEIGHT_KG:
            logger.warning(f"⚠️ Peso inválido: {data.weight_kg}")
            st.error(_MSG_INVALID_WEIGHT)
            return False
        
        logger.info("✅ Validação do passo 1 passou")
        return True


class Step2Validator:
    """
    Validador do passo 2 (objetivos e metas).
    
    Example:
        >>> validator = Step2Validator()
        >>> is_valid = validator.validate(data)
    """
    
    @staticmethod
    def validate(data: OnboardingData) -> bool:
        """
        Valida dados do passo 2.
        
        Args:
            data: Dados do onboarding
        
        Returns:
            True se válido, False caso contrário
        
        Example:
            >>> is_valid = Step2Validator.validate(data)
        """
        if not data.primary_goal:
            logger.warning("⚠️ Objetivo principal não informado")
            st.error(_MSG_GOAL_REQUIRED)
            return False
        
        if data.target_weight_kg <= 0:
            logger.warning("⚠️ Peso desejado não informado")
            st.error(_MSG_TARGET_WEIGHT_REQUIRED)
            return False
        
        if data.target_weight_kg < _MIN_WEIGHT_KG or data.target_weight_kg > _MAX_WEIGHT_KG:
            logger.warning(f"⚠️ Peso desejado inválido: {data.target_weight_kg}")
            st.error(_MSG_TARGET_WEIGHT_INVALID)
            return False
        
        if data.weight_kg > 0 and abs(data.target_weight_kg - data.weight_kg) > _MAX_WEIGHT_DIFF_KG:
            logger.warning("⚠️ Diferença de peso muito grande")
            st.warning(_MSG_WEIGHT_DIFF_WARNING)
        
        logger.info("✅ Validação do passo 2 passou")
        return True


class Step3Validator:
    """
    Validador do passo 3 (hábitos e estilo de vida).
    
    Example:
        >>> validator = Step3Validator()
        >>> is_valid = validator.validate(data)
    """
    
    @staticmethod
    def validate(data: OnboardingData) -> bool:
        """
        Valida dados do passo 3.
        
        Args:
            data: Dados do onboarding
        
        Returns:
            True se válido, False caso contrário
        
        Example:
            >>> is_valid = Step3Validator.validate(data)
        """
        if not data.exercise_frequency:
            logger.warning("⚠️ Frequência de exercícios não informada")
            st.error(_MSG_EXERCISE_REQUIRED)
            return False
        
        if data.sleep_hours < _MIN_SLEEP_HOURS or data.sleep_hours > _MAX_SLEEP_HOURS:
            logger.warning(f"⚠️ Horas de sono inválidas: {data.sleep_hours}")
            st.error(_MSG_SLEEP_INVALID)
            return False
        
        logger.info("✅ Validação do passo 3 passou")
        return True


# ─────────────────────────────────────────────────────────────────────────────
# ONBOARDING RENDERER
# ─────────────────────────────────────────────────────────────────────────────

class OnboardingRenderer:
    """
    Renderer dedicado para o fluxo de onboarding.
    
    Gerencia fluxo guiado de 6 passos para configurar perfil do paciente.
    
    Attributes:
        services: Dicionário de serviços
        db: Serviço de banco de dados
    
    Example:
        >>> renderer = OnboardingRenderer(services)
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
            >>> renderer = OnboardingRenderer({"db": db})
        """
        self.services = services
        self.db = services.get("db")
        
        # Valida serviço obrigatório
        if not self.db:
            logger.error("❌ Serviço 'db' não encontrado")
            raise ValueError("Serviço 'db' é obrigatório")
        
        self._init_session_state()
        logger.debug("✅ OnboardingRenderer inicializado")
    
    def _init_session_state(self) -> None:
        """
        Inicializa estado do onboarding.
        
        Cria chaves de sessão se não existirem.
        
        Example:
            >>> renderer._init_session_state()
        """
        if _SESSION_KEY_STEP not in st.session_state:
            st.session_state[_SESSION_KEY_STEP] = 1
            logger.debug("🔄 Passo do onboarding inicializado: 1")
        
        if _SESSION_KEY_DATA not in st.session_state:
            st.session_state[_SESSION_KEY_DATA] = OnboardingData()
            logger.debug("🔄 Dados do onboarding inicializados")
        
        if _SESSION_KEY_COMPLETED not in st.session_state:
            st.session_state[_SESSION_KEY_COMPLETED] = False
            logger.debug("🔄 Status de conclusão do onboarding inicializado")
    
    def render(self) -> None:
        """
        Renderiza fluxo de onboarding completo.
        
        Verifica se já completou e renderiza passo atual.
        
        Example:
            >>> renderer.render()
        """
        logger.debug(f"🔄 Renderizando onboarding (passo {st.session_state[_SESSION_KEY_STEP]})")
        
        try:
            # Verifica se já completou
            if st.session_state[_SESSION_KEY_COMPLETED]:
                logger.info("✅ Onboarding já completado")
                self._render_completed()
                return
            
            # Progresso
            self._render_progress()
            
            # Passo atual
            step = st.session_state[_SESSION_KEY_STEP]
            
            if step == 1:
                self._render_step_1()
            elif step == 2:
                self._render_step_2()
            elif step == 3:
                self._render_step_3()
            elif step == 4:
                self._render_step_4()
            elif step == 5:
                self._render_step_5()
            elif step == 6:
                self._render_step_6()
            else:
                logger.warning(f"⚠️ Passo inválido: {step}, resetando para 1")
                self._render_step_1()
            
        except Exception as e:
            logger.error(f"❌ Erro ao renderizar onboarding: {e}", exc_info=True)
            st.error("Ocorreu um erro ao carregar a página. Por favor, recarregue.")
    
    def _render_progress(self) -> None:
        """
        Renderiza barra de progresso.
        
        Exibe progresso visual do onboarding.
        
        Example:
            >>> renderer._render_progress()
        """
        current_step = st.session_state[_SESSION_KEY_STEP]
        progress = (current_step - 1) / _TOTAL_STEPS
        
        logger.debug(f"🔄 Renderizando progresso: passo {current_step}/{_TOTAL_STEPS}")
        
        st.markdown(
            f"""
            <div class="max-w-xl mx-auto mb-xl">
                <div class="flex justify-between text-xs text-muted mb-xs">
                    <span>Passo {current_step} de {_TOTAL_STEPS}</span>
                    <span>{int(progress * 100)}% completo</span>
                </div>
                <div class="progress-track">
                    <div class="progress-fill" style="width:{progress * 100}%;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_step_1(self) -> None:
        """
        Passo 1: Dados pessoais.
        
        Coleta data de nascimento, gênero, altura e peso.
        
        Example:
            >>> renderer._render_step_1()
        """
        logger.debug("🔄 Renderizando passo 1: Dados pessoais")
        
        data: OnboardingData = st.session_state[_SESSION_KEY_DATA]
        
        st.markdown(
            """
            <div class="text-center max-w-xl mx-auto">
                <h3 class="text-lg font-bold text-center">
                    📋 Vamos começar com seus dados
                </h3>
                <p class="text-center text-muted mb-lg">
                    Essas informações nos ajudam a personalizar seu plano
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        with st.form("onboarding_step_1", clear_on_submit=False):
            col1, col2 = st.columns(2)
            with col1:
                data.birth_date = st.date_input(
                    "Data de nascimento",
                    value=data.birth_date or datetime(1990, 1, 1),
                    min_value=datetime(1900, 1, 1),
                    max_value=datetime.now(),
                    key="onb_birth",
                )
                data.gender = st.selectbox(
                    "Gênero",
                    list(_GENDERS),
                    index=list(_GENDERS).index(data.gender) if data.gender in _GENDERS else 0,
                    key="onb_gender",
                )
            
            with col2:
                data.height_cm = st.number_input(
                    "Altura (cm)",
                    min_value=_MIN_HEIGHT_CM,
                    max_value=_MAX_HEIGHT_CM,
                    value=data.height_cm or 165.0,
                    step=1.0,
                    key="onb_height",
                )
                data.weight_kg = st.number_input(
                    "Peso atual (kg)",
                    min_value=_MIN_WEIGHT_KG,
                    max_value=_MAX_WEIGHT_KG,
                    value=data.weight_kg or 70.0,
                    step=0.5,
                    key="onb_weight",
                )
            
            col1, col2 = st.columns(2)
            with col1:
                st.caption("💡 Exemplo: 16/05/1990")
            
            submitted = st.form_submit_button(
                "Próximo →",
                type="primary",
                use_container_width=True,
            )
        
        if submitted:
            logger.info("👆 Formulário do passo 1 submetido")
            if Step1Validator.validate(data):
                st.session_state[_SESSION_KEY_STEP] = 2
                logger.info("✅ Passo 1 validado, avançando para passo 2")
                st.rerun()
    
    def _render_step_2(self) -> None:
        """
        Passo 2: Objetivos e metas.
        
        Coleta objetivo principal, peso desejado e ritmo de progresso.
        
        Example:
            >>> renderer._render_step_2()
        """
        logger.debug("🔄 Renderizando passo 2: Objetivos e metas")
        
        data: OnboardingData = st.session_state[_SESSION_KEY_DATA]
        
        st.markdown(
            """
            <div class="text-center max-w-xl mx-auto">
                <h3 class="text-lg font-bold text-center">
                    🎯 Qual é o seu objetivo?
                </h3>
                <p class="text-center text-muted mb-lg">
                    Defina metas realistas para sua jornada
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        with st.form("onboarding_step_2", clear_on_submit=False):
            data.primary_goal = st.selectbox(
                "Objetivo principal",
                list(_PRIMARY_GOALS.keys()),
                format_func=lambda x: _PRIMARY_GOALS[x],
                index=0,
                key="onb_goal",
            )
            
            data.target_weight_kg = st.number_input(
                "Peso desejado (kg)",
                min_value=_MIN_WEIGHT_KG,
                max_value=300.0,
                value=data.target_weight_kg or 65.0,
                step=0.5,
                key="onb_target_weight",
                help="Defina um peso realista e saudável",
            )
            
            data.weekly_goal = st.select_slider(
                "Ritmo de progresso semanal",
                options=["light", "moderate", "intense"],
                format_func=lambda x: _WEEKLY_GOALS[x],
                value=data.weekly_goal or "moderate",
                key="onb_weekly_goal",
            )
            
            # Mostra estimativa
            self._show_goal_estimate(data)
            
            submitted = st.form_submit_button(
                "Próximo →",
                type="primary",
                use_container_width=True,
            )
        
        if submitted:
            logger.info("👆 Formulário do passo 2 submetido")
            if Step2Validator.validate(data):
                st.session_state[_SESSION_KEY_STEP] = 3
                logger.info("✅ Passo 2 validado, avançando para passo 3")
                st.rerun()
    
    def _render_step_3(self) -> None:
        """
        Passo 3: Hábitos e estilo de vida.
        
        Coleta frequência de exercícios, nível fitness e horas de sono.
        
        Example:
            >>> renderer._render_step_3()
        """
        logger.debug("🔄 Renderizando passo 3: Hábitos e estilo de vida")
        
        data: OnboardingData = st.session_state[_SESSION_KEY_DATA]
        
        st.markdown(
            """
            <div class="text-center max-w-xl mx-auto">
                <h3 class="text-lg font-bold text-center">
                    🏃‍♂️ Conte sobre sua rotina
                </h3>
                <p class="text-center text-muted mb-lg">
                    Entendendo seus hábitos para recomendações melhores
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        with st.form("onboarding_step_3", clear_on_submit=False):
            data.exercise_frequency = st.selectbox(
                "Frequência de exercícios físicos",
                list(_EXERCISE_FREQUENCIES),
                index=list(_EXERCISE_FREQUENCIES).index(data.exercise_frequency)
                if data.exercise_frequency in _EXERCISE_FREQUENCIES
                else 0,
                key="onb_exercise",
            )
            
            data.fitness_level = st.select_slider(
                "Nível de condicionamento físico atual",
                options=["beginner", "intermediate", "advanced"],
                format_func=lambda x: _FITNESS_LEVELS[x],
                value=data.fitness_level or "beginner",
                key="onb_fitness",
            )
            
            data.sleep_hours = st.slider(
                "Horas de sono por noite",
                min_value=_MIN_SLEEP_HOURS,
                max_value=_MAX_SLEEP_HOURS,
                value=data.sleep_hours or 7,
                step=1,
                key="onb_sleep",
                help="O sono adequado é fundamental para os resultados",
            )
            
            submitted = st.form_submit_button(
                "Próximo →",
                type="primary",
                use_container_width=True,
            )
        
        if submitted:
            logger.info("👆 Formulário do passo 3 submetido")
            if Step3Validator.validate(data):
                st.session_state[_SESSION_KEY_STEP] = 4
                logger.info("✅ Passo 3 validado, avançando para passo 4")
                st.rerun()
    
    def _render_step_4(self) -> None:
        """
        Passo 4: Restrições alimentares.
        
        Coleta restrições alimentares e dietas anteriores.
        
        Example:
            >>> renderer._render_step_4()
        """
        logger.debug("🔄 Renderizando passo 4: Restrições alimentares")
        
        data: OnboardingData = st.session_state[_SESSION_KEY_DATA]
        
        st.markdown(
            """
            <div class="text-center max-w-xl mx-auto">
                <h3 class="text-lg font-bold text-center">
                    🍽️ Preferências alimentares
                </h3>
                <p class="text-center text-muted mb-lg">
                    Selecione suas restrições e preferências
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        with st.form("onboarding_step_4", clear_on_submit=False):
            data.dietary_restrictions = st.multiselect(
                "Restrições alimentares (opcional)",
                list(_DIETARY_RESTRICTIONS),
                default=data.dietary_restrictions,
                key="onb_restrictions",
                help="Selecione todas que se aplicam a você",
            )
            
            data.previous_diets = st.multiselect(
                "Dietas que já tentou",
                list(_PREVIOUS_DIETS),
                default=data.previous_diets,
                key="onb_previous_diets",
                help="Isso nos ajuda a entender sua experiência",
            )
            
            submitted = st.form_submit_button(
                "Próximo →",
                type="primary",
                use_container_width=True,
            )
        
        if submitted:
            logger.info("👆 Formulário do passo 4 submetido")
            st.session_state[_SESSION_KEY_STEP] = 5
            logger.info("✅ Passo 4 submetido, avançando para passo 5")
            st.rerun()
    
    def _render_step_5(self) -> None:
        """
        Passo 5: Condições médicas.
        
        Coleta condições médicas e medicamentos em uso.
        
        Example:
            >>> renderer._render_step_5()
        """
        logger.debug("🔄 Renderizando passo 5: Condições médicas")
        
        data: OnboardingData = st.session_state[_SESSION_KEY_DATA]
        
        st.markdown(
            """
            <div class="text-center max-w-xl mx-auto">
                <h3 class="text-lg font-bold text-center">
                    🏥 Saúde e condições médicas
                </h3>
                <p class="text-center text-muted mb-lg">
                    Essas informações são confidenciais e nos ajudam a personalizar seu plano com segurança
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        with st.form("onboarding_step_5", clear_on_submit=False):
            data.medical_conditions = st.multiselect(
                "Condições médicas existentes",
                list(_MEDICAL_CONDITIONS),
                default=data.medical_conditions,
                key="onb_conditions",
                help="Selecione todas que se aplicam",
            )
            
            if "Outro" in data.medical_conditions:
                other_condition = st.text_input(
                    "Especifique outras condições",
                    key="onb_condition_other",
                    placeholder="Ex: Asma, Artrite...",
                )
            
            medications_text = st.text_area(
                "Medicamentos em uso (opcional)",
                value=", ".join(data.medications) if data.medications else "",
                placeholder="Ex: Metformina, Losartana, Vitamina D...",
                key="onb_medications",
                help="Liste todos os medicamentos que você toma regularmente",
            )
            
            st.info(
                "⚠️ **Importante**: Consulte sempre seu médico antes de iniciar "
                "qualquer programa de mudança alimentar ou exercícios."
            )
            
            submitted = st.form_submit_button(
                "Próximo →",
                type="primary",
                use_container_width=True,
            )
        
        if submitted:
            logger.info("👆 Formulário do passo 5 submetido")
            
            # Atualiza medicações
            if medications_text:
                data.medications = [m.strip() for m in medications_text.split(",") if m.strip()]
                logger.info(f"💊 Medicamentos atualizados: {len(data.medications)} itens")
            
            st.session_state[_SESSION_KEY_STEP] = 6
            logger.info("✅ Passo 5 submetido, avançando para passo 6")
            st.rerun()
    
    def _render_step_6(self) -> None:
        """
        Passo 6: Revisão e finalização.
        
        Exibe resumo dos dados e permite finalizar o onboarding.
        
        Example:
            >>> renderer._render_step_6()
        """
        logger.debug("🔄 Renderizando passo 6: Revisão e finalização")
        
        data: OnboardingData = st.session_state[_SESSION_KEY_DATA]
        
        st.markdown(
            """
            <div class="text-center max-w-xl mx-auto">
                <h3 class="text-lg font-bold text-center">
                    ✅ Revisão do seu perfil
                </h3>
                <p class="text-center text-muted mb-lg">
                    Confirme se todas as informações estão corretas
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Exibe resumo
        self._render_summary(data)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Voltar", use_container_width=True):
                logger.info("👆 Botão 'Voltar' clicado no passo 6")
                st.session_state[_SESSION_KEY_STEP] = 5
                st.rerun()
        
        with col2:
            if st.button(
                "✅ Finalizar cadastro",
                type="primary",
                use_container_width=True,
            ):
                logger.info("👆 Botão 'Finalizar cadastro' clicado")
                self._complete_onboarding(data)
    
    def _render_summary(self, data: OnboardingData) -> None:
        """
        Renderiza resumo dos dados.
        
        Exibe todos os dados coletados em expanders organizados.
        
        Args:
            data: Dados do onboarding
        
        Example:
            >>> renderer._render_summary(data)
        """
        logger.debug("🔄 Renderizando resumo dos dados")
        
        # Dados pessoais
        with st.expander("📋 Dados pessoais", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                age = calculate_age(data.birth_date) if data.birth_date else None
                st.metric("Idade", f"{age} anos" if age else "—")
            with col2:
                st.metric("Gênero", data.gender or "—")
            with col3:
                st.metric("Altura", f"{data.height_cm:.1f} cm" if data.height_cm else "—")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Peso atual", f"{data.weight_kg:.1f} kg" if data.weight_kg else "—")
            with col2:
                st.metric(
                    "Peso desejado",
                    f"{data.target_weight_kg:.1f} kg" if data.target_weight_kg else "—",
                )
        
        # Objetivos
        with st.expander("🎯 Objetivos", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Objetivo", _PRIMARY_GOALS.get(data.primary_goal, "—"))
            with col2:
                st.metric("Ritmo", _WEEKLY_GOALS.get(data.weekly_goal, "—"))
        
        # Hábitos
        with st.expander("🏃‍♂️ Hábitos", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Exercícios", data.exercise_frequency or "—")
            with col2:
                st.metric("Nível", _FITNESS_LEVELS.get(data.fitness_level, "—"))
            with col3:
                st.metric("Sono", f"{data.sleep_hours}h" if data.sleep_hours else "—")
        
        # Restrições e saúde
        with st.expander("🍽️ Preferências e saúde", expanded=False):
            if data.dietary_restrictions:
                st.write("**Restrições alimentares:**", ", ".join(data.dietary_restrictions))
            else:
                st.write("**Restrições alimentares:** Nenhuma")
            
            if data.previous_diets:
                st.write("**Dietas anteriores:**", ", ".join(data.previous_diets))
            
            if data.medical_conditions:
                st.write("**Condições médicas:**", ", ".join(data.medical_conditions))
            
            if data.medications:
                st.write("**Medicamentos:**", ", ".join(data.medications))
    
    def _complete_onboarding(self, data: OnboardingData) -> None:
        """
        Completa o onboarding e salva os dados.
        
        Salva dados no banco, marca como completo e redireciona para home.
        
        Args:
            data: Dados do onboarding
        
        Example:
            >>> renderer._complete_onboarding(data)
        """
        logger.info("🔄 Completando onboarding")
        
        try:
            # Salva dados no banco
            user_data = st.session_state.get(_SESSION_KEY_USER, {})
            if user_data:
                onboarding_dict = data.to_dict()
                
                # Atualiza usuário com dados do onboarding
                update_data = {
                    "onboarding_done": True,
                    "onboarding_data": onboarding_dict,
                    "onboarding_completed_at": datetime.now().isoformat(),
                }
                
                success = self.db.update_user(update_data)
                
                if success:
                    logger.info("✅ Dados do onboarding salvos no banco")
                    
                    # Atualiza sessão
                    st.session_state[_SESSION_KEY_USER]["onboarding_done"] = True
                    st.session_state[_SESSION_KEY_USER]["onboarding_data"] = onboarding_dict
                else:
                    logger.error("❌ Falha ao salvar dados do onboarding no banco")
                    st.error("❌ Erro ao salvar dados. Tente novamente.")
                    return
            
            # Marca como completo
            st.session_state[_SESSION_KEY_COMPLETED] = True
            
            # Mensagem de sucesso
            st.success(_MSG_PROFILE_SAVED)
            st.balloons()
            
            # Aguarda um momento e redireciona
            st.info(_MSG_REDIRECTING)
            
            import time
            time.sleep(1.5)
            
            st.session_state[_SESSION_KEY_PAGE] = _PAGE_HOME
            logger.info("✅ Onboarding completado, redirecionando para home")
            st.rerun()
            
        except Exception as e:
            logger.error(f"❌ Erro ao completar onboarding: {e}", exc_info=True)
            st.error(f"❌ Erro ao salvar dados: {str(e)}")
            st.session_state[_SESSION_KEY_COMPLETED] = False
    
    def _render_completed(self) -> None:
        """
        Renderiza estado de onboarding já completo.
        
        Exibe mensagem de sucesso e botão para ir para home.
        
        Example:
            >>> renderer._render_completed()
        """
        logger.debug("🔄 Renderizando estado de onboarding completado")
        
        st.success(_MSG_ALREADY_COMPLETED)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("Ir para página inicial →", type="primary", use_container_width=True):
                logger.info("👆 Botão 'Ir para página inicial' clicado")
                st.session_state[_SESSION_KEY_PAGE] = _PAGE_HOME
                st.rerun()
    
    def _show_goal_estimate(self, data: OnboardingData) -> None:
        """
        Mostra estimativa de tempo para atingir meta.
        
        Args:
            data: Dados do onboarding
        
        Example:
            >>> renderer._show_goal_estimate(data)
        """
        weeks = estimate_goal_weeks(data.weight_kg, data.target_weight_kg, data.weekly_goal)
        
        if weeks is not None:
            if weeks > 0:
                months = int(weeks / 4.3)
                st.info(
                    f"💡 Com seu ritmo atual, você pode atingir seu peso desejado "
                    f"em aproximadamente **{weeks:.1f} semanas** "
                    f"({months} meses)."
                )
                logger.info(f"💡 Estimativa calculada: {weeks:.1f} semanas")
            else:
                st.success("✅ Você já está em seu peso desejado!")
                logger.info("✅ Usuário já está no peso desejado")
        elif data.weight_kg > 0 and data.target_weight_kg > 0 and data.weight_kg < data.target_weight_kg:
            st.info("🎯 Você está buscando ganho de peso/massa muscular. Vamos trabalhar nisso!")
            logger.info("🎯 Usuário buscando ganho de peso")


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
        >>> from views.patient.onboarding import render
        >>> render(services)
    """
    logger.debug("🔄 Renderizando página de onboarding")
    
    try:
        renderer = OnboardingRenderer(services)
        renderer.render()
    except Exception as e:
        logger.error(f"❌ Erro crítico ao renderizar onboarding: {e}", exc_info=True)
        st.error("Ocorreu um erro ao carregar a página. Por favor, recarregue.")


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTS
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    "render",
    "OnboardingRenderer",
    "OnboardingData",
    "Step1Validator",
    "Step2Validator",
    "Step3Validator",
    "calculate_age",
    "estimate_goal_weeks",
    "DatabaseService",
    "ServicesDict",
]
