"""
Melshape — Modelos de Dados.

Define todas as entidades do sistema como dataclasses imutáveis.
Centraliza a lógica de negócio relacionada aos modelos.

Princípios:
- Imutabilidade: todas as dataclasses são frozen=True
- Validação: validação de dados na criação (__post_init__)
- Serialização: to_dict() e from_dict() para todos os modelos
- Tipagem forte: uso extensivo de Type Hints e Enums
- Domínio: modelos refletem o domínio do negócio
- Datas: objetos date/datetime internamente, ISO strings na serialização

Modelos:
    - User: Paciente da plataforma
    - Professional: Profissional de saúde
    - Meal: Refeição registrada
    - WeightLog: Registro de peso
    - HydrationLog: Registro de hidratação
    - Supplement: Suplemento alimentar
    - WorkoutLog: Registro de treino
    - SleepLog: Registro de sono
    - SymptomLog: Registro de sintomas
    - CycleLog: Registro de ciclo menstrual
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Final, Self

import config

# ─────────────────────────────────────────────────────────────────────────────
# ENUMS DE DOMÍNIO
# ─────────────────────────────────────────────────────────────────────────────

class Gender(str, Enum):
    """Gênero do usuário."""
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"


class HealthMode(str, Enum):
    """Modo de saúde do usuário."""
    GENERAL = "general"
    FITNESS = "fitness"
    BARIATRIC = "bariatric"
    GLP1 = "glp1"


class Plan(str, Enum):
    """Plano de assinatura."""
    FREE = "free"
    TRIAL = "trial"
    PRO = "pro"
    CLINIC = "clinic"
    LIFETIME = "lifetime"


class ActivityLevel(str, Enum):
    """Nível de atividade física."""
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


class Goal(str, Enum):
    """Objetivo do usuário."""
    LOSE = "lose"
    MAINTAIN = "maintain"
    GAIN = "gain"


class Specialty(str, Enum):
    """Especialidade do profissional."""
    NUTRITIONIST = "nutritionist"
    ENDOCRINOLOGIST = "endocrinologist"
    OTHER = "other"


class MealType(str, Enum):
    """Tipo de refeição."""
    CAFE_MANHA = "cafe_manha"
    LANCHE = "lanche"
    ALMOCO = "almoco"
    LANCHE_TARDE = "lanche_tarde"
    JANTAR = "jantar"
    CEIA = "ceia"
    PRE_POS_TREINO = "pre_pos_treino"


class WorkoutType(str, Enum):
    """Tipo de treino."""
    STRENGTH = "strength"
    CARDIO = "cardio"
    HIIT = "hiit"
    YOGA = "yoga"
    SWIMMING = "swimming"
    CYCLING = "cycling"
    WALKING = "walking"
    FUNCTIONAL = "functional"
    SPORTS = "sports"
    OTHER = "other"


class Intensity(str, Enum):
    """Intensidade do treino."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    MAXIMUM = "maximum"


class HydrationSource(str, Enum):
    """Fonte de hidratação."""
    WATER = "water"
    JUICE = "juice"
    TEA = "tea"
    OTHER = "other"


class SupplementCategory(str, Enum):
    """Categoria de suplemento."""
    PROTEIN = "protein"
    VITAMIN = "vitamin"
    MINERAL = "mineral"
    OTHER = "other"


class SupplementUnit(str, Enum):
    """Unidade de medida de suplemento."""
    MG = "mg"
    G = "g"
    ML = "ml"
    UI = "UI"
    CAPSULA = "cápsula"
    COMPRIMIDO = "comprimido"


class CyclePhase(str, Enum):
    """Fase do ciclo menstrual."""
    FOLLICULAR = "follicular"
    OVULATORY = "ovulatory"
    LUTEAL = "luteal"
    MENSTRUAL = "menstrual"
    UNKNOWN = "unknown"


class CycleFlow(str, Enum):
    """Fluxo menstrual."""
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"
    SPOTTING = "spotting"
    NONE = "none"


# ─────────────────────────────────────────────────────────────────────────────
# MIXIN DE SERIALIZAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

class SerializableMixin:
    """
    Mixin para serialização de dataclasses.
    
    Fornece to_dict() e from_dict() para qualquer dataclass.
    Converte automaticamente:
    - date/datetime para ISO strings
    - Enum para valores
    - Objetos aninhados (recursivo)
    """
    
    def to_dict(self) -> dict[str, Any]:
        """
        Converte o objeto para dicionário.
        
        Returns:
            Dicionário com todos os campos da dataclass
            
        Exemplo:
            >>> user = User(email="user@example.com", name="João")
            >>> user.to_dict()
            {"email": "user@example.com", "name": "João", ...}
        """
        result = {}
        
        for f in dataclasses.fields(self):
            value = getattr(self, f.name)
            result[f.name] = self._serialize_value(value)
        
        return result
    
    def _serialize_value(self, value: Any) -> Any:
        """Serializa um valor recursivamente."""
        # None
        if value is None:
            return None
        
        # date/datetime → ISO string
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        
        # Enum → valor
        if isinstance(value, Enum):
            return value.value
        
        # Dataclass aninhada
        if dataclasses.is_dataclass(value):
            return value.to_dict()
        
        # Lista
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        
        # Dict
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        
        # Valor primitivo
        return value
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Cria uma instância a partir de um dicionário.
        
        Args:
            data: Dicionário com os dados
            
        Returns:
            Instância da dataclass
            
        Exemplo:
            >>> data = {"email": "user@example.com", "name": "João"}
            >>> user = User.from_dict(data)
        """
        # Filtra apenas campos que existem na dataclass
        fields = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in fields}
        
        # Converte strings ISO para date/datetime
        converted = cls._deserialize_values(filtered)
        
        return cls(**converted)
    
    @classmethod
    def _deserialize_values(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Converte valores serializados de volta para objetos."""
        result = {}
        
        for key, value in data.items():
            field_info = next((f for f in dataclasses.fields(cls) if f.name == key), None)
            
            if field_info is None:
                result[key] = value
                continue
            
            # Converte string ISO para date/datetime
            if isinstance(value, str) and field_info.type in ("date", "datetime"):
                try:
                    if field_info.type == "date":
                        result[key] = date.fromisoformat(value)
                    else:
                        result[key] = datetime.fromisoformat(value)
                except (ValueError, TypeError):
                    result[key] = value
            else:
                result[key] = value
        
        return result


# ─────────────────────────────────────────────────────────────────────────────
# MODELO: USER (Paciente)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class User(SerializableMixin):
    """
    Modelo do paciente (usuário final da plataforma).
    
    Attributes:
        email: Email do usuário (identificador único)
        name: Nome completo
        password_hash: Hash da senha (PBKDF2)
        plan: Plano atual (free/trial/pro/clinic/lifetime)
        gender: Gênero (female/male/other)
        health_mode: Modo de saúde (general/fitness/bariatric/glp1)
        current_weight: Peso atual (kg)
        goal_weight: Peso desejado (kg)
        height: Altura (cm)
        age: Idade (anos)
        activity_level: Nível de atividade física
        goal: Objetivo (lose/maintain/gain)
        onboarding_done: Flag de onboarding concluído
        dark_mode: Flag de tema escuro
        trial_end: Data de término do trial
        lgpd_ts: Timestamp de consentimento LGPD
        professional_id: ID do profissional vinculado
        created_at: Data de criação
    """
    email: str
    name: str
    password_hash: str = ""
    plan: Plan = Plan.TRIAL
    gender: Gender = Gender.FEMALE
    health_mode: HealthMode = HealthMode.GENERAL
    current_weight: float | None = None
    goal_weight: float | None = None
    height: int | None = None
    age: int | None = None
    activity_level: ActivityLevel = ActivityLevel.MODERATE
    goal: Goal = Goal.LOSE
    onboarding_done: bool = False
    dark_mode: bool = False
    trial_end: date | None = None
    lgpd_ts: datetime | None = None
    professional_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __post_init__(self) -> None:
        """Valida os dados após a criação."""
        # Validação de email
        self._validate_email()
        
        # Validações de domínio
        self._validate_weight()
        self._validate_height()
        self._validate_age()
    
    def _validate_email(self) -> None:
        """Valida formato do email."""
        # Lazy import para evitar circular dependency
        from core.security import validate_email
        
        result = validate_email(self.email)
        if not result:
            raise ValueError(f"Email inválido: {self.email}")
    
    def _validate_weight(self) -> None:
        """Valida peso."""
        if self.current_weight is not None and self.current_weight <= 0:
            raise ValueError(f"Peso inválido: {self.current_weight}")
        
        if self.goal_weight is not None and self.goal_weight <= 0:
            raise ValueError(f"Peso objetivo inválido: {self.goal_weight}")
    
    def _validate_height(self) -> None:
        """Valida altura."""
        if self.height is not None and not (50 <= self.height <= 300):
            raise ValueError(f"Altura inválida: {self.height}cm")
    
    def _validate_age(self) -> None:
        """Valida idade."""
        if self.age is not None and not (0 <= self.age <= 150):
            raise ValueError(f"Idade inválida: {self.age}")
    
    def trial_days_remaining(self) -> int:
        """
        Calcula dias restantes do trial.
        
        Returns:
            Número de dias restantes (0 se expirado ou não for trial)
        """
        if self.plan != Plan.TRIAL or not self.trial_end:
            return 0
        
        try:
            today = date.today()
            return max(0, (self.trial_end - today).days)
        except (ValueError, TypeError):
            return 0
    
    def effective_plan(self) -> Plan:
        """
        Retorna o plano efetivo considerando expiração do trial.
        
        Returns:
            Plan.TRIAL se ainda tem dias restantes
            Plan.FREE se trial expirou
            O plano atual caso contrário
        """
        if self.plan == Plan.TRIAL:
            return Plan.TRIAL if self.trial_days_remaining() > 0 else Plan.FREE
        return self.plan
    
    def is_pro(self) -> bool:
        """Verifica se o usuário tem acesso Pro."""
        return self.effective_plan() in {Plan.PRO, Plan.CLINIC, Plan.LIFETIME}
    
    def is_trial_active(self) -> bool:
        """Verifica se o trial está ativo."""
        return self.plan == Plan.TRIAL and self.trial_days_remaining() > 0
    
    def has_professional(self) -> bool:
        """Verifica se o usuário tem um profissional vinculado."""
        return bool(self.professional_id)
    
    @classmethod
    def create_trial_user(cls, email: str, name: str, **kwargs) -> Self:
        """
        Factory method para criar usuário em trial.
        
        Args:
            email: Email do usuário
            name: Nome do usuário
            **kwargs: Argumentos adicionais
            
        Returns:
            Instância de User em trial
        """
        from datetime import timedelta
        
        trial_end = date.today() + timedelta(days=config.TRIAL_DAYS)
        
        return cls(
            email=email,
            name=name,
            plan=Plan.TRIAL,
            trial_end=trial_end,
            **kwargs
        )


# ─────────────────────────────────────────────────────────────────────────────
# MODELO: PROFESSIONAL
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Professional(SerializableMixin):
    """
    Modelo do profissional de saúde.
    
    Attributes:
        email: Email do profissional (identificador único)
        name: Nome completo
        specialty: Especialidade (nutritionist/endocrinologist/other)
        crn: Número de registro (CRN/CRM)
        password_hash: Hash da senha (PBKDF2)
        plan: Plano atual (trial/pro/clinic)
        created_at: Data de criação
    """
    email: str
    name: str
    specialty: Specialty = Specialty.NUTRITIONIST
    crn: str = ""
    password_hash: str = ""
    plan: Plan = Plan.TRIAL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __post_init__(self) -> None:
        """Valida os dados após a criação."""
        from core.security import validate_email
        
        result = validate_email(self.email)
        if not result:
            raise ValueError(f"Email inválido: {self.email}")
    
    def is_nutritionist(self) -> bool:
        """Verifica se o profissional é nutricionista."""
        return self.specialty == Specialty.NUTRITIONIST
    
    def is_endocrinologist(self) -> bool:
        """Verifica se o profissional é endocrinologista."""
        return self.specialty == Specialty.ENDOCRINOLOGIST


# ─────────────────────────────────────────────────────────────────────────────
# MODELO: MEAL (Refeição)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Meal(SerializableMixin):
    """
    Modelo de refeição registrada.
    
    Attributes:
        food: Nome do alimento
        calories: Calorias (kcal)
        protein: Proteína (g)
        carbs: Carboidratos (g)
        fat: Gorduras (g)
        fiber: Fibras (g)
        quantity: Quantidade (em 100g, padrão: 1.0)
        volume_ml: Volume (ml, para bariátrica)
        meal_time: Horário da refeição (HH:MM)
        meal_type: Tipo da refeição
        meal_date: Data da refeição
        mood: Humor no momento da refeição
        notes: Observações
        nutrient_score: Score nutricional (0-100)
        user_id: ID do usuário
    """
    food: str
    calories: float
    protein: float
    carbs: float
    fat: float
    fiber: float = 0.0
    quantity: float = 1.0
    volume_ml: float = 0.0
    meal_time: str = "12:00"
    meal_type: MealType = MealType.ALMOCO
    meal_date: date = field(default_factory=date.today)
    mood: str = ""
    notes: str = ""
    nutrient_score: int = 50
    user_id: str = ""
    
    def __post_init__(self) -> None:
        """Valida os dados após a criação."""
        self._validate_time()
        self._validate_macros()
        self._validate_score()
    
    def _validate_time(self) -> None:
        """Valida formato do horário."""
        if self.meal_time and ":" not in self.meal_time:
            raise ValueError(f"Horário inválido: {self.meal_time}")
    
    def _validate_macros(self) -> None:
        """Valida macronutrientes."""
        if self.calories < 0:
            raise ValueError(f"Calorias inválidas: {self.calories}")
        
        if self.protein < 0 or self.carbs < 0 or self.fat < 0 or self.fiber < 0:
            raise ValueError("Macros não podem ser negativos")
        
        if self.quantity <= 0:
            raise ValueError(f"Quantidade inválida: {self.quantity}")
    
    def _validate_score(self) -> None:
        """Valida score nutricional."""
        if not 0 <= self.nutrient_score <= 100:
            raise ValueError(f"Score nutricional inválido: {self.nutrient_score}")
    
    @property
    def total_calories(self) -> float:
        """Calorias totais (considerando quantidade)."""
        return self.calories * self.quantity
    
    @property
    def total_protein(self) -> float:
        """Proteína total (considerando quantidade)."""
        return self.protein * self.quantity
    
    @property
    def total_carbs(self) -> float:
        """Carboidratos totais (considerando quantidade)."""
        return self.carbs * self.quantity
    
    @property
    def total_fat(self) -> float:
        """Gorduras totais (considerando quantidade)."""
        return self.fat * self.quantity
    
    @property
    def is_healthy(self) -> bool:
        """Verifica se a refeição é saudável (score >= 70)."""
        return self.nutrient_score >= 70
    
    @property
    def macro_ratio(self) -> dict[str, float]:
        """Retorna proporção de macros em percentual."""
        total = self.total_protein + self.total_carbs + self.total_fat
        if total == 0:
            return {"protein": 0, "carbs": 0, "fat": 0}
        
        return {
            "protein": (self.total_protein / total) * 100,
            "carbs": (self.total_carbs / total) * 100,
            "fat": (self.total_fat / total) * 100,
        }


# ─────────────────────────────────────────────────────────────────────────────
# MODELO: WEIGHT_LOG (Peso)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class WeightLog(SerializableMixin):
    """
    Modelo de registro de peso.
    
    Attributes:
        weight: Peso (kg)
        log_date: Data do registro
        notes: Observações
        body_fat: Percentual de gordura (%)
        muscle_mass: Massa muscular (kg)
        user_id: ID do usuário
    """
    weight: float
    log_date: date = field(default_factory=date.today)
    notes: str = ""
    body_fat: float | None = None
    muscle_mass: float | None = None
    user_id: str = ""
    
    def __post_init__(self) -> None:
        """Valida os dados após a criação."""
        if self.weight <= 0:
            raise ValueError(f"Peso inválido: {self.weight}kg")
        
        if self.body_fat is not None and not (0 <= self.body_fat <= 100):
            raise ValueError(f"Percentual de gordura inválido: {self.body_fat}%")
        
        if self.muscle_mass is not None and self.muscle_mass < 0:
            raise ValueError(f"Massa muscular inválida: {self.muscle_mass}kg")


# ─────────────────────────────────────────────────────────────────────────────
# MODELO: HYDRATION_LOG (Hidratação)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class HydrationLog(SerializableMixin):
    """
    Modelo de registro de hidratação.
    
    Attributes:
        amount_ml: Quantidade (ml)
        log_time: Horário do registro (HH:MM)
        log_date: Data do registro
        source: Fonte da água (water/juice/tea/other)
        user_id: ID do usuário
    """
    amount_ml: int
    log_time: str = "12:00"
    log_date: date = field(default_factory=date.today)
    source: HydrationSource = HydrationSource.WATER
    user_id: str = ""
    
    def __post_init__(self) -> None:
        """Valida os dados após a criação."""
        if self.amount_ml <= 0:
            raise ValueError(f"Quantidade inválida: {self.amount_ml}ml")
        
        if self.amount_ml > 10000:
            raise ValueError(f"Quantidade excede o limite: {self.amount_ml}ml")
    
    @property
    def in_liters(self) -> float:
        """Retorna a quantidade em litros."""
        return self.amount_ml / 1000


# ─────────────────────────────────────────────────────────────────────────────
# MODELO: SUPPLEMENT (Suplemento)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Supplement(SerializableMixin):
    """
    Modelo de suplemento registrado.
    
    Attributes:
        name: Nome do suplemento
        dose: Dose tomada
        unit: Unidade (mg/g/ml/UI/cápsula/comprimido)
        category: Categoria (protein/vitamin/mineral/other)
        time_taken: Horário da tomada (HH:MM)
        notes: Observações
        log_date: Data do registro
        user_id: ID do usuário
    """
    name: str
    dose: str
    unit: SupplementUnit = SupplementUnit.G
    category: SupplementCategory = SupplementCategory.PROTEIN
    time_taken: str = "08:00"
    notes: str = ""
    log_date: date = field(default_factory=date.today)
    user_id: str = ""
    
    def __post_init__(self) -> None:
        """Valida os dados após a criação."""
        if not self.name.strip():
            raise ValueError("Nome do suplemento é obrigatório")
        
        if not self.dose.strip():
            raise ValueError("Dose é obrigatória")


# ─────────────────────────────────────────────────────────────────────────────
# MODELO: WORKOUT_LOG (Treino)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class WorkoutLog(SerializableMixin):
    """
    Modelo de registro de treino.
    
    Attributes:
        workout_type: Tipo de treino (strength/cardio/hiit/etc)
        muscle_group: Grupo muscular (full/chest/back/legs/etc)
        intensity: Intensidade (low/moderate/high/maximum)
        duration: Duração (minutos)
        notes: Observações
        log_date: Data do registro
        user_id: ID do usuário
    """
    workout_type: WorkoutType
    muscle_group: str = "full"
    intensity: Intensity = Intensity.MODERATE
    duration: int = 60
    notes: str = ""
    log_date: date = field(default_factory=date.today)
    user_id: str = ""
    
    def __post_init__(self) -> None:
        """Valida os dados após a criação."""
        if self.duration <= 0:
            raise ValueError(f"Duração inválida: {self.duration}min")
        
        if self.duration > 600:
            raise ValueError(f"Duração excede o limite: {self.duration}min")
    
    @property
    def intensity_label(self) -> str:
        """Retorna o rótulo da intensidade."""
        labels = {
            Intensity.LOW: "Baixa",
            Intensity.MODERATE: "Moderada",
            Intensity.HIGH: "Alta",
            Intensity.MAXIMUM: "Máxima",
        }
        return labels.get(self.intensity, self.intensity.value)


# ─────────────────────────────────────────────────────────────────────────────
# MODELO: SLEEP_LOG (Sono)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SleepLog(SerializableMixin):
    """
    Modelo de registro de sono.
    
    Attributes:
        hours: Horas de sono
        quality: Qualidade do sono (1-5)
        log_date: Data do registro
        user_id: ID do usuário
    """
    hours: float
    quality: int = 3
    log_date: date = field(default_factory=date.today)
    user_id: str = ""
    
    def __post_init__(self) -> None:
        """Valida os dados após a criação."""
        if not (0 < self.hours <= 24):
            raise ValueError(f"Horas de sono inválidas: {self.hours}")
        
        if not (1 <= self.quality <= 5):
            raise ValueError(f"Qualidade de sono inválida: {self.quality}")
    
    @property
    def is_good_quality(self) -> bool:
        """Verifica se a qualidade do sono é boa (>= 4)."""
        return self.quality >= 4
    
    @property
    def is_sufficient(self) -> bool:
        """Verifica se as horas de sono são suficientes (>= 7)."""
        return self.hours >= 7


# ─────────────────────────────────────────────────────────────────────────────
# MODELO: SYMPTOM_LOG (Sintomas)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SymptomLog(SerializableMixin):
    """
    Modelo de registro de sintomas.
    
    Attributes:
        symptom: Nome do sintoma
        severity: Severidade (1-3)
        notes: Observações
        log_date: Data do registro
        user_id: ID do usuário
    """
    symptom: str
    severity: int = 1
    notes: str = ""
    log_date: date = field(default_factory=date.today)
    user_id: str = ""
    
    def __post_init__(self) -> None:
        """Valida os dados após a criação."""
        if not self.symptom.strip():
            raise ValueError("Sintoma é obrigatório")
        
        if not (1 <= self.severity <= 3):
            raise ValueError(f"Severidade inválida: {self.severity}")
    
    def is_severe(self) -> bool:
        """Verifica se o sintoma é grave (severidade >= 2)."""
        return self.severity >= 2
    
    @property
    def severity_label(self) -> str:
        """Retorna o rótulo da severidade."""
        labels = {1: "Leve", 2: "Moderada", 3: "Grave"}
        return labels.get(self.severity, str(self.severity))


# ─────────────────────────────────────────────────────────────────────────────
# MODELO: CYCLE_LOG (Ciclo Menstrual)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CycleLog(SerializableMixin):
    """
    Modelo de registro de ciclo menstrual.
    
    Attributes:
        phase: Fase do ciclo (follicular/ovulatory/luteal/menstrual/unknown)
        flow: Fluxo (light/moderate/heavy/spotting/none)
        symptoms: Sintomas (texto livre)
        log_date: Data do registro
        user_id: ID do usuário
    """
    phase: CyclePhase = CyclePhase.UNKNOWN
    flow: CycleFlow | None = None
    symptoms: str = ""
    log_date: date = field(default_factory=date.today)
    user_id: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTS PÚBLICOS
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    # Enums
    "Gender",
    "HealthMode",
    "Plan",
    "ActivityLevel",
    "Goal",
    "Specialty",
    "MealType",
    "WorkoutType",
    "Intensity",
    "HydrationSource",
    "SupplementCategory",
    "SupplementUnit",
    "CyclePhase",
    "CycleFlow",
    # Models
    "User",
    "Professional",
    "Meal",
    "WeightLog",
    "HydrationLog",
    "Supplement",
    "WorkoutLog",
    "SleepLog",
    "SymptomLog",
    "CycleLog",
]
