"""
Melshape — Gamification Service.

Gerencia streaks, conquistas, XP, níveis, ranking e desafios semanais.
O coração do engajamento do paciente.

Princípios:
- Streak: dias consecutivos de check-in (mais preciso que refeições)
- Conquistas: badges desbloqueados automaticamente por critérios
- XP: pontos acumulados por ações (checkin, refeição, peso, hábito, etc.)
- Níveis: progressão baseada em XP acumulado
- Ranking: comparação global entre pacientes
- Desafios: objetivos semanais com recompensa em XP
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas

Views/Tabelas utilizadas:
    - experiencia_usuario: xp_total, nivel_atual_id
    - badges_usuario: badges conquistadas
    - vw_conquistas_usuario: view com nome do badge + data
    - vw_ranking_gamificacao: ranking global de XP
    - desafios, desafios_usuario: desafios ativos e progresso
    - fn_ganhar_xp (RPC): function que credita XP com segurança

Arquitetura:
    GamificationService
    ├── Streak
    │   └── streak() -> int
    ├── XP e Nível
    │   ├── total_xp() -> int
    │   └── level() -> LevelInfo
    ├── Conquistas
    │   ├── check_achievements(user) -> list[Achievement]
    │   ├── _check_activity_achievements() -> list[tuple]
    │   ├── _check_weight_achievements() -> list[tuple]
    │   └── _check_mode_achievements(user) -> list[tuple]
    ├── Desafios Semanais
    │   └── weekly_challenges() -> list[WeeklyChallenge]
    └── Dashboard Rápido
        └── quick_stats() -> GamificationStats
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import config
from core.database import Database

logger = logging.getLogger("Melshape.Gamification")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DE GAMIFICAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Achievement:
    """
    Modelo de conquista (badge).
    
    Attributes:
        name: Nome interno da conquista
        title: Título exibido ao usuário
        desc: Descrição da conquista
        xp: Pontos de experiência concedidos
        emoji: Emoji representativo
    """
    name: str
    title: str
    desc: str
    xp: int
    emoji: str = "🏆"
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Achievement:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            name=data.get("name", ""),
            title=data.get("title", ""),
            desc=data.get("desc", ""),
            xp=int(data.get("xp", 0)),
            emoji=data.get("emoji", "🏆"),
        )


@dataclass(frozen=True)
class Level:
    """
    Modelo de nível do usuário.
    
    Attributes:
        level: Número do nível
        name: Nome do nível
        min_xp: XP mínimo para alcançar este nível
        icon: Ícone representativo
    """
    level: int
    name: str
    min_xp: int
    icon: str = "⭐"
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Level:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            level=int(data.get("level", 1)),
            name=data.get("name", ""),
            min_xp=int(data.get("min_xp", 0)),
            icon=data.get("icon", "⭐"),
        )


@dataclass(frozen=True)
class WeeklyChallenge:
    """
    Modelo de desafio semanal.
    
    Attributes:
        title: Título do desafio
        xp: Pontos de experiência concedidos
        emoji: Emoji representativo
    """
    title: str
    xp: int
    emoji: str = "🎯"
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WeeklyChallenge:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            title=data.get("title", ""),
            xp=int(data.get("xp", 0)),
            emoji=data.get("emoji", "🎯"),
        )


@dataclass(frozen=True)
class LevelInfo:
    """
    Informações completas do nível atual do usuário.
    
    Attributes:
        xp: XP total acumulado
        current: Nível atual
        next: Próximo nível (ou None se máximo)
        progress_pct: Progresso percentual para o próximo nível (0-100)
    """
    xp: int
    current: Level
    next: Level | None
    progress_pct: int


@dataclass(frozen=True)
class GamificationStats:
    """
    Estatísticas consolidadas de gamificação.
    
    Attributes:
        xp: XP total
        level_name: Nome do nível atual
        level_icon: Ícone do nível
        level_number: Número do nível
        progress_pct: Progresso para próximo nível
        next_level: Nome do próximo nível (ou None)
        xp_to_next: XP necessário para próximo nível
        streak: Dias consecutivos
        total_badges: Total de conquistas desbloqueadas
    """
    xp: int
    level_name: str
    level_icon: str
    level_number: int
    progress_pct: int
    next_level: str | None
    xp_to_next: int
    streak: int
    total_badges: int


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES (referenciadas de config.py)
# ─────────────────────────────────────────────────────────────────────────────

# Converte configurações para objetos tipados
ACHIEVEMENTS: list[Achievement] = [
    Achievement.from_dict(a) for a in [
        {"name": "first_meal",       "title": "🍽️ Primeira Refeição",  "desc": "Registrou a primeira refeição!",           "xp": 50,  "emoji": "🍽️"},
        {"name": "ten_meals",        "title": "🍴 10 Refeições",        "desc": "10 refeições registradas!",                "xp": 100, "emoji": "🍴"},
        {"name": "fifty_meals",      "title": "🎖️ 50 Refeições",       "desc": "Mestre do registro!",                      "xp": 500, "emoji": "🎖️"},
        {"name": "week_streak",      "title": "📅 7 Dias Seguidos",     "desc": "Uma semana de consistência!",              "xp": 200, "emoji": "📅"},
        {"name": "month_streak",     "title": "🏆 30 Dias!",            "desc": "30 dias consecutivos. Incrível!",          "xp": 1000, "emoji": "🏆"},
        {"name": "first_weight",     "title": "⚖️ Primeira Pesagem",    "desc": "Começou a monitorar o peso!",              "xp": 50,  "emoji": "⚖️"},
        {"name": "lost_1kg",         "title": "📉 Perdeu 1 kg",         "desc": "1 kg eliminado!",                          "xp": 300, "emoji": "📉"},
        {"name": "lost_5kg",         "title": "💪 Perdeu 5 kg",         "desc": "5 kg eliminados!",                         "xp": 1000, "emoji": "💪"},
        {"name": "first_workout",    "title": "🏋️ Primeiro Treino",     "desc": "Registrou o primeiro treino!",             "xp": 50,  "emoji": "🏋️"},
        {"name": "first_supplement", "title": "💊 Suplementação",        "desc": "Registrou suplementos pela primeira vez!", "xp": 50,  "emoji": "💊"},
        {"name": "hydration_goal",   "title": "💧 Hidratação em Dia",    "desc": "Atingiu a meta de água hoje!",             "xp": 30,  "emoji": "💧"},
        {"name": "glp1_week",        "title": "💉 1 Semana GLP-1",      "desc": "Uma semana de tratamento monitorado!",     "xp": 150, "emoji": "💉"},
        {"name": "bariatric_month",  "title": "🔪 1 Mês Pós-Cirurgia",  "desc": "Um mês de acompanhamento bariátrico!",    "xp": 500, "emoji": "🔪"},
        {"name": "first_sleep",      "title": "😴 Sono Registrado",     "desc": "Começou a monitorar o sono!",              "xp": 30,  "emoji": "😴"},
        {"name": "first_checkin",    "title": "✅ Primeiro Check-in",   "desc": "Fez o primeiro check-in diário!",          "xp": 30,  "emoji": "✅"},
        {"name": "streak_checkin_7", "title": "🔥 7 Check-ins Seguidos","desc": "7 dias de check-in consecutivos!",         "xp": 150, "emoji": "🔥"},
    ]
]

LEVELS: list[Level] = [
    Level.from_dict(l) for l in [
        {"level": 1, "name": "Iniciante",   "min_xp": 0,    "icon": "🌱"},
        {"level": 2, "name": "Determinado", "min_xp": 200,  "icon": "🌿"},
        {"level": 3, "name": "Consistente", "min_xp": 500,  "icon": "🌳"},
        {"level": 4, "name": "Dedicado",    "min_xp": 1000, "icon": "⭐"},
        {"level": 5, "name": "Campeão",     "min_xp": 2000, "icon": "🏆"},
        {"level": 6, "name": "Lendário",    "min_xp": 5000, "icon": "👑"},
    ]
]

WEEKLY_CHALLENGES: list[WeeklyChallenge] = [
    WeeklyChallenge.from_dict(c) for c in [
        {"title": "Registrar 14 refeições esta semana", "xp": 50,  "emoji": "🍴"},
        {"title": "Atingir meta proteica por 3 dias",   "xp": 120, "emoji": "🥩"},
        {"title": "Beber 2L de água por 5 dias",        "xp": 80,  "emoji": "💧"},
        {"title": "Pesar-se 2 vezes esta semana",       "xp": 80,  "emoji": "⚖️"},
        {"title": "Registrar treino por 3 dias",        "xp": 100, "emoji": "🏋️"},
        {"title": "Fazer check-in por 5 dias",          "xp": 90,  "emoji": "✅"},
        {"title": "Registrar sono por 5 dias seguidos", "xp": 70,  "emoji": "😴"},
    ]
]


# ─────────────────────────────────────────────────────────────────────────────
# GAMIFICATION SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class GamificationService:
    """
    Serviço de gamificação: streaks, XP, níveis, conquistas e desafios.
    
    Example:
        >>> db = Database()
        >>> gami = GamificationService(db)
        >>> stats = gami.quick_stats()
        >>> print(f"Nível: {stats.level_name} - XP: {stats.xp}")
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o serviço de gamificação.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        logger.debug("✅ GamificationService inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # STREAK
    # ─────────────────────────────────────────────────────────────────────────

    def streak(self) -> int:
        """
        Calcula a streak atual (dias consecutivos de check-in).
        
        Returns:
            Número de dias consecutivos
            
        Example:
            >>> streak = gami.streak()
            >>> print(f"Streak: {streak} dias")
        """
        # Usa check-in streak (mais preciso)
        streak_val = self.db.get_checkin_streak()
        
        if streak_val > 0:
            logger.debug(f"✅ Streak (check-in): {streak_val} dias")
            return streak_val

        # Fallback: streak por refeições
        streak_val = self._calculate_meal_streak()
        
        logger.debug(f"✅ Streak (refeições): {streak_val} dias")
        return streak_val

    def _calculate_meal_streak(self) -> int:
        """
        Calcula streak baseado em refeições (fallback).
        
        Returns:
            Número de dias consecutivos com refeições
        """
        meals = self.db.get_meals(60)
        
        if not meals:
            logger.debug("Streak: nenhuma refeição encontrada")
            return 0

        # Extrai datas únicas ordenadas
        dates = sorted(
            set(datetime.strptime(m.meal_date, "%Y-%m-%d").date() for m in meals)
        )

        today = date.today()

        # Verifica se a última data é hoje ou ontem
        if not dates or dates[-1] not in [today, today - timedelta(days=1)]:
            logger.debug(f"Streak: última data {dates[-1] if dates else 'None'} não é hoje ou ontem")
            return 0

        # Calcula streak
        count = 1
        for i in range(len(dates) - 1, 0, -1):
            if (dates[i] - dates[i - 1]).days == 1:
                count += 1
            else:
                break

        return count

    # ─────────────────────────────────────────────────────────────────────────
    # XP E NÍVEL
    # ─────────────────────────────────────────────────────────────────────────

    def total_xp(self) -> int:
        """
        Retorna o XP total do usuário.
        
        Returns:
            XP total acumulado
            
        Example:
            >>> xp = gami.total_xp()
            >>> print(f"XP total: {xp}")
        """
        # 1. Tenta ler de experiencia_usuario (Supabase)
        xp_banco = self.db.get_xp()
        
        if xp_banco > 0:
            logger.debug(f"✅ XP total (banco): {xp_banco}")
            return xp_banco

        # 2. Fallback: soma das conquistas desbloqueadas
        earned = {a.get("achievement_name") for a in self.db.get_achievements()}
        xp = sum(a.xp for a in ACHIEVEMENTS if a.name in earned)
        
        logger.debug(f"✅ XP total (conquistas): {xp}")
        return xp

    def level(self) -> LevelInfo:
        """
        Retorna o nível atual do usuário.
        
        Returns:
            LevelInfo com xp, current, next e progress_pct
            
        Example:
            >>> level_info = gami.level()
            >>> print(f"Nível: {level_info.current.name} - {level_info.progress_pct}%")
        """
        xp = self.total_xp()
        
        # Encontra o nível atual
        current = LEVELS[0]
        for lvl in LEVELS:
            if xp >= lvl.min_xp:
                current = lvl

        # Encontra o próximo nível
        idx = LEVELS.index(current)
        next_lvl = LEVELS[idx + 1] if idx + 1 < len(LEVELS) else None

        # Calcula progresso para o próximo nível
        if next_lvl:
            progress_pct = int(
                (xp - current.min_xp) / (next_lvl.min_xp - current.min_xp) * 100
            )
        else:
            progress_pct = 100

        result = LevelInfo(
            xp=xp,
            current=current,
            next=next_lvl,
            progress_pct=progress_pct,
        )
        
        logger.debug(f"✅ Level: {current.name} (XP: {xp}, Progress: {progress_pct}%)")
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # CONQUISTAS
    # ─────────────────────────────────────────────────────────────────────────

    def check_achievements(self, user: dict[str, Any] | None = None) -> list[Achievement]:
        """
        Verifica condições e desbloqueia conquistas novas.
        
        Args:
            user: Dicionário com dados do usuário (opcional)
            
        Returns:
            Lista de conquistas desbloqueadas nesta verificação
            
        Example:
            >>> novos = gami.check_achievements(user)
            >>> for achievement in novos:
            ...     print(f"🏆 Nova conquista: {achievement.title}")
        """
        # Coleta todas as verificações
        checks = []
        checks.extend(self._check_activity_achievements())
        checks.extend(self._check_weight_achievements())
        
        if user:
            checks.extend(self._check_mode_achievements(user))
        
        # Processa verificações
        unlocked = self._process_achievement_checks(checks)
        
        if unlocked:
            logger.info(f"🎉 {len(unlocked)} nova(s) conquista(s): {[a.title for a in unlocked]}")
        
        return unlocked

    def _check_activity_achievements(self) -> list[tuple[str, str, bool]]:
        """
        Verifica conquistas baseadas em atividades gerais.
        
        Returns:
            Lista de tuplas (name, title, condition)
        """
        meals = self.db.get_meals(365)
        workouts = self.db.get_workouts(365) if hasattr(self.db, 'get_workouts') else []
        supplements = self.db.get_supplements(365)
        sleep_logs = self.db.get_sleep_logs(365) if hasattr(self.db, 'get_sleep_logs') else []
        streak_val = self.streak()
        checkin_today = self.db.get_checkin_today()
        streak_checkin = self.db.get_checkin_streak()
        
        return [
            ("first_meal", "🍽️ Primeira Refeição", len(meals) >= 1),
            ("ten_meals", "🍴 10 Refeições", len(meals) >= 10),
            ("fifty_meals", "🎖️ 50 Refeições", len(meals) >= 50),
            ("week_streak", "📅 7 Dias Seguidos", streak_val >= 7),
            ("month_streak", "🏆 30 Dias!", streak_val >= 30),
            ("first_workout", "🏋️ Primeiro Treino", len(workouts) >= 1),
            ("first_supplement", "💊 Suplementação", len(supplements) >= 1),
            ("first_sleep", "😴 Sono Registrado", len(sleep_logs) >= 1),
            ("first_checkin", "✅ Primeiro Check-in", checkin_today is not None),
            ("streak_checkin_7", "🔥 7 Check-ins Seguidos", streak_checkin >= 7),
        ]

    def _check_weight_achievements(self) -> list[tuple[str, str, bool]]:
        """
        Verifica conquistas baseadas em peso.
        
        Returns:
            Lista de tuplas (name, title, condition)
        """
        weights = self.db.get_weights(365)
        checks = []
        
        if not weights.empty:
            checks.append(("first_weight", "⚖️ Primeira Pesagem", True))
            
            if len(weights) >= 2:
                try:
                    first_weight = float(weights.iloc[0]["weight"])
                    last_weight = float(weights.iloc[-1]["weight"])
                    diff = first_weight - last_weight
                    
                    checks.append(("lost_1kg", "📉 Perdeu 1 kg", diff >= 1.0))
                    checks.append(("lost_5kg", "💪 Perdeu 5 kg", diff >= 5.0))
                except Exception as e:
                    logger.warning(f"Erro ao verificar perda de peso: {e}")
        
        return checks

    def _check_mode_achievements(self, user: dict[str, Any]) -> list[tuple[str, str, bool]]:
        """
        Verifica conquistas baseadas no modo de saúde (GLP-1, Bariátrica).
        
        Args:
            user: Dicionário com dados do usuário
            
        Returns:
            Lista de tuplas (name, title, condition)
        """
        checks = []
        
        # Verifica GLP-1
        if user.get("uses_glp1") and user.get("glp1_start_date"):
            try:
                start = datetime.strptime(user["glp1_start_date"], "%Y-%m-%d").date()
                days = (date.today() - start).days
                checks.append(("glp1_week", "💉 1 Semana GLP-1", days >= 7))
            except Exception as e:
                logger.warning(f"Erro ao verificar GLP-1: {e}")
        
        # Verifica Bariátrica
        if user.get("is_bariatric") and user.get("surgery_date"):
            try:
                start = datetime.strptime(user["surgery_date"], "%Y-%m-%d").date()
                days = (date.today() - start).days
                checks.append(("bariatric_month", "🔪 1 Mês Pós-Cirurgia", days >= 30))
            except Exception as e:
                logger.warning(f"Erro ao verificar bariátrica: {e}")
        
        return checks

    def _process_achievement_checks(self, checks: list[tuple[str, str, bool]]) -> list[Achievement]:
        """
        Processa lista de verificações e desbloqueia conquistas.
        
        Args:
            checks: Lista de tuplas (name, title, condition)
            
        Returns:
            Lista de conquistas desbloqueadas
        """
        unlocked = []
        
        for name, title, condition in checks:
            if not condition:
                continue
            
            # Desbloqueia conquista no banco
            desbloqueou = self.db.unlock_achievement(name, title)
            
            if desbloqueou:
                # Busca objeto Achievement
                achievement = next((a for a in ACHIEVEMENTS if a.name == name), None)
                
                if achievement:
                    unlocked.append(achievement)
                    
                    # Credita XP
                    if achievement.xp > 0:
                        self.db.add_xp(achievement.xp, motivo=name)
                        logger.info(f"✅ Conquista desbloqueada: {title} (+{achievement.xp} XP)")
        
        return unlocked

    # ─────────────────────────────────────────────────────────────────────────
    # DESAFIOS SEMANAIS
    # ─────────────────────────────────────────────────────────────────────────

    def weekly_challenges(self) -> list[WeeklyChallenge]:
        """
        Retorna os desafios semanais atuais.
        
        Returns:
            Lista de até 3 desafios da semana
            
        Example:
            >>> desafios = gami.weekly_challenges()
            >>> for d in desafios:
            ...     print(f"{d.emoji} {d.title} - +{d.xp} XP")
        """
        week_number = date.today().isocalendar()[1]
        start_index = week_number % len(WEEKLY_CHALLENGES)
        
        # Rotaciona desafios baseado na semana
        challenges = (WEEKLY_CHALLENGES[start_index:] + WEEKLY_CHALLENGES[:start_index])[:3]
        
        logger.debug(f"✅ Desafios semanais: {len(challenges)} desafios")
        return challenges

    # ─────────────────────────────────────────────────────────────────────────
    # DASHBOARD RÁPIDO
    # ─────────────────────────────────────────────────────────────────────────

    def quick_stats(self) -> GamificationStats:
        """
        Retorna estatísticas consolidadas para o card de gamificação na home.
        
        Returns:
            GamificationStats com todas as informações necessárias
            
        Example:
            >>> stats = gami.quick_stats()
            >>> print(f"{stats.level_icon} Nível {stats.level_number} - {stats.level_name}")
        """
        level_data = self.level()
        streak_val = self.streak()
        achievements = self.db.get_achievements()

        current = level_data.current
        next_lvl = level_data.next

        stats = GamificationStats(
            xp=level_data.xp,
            level_name=current.name,
            level_icon=current.icon,
            level_number=current.level,
            progress_pct=level_data.progress_pct,
            next_level=next_lvl.name if next_lvl else None,
            xp_to_next=(next_lvl.min_xp - level_data.xp) if next_lvl else 0,
            streak=streak_val,
            total_badges=len(achievements),
        )
        
        logger.debug(f"✅ Quick stats: Nível {stats.level_number} ({stats.level_name}), XP: {stats.xp}")
        return stats

    # ─────────────────────────────────────────────────────────────────────────
    # MÉTODOS AUXILIARES
    # ─────────────────────────────────────────────────────────────────────────

    def get_achievement_by_name(self, name: str) -> Achievement | None:
        """
        Busca uma conquista pelo nome.
        
        Args:
            name: Nome interno da conquista
            
        Returns:
            Objeto Achievement ou None
            
        Example:
            >>> achievement = gami.get_achievement_by_name("first_meal")
            >>> if achievement:
            ...     print(f"{achievement.title}: {achievement.desc}")
        """
        return next((a for a in ACHIEVEMENTS if a.name == name), None)

    def get_level_by_xp(self, xp: int) -> Level:
        """
        Determina o nível baseado no XP.
        
        Args:
            xp: XP total
            
        Returns:
            Objeto Level correspondente
            
        Example:
            >>> level = gami.get_level_by_xp(1500)
            >>> print(f"Nível: {level.name}")
        """
        current = LEVELS[0]
        for lvl in LEVELS:
            if xp >= lvl.min_xp:
                current = lvl
        return current

    def xp_to_next_level(self, current_xp: int) -> int:
        """
        Calcula XP necessário para o próximo nível.
        
        Args:
            current_xp: XP atual
            
        Returns:
            XP necessário (0 se já no nível máximo)
            
        Example:
            >>> needed = gami.xp_to_next_level(1500)
            >>> print(f"Faltam {needed} XP para o próximo nível")
        """
        current_level = self.get_level_by_xp(current_xp)
        idx = LEVELS.index(current_level)
        
        if idx + 1 >= len(LEVELS):
            return 0
        
        next_level = LEVELS[idx + 1]
        return max(0, next_level.min_xp - current_xp)


__all__ = [
    "GamificationService",
    "Achievement",
    "Level",
    "WeeklyChallenge",
    "LevelInfo",
    "GamificationStats",
    "ACHIEVEMENTS",
    "LEVELS",
    "WEEKLY_CHALLENGES",
]
