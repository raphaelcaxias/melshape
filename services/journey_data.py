"""
Melshape — Journey Data.

Dados de referência das jornadas por pilar.
Importado por JourneyService.

Fornece:
  - Etapas por pilar (general, fitness, bariatric, glp1)
  - Nomes das jornadas
  - Funções de acesso otimizadas (get_stages, get_journey_name, get_pillars)

Estrutura de uma etapa:
    Stage(
        ordem: int,
        nome: str,
        descricao: str,
        icone: str,
        criterios: list[str]
    )

Princípios:
- Imutabilidade: dataclasses frozen para todas as entidades
- Tipagem forte: Enum para pilares, dataclass para etapas
- Validação: dados validados no carregamento
- Cache: consultas frequentes são cacheadas
- Consistência: nomenclatura uniforme (tudo em inglês)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Any

logger = logging.getLogger("Melshape.JourneyData")


# ─────────────────────────────────────────────────────────────────────────────
# TIPOS
# ─────────────────────────────────────────────────────────────────────────────

class Pillar(str, Enum):
    """Pilares de jornada disponíveis."""
    GENERAL = "general"
    FITNESS = "fitness"
    BARIATRIC = "bariatric"
    GLP1 = "glp1"
    
    @property
    def icon(self) -> str:
        """Retorna ícone do pilar."""
        return {
            Pillar.GENERAL: "⚖️",
            Pillar.FITNESS: "💪",
            Pillar.BARIATRIC: "🔪",
            Pillar.GLP1: "💉",
        }[self]
    
    @property
    def label(self) -> str:
        """Retorna label do pilar."""
        return {
            Pillar.GENERAL: "Emagrecimento",
            Pillar.FITNESS: "Fitness",
            Pillar.BARIATRIC: "Pós-Bariátrica",
            Pillar.GLP1: "GLP-1",
        }[self]
    
    @property
    def journey_name(self) -> str:
        """Retorna nome da jornada."""
        return {
            Pillar.GENERAL: "Jornada de Emagrecimento",
            Pillar.FITNESS: "Jornada Fitness",
            Pillar.BARIATRIC: "Jornada Pós-Bariátrica",
            Pillar.GLP1: "Jornada GLP-1",
        }[self]


@dataclass(frozen=True)
class Stage:
    """
    Etapa de uma jornada.
    
    Attributes:
        ordem: Número da etapa (1-based)
        nome: Nome da etapa
        descricao: Descrição detalhada
        icone: Ícone visual (emoji)
        criterios: Lista de critérios de conclusão
    """
    ordem: int
    nome: str
    descricao: str
    icone: str
    criterios: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário (compatibilidade retroativa)."""
        return {
            "ordem": self.ordem,
            "nome": self.nome,
            "descricao": self.descricao,
            "icone": self.icone,
            "criterios": self.criterios.copy(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# DADOS DAS JORNADAS
# ─────────────────────────────────────────────────────────────────────────────

_STAGES: dict[Pillar, list[Stage]] = {
    Pillar.GENERAL: [
        Stage(
            ordem=1,
            nome="Primeiros Passos",
            descricao="Configure seu perfil e registre os primeiros dados.",
            icone="🌱",
            criterios=["Perfil completo", "1ª pesagem", "1º check-in"],
        ),
        Stage(
            ordem=2,
            nome="Construindo o Hábito",
            descricao="7 dias consecutivos de check-in.",
            icone="🔥",
            criterios=["7 check-ins seguidos", "7 refeições registradas"],
        ),
        Stage(
            ordem=3,
            nome="Consistência Real",
            descricao="30 dias de acompanhamento ativo.",
            icone="📈",
            criterios=["30 dias de check-in", "Meta de água 5x"],
        ),
        Stage(
            ordem=4,
            nome="Transformação Visível",
            descricao="Resultado mensurável e consistência sólida.",
            icone="⭐",
            criterios=["Perda de 3kg", "Nível 4 alcançado"],
        ),
        Stage(
            ordem=5,
            nome="Novo Padrão de Vida",
            descricao="90 dias. Os hábitos já são parte de você.",
            icone="🏆",
            criterios=["90 dias ativos", "Badge Lendário"],
        ),
    ],
    Pillar.FITNESS: [
        Stage(
            ordem=1,
            nome="Linha de Base",
            descricao="Avalie sua composição corporal inicial.",
            icone="📊",
            criterios=["Medidas iniciais", "1º treino registrado"],
        ),
        Stage(
            ordem=2,
            nome="Rotina Estabelecida",
            descricao="3 treinos por semana por 2 semanas.",
            icone="🏋️",
            criterios=["6 treinos em 14 dias", "Meta proteica 5x"],
        ),
        Stage(
            ordem=3,
            nome="Progressão de Carga",
            descricao="Evolução mensurável de força ou volume.",
            icone="💪",
            criterios=["30 dias de treino", "Aumento de carga"],
        ),
        Stage(
            ordem=4,
            nome="Composição em Foco",
            descricao="Redução de gordura com manutenção de massa.",
            icone="📉",
            criterios=["Gordura reduzida 2%", "Massa mantida"],
        ),
        Stage(
            ordem=5,
            nome="Alta Performance",
            descricao="90 dias de evolução contínua.",
            icone="🥇",
            criterios=["90 dias ativos", "Nível 5 alcançado"],
        ),
    ],
    Pillar.BARIATRIC: [
        Stage(
            ordem=1,
            nome="Adaptação Alimentar",
            descricao="Fase líquida — foco em hidratação e volume.",
            icone="💧",
            criterios=["Volume diário controlado", "Suplementos registrados"],
        ),
        Stage(
            ordem=2,
            nome="Evolução da Textura",
            descricao="Progressão para alimentos pastosos e brandos.",
            icone="🥄",
            criterios=["14 dias na fase", "Proteína meta 5x"],
        ),
        Stage(
            ordem=3,
            nome="Reintrodução Sólida",
            descricao="Alimentação sólida fracionada.",
            icone="🍽️",
            criterios=["30 dias pós-cirurgia", "Sem intolerâncias"],
        ),
        Stage(
            ordem=4,
            nome="Hábitos Permanentes",
            descricao="6 meses de acompanhamento e novos hábitos.",
            icone="🌿",
            criterios=["6 meses de registro", "Peso estabilizado"],
        ),
        Stage(
            ordem=5,
            nome="Nova Vida",
            descricao="1 ano pós-cirurgia com saúde e autonomia.",
            icone="🌟",
            criterios=["1 ano de acompanhamento", "Exames em dia"],
        ),
    ],
    Pillar.GLP1: [
        Stage(
            ordem=1,
            nome="Início do Tratamento",
            descricao="Primeira dose registrada e protocolo ativo.",
            icone="💉",
            criterios=["Dose registrada", "Perfil GLP-1 completo"],
        ),
        Stage(
            ordem=2,
            nome="Adaptação",
            descricao="Primeiras semanas — monitorar sintomas e adesão.",
            icone="🔬",
            criterios=["7 dias de adesão", "Sintomas monitorados"],
        ),
        Stage(
            ordem=3,
            nome="Ajuste de Dose",
            descricao="Dose estabilizada e alimentação adaptada.",
            icone="⚖️",
            criterios=["30 dias de tratamento", "Proteína meta 10x"],
        ),
        Stage(
            ordem=4,
            nome="Resultados Visíveis",
            descricao="Perda de peso consistente com tratamento ativo.",
            icone="📉",
            criterios=["Perda de 5%", "60 dias de adesão"],
        ),
        Stage(
            ordem=5,
            nome="Manutenção Comportamental",
            descricao="Hábitos sólidos que sustentam o tratamento.",
            icone="🏆",
            criterios=["90 dias", "Hábitos estabelecidos"],
        ),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# VALIDAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

def _validate_stages() -> None:
    """Valida integridade dos dados de etapas no carregamento."""
    for pillar, stages in _STAGES.items():
        if not stages:
            logger.error(f"Pilar {pillar.value} não tem etapas")
            continue
        
        # Verifica se ordens são sequenciais começando em 1
        ordens = [s.ordem for s in stages]
        expected = list(range(1, len(stages) + 1))
        if ordens != expected:
            logger.error(
                f"Pilar {pillar.value}: ordens inválidas {ordens}, "
                f"esperado {expected}"
            )
        
        # Verifica se não há nomes vazios
        for stage in stages:
            if not stage.nome or not stage.descricao:
                logger.error(
                    f"Pilar {pillar.value}, etapa {stage.ordem}: "
                    f"nome ou descrição vazios"
                )


# Executa validação no import
_validate_stages()


# ─────────────────────────────────────────────────────────────────────────────
# FUNÇÕES DE ACESSO (com cache)
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_pillar(pillar: str | Pillar) -> Pillar:
    """Converte string para Pillar enum de forma segura."""
    if isinstance(pillar, Pillar):
        return pillar
    try:
        return Pillar(pillar)
    except ValueError:
        logger.warning(f"Pilar inválido: {pillar}, usando GENERAL")
        return Pillar.GENERAL


@lru_cache(maxsize=32)
def get_stages(pillar: str | Pillar) -> list[Stage]:
    """
    Retorna as etapas de um pilar.
    
    Args:
        pillar: Nome do pilar (string ou enum Pillar)
    
    Returns:
        Lista de etapas do pilar (cópia para evitar mutação)
    
    Example:
        >>> stages = get_stages("general")
        >>> len(stages)
        5
        >>> stages[0].nome
        'Primeiros Passos'
    """
    pillar_enum = _normalize_pillar(pillar)
    return _STAGES[pillar_enum].copy()


@lru_cache(maxsize=32)
def get_journey_name(pillar: str | Pillar) -> str:
    """
    Retorna o nome da jornada para um pilar.
    
    Args:
        pillar: Nome do pilar (string ou enum Pillar)
    
    Returns:
        Nome da jornada
    
    Example:
        >>> get_journey_name("fitness")
        'Jornada Fitness'
    """
    pillar_enum = _normalize_pillar(pillar)
    return pillar_enum.journey_name


@lru_cache(maxsize=1)
def get_pillars() -> list[Pillar]:
    """
    Retorna lista de pilares disponíveis.
    
    Returns:
        Lista de enums Pillar
    
    Example:
        >>> pillars = get_pillars()
        >>> Pillar.GENERAL in pillars
        True
    """
    return list(_STAGES.keys())


@lru_cache(maxsize=32)
def get_pillar_icon(pillar: str | Pillar) -> str:
    """
    Retorna o ícone de um pilar.
    
    Args:
        pillar: Nome do pilar (string ou enum Pillar)
    
    Returns:
        Ícone do pilar (emoji)
    
    Example:
        >>> get_pillar_icon("glp1")
        '💉'
    """
    pillar_enum = _normalize_pillar(pillar)
    return pillar_enum.icon


@lru_cache(maxsize=32)
def get_pillar_label(pillar: str | Pillar) -> str:
    """
    Retorna o label de um pilar.
    
    Args:
        pillar: Nome do pilar (string ou enum Pillar)
    
    Returns:
        Label do pilar
    
    Example:
        >>> get_pillar_label("bariatric")
        'Pós-Bariátrica'
    """
    pillar_enum = _normalize_pillar(pillar)
    return pillar_enum.label


@lru_cache(maxsize=128)
def get_stage_by_ordem(pillar: str | Pillar, ordem: int) -> Stage | None:
    """
    Retorna uma etapa específica de um pilar.
    
    Args:
        pillar: Nome do pilar (string ou enum Pillar)
        ordem: Número da etapa (1-5)
    
    Returns:
        Etapa ou None se não encontrada
    
    Example:
        >>> stage = get_stage_by_ordem("general", 1)
        >>> stage.nome
        'Primeiros Passos'
    """
    pillar_enum = _normalize_pillar(pillar)
    stages = _STAGES[pillar_enum]
    
    # Busca por índice (ordem é 1-based, lista é 0-based)
    if 1 <= ordem <= len(stages):
        return stages[ordem - 1]
    return None


@lru_cache(maxsize=128)
def get_next_stage(pillar: str | Pillar, current_ordem: int) -> Stage | None:
    """
    Retorna a próxima etapa de um pilar.
    
    Args:
        pillar: Nome do pilar (string ou enum Pillar)
        current_ordem: Ordem da etapa atual
    
    Returns:
        Próxima etapa ou None se for a última
    
    Example:
        >>> next_stage = get_next_stage("general", 2)
        >>> next_stage.nome
        'Consistência Real'
    """
    return get_stage_by_ordem(pillar, current_ordem + 1)


@lru_cache(maxsize=32)
def get_pillar_summary(pillar: str | Pillar) -> dict[str, Any]:
    """
    Retorna um resumo completo do pilar.
    
    Args:
        pillar: Nome do pilar (string ou enum Pillar)
    
    Returns:
        Dicionário com nome, ícone, label, total_etapas e etapas
    
    Example:
        >>> summary = get_pillar_summary("fitness")
        >>> summary["nome"]
        'Jornada Fitness'
        >>> summary["total_etapas"]
        5
    """
    pillar_enum = _normalize_pillar(pillar)
    stages = get_stages(pillar_enum)
    
    return {
        "nome": pillar_enum.journey_name,
        "icone": pillar_enum.icon,
        "label": pillar_enum.label,
        "total_etapas": len(stages),
        "etapas": [s.to_dict() for s in stages],
    }


def get_total_stages(pillar: str | Pillar) -> int:
    """
    Retorna o total de etapas de um pilar.
    
    Args:
        pillar: Nome do pilar (string ou enum Pillar)
    
    Returns:
        Total de etapas
    
    Example:
        >>> get_total_stages("general")
        5
    """
    return len(get_stages(pillar))


# ─────────────────────────────────────────────────────────────────────────────
# UTILITÁRIOS
# ─────────────────────────────────────────────────────────────────────────────

def is_valid_pillar(pillar: str) -> bool:
    """
    Verifica se um pilar é válido.
    
    Args:
        pillar: Nome do pilar
    
    Returns:
        True se válido, False caso contrário
    
    Example:
        >>> is_valid_pillar("general")
        True
        >>> is_valid_pillar("invalid")
        False
    """
    try:
        Pillar(pillar)
        return True
    except ValueError:
        return False


def get_pillar_from_string(pillar_str: str) -> Pillar:
    """
    Converte string para Pillar enum com validação.
    
    Args:
        pillar_str: String do pilar
    
    Returns:
        Enum Pillar
    
    Raises:
        ValueError: Se o pilar for inválido
    
    Example:
        >>> get_pillar_from_string("fitness")
        <Pillar.FITNESS: 'fitness'>
    """
    return Pillar(pillar_str)


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTS
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    # Tipos
    "Pillar",
    "Stage",
    # Funções de acesso
    "get_stages",
    "get_journey_name",
    "get_pillars",
    "get_pillar_icon",
    "get_pillar_label",
    "get_stage_by_ordem",
    "get_next_stage",
    "get_pillar_summary",
    "get_total_stages",
    # Utilitários
    "is_valid_pillar",
    "get_pillar_from_string",
]


# ─────────────────────────────────────────────────────────────────────────────
# COMPAT SHIMS — suporte a código legado que usa _ETAPAS[health_mode]
# ─────────────────────────────────────────────────────────────────────────────

class _EtapasProxy:
    """Proxy que permite _ETAPAS[pillar] e _ETAPAS.get(pillar, default)."""

    def __getitem__(self, key: str) -> list[dict]:
        return [s.__dict__ for s in get_stages(key)]

    def get(self, key: str, default=None) -> list[dict]:
        try:
            stages = get_stages(key)
            return [s.__dict__ for s in stages] if stages else (default or [])
        except Exception:
            return default or []


class _NomesProxy:
    """Proxy que permite _NOMES_JORNADA[pillar] e _NOMES_JORNADA.get(pillar, default)."""

    def __getitem__(self, key: str) -> str:
        return get_journey_name(key)

    def get(self, key: str, default: str = "Minha Jornada") -> str:
        try:
            return get_journey_name(key) or default
        except Exception:
            return default


_ETAPAS = _EtapasProxy()
_NOMES_JORNADA = _NomesProxy()
