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
    ├── Core Methods (retornam ContextualMessage)
    │   ├── calories(consumed, goal) -> ContextualMessage
    │   ├── protein(consumed, goal) -> ContextualMessage
    │   ├── hydration(consumed, goal) -> ContextualMessage
    │   ├── streak(days) -> ContextualMessage
    │   ├── weight(current, previous, goal) -> ContextualMessage
    │   ├── score(value) -> ContextualMessage
    │   ├── habit(name, done, streak) -> ContextualMessage
    │   ├── adherence(pct, context) -> ContextualMessage
    │   ├── risk(pct) -> ContextualMessage
    │   ├── bariatric_phase(phase, days, max_ml, max_cal) -> ContextualMessage
    │   ├── glp1(medication, dose, phase, adherence_pct) -> ContextualMessage
    │   ├── recovery(best_streak, xp_reward) -> ContextualMessage
    │   └── progress(current, target, label) -> ContextualMessage
    ├── Extended Methods
    │   ├── get_welcome_message(user) -> ContextualMessage
    │   ├── get_farewell_message(user) -> ContextualMessage
    │   ├── get_achievement_message(achievement_name) -> ContextualMessage
    │   ├── get_health_alert(alert_type, severity) -> ContextualMessage
    │   ├── get_goal_progress_message(goal_name, progress_pct) -> ContextualMessage
    │   ├── get_temporal_comparison(current, previous, label) -> ContextualMessage
    │   ├── get_time_based_message() -> ContextualMessage
    │   ├── get_reflection_message() -> ContextualMessage
    │   ├── get_celebration_message(reason) -> ContextualMessage
    │   ├── get_emotional_support(situation) -> ContextualMessage
    │   └── get_reminder_message(task, urgency) -> ContextualMessage
    ├── Utilities
    │   ├── format_contextual(text, level) -> ContextualMessage
    │   ├── combine_messages(messages) -> ContextualMessage
    │   ├── get_context_summary(data) -> ContextualMessage
    │   ├── format_with_name(message, name) -> str
    │   └── get_time_based_greeting() -> str
    └── Helpers
        ├── _random_message(messages) -> str
        ├── _calculate_percentage(current, target) -> float
        └── _determine_tone(level) -> str
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
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

# Progress thresholds
_PROGRESS_COMPLETE: float = 100.0
_PROGRESS_ALMOST: float = 75.0
_PROGRESS_HALFWAY: float = 50.0
_PROGRESS_QUARTER: float = 25.0


# ─────────────────────────────────────────────────────────────────────────────
# MENSAGENS MOTIVACIONAIS
# ─────────────────────────────────────────────────────────────────────────────

_MOTIVATIONAL_MESSAGES: dict[str, list[str]] = {
    "morning": [
        "O dia de hoje é uma tela em branco. O que você vai pintar?",
        "A consistência começa no primeiro passo do dia.",
        "Seu futuro eu agradece por cada escolha de hoje.",
        "Cada manhã é uma nova oportunidade de ser melhor.",
        "Comece o dia com intenção. Pequenas escolhas, grandes resultados.",
    ],
    "afternoon": [
        "A metade do dia já passou. Ainda há tempo para fazer escolhas boas.",
        "Cada refeição é uma chance de nutrir seu corpo com intenção.",
        "Você já chegou até aqui — continue.",
        "O meio do dia é um bom momento para reavaliar e ajustar.",
        "Mantenha o foco. Você está no caminho certo.",
    ],
    "evening": [
        "O dia terminou. O que você fez hoje que te aproximou do seu objetivo?",
        "O descanso também é parte do treino.",
        "Amanhã é uma nova oportunidade.",
        "Celebre as pequenas vitórias de hoje.",
        "O descanso é essencial para a transformação.",
    ],
    "streak": [
        "A consistência é mais importante que a perfeição.",
        "Você já provou que consegue. Continue.",
        "Cada dia é uma vitória.",
        "Sua dedicação está construindo algo sólido.",
        "O hábito está se formando. Não pare agora.",
    ],
    "recovery": [
        "Recomeçar é parte da jornada. Você já foi mais longe antes.",
        "Todo recomeço é uma oportunidade para crescer.",
        "Sua sequência anterior prova que você consegue.",
        "Cair não é fracasso. Ficar no chão é.",
        "Levante-se. Seu futuro eu está te esperando.",
    ],
    "challenge": [
        "Desafios são oportunidades disfarçadas.",
        "Você é mais forte do que pensa.",
        "Cada obstáculo é um degrau para o próximo nível.",
        "A dificuldade de hoje é a força de amanhã.",
        "Confie no processo. Você está evoluindo.",
    ],
    "celebration": [
        "Você merece celebrar cada conquista, por menor que seja.",
        "Reconheça seu esforço. Você está fazendo um ótimo trabalho.",
        "Cada passo conta. Cada vitória importa.",
        "Orgulhe-se do seu progresso. Você está no caminho certo.",
        "Suas escolhas estão transformando sua vida.",
    ],
}

_STREAK_MESSAGES: dict[str, list[str]] = {
    "low": [
        "🌱 {days} dia(s). O hábito está começando a se formar.",
        "🌱 {days} dia(s). Você está plantando a semente da consistência.",
        "🌱 {days} dia(s). Cada dia é um passo mais perto do seu objetivo.",
        "🌱 {days} dia(s). O começo é sempre o mais difícil. Continue!",
    ],
    "medium": [
        "⚡ {days} dias. Você está construindo consistência real.",
        "⚡ {days} dias. O ritmo já está no seu sangue.",
        "⚡ {days} dias. Continue — o hábito está se consolidando.",
        "⚡ {days} dias. Você está no caminho da transformação.",
    ],
    "high": [
        "🔥 {days} dias! Você é mais consistente do que a maioria das pessoas.",
        "🔥 {days} dias! A consistência está virando parte de você.",
        "🔥 {days} dias! Você está provando que consegue.",
        "🔥 {days} dias! Sua dedicação é inspiradora.",
    ],
    "legendary": [
        "👑 {days} dias! Isso é lendário.",
        "👑 {days} dias! Você é referência de consistência.",
        "👑 {days} dias! Sua jornada inspira.",
        "👑 {days} dias! Você entrou para a história.",
    ],
    "zero": [
        "🌱 O primeiro passo de volta. Amanhã será mais fácil.",
        "🌱 Todo recomeço é uma nova oportunidade.",
        "🌱 Você já foi mais longe antes. Confie em você.",
        "🌱 Recomeçar é um ato de coragem. Você é corajoso(a).",
    ],
}

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

_ACHIEVEMENT_MESSAGES: list[str] = [
    "🏆 Conquista desbloqueada! Você está construindo algo incrível.",
    "🎉 Parabéns! Mais uma conquista na sua jornada.",
    "⭐ Você conseguiu! Continue colecionando vitórias.",
    "🌟 Conquista desbloqueada! Seu esforço está valendo a pena.",
    "🏅 Mais uma conquista! Você está no caminho certo.",
]

_WELCOME_MESSAGES: list[str] = [
    "Bem-vindo(a) de volta! Pronto(a) para mais um dia de progresso?",
    "Que bom te ver! Vamos fazer hoje contar?",
    "Olá! Cada dia é uma nova oportunidade. Vamos juntos?",
    "Bem-vindo(a)! Seu progresso é nossa prioridade.",
    "Que bom te ver de novo! Continue firme na sua jornada.",
]

_FAREWELL_MESSAGES: list[str] = [
    "Até amanhã! Descanse bem — você merece.",
    "Bom descanso! Amanhã tem mais.",
    "Até logo! Continue firme na sua jornada.",
    "Cuide-se! Amanhã é mais um dia de progresso.",
    "Até a próxima! Você está no caminho certo.",
]

_HEALTH_ALERTS: dict[str, list[str]] = {
    "low_calorie": [
        "⚠️ Sua ingestão calórica está baixa. Considere fazer uma refeição nutritiva.",
        "⚠️ Você precisa de mais energia. Não pule refeições.",
        "⚠️ Alimente-se bem. Seu corpo precisa de combustível.",
    ],
    "high_calorie": [
        "⚠️ Você excedeu sua meta calórica. Não se preocupe — amanhã é um novo dia.",
        "⚠️ Calorias acima da meta. Foque na qualidade das próximas refeições.",
        "⚠️ Meta calórica ultrapassada. Continue no ritmo amanhã.",
    ],
    "low_protein": [
        "⚠️ Proteína baixa hoje. Inclua uma fonte proteica na próxima refeição.",
        "⚠️ Você precisa de mais proteína. Isso é essencial para sua jornada.",
        "⚠️ Proteína insuficiente. Priorize alimentos proteicos.",
    ],
    "dehydration": [
        "⚠️ Você está desidratado(a). Beba água agora!",
        "⚠️ Hidratação baixa. Seu corpo precisa de água.",
        "⚠️ Beba mais água. Isso faz diferença no seu progresso.",
    ],
    "no_checkin": [
        "⚠️ Você ainda não fez check-in hoje. Não quebre sua sequência!",
        "⚠️ Check-in pendente. Seu futuro eu agradece.",
        "⚠️ Faça seu check-in. É rápido e importante.",
    ],
}

_REFLECTION_MESSAGES: list[str] = [
    "O que você aprendeu hoje sobre si mesmo(a)?",
    "Qual foi sua maior vitória hoje, por menor que seja?",
    "O que você faria diferente se pudesse voltar no tempo?",
    "Como você se sente em relação ao seu progresso?",
    "O que te motivou hoje? E o que te desafiou?",
]

_CELEBRATION_MESSAGES: dict[str, list[str]] = {
    "streak": [
        "🎉 Parabéns pela sua sequência! Você é incrível!",
        "🎊 Sua consistência é inspiradora. Continue assim!",
        "🌟 Você está construindo algo sólido. Celebre essa conquista!",
    ],
    "goal": [
        "🎯 Meta alcançada! Você conseguiu! Orgulhe-se do seu esforço.",
        "🏆 Parabéns! Mais uma meta conquistada. Você é demais!",
        "⭐ Você alcançou seu objetivo! Continue colecionando vitórias.",
    ],
    "weight": [
        "⚖️ Peso ideal alcançado! Você é uma inspiração!",
        "🎉 Parabéns pelo peso objetivo! Seu esforço valeu a pena!",
        "🏆 Você atingiu seu peso meta! Celebre essa conquista!",
    ],
    "general": [
        "🎉 Parabéns! Você está fazendo um trabalho incrível!",
        "🌟 Continue assim! Você está no caminho certo!",
        "🏆 Seu progresso é admirável. Celebre cada vitória!",
    ],
}

_EMOTIONAL_SUPPORT: dict[str, list[str]] = [
    "Está tudo bem ter dias difíceis. O importante é não desistir.",
    "Você não está sozinho(a) nessa jornada. Estamos aqui para te apoiar.",
    "Cada dia é uma nova oportunidade. Amanhã será melhor.",
    "Seja gentil consigo mesmo(a). Você está fazendo o seu melhor.",
    "Dias difíceis fazem parte da jornada. Você vai superar isso.",
    "Respire fundo. Você já superou coisas piores antes.",
    "Não se compare com os outros. Sua jornada é única.",
    "Está tudo bem não estar bem o tempo todo. Cuide de você.",
]

_REMINDER_MESSAGES: dict[str, list[str]] = {
    "alta": [
        "⏰ Lembrete importante: {task}. Não esqueça!",
        "⏰ Atenção: {task}. Isso é prioridade!",
        "⏰ Não esqueça: {task}. Seu futuro eu agradece!",
    ],
    "media": [
        "🔔 Lembrete: {task}. Quando puder, cuide disso.",
        "🔔 Não esqueça: {task}. Faz diferença no seu progresso.",
        "🔔 Lembrete amigável: {task}. Você consegue!",
    ],
    "baixa": [
        "💡 Sugestão: {task}. Quando tiver um tempinho.",
        "💡 Lembrete leve: {task}. Sem pressão!",
        "💡 Dica: {task}. Pode ser útil para você.",
    ],
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
    
    @classmethod
    def from_percentage(cls, pct: float) -> ContextLevel:
        """Determina nível baseado em percentual."""
        if pct >= 80:
            return cls.EXCELLENT
        elif pct >= 60:
            return cls.GOOD
        elif pct >= 40:
            return cls.MODERATE
        elif pct >= 20:
            return cls.LOW
        return cls.EMPTY


class MessageTone(str, Enum):
    """Tons de mensagem."""
    ENCOURAGING = "encouraging"
    CELEBRATORY = "celebratory"
    SUPPORTIVE = "supportive"
    INFORMATIVE = "informative"
    URGENT = "urgent"
    REFLECTIVE = "reflective"
    
    @property
    def icon(self) -> str:
        """Retorna ícone do tom."""
        icons = {
            "encouraging": "💪",
            "celebratory": "🎉",
            "supportive": "🤗",
            "informative": "ℹ️",
            "urgent": "⚠️",
            "reflective": "🤔",
        }
        return icons.get(self.value, "💬")


class MessageUrgency(str, Enum):
    """Níveis de urgência."""
    LOW = "baixa"
    MEDIUM = "media"
    HIGH = "alta"
    
    @property
    def icon(self) -> str:
        """Retorna ícone da urgência."""
        icons = {
            "baixa": "💡",
            "media": "🔔",
            "alta": "⏰",
        }
        return icons.get(self.value, "💬")


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
        tone: Tom da mensagem
        urgency: Urgência da mensagem
        title: Título opcional
        subtitle: Subtítulo opcional
    """
    text: str
    icon: str = ""
    level: ContextLevel = ContextLevel.MEDIUM
    emoji: str = ""
    tone: MessageTone = MessageTone.INFORMATIVE
    urgency: MessageUrgency = MessageUrgency.LOW
    title: str = ""
    subtitle: str = ""
    
    @property
    def full_text(self) -> str:
        """Retorna texto completo com ícone."""
        parts = []
        if self.icon:
            parts.append(self.icon)
        if self.title:
            parts.append(self.title)
        parts.append(self.text)
        if self.subtitle:
            parts.append(self.subtitle)
        return " ".join(parts)
    
    @property
    def display_text(self) -> str:
        """Retorna texto para exibição (com emoji se houver)."""
        if self.emoji:
            return f"{self.emoji} {self.full_text}"
        return self.full_text
    
    @property
    def is_positive(self) -> bool:
        """Verifica se é uma mensagem positiva."""
        return self.level in [
            ContextLevel.HIGH,
            ContextLevel.LEGENDARY,
            ContextLevel.EXCELLENT,
            ContextLevel.GOOD,
        ]
    
    @property
    def is_neutral(self) -> bool:
        """Verifica se é uma mensagem neutra."""
        return self.level in [ContextLevel.MEDIUM, ContextLevel.MODERATE]
    
    @property
    def is_negative(self) -> bool:
        """Verifica se é uma mensagem negativa."""
        return self.level in [ContextLevel.LOW, ContextLevel.ZERO, ContextLevel.EMPTY]
    
    @property
    def is_encouraging(self) -> bool:
        """Verifica se é uma mensagem encorajadora."""
        return self.tone == MessageTone.ENCOURAGING
    
    @property
    def is_celebratory(self) -> bool:
        """Verifica se é uma mensagem celebratória."""
        return self.tone == MessageTone.CELEBRATORY
    
    @property
    def is_supportive(self) -> bool:
        """Verifica se é uma mensagem de suporte."""
        return self.tone == MessageTone.SUPPORTIVE
    
    @property
    def is_urgent(self) -> bool:
        """Verifica se é uma mensagem urgente."""
        return self.urgency == MessageUrgency.HIGH
    
    @property
    def color(self) -> str:
        """Retorna cor CSS baseada no nível."""
        colors = {
            ContextLevel.EXCELLENT: "var(--success)",
            ContextLevel.GOOD: "var(--primary)",
            ContextLevel.MODERATE: "var(--warning)",
            ContextLevel.LOW: "var(--info)",
            ContextLevel.ZERO: "var(--text-muted)",
            ContextLevel.EMPTY: "var(--text-muted)",
        }
        return colors.get(self.level, "var(--text)")
    
    @property
    def tone_label(self) -> str:
        """Retorna label do tom."""
        labels = {
            MessageTone.ENCOURAGING: "Encorajador",
            MessageTone.CELEBRATORY: "Celebratório",
            MessageTone.SUPPORTIVE: "Acolhedor",
            MessageTone.INFORMATIVE: "Informativo",
            MessageTone.URGENT: "Urgente",
            MessageTone.REFLECTIVE: "Reflexivo",
        }
        return labels.get(self.tone, "Informativo")
    
    @property
    def urgency_label(self) -> str:
        """Retorna label da urgência."""
        labels = {
            MessageUrgency.LOW: "Baixa",
            MessageUrgency.MEDIUM: "Média",
            MessageUrgency.HIGH: "Alta",
        }
        return labels.get(self.urgency, "Baixa")


# ─────────────────────────────────────────────────────────────────────────────
# CONTEXTUALIZER
# ─────────────────────────────────────────────────────────────────────────────

class Contextualizer:
    """
    Motor de contextualização — transforma números em narrativas humanas.
    
    Example:
        >>> ctx = Contextualizer()
        >>> msg = ctx.calories(800, 2000)
        >>> print(msg.full_text)
        "Você consumiu 800 kcal. Faltam 1200 kcal — continue no ritmo."
    """

    def __init__(self) -> None:
        """Inicializa o contextualizer."""
        logger.debug("✅ Contextualizer inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # CORE METHODS (retornam ContextualMessage)
    # ─────────────────────────────────────────────────────────────────────────

    def calories(self, consumed: float, goal: float) -> ContextualMessage:
        """
        Gera mensagem sobre consumo calórico.
        
        Args:
            consumed: Calorias consumidas
            goal: Meta calórica
            
        Returns:
            ContextualMessage com mensagem contextual
            
        Example:
            >>> msg = ctx.calories(800, 2000)
            >>> print(msg.full_text)
        """
        if goal <= 0:
            return self.format_contextual(
                "Acompanhe sua alimentação com atenção.",
                ContextLevel.EMPTY,
            )

        pct = self._calculate_percentage(consumed, goal)
        remaining = max(0, goal - consumed)

        if pct >= 100:
            text = (
                f"Você atingiu sua meta calórica! {consumed:.0f} kcal. "
                f"Foque na qualidade das próximas refeições."
            )
            level = ContextLevel.EXCELLENT
            tone = MessageTone.CELEBRATORY
        elif pct >= _CALORIE_NEARLY_DONE:
            text = (
                f"Quase lá! {consumed:.0f} kcal — "
                f"faltam {remaining:.0f} kcal para sua meta."
            )
            level = ContextLevel.GOOD
            tone = MessageTone.ENCOURAGING
        elif pct >= _CALORIE_HALFWAY:
            text = (
                f"{consumed:.0f} kcal de {goal:.0f}. "
                f"Continue no seu ritmo — qualidade importa."
            )
            level = ContextLevel.MODERATE
            tone = MessageTone.ENCOURAGING
        elif consumed > 0:
            text = (
                f"{consumed:.0f} kcal registradas. "
                f"Lembre-se de se alimentar bem ao longo do dia."
            )
            level = ContextLevel.LOW
            tone = MessageTone.INFORMATIVE
        else:
            text = "Comece seu dia com uma refeição nutritiva."
            level = ContextLevel.EMPTY
            tone = MessageTone.ENCOURAGING

        return ContextualMessage(
            text=text,
            icon="🍽️",
            level=level,
            tone=tone,
        )

    def protein(self, consumed: float, goal: float) -> ContextualMessage:
        """
        Gera mensagem sobre consumo de proteína.
        
        Args:
            consumed: Proteína consumida (g)
            goal: Meta de proteína (g)
            
        Returns:
            ContextualMessage com mensagem contextual
        """
        if goal <= 0:
            return self.format_contextual(
                "A proteína é essencial para sua jornada.",
                ContextLevel.EMPTY,
            )

        if consumed <= 0:
            return ContextualMessage(
                text="Inclua uma fonte de proteína na próxima refeição.",
                icon="🥩",
                level=ContextLevel.EMPTY,
                tone=MessageTone.ENCOURAGING,
            )

        pct = self._calculate_percentage(consumed, goal)

        if pct >= _PROTEIN_GOOD:
            text = (
                f"{consumed:.0f}g de {goal:.0f}g — "
                f"excelente! Isso preserva sua massa muscular."
            )
            level = ContextLevel.EXCELLENT
            tone = MessageTone.CELEBRATORY
        elif pct >= _PROTEIN_MODERATE:
            text = (
                f"{consumed:.0f}g de {goal:.0f}g. "
                f"Continue priorizando proteína."
            )
            level = ContextLevel.GOOD
            tone = MessageTone.ENCOURAGING
        else:
            text = (
                f"{consumed:.0f}g de {goal:.0f}g. "
                f"Adicione uma fonte proteica na próxima refeição."
            )
            level = ContextLevel.LOW
            tone = MessageTone.ENCOURAGING

        return ContextualMessage(
            text=text,
            icon="🥩",
            level=level,
            tone=tone,
        )

    def hydration(self, consumed: float, goal: float) -> ContextualMessage:
        """
        Gera mensagem sobre hidratação.
        
        Args:
            consumed: Água consumida (ml)
            goal: Meta de água (ml)
            
        Returns:
            ContextualMessage com mensagem contextual
        """
        if goal <= 0:
            return self.format_contextual(
                "A hidratação é essencial para sua saúde.",
                ContextLevel.EMPTY,
            )

        if consumed <= 0:
            return ContextualMessage(
                text="Comece a beber água agora. Seu corpo agradece.",
                icon="💧",
                level=ContextLevel.EMPTY,
                tone=MessageTone.ENCOURAGING,
            )

        pct = self._calculate_percentage(consumed, goal)
        remaining = max(0, goal - consumed)

        if pct >= 100:
            text = f"Meta de água atingida! {consumed:.0f}ml — muito bem."
            level = ContextLevel.EXCELLENT
            tone = MessageTone.CELEBRATORY
        elif pct >= _HYDRATION_GOOD:
            text = f"{consumed:.0f}ml — faltam {remaining:.0f}ml para a meta."
            level = ContextLevel.GOOD
            tone = MessageTone.ENCOURAGING
        elif pct >= _HYDRATION_MODERATE:
            text = f"{consumed:.0f}ml de {goal:.0f}ml. Continue bebendo."
            level = ContextLevel.MODERATE
            tone = MessageTone.ENCOURAGING
        else:
            text = f"{consumed:.0f}ml registrados. Que tal um copo agora?"
            level = ContextLevel.LOW
            tone = MessageTone.ENCOURAGING

        return ContextualMessage(
            text=text,
            icon="💧",
            level=level,
            tone=tone,
        )

    def streak(self, days: int) -> ContextualMessage:
        """
        Gera mensagem sobre streak (dias consecutivos).
        
        Args:
            days: Dias consecutivos
            
        Returns:
            ContextualMessage com mensagem contextual
        """
        level = ContextLevel.from_streak(days)
        
        if days <= 0:
            text = self._random_message(_STREAK_MESSAGES["zero"])
        elif days >= _STREAK_LEGENDARY:
            text = self._random_message(_STREAK_MESSAGES["legendary"]).format(days=days)
        elif days >= _STREAK_HIGH:
            text = self._random_message(_STREAK_MESSAGES["high"]).format(days=days)
        elif days >= _STREAK_MEDIUM:
            text = self._random_message(_STREAK_MESSAGES["medium"]).format(days=days)
        else:
            text = self._random_message(_STREAK_MESSAGES["low"]).format(days=days)

        tone = MessageTone.CELEBRATORY if days > 0 else MessageTone.SUPPORTIVE

        return ContextualMessage(
            text=text,
            icon="🔥",
            level=level,
            tone=tone,
        )

    def weight(
        self,
        current: float,
        previous: float | None = None,
        goal: float | None = None,
    ) -> ContextualMessage:
        """
        Gera mensagem sobre peso.
        
        Args:
            current: Peso atual (kg)
            previous: Peso anterior (kg) - opcional
            goal: Peso objetivo (kg) - opcional
            
        Returns:
            ContextualMessage com mensagem contextual
        """
        msg = f"Seu peso atual é {current:.1f} kg."
        level = ContextLevel.MODERATE
        tone = MessageTone.INFORMATIVE

        if previous is not None:
            diff = current - previous
            if diff < -_WEIGHT_SIGNIFICANT_LOSS:
                msg += f" Você progrediu! {abs(diff):.1f} kg desde o último registro."
                level = ContextLevel.GOOD
                tone = MessageTone.CELEBRATORY
            elif diff > _WEIGHT_SIGNIFICANT_GAIN:
                msg += " Pequenas variações são normais. Continue focado na consistência."
                level = ContextLevel.MODERATE
                tone = MessageTone.SUPPORTIVE
            else:
                msg += " Peso estável — a consistência está funcionando."
                level = ContextLevel.GOOD
                tone = MessageTone.ENCOURAGING

        if goal is not None:
            diff_g = current - goal
            if diff_g > _WEIGHT_GOAL_DIFF:
                msg += f" Faltam {diff_g:.1f} kg para sua meta — você está no caminho."
            elif diff_g <= 0:
                msg += " 🎯 Meta atingida! Mantenha o foco."
                level = ContextLevel.EXCELLENT
                tone = MessageTone.CELEBRATORY

        return ContextualMessage(
            text=msg,
            icon="⚖️",
            level=level,
            tone=tone,
        )

    def score(self, value: float) -> ContextualMessage:
        """
        Gera mensagem sobre score de transformação.
        
        Args:
            value: Valor do score (0-100)
            
        Returns:
            ContextualMessage com mensagem contextual
        """
        level = ContextLevel.from_score(value)
        
        if value >= _SCORE_EXCELLENT:
            text = "Seu progresso está acima de 80% da média. Continue assim."
            tone = MessageTone.CELEBRATORY
        elif value >= _SCORE_GOOD:
            text = "Você está evoluindo de forma consistente. Continue focado."
            tone = MessageTone.ENCOURAGING
        elif value >= _SCORE_MODERATE:
            text = "Você está no caminho certo. Cada dia é um passo."
            tone = MessageTone.ENCOURAGING
        elif value >= _SCORE_LOW:
            text = "Continue construindo sua consistência. Pequenos passos geram grandes mudanças."
            tone = MessageTone.ENCOURAGING
        else:
            text = "Começar já é uma vitória. Estamos aqui para te apoiar."
            tone = MessageTone.SUPPORTIVE

        return ContextualMessage(
            text=text,
            icon="📊",
            level=level,
            tone=tone,
        )

    def habit(self, name: str, done: bool, streak: int = 0) -> ContextualMessage:
        """
        Gera mensagem sobre hábito.
        
        Args:
            name: Nome do hábito
            done: Se foi concluído hoje
            streak: Dias consecutivos
            
        Returns:
            ContextualMessage com mensagem contextual
        """
        if done:
            if streak >= _STREAK_MEDIUM:
                text = (
                    f"{name} — {streak} dias seguidos! "
                    f"Você está construindo algo sólido."
                )
                level = ContextLevel.HIGH
                tone = MessageTone.CELEBRATORY
            else:
                text = f"{name} concluído hoje. Ótimo trabalho!"
                level = ContextLevel.GOOD
                tone = MessageTone.CELEBRATORY
            icon = "✅"
        else:
            if streak > 0:
                text = (
                    f"{name} ainda pendente. "
                    f"Sua sequência de {streak} dias está te esperando."
                )
                level = ContextLevel.MODERATE
            else:
                text = f"{name} — que tal completar hoje?"
                level = ContextLevel.LOW
            icon = "⏳"
            tone = MessageTone.ENCOURAGING

        return ContextualMessage(
            text=text,
            icon=icon,
            level=level,
            tone=tone,
        )

    def adherence(self, pct: float, context: str = "paciente") -> ContextualMessage:
        """
        Gera mensagem sobre aderência.
        
        Args:
            pct: Percentual de aderência (0-100)
            context: Contexto ("paciente" ou "profissional")
            
        Returns:
            ContextualMessage com mensagem contextual
        """
        level = ContextLevel.from_percentage(pct)
        
        if context == "profissional":
            if pct >= _ADHERENCE_EXCELLENT:
                text = f"{pct:.0f}% — adesão boa. Mantenha o plano."
                tone = MessageTone.INFORMATIVE
            elif pct >= _ADHERENCE_GOOD:
                text = f"{pct:.0f}% — adesão moderada. Considere reforçar orientações."
                tone = MessageTone.INFORMATIVE
            else:
                text = f"{pct:.0f}% — adesão baixa. Intervenção necessária."
                tone = MessageTone.URGENT
        else:  # paciente
            if pct >= _ADHERENCE_EXCELLENT:
                text = f"{pct:.0f}% — você está no caminho certo!"
                tone = MessageTone.CELEBRATORY
            elif pct >= _ADHERENCE_GOOD:
                text = f"{pct:.0f}% — continue construindo consistência."
                tone = MessageTone.ENCOURAGING
            elif pct >= _ADHERENCE_MODERATE:
                text = f"{pct:.0f}% — cada dia conta. Não desista."
                tone = MessageTone.ENCOURAGING
            else:
                text = f"{pct:.0f}% — comece hoje. Cada passo importa."
                tone = MessageTone.SUPPORTIVE

        return ContextualMessage(
            text=text,
            icon="📈",
            level=level,
            tone=tone,
        )

    def risk(self, pct: float) -> ContextualMessage:
        """
        Gera mensagem sobre risco de abandono.
        
        Args:
            pct: Percentual de risco (0-100)
            
        Returns:
            ContextualMessage com mensagem contextual
        """
        if pct >= _RISK_HIGH:
            text = f"{pct:.0f}% — risco alto. Ação urgente necessária."
            level = ContextLevel.LOW
            tone = MessageTone.URGENT
            urgency = MessageUrgency.HIGH
        elif pct >= _RISK_MODERATE:
            text = f"{pct:.0f}% — risco moderado. Monitorar de perto."
            level = ContextLevel.MODERATE
            tone = MessageTone.INFORMATIVE
            urgency = MessageUrgency.MEDIUM
        else:
            text = f"{pct:.0f}% — risco baixo. Manter estratégia."
            level = ContextLevel.GOOD
            tone = MessageTone.INFORMATIVE
            urgency = MessageUrgency.LOW

        return ContextualMessage(
            text=text,
            icon="⚠️",
            level=level,
            tone=tone,
            urgency=urgency,
        )

    def bariatric_phase(
        self,
        phase: str,
        days: int,
        max_ml: int,
        max_cal: int,
    ) -> ContextualMessage:
        """
        Gera mensagem sobre fase bariátrica.
        
        Args:
            phase: Nome da fase
            days: Dias pós-cirurgia
            max_ml: Volume máximo por refeição
            max_cal: Calorias máximas por dia
            
        Returns:
            ContextualMessage com mensagem contextual
        """
        text = (
            f"Fase {phase} — {days} dias pós-cirurgia. "
            f"Máx {max_ml}ml por refeição e {max_cal} kcal/dia. "
            f"Fracione as refeições e priorize proteína."
        )

        return ContextualMessage(
            text=text,
            icon="🔪",
            level=ContextLevel.MODERATE,
            tone=MessageTone.INFORMATIVE,
        )

    def glp1(
        self,
        medication: str,
        dose: str,
        phase: str,
        adherence_pct: float,
    ) -> ContextualMessage:
        """
        Gera mensagem sobre tratamento GLP-1.
        
        Args:
            medication: Medicamento
            dose: Dose atual
            phase: Fase do tratamento
            adherence_pct: Percentual de adesão
            
        Returns:
            ContextualMessage com mensagem contextual
        """
        phase_labels = {
            "adapting": "Adaptação",
            "maintenance": "Manutenção",
            "tapering": "Desmame",
            "stopped": "Parado",
        }
        phase_label = phase_labels.get(phase, phase)

        if adherence_pct >= _ADHERENCE_EXCELLENT:
            text = (
                f"{medication} {dose} — Fase {phase_label}. "
                f"Adesão excelente ({adherence_pct:.0f}%). Continue assim!"
            )
            level = ContextLevel.EXCELLENT
            tone = MessageTone.CELEBRATORY
        elif adherence_pct >= _ADHERENCE_MODERATE:
            text = (
                f"{medication} {dose} — Fase {phase_label}. "
                f"Adesão {adherence_pct:.0f}%. Tente manter a regularidade."
            )
            level = ContextLevel.GOOD
            tone = MessageTone.ENCOURAGING
        else:
            text = (
                f"{medication} {dose} — Fase {phase_label}. "
                f"Adesão {adherence_pct:.0f}%. Considere ajustar a rotina de doses."
            )
            level = ContextLevel.LOW
            tone = MessageTone.ENCOURAGING

        return ContextualMessage(
            text=text,
            icon="💉",
            level=level,
            tone=tone,
        )

    def recovery(self, best_streak: int, xp_reward: int) -> ContextualMessage:
        """
        Gera mensagem para recomeço.
        
        Args:
            best_streak: Melhor streak já alcançado
            xp_reward: XP de recomeço
            
        Returns:
            ContextualMessage com mensagem contextual
        """
        if best_streak >= _STREAK_LEGENDARY:
            icon = "👑"
            msg = f"Sua sequência lendária de {best_streak} dias prova que você tem o que é preciso."
            level = ContextLevel.LEGENDARY
        elif best_streak >= _STREAK_HIGH:
            icon = "🔥"
            msg = f"Sua sequência de {best_streak} dias não foi em vão. Você já provou que consegue."
            level = ContextLevel.HIGH
        elif best_streak >= _STREAK_MEDIUM:
            icon = "💪"
            msg = f"Sua sequência de {best_streak} dias mostra sua força. Recomece com confiança."
            level = ContextLevel.MEDIUM
        else:
            icon = "🌱"
            msg = "Cada recomeço é uma nova oportunidade. Você já foi mais longe antes."
            level = ContextLevel.LOW

        text = f"{msg} +{xp_reward} XP pelo recomeço!"

        return ContextualMessage(
            text=text,
            icon=icon,
            level=level,
            tone=MessageTone.SUPPORTIVE,
        )

    def progress(self, current: float, target: float, label: str = "") -> ContextualMessage:
        """
        Gera mensagem sobre progresso geral.
        
        Args:
            current: Valor atual
            target: Valor alvo
            label: Rótulo do progresso (opcional)
            
        Returns:
            ContextualMessage com mensagem contextual
        """
        if target <= 0:
            return self.format_contextual(
                "Continue acompanhando seu progresso.",
                ContextLevel.EMPTY,
            )

        pct = min(100, int(self._calculate_percentage(current, target)))
        level = ContextLevel.from_percentage(pct)

        if pct >= _PROGRESS_COMPLETE:
            text = "🎯 Meta atingida! Você conseguiu!"
            tone = MessageTone.CELEBRATORY
        elif pct >= _PROGRESS_ALMOST:
            text = f"🔥 {pct}% — quase lá! Continue firme."
            tone = MessageTone.ENCOURAGING
        elif pct >= _PROGRESS_HALFWAY:
            text = f"💪 {pct}% — metade do caminho! Você está no ritmo."
            tone = MessageTone.ENCOURAGING
        elif pct >= _PROGRESS_QUARTER:
            text = f"🌱 {pct}% — começo sólido. Continue construindo."
            tone = MessageTone.ENCOURAGING
        elif pct > 0:
            text = f"🌱 {pct}% — primeiros passos. Cada dia conta."
            tone = MessageTone.ENCOURAGING
        else:
            text = "🌱 Comece sua jornada. O primeiro passo é o mais importante."
            tone = MessageTone.SUPPORTIVE

        return ContextualMessage(
            text=text,
            icon="📊",
            level=level,
            tone=tone,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # EXTENDED METHODS
    # ─────────────────────────────────────────────────────────────────────────

    def get_welcome_message(self, user: dict[str, Any] | Any = None) -> ContextualMessage:
        """
        Retorna mensagem de boas-vindas.
        
        Args:
            user: Dados do usuário (opcional)
            
        Returns:
            ContextualMessage com mensagem de boas-vindas
        """
        text = self._random_message(_WELCOME_MESSAGES)
        
        if user:
            name = self._extract_name(user)
            if name:
                text = self.format_with_name(text, name)

        return ContextualMessage(
            text=text,
            icon="👋",
            level=ContextLevel.GOOD,
            tone=MessageTone.ENCOURAGING,
        )

    def get_farewell_message(self, user: dict[str, Any] | Any = None) -> ContextualMessage:
        """
        Retorna mensagem de despedida.
        
        Args:
            user: Dados do usuário (opcional)
            
        Returns:
            ContextualMessage com mensagem de despedida
        """
        text = self._random_message(_FAREWELL_MESSAGES)
        
        if user:
            name = self._extract_name(user)
            if name:
                text = self.format_with_name(text, name)

        return ContextualMessage(
            text=text,
            icon="🌙",
            level=ContextLevel.GOOD,
            tone=MessageTone.SUPPORTIVE,
        )

    def get_achievement_message(self, achievement_name: str) -> ContextualMessage:
        """
        Retorna mensagem de conquista desbloqueada.
        
        Args:
            achievement_name: Nome da conquista
            
        Returns:
            ContextualMessage com mensagem de conquista
        """
        text = self._random_message(_ACHIEVEMENT_MESSAGES)
        text = f"{achievement_name} — {text}"

        return ContextualMessage(
            text=text,
            icon="🏆",
            level=ContextLevel.EXCELLENT,
            tone=MessageTone.CELEBRATORY,
        )

    def get_health_alert(
        self,
        alert_type: str,
        severity: str = "media",
    ) -> ContextualMessage:
        """
        Retorna alerta de saúde.
        
        Args:
            alert_type: Tipo de alerta (low_calorie/high_calorie/low_protein/dehydration/no_checkin)
            severity: Severidade (baixa/media/alta)
            
        Returns:
            ContextualMessage com alerta de saúde
        """
        messages = _HEALTH_ALERTS.get(alert_type, _HEALTH_ALERTS["no_checkin"])
        text = self._random_message(messages)
        
        urgency_map = {
            "baixa": MessageUrgency.LOW,
            "media": MessageUrgency.MEDIUM,
            "alta": MessageUrgency.HIGH,
        }
        urgency = urgency_map.get(severity, MessageUrgency.MEDIUM)

        return ContextualMessage(
            text=text,
            icon="⚠️",
            level=ContextLevel.LOW,
            tone=MessageTone.URGENT,
            urgency=urgency,
        )

    def get_goal_progress_message(
        self,
        goal_name: str,
        progress_pct: float,
    ) -> ContextualMessage:
        """
        Retorna mensagem de progresso de meta.
        
        Args:
            goal_name: Nome da meta
            progress_pct: Percentual de progresso (0-100)
            
        Returns:
            ContextualMessage com mensagem de progresso
        """
        return self.progress(progress_pct, 100, goal_name)

    def get_temporal_comparison(
        self,
        current: float,
        previous: float,
        label: str = "",
    ) -> ContextualMessage:
        """
        Retorna mensagem de comparação temporal.
        
        Args:
            current: Valor atual
            previous: Valor anterior
            label: Rótulo (opcional)
            
        Returns:
            ContextualMessage com comparação
        """
        diff = current - previous
        pct_change = self._calculate_percentage(abs(diff), abs(previous)) if previous != 0 else 0

        if diff > 0:
            text = f"{label + ': ' if label else ''}{current:.1f} — aumento de {abs(diff):.1f} ({pct_change:.1f}%)"
            level = ContextLevel.GOOD
            tone = MessageTone.CELEBRATORY
        elif diff < 0:
            text = f"{label + ': ' if label else ''}{current:.1f} — redução de {abs(diff):.1f} ({pct_change:.1f}%)"
            level = ContextLevel.MODERATE
            tone = MessageTone.INFORMATIVE
        else:
            text = f"{label + ': ' if label else ''}{current:.1f} — estável"
            level = ContextLevel.GOOD
            tone = MessageTone.ENCOURAGING

        return ContextualMessage(
            text=text,
            icon="📊",
            level=level,
            tone=tone,
        )

    def get_time_based_message(self) -> ContextualMessage:
        """
        Retorna mensagem baseada no horário do dia.
        
        Returns:
            ContextualMessage com mensagem do período
        """
        hour = datetime.now().hour
        
        if hour < 12:
            period = "morning"
            icon = "🌅"
        elif hour < 18:
            period = "afternoon"
            icon = "☀️"
        else:
            period = "evening"
            icon = "🌙"

        messages = _MOTIVATIONAL_MESSAGES.get(period, _MOTIVATIONAL_MESSAGES["morning"])
        text = self._random_message(messages)

        return ContextualMessage(
            text=text,
            icon=icon,
            level=ContextLevel.GOOD,
            tone=MessageTone.ENCOURAGING,
        )

    def get_reflection_message(self) -> ContextualMessage:
        """
        Retorna mensagem de reflexão.
        
        Returns:
            ContextualMessage com pergunta reflexiva
        """
        text = self._random_message(_REFLECTION_MESSAGES)

        return ContextualMessage(
            text=text,
            icon="🤔",
            level=ContextLevel.MODERATE,
            tone=MessageTone.REFLECTIVE,
        )

    def get_celebration_message(self, reason: str = "general") -> ContextualMessage:
        """
        Retorna mensagem de celebração.
        
        Args:
            reason: Motivo da celebração (streak/goal/weight/general)
            
        Returns:
            ContextualMessage com mensagem de celebração
        """
        messages = _CELEBRATION_MESSAGES.get(reason, _CELEBRATION_MESSAGES["general"])
        text = self._random_message(messages)

        return ContextualMessage(
            text=text,
            icon="🎉",
            level=ContextLevel.EXCELLENT,
            tone=MessageTone.CELEBRATORY,
        )

    def get_emotional_support(self, situation: str = "general") -> ContextualMessage:
        """
        Retorna mensagem de suporte emocional.
        
        Args:
            situation: Situação (opcional)
            
        Returns:
            ContextualMessage com mensagem de suporte
        """
        text = self._random_message(_EMOTIONAL_SUPPORT)

        return ContextualMessage(
            text=text,
            icon="🤗",
            level=ContextLevel.MODERATE,
            tone=MessageTone.SUPPORTIVE,
        )

    def get_reminder_message(
        self,
        task: str,
        urgency: str = "media",
    ) -> ContextualMessage:
        """
        Retorna mensagem de lembrete.
        
        Args:
            task: Tarefa a ser lembrada
            urgency: Urgência (baixa/media/alta)
            
        Returns:
            ContextualMessage com lembrete
        """
        messages = _REMINDER_MESSAGES.get(urgency, _REMINDER_MESSAGES["media"])
        text = self._random_message(messages).format(task=task)
        
        urgency_map = {
            "baixa": MessageUrgency.LOW,
            "media": MessageUrgency.MEDIUM,
            "alta": MessageUrgency.HIGH,
        }
        urgency_enum = urgency_map.get(urgency, MessageUrgency.MEDIUM)

        return ContextualMessage(
            text=text,
            icon=urgency_enum.icon,
            level=ContextLevel.MODERATE,
            tone=MessageTone.INFORMATIVE,
            urgency=urgency_enum,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────────────────────

    def format_contextual(
        self,
        text: str,
        level: ContextLevel = ContextLevel.MEDIUM,
        icon: str = "",
        tone: MessageTone = MessageTone.INFORMATIVE,
    ) -> ContextualMessage:
        """
        Formata texto como ContextualMessage.
        
        Args:
            text: Texto da mensagem
            level: Nível de contexto
            icon: Ícone (opcional)
            tone: Tom da mensagem
            
        Returns:
            ContextualMessage formatado
        """
        return ContextualMessage(
            text=text,
            icon=icon,
            level=level,
            tone=tone,
        )

    def combine_messages(self, messages: list[ContextualMessage]) -> ContextualMessage:
        """
        Combina múltiplas mensagens em uma.
        
        Args:
            messages: Lista de ContextualMessage
            
        Returns:
            ContextualMessage combinado
        """
        if not messages:
            return self.format_contextual("", ContextLevel.EMPTY)
        
        if len(messages) == 1:
            return messages[0]
        
        # Combina textos
        texts = [msg.text for msg in messages if msg.text]
        combined_text = " ".join(texts)
        
        # Usa o nível mais alto
        levels = [msg.level for msg in messages]
        highest_level = max(levels, key=lambda x: self._level_priority(x))
        
        # Usa o ícone do primeiro
        icon = messages[0].icon if messages[0].icon else ""

        return ContextualMessage(
            text=combined_text,
            icon=icon,
            level=highest_level,
            tone=messages[0].tone,
        )

    def get_context_summary(self, data: dict[str, Any]) -> ContextualMessage:
        """
        Gera resumo contextual baseado em dados.
        
        Args:
            data: Dicionário com dados (calories, protein, hydration, streak, etc)
            
        Returns:
            ContextualMessage com resumo
        """
        parts = []
        
        if "calories" in data and "calorie_goal" in data:
            cal_msg = self.calories(data["calories"], data["calorie_goal"])
            parts.append(cal_msg.text)
        
        if "protein" in data and "protein_goal" in data:
            prot_msg = self.protein(data["protein"], data["protein_goal"])
            parts.append(prot_msg.text)
        
        if "hydration" in data and "hydration_goal" in data:
            hyd_msg = self.hydration(data["hydration"], data["hydration_goal"])
            parts.append(hyd_msg.text)
        
        if "streak" in data:
            streak_msg = self.streak(data["streak"])
            parts.append(streak_msg.text)
        
        combined_text = " | ".join(parts) if parts else "Continue acompanhando seu progresso."
        
        return ContextualMessage(
            text=combined_text,
            icon="📊",
            level=ContextLevel.MODERATE,
            tone=MessageTone.INFORMATIVE,
        )

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
        hour = datetime.now().hour
        if hour < 12:
            return "Bom dia"
        elif hour < 18:
            return "Boa tarde"
        return "Boa noite"

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _random_message(self, messages: list[str]) -> str:
        """Retorna uma mensagem aleatória da lista."""
        return random.choice(messages) if messages else ""

    def _calculate_percentage(self, current: float, target: float) -> float:
        """
        Calcula percentual de forma segura.
        
        Args:
            current: Valor atual
            target: Valor alvo
            
        Returns:
            Percentual (0-100)
        """
        if target <= 0:
            return 0.0
        return (current / target) * 100

    def _level_priority(self, level: ContextLevel) -> int:
        """
        Retorna prioridade do nível (para comparação).
        
        Args:
            level: Nível de contexto
            
        Returns:
            Prioridade (0-10)
        """
        priorities = {
            ContextLevel.LEGENDARY: 10,
            ContextLevel.EXCELLENT: 9,
            ContextLevel.HIGH: 8,
            ContextLevel.GOOD: 7,
            ContextLevel.MEDIUM: 6,
            ContextLevel.MODERATE: 5,
            ContextLevel.LOW: 4,
            ContextLevel.ZERO: 3,
            ContextLevel.EMPTY: 2,
        }
        return priorities.get(level, 5)

    def _extract_name(self, user: dict[str, Any] | Any) -> str:
        """
        Extrai nome do usuário.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            Primeiro nome ou string vazia
        """
        if isinstance(user, dict):
            name = user.get("name", "")
        else:
            name = getattr(user, "name", "") if hasattr(user, "name") else ""
        
        if name:
            return name.split()[0]
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# INSTÂNCIA GLOBAL
# ─────────────────────────────────────────────────────────────────────────────

ctx = Contextualizer()


__all__ = [
    "Contextualizer",
    "ContextLevel",
    "ContextualMessage",
    "MessageTone",
    "MessageUrgency",
    "ctx",
]
