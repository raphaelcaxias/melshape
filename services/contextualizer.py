"""
Melshape — Contextualizer Engine.

Transforma dados brutos em narrativas humanas acolhedoras.
Garante que nenhum número chegue à tela sem contexto emocional.

REGRA: Nunca punir. Sempre acolher, motivar e orientar.

Princípios:
- Nunca números crus sem contexto
- Sempre acolhedor e motivacional
- Linguagem humana, não técnica
- Adaptado ao contexto (paciente vs profissional)
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para todas as entidades

Arquitetura:
    Contextualizer
    ├── Calorias
    │   └── calories(consumed, goal) -> str
    ├── Proteína
    │   └── protein(consumed, goal) -> str
    ├── Hidratação
    │   └── hydration(consumed, goal) -> str
    ├── Streak
    │   └── streak(days) -> str
    ├── Peso
    │   └── weight(current, previous, goal) -> str
    ├── Score
    │   └── score(value) -> str
    ├── Hábito
    │   └── habit(name, done, streak) -> str
    ├── Aderência
    │   └── adherence(pct, context) -> str
    ├── Risco
    │   └── risk(pct) -> str
    ├── Fase Bariátrica
    │   └── bariatric_phase(phase, days, max_ml, max_cal) -> str
    ├── GLP-1
    │   └── glp1(medication, dose, phase, adherence_pct) -> str
    ├── Recomeço
    │   └── recovery(best_streak, xp_reward) -> str
    ├── Progresso
    │   └── progress(current, target, label) -> str
    └── Mensagens Aleatórias
        ├── _random_message(messages) -> str
        └── get_motivational_message(level) -> str
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("Melshape.Contextualizer")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Thresholds gerais
_STREAK_LOW: int = 3
_STREAK_MEDIUM: int = 7
_STREAK_HIGH: int = 30
_STREAK_LEGENDARY: int = 90

_SCORE_EXCELLENT: float = 80.0
_SCORE_GOOD: float = 60.0
_SCORE_MODERATE: float = 40.0
_SCORE_LOW: float = 20.0

_ADHERENCE_EXCELLENT: float = 80.0
_ADHERENCE_GOOD: float = 60.0
_ADHERENCE_MODERATE: float = 40.0

_RISK_HIGH: float = 50.0
_RISK_MODERATE: float = 30.0

_CALORIE_NEARLY_DONE: float = 80.0
_CALORIE_HALFWAY: float = 50.0
_PROTEIN_GOOD: float = 80.0
_PROTEIN_MODERATE: float = 50.0
_HYDRATION_GOOD: float = 70.0
_HYDRATION_MODERATE: float = 40.0

_WEIGHT_SIGNIFICANT_LOSS: float = 0.5
_WEIGHT_SIGNIFICANT_GAIN: float = 0.5
_WEIGHT_GOAL_DIFF: float = 0.5

# Mensagens motivacionais
_MOTIVATIONAL_MESSAGES: dict[str, list[str]] = {
    "morning": [
        "O dia de hoje é uma tela em branco. O que você vai pintar?",
        "A consistência começa no primeiro passo do dia.",
        "Seu futuro eu agradece por cada escolha de hoje.",
    ],
    "afternoon": [
        "A metade do dia já passou. Ainda há tempo para fazer escolhas boas.",
        "Cada refeição é uma chance de nutrir seu corpo com intenção.",
        "Você já chegou até aqui — continue.",
    ],
    "evening": [
        "O dia terminou. O que você fez hoje que te aproximou do seu objetivo?",
        "O descanso também é parte do treino.",
        "Amanhã é uma nova oportunidade.",
    ],
    "streak": [
        "A consistência é mais importante que a perfeição.",
        "Você já provou que consegue. Continue.",
        "Cada dia é uma vitória.",
    ],
    "recovery": [
        "Recomeçar é parte da jornada. Você já foi mais longe antes.",
        "Todo recomeço é uma oportunidade para crescer.",
        "Sua sequência anterior prova que você consegue.",
    ],
}

# Mensagens por nível de streak
_STREAK_MESSAGES: dict[str, list[str]] = {
    "low": [
        "🌱 {days} dia(s). O hábito está começando a se formar.",
        "🌱 {days} dia(s). Você está plantando a semente da consistência.",
        "🌱 {days} dia(s). Cada dia é um passo mais perto do seu objetivo.",
    ],
    "medium": [
        "⚡ {days} dias. Você está construindo consistência real.",
        "⚡ {days} dias. O ritmo já está no seu sangue.",
        "⚡ {days} dias. Continue — o hábito está se consolidando.",
    ],
    "high": [
        "🔥 {days} dias! Você é mais consistente do que a maioria das pessoas.",
        "🔥 {days} dias! A consistência está virando parte de você.",
        "🔥 {days} dias! Você está provando que consegue.",
    ],
    "legendary": [
        "👑 {days} dias! Isso é lendário.",
        "👑 {days} dias! Você é referência de consistência.",
        "👑 {days} dias! Sua jornada inspira.",
    ],
    "zero": [
        "🌱 O primeiro passo de volta. Amanhã será mais fácil.",
        "🌱 Todo recomeço é uma nova oportunidade.",
        "🌱 Você já foi mais longe antes. Confie em você.",
    ],
}

# Mensagens por nível de score
_SCORE_NARRATIVES: dict[str, dict[str, str]] = {
    "excellent": {
        "title": "🏆 Transformação Avançada",
        "message": "Sua consistência está gerando resultados excepcionais. Você está entre os mais engajados.",
        "sub": "Mantenha o foco — você é referência!",
    },
    "good": {
        "title": "📈 Progresso Consistente",
        "message": "Você está evoluindo de forma sólida. Continue — os resultados estão chegando.",
        "sub": "Pequenos ajustes podem acelerar ainda mais.",
    },
    "moderate": {
        "title": "⚡ Caminho Certo",
        "message": "Você está no caminho certo. Pequenos ajustes vão acelerar sua transformação.",
        "sub": "Foque em um hábito por vez.",
    },
    "low": {
        "title": "🌱 Primeiros Passos",
        "message": "Cada dia que você registra é um passo real. A consistência se constrói aos poucos.",
        "sub": "Você já começou. Isso é o mais importante.",
    },
    "empty": {
        "title": "🗺️ Comece sua Jornada",
        "message": "Registre seus dados para ver seu score de transformação.",
        "sub": "O primeiro passo é o mais importante.",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class ContextLevel(str, Enum):
    """Níveis de contexto para mensagens."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    LEGENDARY = "legendary"
    ZERO = "zero"
    EMPTY = "empty"
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    
    @classmethod
    def from_streak(cls, days: int) -> ContextLevel:
        """Determina nível baseado em streak."""
        if days >= _STREAK_LEGENDARY:
            return cls.LEGENDARY
        elif days >= _STREAK_HIGH:
            return cls.HIGH
        elif days >= _STREAK_MEDIUM:
            return cls.MEDIUM
        elif days > 0:
            return cls.LOW
        return cls.ZERO
    
    @classmethod
    def from_score(cls, score: float) -> ContextLevel:
        """Determina nível baseado em score."""
        if score >= _SCORE_EXCELLENT:
            return cls.EXCELLENT
        elif score >= _SCORE_GOOD:
            return cls.GOOD
        elif score >= _SCORE_MODERATE:
            return cls.MODERATE
        elif score >= _SCORE_LOW:
            return cls.LOW
        return cls.EMPTY


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DO CONTEXTUALIZER
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ContextualMessage:
    """
    Modelo de mensagem contextual.
    
    Attributes:
        text: Texto da mensagem
        icon: Ícone representativo
        level: Nível de contexto
        emoji: Emoji adicional
    """
    text: str
    icon: str = ""
    level: ContextLevel = ContextLevel.MEDIUM
    emoji: str = ""
    
    @property
    def full_text(self) -> str:
        """Retorna texto completo com ícone."""
        if self.icon:
            return f"{self.icon} {self.text}"
        return self.text
    
    @property
    def is_positive(self) -> bool:
        """Verifica se é uma mensagem positiva."""
        return self.level in [ContextLevel.HIGH, ContextLevel.LEGENDARY, ContextLevel.EXCELLENT, ContextLevel.GOOD]


# ─────────────────────────────────────────────────────────────────────────────
# CONTEXTUALIZER
# ─────────────────────────────────────────────────────────────────────────────

class Contextualizer:
    """
    Motor de contextualização — transforma números em narrativas humanas.
    
    Example:
        >>> ctx = Contextualizer()
        >>> msg = ctx.calories(800, 2000)
        >>> print(msg)
        "Você consumiu 800 kcal. Faltam 1200 kcal — continue no ritmo."
    """

    def __init__(self) -> None:
        """Inicializa o contextualizer."""
        logger.debug("✅ Contextualizer inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # CALORIAS
    # ─────────────────────────────────────────────────────────────────────────

    def calories(self, consumed: float, goal: float) -> str:
        """
        Gera mensagem sobre consumo calórico.
        
        Args:
            consumed: Calorias consumidas
            goal: Meta calórica
            
        Returns:
            Mensagem contextual
            
        Example:
            >>> ctx.calories(800, 2000)
            "Você consumiu 800 kcal. Faltam 1200 kcal — continue no ritmo."
        """
        if goal <= 0:
            return "Acompanhe sua alimentação com atenção."

        pct = consumed / goal * 100
        remaining = max(0, goal - consumed)

        if pct >= 100:
            return (
                f"Você atingiu sua meta calórica! {consumed:.0f} kcal. "
                f"Foque na qualidade das próximas refeições."
            )
        elif pct >= _CALORIE_NEARLY_DONE:
            return (
                f"Quase lá! {consumed:.0f} kcal — "
                f"faltam {remaining:.0f} kcal para sua meta."
            )
        elif pct >= _CALORIE_HALFWAY:
            return (
                f"{consumed:.0f} kcal de {goal:.0f}. "
                f"Continue no seu ritmo — qualidade importa."
            )
        elif consumed > 0:
            return (
                f"{consumed:.0f} kcal registradas. "
                f"Lembre-se de se alimentar bem ao longo do dia."
            )
        return "Comece seu dia com uma refeição nutritiva."

    # ─────────────────────────────────────────────────────────────────────────
    # PROTEÍNA
    # ─────────────────────────────────────────────────────────────────────────

    def protein(self, consumed: float, goal: float) -> str:
        """
        Gera mensagem sobre consumo de proteína.
        
        Args:
            consumed: Proteína consumida (g)
            goal: Meta de proteína (g)
            
        Returns:
            Mensagem contextual
            
        Example:
            >>> ctx.protein(80, 150)
            "80g de 150g. Continue priorizando proteína."
        """
        if goal <= 0:
            return "A proteína é essencial para sua jornada."

        if consumed <= 0:
            return "Inclua uma fonte de proteína na próxima refeição."

        pct = consumed / goal * 100

        if pct >= _PROTEIN_GOOD:
            return (
                f"{consumed:.0f}g de {goal:.0f}g — "
                f"excelente! Isso preserva sua massa muscular."
            )
        elif pct >= _PROTEIN_MODERATE:
            return (
                f"{consumed:.0f}g de {goal:.0f}g. "
                f"Continue priorizando proteína."
            )
        return (
            f"{consumed:.0f}g de {goal:.0f}g. "
            f"Adicione uma fonte proteica na próxima refeição."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # HIDRATAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def hydration(self, consumed: float, goal: float) -> str:
        """
        Gera mensagem sobre hidratação.
        
        Args:
            consumed: Água consumida (ml)
            goal: Meta de água (ml)
            
        Returns:
            Mensagem contextual
            
        Example:
            >>> ctx.hydration(1500, 2500)
            "💧 1500ml — faltam 1000ml para a meta."
        """
        if goal <= 0:
            return "A hidratação é essencial para sua saúde."

        if consumed <= 0:
            return "💧 Comece a beber água agora. Seu corpo agradece."

        pct = consumed / goal * 100
        remaining = max(0, goal - consumed)

        if pct >= 100:
            return f"💧 Meta de água atingida! {consumed:.0f}ml — muito bem."
        elif pct >= _HYDRATION_GOOD:
            return f"💧 {consumed:.0f}ml — faltam {remaining:.0f}ml para a meta."
        elif pct >= _HYDRATION_MODERATE:
            return f"💧 {consumed:.0f}ml de {goal:.0f}ml. Continue bebendo."
        return f"💧 {consumed:.0f}ml registrados. Que tal um copo agora?"

    # ─────────────────────────────────────────────────────────────────────────
    # STREAK
    # ─────────────────────────────────────────────────────────────────────────

    def streak(self, days: int) -> str:
        """
        Gera mensagem sobre streak (dias consecutivos).
        
        Args:
            days: Dias consecutivos
            
        Returns:
            Mensagem contextual
            
        Example:
            >>> ctx.streak(0)
            "🌱 O primeiro passo de volta. Amanhã será mais fácil."
            >>> ctx.streak(15)
            "⚡ 15 dias. Você está construindo consistência real."
        """
        if days <= 0:
            return self._random_message(_STREAK_MESSAGES["zero"])
        elif days >= _STREAK_LEGENDARY:
            return self._random_message(_STREAK_MESSAGES["legendary"]).format(days=days)
        elif days >= _STREAK_HIGH:
            return self._random_message(_STREAK_MESSAGES["high"]).format(days=days)
        elif days >= _STREAK_MEDIUM:
            return self._random_message(_STREAK_MESSAGES["medium"]).format(days=days)
        else:
            return self._random_message(_STREAK_MESSAGES["low"]).format(days=days)

    # ─────────────────────────────────────────────────────────────────────────
    # PESO
    # ─────────────────────────────────────────────────────────────────────────

    def weight(
        self,
        current: float,
        previous: float | None = None,
        goal: float | None = None,
    ) -> str:
        """
        Gera mensagem sobre peso.
        
        Args:
            current: Peso atual (kg)
            previous: Peso anterior (kg) - opcional
            goal: Peso objetivo (kg) - opcional
            
        Returns:
            Mensagem contextual
            
        Example:
            >>> ctx.weight(75.0, 76.0, 70.0)
            "Seu peso atual é 75.0 kg. Você progrediu! 1.0 kg desde o último registro. Faltam 5.0 kg para sua meta."
        """
        msg = f"Seu peso atual é {current:.1f} kg."

        if previous is not None:
            diff = current - previous
            if diff < -_WEIGHT_SIGNIFICANT_LOSS:
                msg += f" Você progrediu! {abs(diff):.1f} kg desde o último registro."
            elif diff > _WEIGHT_SIGNIFICANT_GAIN:
                msg += " Pequenas variações são normais. Continue focado na consistência."
            else:
                msg += " Peso estável — a consistência está funcionando."

        if goal is not None:
            diff_g = current - goal
            if diff_g > _WEIGHT_GOAL_DIFF:
                msg += f" Faltam {diff_g:.1f} kg para sua meta — você está no caminho."
            elif diff_g <= 0:
                msg += " 🎯 Meta atingida! Mantenha o foco."

        return msg

    # ─────────────────────────────────────────────────────────────────────────
    # SCORE
    # ─────────────────────────────────────────────────────────────────────────

    def score(self, value: float) -> str:
        """
        Gera mensagem sobre score de transformação.
        
        Args:
            value: Valor do score (0-100)
            
        Returns:
            Mensagem contextual
            
        Example:
            >>> ctx.score(75)
            "Seu progresso está acima de 80% da média. Continue assim."
        """
        if value >= _SCORE_EXCELLENT:
            return (
                "Seu progresso está acima de 80% da média. "
                "Continue assim."
            )
        elif value >= _SCORE_GOOD:
            return "Você está evoluindo de forma consistente. Continue focado."
        elif value >= _SCORE_MODERATE:
            return "Você está no caminho certo. Cada dia é um passo."
        elif value >= _SCORE_LOW:
            return (
                "Continue construindo sua consistência. "
                "Pequenos passos geram grandes mudanças."
            )
        return "Começar já é uma vitória. Estamos aqui para te apoiar."

    # ─────────────────────────────────────────────────────────────────────────
    # HÁBITO
    # ─────────────────────────────────────────────────────────────────────────

    def habit(self, name: str, done: bool, streak: int = 0) -> str:
        """
        Gera mensagem sobre hábito.
        
        Args:
            name: Nome do hábito
            done: Se foi concluído hoje
            streak: Dias consecutivos
            
        Returns:
            Mensagem contextual
            
        Example:
            >>> ctx.habit("Beber água", True, 7)
            "✅ Beber água — 7 dias seguidos! Você está construindo algo sólido."
        """
        if done:
            if streak >= _STREAK_MEDIUM:
                return (
                    f"✅ {name} — {streak} dias seguidos! "
                    f"Você está construindo algo sólido."
                )
            return f"✅ {name} concluído hoje. Ótimo trabalho!"
        if streak > 0:
            return (
                f"⏳ {name} ainda pendente. "
                f"Sua sequência de {streak} dias está te esperando."
            )
        return f"⏳ {name} — que tal completar hoje?"

    # ─────────────────────────────────────────────────────────────────────────
    # ADERÊNCIA
    # ─────────────────────────────────────────────────────────────────────────

    def adherence(self, pct: float, context: str = "paciente") -> str:
        """
        Gera mensagem sobre aderência.
        
        Args:
            pct: Percentual de aderência (0-100)
            context: Contexto ("paciente" ou "profissional")
            
        Returns:
            Mensagem contextual
            
        Example:
            >>> ctx.adherence(85, "paciente")
            "85% — você está no caminho certo!"
            >>> ctx.adherence(45, "profissional")
            "45% — adesão baixa. Intervenção necessária."
        """
        if context == "profissional":
            if pct >= _ADHERENCE_EXCELLENT:
                return f"{pct:.0f}% — adesão boa. Mantenha o plano."
            elif pct >= _ADHERENCE_GOOD:
                return (
                    f"{pct:.0f}% — adesão moderada. "
                    f"Considere reforçar orientações."
                )
            return f"{pct:.0f}% — adesão baixa. Intervenção necessária."

        # paciente
        if pct >= _ADHERENCE_EXCELLENT:
            return f"{pct:.0f}% — você está no caminho certo!"
        elif pct >= _ADHERENCE_GOOD:
            return f"{pct:.0f}% — continue construindo consistência."
        elif pct >= _ADHERENCE_MODERATE:
            return f"{pct:.0f}% — cada dia conta. Não desista."
        return f"{pct:.0f}% — comece hoje. Cada passo importa."

    # ─────────────────────────────────────────────────────────────────────────
    # RISCO
    # ─────────────────────────────────────────────────────────────────────────

    def risk(self, pct: float) -> str:
        """
        Gera mensagem sobre risco de abandono.
        
        Args:
            pct: Percentual de risco (0-100)
            
        Returns:
            Mensagem contextual
            
        Example:
            >>> ctx.risk(60)
            "60% — risco alto. Ação urgente necessária."
        """
        if pct >= _RISK_HIGH:
            return f"{pct:.0f}% — risco alto. Ação urgente necessária."
        elif pct >= _RISK_MODERATE:
            return f"{pct:.0f}% — risco moderado. Monitorar de perto."
        return f"{pct:.0f}% — risco baixo. Manter estratégia."

    # ─────────────────────────────────────────────────────────────────────────
    # FASE BARIÁTRICA
    # ─────────────────────────────────────────────────────────────────────────

    def bariatric_phase(
        self,
        phase: str,
        days: int,
        max_ml: int,
        max_cal: int,
    ) -> str:
        """
        Gera mensagem sobre fase bariátrica.
        
        Args:
            phase: Nome da fase
            days: Dias pós-cirurgia
            max_ml: Volume máximo por refeição
            max_cal: Calorias máximas por dia
            
        Returns:
            Mensagem contextual
        """
        return (
            f"🔪 Fase {phase} — {days} dias pós-cirurgia. "
            f"Máx {max_ml}ml por refeição e {max_cal} kcal/dia. "
            f"Fracione as refeições e priorize proteína."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # GLP-1
    # ─────────────────────────────────────────────────────────────────────────

    def glp1(
        self,
        medication: str,
        dose: str,
        phase: str,
        adherence_pct: float,
    ) -> str:
        """
        Gera mensagem sobre tratamento GLP-1.
        
        Args:
            medication: Medicamento
            dose: Dose atual
            phase: Fase do tratamento
            adherence_pct: Percentual de adesão
            
        Returns:
            Mensagem contextual
        """
        phase_labels = {
            "adapting": "Adaptação",
            "maintenance": "Manutenção",
            "tapering": "Desmame",
            "stopped": "Parado",
        }
        phase_label = phase_labels.get(phase, phase)

        if adherence_pct >= _ADHERENCE_EXCELLENT:
            return (
                f"💉 {medication} {dose} — Fase {phase_label}. "
                f"Adesão excelente ({adherence_pct:.0f}%). Continue assim!"
            )
        elif adherence_pct >= _ADHERENCE_MODERATE:
            return (
                f"💉 {medication} {dose} — Fase {phase_label}. "
                f"Adesão {adherence_pct:.0f}%. Tente manter a regularidade."
            )
        return (
            f"💉 {medication} {dose} — Fase {phase_label}. "
            f"Adesão {adherence_pct:.0f}%. Considere ajustar a rotina de doses."
        )

    # ─────────────────────────────────────────────────────────────────────────
    # RECOMEÇO
    # ─────────────────────────────────────────────────────────────────────────

    def recovery(self, best_streak: int, xp_reward: int) -> str:
        """
        Gera mensagem para recomeço.
        
        Args:
            best_streak: Melhor streak já alcançado
            xp_reward: XP de recomeço
            
        Returns:
            Mensagem contextual
        """
        if best_streak >= _STREAK_LEGENDARY:
            icon = "👑"
            msg = f"Sua sequência lendária de {best_streak} dias prova que você tem o que é preciso."
        elif best_streak >= _STREAK_HIGH:
            icon = "🔥"
            msg = f"Sua sequência de {best_streak} dias não foi em vão. Você já provou que consegue."
        elif best_streak >= _STREAK_MEDIUM:
            icon = "💪"
            msg = f"Sua sequência de {best_streak} dias mostra sua força. Recomece com confiança."
        else:
            icon = "🌱"
            msg = "Cada recomeço é uma nova oportunidade. Você já foi mais longe antes."

        return f"{icon} {msg} +{xp_reward} XP pelo recomeço!"

    # ─────────────────────────────────────────────────────────────────────────
    # PROGRESSO
    # ─────────────────────────────────────────────────────────────────────────

    def progress(self, current: float, target: float, label: str = "") -> str:
        """
        Gera mensagem sobre progresso geral.
        
        Args:
            current: Valor atual
            target: Valor alvo
            label: Rótulo do progresso (opcional)
            
        Returns:
            Mensagem contextual
        """
        if target <= 0:
            return "Continue acompanhando seu progresso."

        pct = min(100, int(current / target * 100))

        if pct >= 100:
            return "🎯 Meta atingida! Você conseguiu!"
        elif pct >= 75:
            return f"🔥 {pct}% — quase lá! Continue firme."
        elif pct >= 50:
            return f"💪 {pct}% — metade do caminho! Você está no ritmo."
        elif pct >= 25:
            return f"🌱 {pct}% — começo sólido. Continue construindo."
        elif pct > 0:
            return f"🌱 {pct}% — primeiros passos. Cada dia conta."
        return f"🌱 Comece sua jornada. O primeiro passo é o mais importante."

    # ─────────────────────────────────────────────────────────────────────────
    # MENSAGENS MOTIVACIONAIS
    # ─────────────────────────────────────────────────────────────────────────

    def get_motivational_message(self, level: str = "morning") -> str:
        """
        Retorna uma mensagem motivacional aleatória.
        
        Args:
            level: Nível da mensagem (morning/afternoon/evening/streak/recovery)
            
        Returns:
            Mensagem motivacional
        """
        messages = _MOTIVATIONAL_MESSAGES.get(level, _MOTIVATIONAL_MESSAGES["morning"])
        return random.choice(messages)

    def get_streak_message(self, days: int) -> str:
        """
        Retorna mensagem específica para streak.
        
        Args:
            days: Dias consecutivos
            
        Returns:
            Mensagem de streak
        """
        level = ContextLevel.from_streak(days)
        return self.streak(days)

    def get_score_narrative(self, score: float) -> dict[str, str]:
        """
        Retorna narrativa completa do score.
        
        Args:
            score: Valor do score (0-100)
            
        Returns:
            Dicionário com title, message, sub
            
        Example:
            >>> ctx.get_score_narrative(75)
            {
                "title": "📈 Progresso Consistente",
                "message": "Você está evoluindo de forma sólida...",
                "sub": "Pequenos ajustes podem acelerar ainda mais."
            }
        """
        level = ContextLevel.from_score(score)
        key = level.value if level.value in _SCORE_NARRATIVES else "empty"
        return _SCORE_NARRATIVES[key]

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _random_message(self, messages: list[str]) -> str:
        """Retorna uma mensagem aleatória da lista."""
        return random.choice(messages) if messages else ""

    def format_with_name(self, message: str, name: str) -> str:
        """
        Formata mensagem com nome do usuário.
        
        Args:
            message: Mensagem base
            name: Nome do usuário
            
        Returns:
            Mensagem personalizada
        """
        if not name:
            return message
        return message.replace("{name}", name).replace("{Name}", name.capitalize())

    def get_time_based_greeting(self) -> str:
        """
        Retorna saudação baseada no horário.
        
        Returns:
            Saudação (Bom dia/Boa tarde/Boa noite)
        """
        from datetime import datetime
        hour = datetime.now().hour
        if hour < 12:
            return "Bom dia"
        elif hour < 18:
            return "Boa tarde"
        return "Boa noite"


# ─────────────────────────────────────────────────────────────────────────────
# INSTÂNCIA GLOBAL
# ─────────────────────────────────────────────────────────────────────────────

ctx = Contextualizer()


__all__ = [
    "Contextualizer",
    "ContextLevel",
    "ContextualMessage",
    "ctx",
]
