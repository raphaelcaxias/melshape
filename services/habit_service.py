"""
Melshape — Habit Service.

Serviço para gerenciamento de hábitos: streak, aderência, calendário,
registro com XP e sugestões iniciais por pilar.

Princípios:
- Hábito: ação recorrente que o paciente quer incorporar
- Streak: dias consecutivos de conclusão do hábito
- Aderência: % de dias cumpridos em um período
- Calendário: visualização de dias concluídos/não concluídos
- Sugestões: hábitos iniciais baseados no pilar do paciente
- XP: recompensa por consistência (15 XP por hábito + bônus)
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para todas as entidades

Arquitetura:
    HabitService
    ├── Streak
    │   ├── streak(habit_id) -> int
    │   ├── best_streak(habit_id) -> int
    │   └── _calculate_streak_from_dates(dates) -> int
    ├── Aderência
    │   ├── adherence(habit_id, days) -> float
    │   ├── overall_adherence(days) -> float
    │   └── get_habit_stats(habit_id) -> HabitStats
    ├── Calendário
    │   └── calendar(habit_id, days) -> list[CalendarDay]
    ├── Registro
    │   ├── log(habit_id, observation) -> LogResult
    │   └── _calculate_xp_bonus(streak) -> tuple[int, str]
    ├── Sugestões
    │   ├── suggestions(health_mode) -> list[HabitSuggestion]
    │   └── initialize_default_habits(health_mode) -> int
    └── Validação
        ├── get_habit_by_id(habit_id) -> Habit | None
        └── is_habit_active(habit_id) -> bool
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import config
from core.database import Database
from core.models import Habit, HabitRecord

logger = logging.getLogger("Melshape.HabitService")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# XP por hábito concluído (usa config se disponível, senão valor padrão)
_XP_PER_HABIT: int = getattr(config, "XP_HABITO", 15)

# Bônus por streaks
_BONUS_STREAK_7: int = 50
_BONUS_STREAK_30: int = 200
_BONUS_STREAK_10_MULTIPLIER: int = 2  # XP bônus = streak * 2 a cada 10 dias

# Dias para cálculos de aderência
_DEFAULT_ADHERENCE_DAYS: int = 30
_OVERALL_ADHERENCE_DAYS: int = 7

# Dias para calendário
_CALENDAR_DAYS: int = 21

# Dias para streak (limite)
_STREAK_MAX_DAYS: int = 365

# Dias para buscar dados históricos
_HISTORY_DAYS: int = 60

# Dias da semana (português)
_WEEKDAYS_PT: list[str] = ["S", "T", "Q", "Q", "S", "S", "D"]


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DO SERVIÇO DE HÁBITOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class HabitSuggestion:
    """
    Modelo de sugestão de hábito.
    
    Attributes:
        icon: Emoji do hábito
        name: Nome do hábito
        category: Categoria (hidratacao/nutricao/movimento/etc)
        frequency: Frequência (daily/weekly)
        description: Descrição opcional do hábito
    """
    icon: str
    name: str
    category: str
    frequency: str = "daily"
    description: str = ""
    
    @property
    def is_daily(self) -> bool:
        """Verifica se o hábito é diário."""
        return self.frequency == "daily"
    
    @property
    def is_weekly(self) -> bool:
        """Verifica se o hábito é semanal."""
        return self.frequency == "weekly"


@dataclass(frozen=True)
class CalendarDay:
    """
    Modelo de dia no calendário de hábito.
    
    Attributes:
        date: Data no formato YYYY-MM-DD
        completed: Se o hábito foi concluído neste dia
        weekday: Abreviação do dia da semana (S, T, Q, Q, S, S, D)
        is_future: Se é uma data futura
        is_today: Se é hoje
        day_number: Número do dia (1-31)
    """
    date: str
    completed: bool
    weekday: str
    is_future: bool = False
    is_today: bool = False
    day_number: int = 0
    
    @property
    def status_icon(self) -> str:
        """Retorna ícone de status do dia."""
        if self.is_future:
            return "⬜"
        return "✅" if self.completed else "❌"
    
    @property
    def display_text(self) -> str:
        """Retorna texto para exibição."""
        return f"{self.weekday} {self.day_number}"


@dataclass(frozen=True)
class LogResult:
    """
    Resultado do registro de um hábito.
    
    Attributes:
        ok: Se o registro foi bem-sucedido
        xp_earned: XP ganho
        streak: Streak atual após registro
        bonus_message: Mensagem de bônus (se houver)
        habit_name: Nome do hábito (se disponível)
        error_message: Mensagem de erro (se houver)
    """
    ok: bool
    xp_earned: int = 0
    streak: int = 0
    bonus_message: str = ""
    habit_name: str = ""
    error_message: str = ""
    
    @property
    def has_bonus(self) -> bool:
        """Verifica se houve bônus."""
        return bool(self.bonus_message)
    
    @property
    def total_xp(self) -> int:
        """Retorna XP total (base + bônus)."""
        return self.xp_earned
    
    @property
    def is_milestone(self) -> bool:
        """Verifica se é um marco importante (7, 30, 100 dias)."""
        return self.streak in [7, 30, 100, 365]


@dataclass(frozen=True)
class HabitStats:
    """
    Estatísticas completas de um hábito.
    
    Attributes:
        habit_id: ID do hábito
        habit_name: Nome do hábito
        current_streak: Streak atual
        best_streak: Melhor streak histórico
        adherence_7d: Aderência nos últimos 7 dias (0-100)
        adherence_30d: Aderência nos últimos 30 dias (0-100)
        total_completions: Total de conclusões
        days_since_start: Dias desde a criação do hábito
        completion_rate: Taxa de conclusão geral (0-100)
    """
    habit_id: str
    habit_name: str
    current_streak: int = 0
    best_streak: int = 0
    adherence_7d: float = 0.0
    adherence_30d: float = 0.0
    total_completions: int = 0
    days_since_start: int = 0
    completion_rate: float = 0.0
    
    @property
    def is_consistent(self) -> bool:
        """Verifica se o hábito tem boa consistência (>= 70%)."""
        return self.adherence_30d >= 70.0
    
    @property
    def needs_attention(self) -> bool:
        """Verifica se o hábito precisa de atenção (< 50%)."""
        return self.adherence_30d < 50.0


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES — SUGESTÕES POR PILAR
# ─────────────────────────────────────────────────────────────────────────────

_SUGGESTIONS: dict[str, list[HabitSuggestion]] = {
    "general": [
        HabitSuggestion("💧", "Beber 2L de água", "hidratacao", description="Mantenha-se hidratado ao longo do dia"),
        HabitSuggestion("🥩", "Atingir meta de proteína", "nutricao", description="Priorize proteínas em todas as refeições"),
        HabitSuggestion("🚶", "Caminhar 30 minutos", "movimento", description="Atividade física moderada diária"),
        HabitSuggestion("😴", "Dormir 7-8 horas", "sono", description="Sono de qualidade para recuperação"),
        HabitSuggestion("✅", "Registrar refeições", "registro", description="Acompanhe sua alimentação diária"),
    ],
    "fitness": [
        HabitSuggestion("🏋️", "Treinar hoje", "treino", description="Sessão de treino planejada"),
        HabitSuggestion("🥩", "Meta proteica (2g/kg)", "nutricao", description="Alta proteína para ganho muscular"),
        HabitSuggestion("💧", "Beber 3L de água", "hidratacao", description="Hidratação intensificada"),
        HabitSuggestion("😴", "Dormir 8 horas", "sono", description="Recuperação muscular adequada"),
        HabitSuggestion("📊", "Registrar treino", "registro", description="Acompanhe sua evolução"),
    ],
    "bariatric": [
        HabitSuggestion("🥄", "Mastigar devagar", "alimentacao", description="Mastigue cada colherada 20-30 vezes"),
        HabitSuggestion("💊", "Tomar suplementos", "suplementos", description="Suplementação pós-cirurgia essencial"),
        HabitSuggestion("💧", "Beber 1,5L de água", "hidratacao", description="Hidratação fracionada ao longo do dia"),
        HabitSuggestion("⚖️", "Pesar-se semanalmente", "monitoramento", frequency="weekly", description="Acompanhamento de peso"),
        HabitSuggestion("✅", "Registro de volume", "registro", description="Controle volume das refeições"),
    ],
    "glp1": [
        HabitSuggestion("💉", "Registrar dose", "medicamento", frequency="weekly", description="Acompanhamento da medicação"),
        HabitSuggestion("🥩", "Proteína primeiro", "nutricao", description="Priorize proteínas em cada refeição"),
        HabitSuggestion("💧", "Beber 2L de água", "hidratacao", description="Hidratação adequada com GLP-1"),
        HabitSuggestion("📋", "Monitorar sintomas", "saude", description="Acompanhe efeitos colaterais"),
        HabitSuggestion("✅", "Check-in diário", "registro", description="Registro diário de adesão"),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# HABIT SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class HabitService:
    """
    Serviço de hábitos: streak, aderência, calendário, registro com XP.
    
    Example:
        >>> db = Database()
        >>> habit_service = HabitService(db)
        >>> habits = db.get_habits()
        >>> for h in habits:
        ...     streak = habit_service.streak(h.id)
        ...     print(f"{h.nome}: {streak} dias")
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o serviço de hábitos.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        logger.debug("✅ HabitService inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # VALIDAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def get_habit_by_id(self, habit_id: str) -> Habit | None:
        """
        Busca um hábito pelo ID.
        
        Args:
            habit_id: ID do hábito
            
        Returns:
            Objeto Habit ou None se não encontrado
            
        Example:
            >>> habit = habit_service.get_habit_by_id("habit_123")
            >>> if habit:
            ...     print(f"Hábito: {habit.nome}")
        """
        if not habit_id:
            logger.warning("get_habit_by_id: habit_id não informado")
            return None
        
        try:
            habits = self.db.get_habits()
            
            for habit in habits:
                habit_id_value = self._get_habit_id(habit)
                if habit_id_value == habit_id:
                    # Converte para objeto Habit se necessário
                    if isinstance(habit, Habit):
                        return habit
                    return Habit.from_dict(habit)
            
            logger.debug(f"get_habit_by_id: hábito não encontrado: {habit_id}")
            return None
            
        except Exception as e:
            logger.error(f"get_habit_by_id falhou: {e}")
            return None

    def is_habit_active(self, habit_id: str) -> bool:
        """
        Verifica se um hábito existe e está ativo.
        
        Args:
            habit_id: ID do hábito
            
        Returns:
            True se o hábito existe e está ativo
            
        Example:
            >>> if habit_service.is_habit_active("habit_123"):
            ...     print("Hábito ativo!")
        """
        habit = self.get_habit_by_id(habit_id)
        
        if not habit:
            return False
        
        return habit.ativo

    def _get_habit_id(self, habit: Habit | dict[str, Any]) -> str | None:
        """
        Extrai o ID de um hábito (suporta objeto ou dict).
        
        Args:
            habit: Objeto Habit ou dicionário
            
        Returns:
            ID do hábito ou None
        """
        if hasattr(habit, "id"):
            return habit.id
        if isinstance(habit, dict):
            return habit.get("id")
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # STREAK
    # ─────────────────────────────────────────────────────────────────────────

    def streak(self, habit_id: str) -> int:
        """
        Calcula a sequência atual de dias consecutivos do hábito.
        
        Args:
            habit_id: ID do hábito
            
        Returns:
            Número de dias consecutivos
            
        Example:
            >>> streak = habit_service.streak(habit_id)
            >>> print(f"Streak: {streak} dias")
        """
        if not habit_id:
            logger.warning("streak: habit_id não informado")
            return 0

        try:
            # Busca registros dos últimos 365 dias
            records = self.db.get_habit_records(habit_id, days=_STREAK_MAX_DAYS)
            
            if not records:
                logger.debug(f"streak: nenhum registro para {habit_id}")
                return 0

            # Extrai datas únicas
            dates = self._extract_dates_from_records(records)
            
            # Calcula streak
            streak_count = self._calculate_streak_from_dates(dates)
            
            logger.debug(f"✅ Streak para {habit_id}: {streak_count} dias")
            return streak_count

        except Exception as e:
            logger.error(f"streak falhou para {habit_id}: {e}")
            return 0

    def best_streak(self, habit_id: str) -> int:
        """
        Calcula a maior sequência histórica do hábito.
        
        Args:
            habit_id: ID do hábito
            
        Returns:
            Maior streak já alcançado
            
        Example:
            >>> best = habit_service.best_streak(habit_id)
            >>> print(f"Melhor streak: {best} dias")
        """
        if not habit_id:
            logger.warning("best_streak: habit_id não informado")
            return 0

        try:
            # Busca registros do último ano
            records = self.db.get_habit_records(habit_id, days=_STREAK_MAX_DAYS)
            
            if not records:
                logger.debug(f"best_streak: nenhum registro para {habit_id}")
                return 0

            # Extrai datas únicas
            dates = self._extract_dates_from_records(records)
            
            if not dates:
                return 0

            # Calcula maior streak
            best = self._calculate_best_streak_from_dates(dates)
            
            logger.debug(f"✅ Melhor streak para {habit_id}: {best} dias")
            return best

        except Exception as e:
            logger.error(f"best_streak falhou para {habit_id}: {e}")
            return 0

    def _extract_dates_from_records(self, records: list[HabitRecord | dict[str, Any]]) -> list[date]:
        """
        Extrai e ordena datas de uma lista de registros.
        
        Args:
            records: Lista de objetos HabitRecord ou dicionários
            
        Returns:
            Lista de datas ordenadas (crescente)
        """
        dates = []
        
        for record in records:
            date_str = self._get_record_date(record)
            if date_str:
                try:
                    record_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    dates.append(record_date)
                except Exception as e:
                    logger.debug(f"Erro ao parsear data: {date_str} - {e}")
                    continue
        
        # Remove duplicatas e ordena
        return sorted(set(dates))

    def _get_record_date(self, record: HabitRecord | dict[str, Any]) -> str | None:
        """
        Extrai a data de um registro (suporta objeto ou dict).
        
        Args:
            record: Objeto HabitRecord ou dicionário
            
        Returns:
            Data no formato YYYY-MM-DD ou None
        """
        if hasattr(record, "data_registro"):
            return record.data_registro
        if hasattr(record, "date"):
            return record.date
        if isinstance(record, dict):
            return record.get("data_registro") or record.get("date")
        return None

    def _calculate_streak_from_dates(self, dates: list[date]) -> int:
        """
        Calcula streak a partir de lista de datas ordenadas.
        
        Args:
            dates: Lista de datas (já ordenadas crescente)
            
        Returns:
            Número de dias consecutivos a partir de hoje ou ontem
        """
        if not dates:
            return 0

        today = date.today()
        
        # Verifica se o último dia é hoje ou ontem
        if dates[-1] not in [today, today - timedelta(days=1)]:
            return 0

        # Calcula streak começando do mais recente
        streak = 1
        check_date = dates[-1]

        # Itera de trás para frente
        for i in range(len(dates) - 2, -1, -1):
            if (dates[i] - check_date).days == -1:  # É o dia anterior
                streak += 1
                check_date = dates[i]
            else:
                break

        return streak

    def _calculate_best_streak_from_dates(self, dates: list[date]) -> int:
        """
        Calcula o maior streak histórico a partir de lista de datas.
        
        Args:
            dates: Lista de datas (já ordenadas crescente)
            
        Returns:
            Maior streak encontrado
        """
        if not dates:
            return 0
        
        if len(dates) == 1:
            return 1

        best = 1
        current = 1
        
        for i in range(1, len(dates)):
            delta = (dates[i] - dates[i - 1]).days
            if delta == 1:
                current += 1
                best = max(best, current)
            else:
                current = 1

        return best

    # ─────────────────────────────────────────────────────────────────────────
    # ADERÊNCIA
    # ─────────────────────────────────────────────────────────────────────────

    def adherence(self, habit_id: str, days: int = _DEFAULT_ADHERENCE_DAYS) -> float:
        """
        Calcula a taxa de aderência do hábito nos últimos N dias.
        
        Args:
            habit_id: ID do hábito
            days: Número de dias
            
        Returns:
            Taxa de aderência (0.0 a 100.0)
            
        Example:
            >>> adherence = habit_service.adherence(habit_id, days=30)
            >>> print(f"Aderência: {adherence:.1f}%")
        """
        if not habit_id:
            logger.warning("adherence: habit_id não informado")
            return 0.0

        if days <= 0:
            logger.warning(f"adherence: days inválido: {days}")
            return 0.0

        try:
            # Busca registros dos últimos N dias
            records = self.db.get_habit_records(habit_id, days=days)
            
            # Conta dias únicos com registro
            unique_days = len(set(self._extract_dates_from_records(records)))
            
            # Calcula aderência
            adherence_pct = round(unique_days / days * 100, 1)
            
            logger.debug(f"✅ Aderência para {habit_id}: {adherence_pct}% ({unique_days}/{days})")
            return adherence_pct

        except Exception as e:
            logger.error(f"adherence falhou para {habit_id}: {e}")
            return 0.0

    def overall_adherence(self, days: int = _OVERALL_ADHERENCE_DAYS) -> float:
        """
        Calcula a aderência média de todos os hábitos ativos.
        
        Args:
            days: Número de dias
            
        Returns:
            Média de aderência (0.0 a 100.0)
            
        Example:
            >>> overall = habit_service.overall_adherence(days=7)
            >>> print(f"Aderência geral: {overall:.1f}%")
        """
        if days <= 0:
            logger.warning(f"overall_adherence: days inválido: {days}")
            return 0.0

        try:
            habits = self.db.get_habits()
            
            if not habits:
                logger.debug("overall_adherence: nenhum hábito ativo")
                return 0.0

            total_adherence = 0.0
            count = 0

            for habit in habits:
                habit_id = self._get_habit_id(habit)
                if habit_id:
                    total_adherence += self.adherence(habit_id, days=days)
                    count += 1

            if count == 0:
                return 0.0

            average = round(total_adherence / count, 1)
            logger.debug(f"✅ Aderência geral: {average}% ({count} hábitos)")
            return average

        except Exception as e:
            logger.error(f"overall_adherence falhou: {e}")
            return 0.0

    def get_habit_stats(self, habit_id: str) -> HabitStats:
        """
        Retorna estatísticas completas de um hábito.
        
        Args:
            habit_id: ID do hábito
            
        Returns:
            Objeto HabitStats com todas as métricas
            
        Example:
            >>> stats = habit_service.get_habit_stats(habit_id)
            >>> print(f"Streak atual: {stats.current_streak} dias")
            >>> print(f"Melhor streak: {stats.best_streak} dias")
            >>> print(f"Aderência 30d: {stats.adherence_30d:.1f}%")
        """
        if not habit_id:
            logger.warning("get_habit_stats: habit_id não informado")
            return HabitStats(habit_id="", habit_name="")
        
        try:
            # Busca hábito
            habit = self.get_habit_by_id(habit_id)
            habit_name = habit.nome if habit else ""
            
            # Calcula métricas
            current_streak = self.streak(habit_id)
            best_streak_val = self.best_streak(habit_id)
            adherence_7d = self.adherence(habit_id, days=7)
            adherence_30d = self.adherence(habit_id, days=30)
            
            # Total de conclusões
            records = self.db.get_habit_records(habit_id, days=_STREAK_MAX_DAYS)
            total_completions = len(records)
            
            # Dias desde criação
            if habit and habit.criado_em:
                try:
                    created_date = datetime.fromisoformat(habit.criado_em.replace('Z', '+00:00')).date()
                    days_since_start = (date.today() - created_date).days
                except Exception:
                    days_since_start = 0
            else:
                days_since_start = 0
            
            # Taxa de conclusão geral
            if days_since_start > 0:
                completion_rate = round(total_completions / days_since_start * 100, 1)
            else:
                completion_rate = 0.0
            
            stats = HabitStats(
                habit_id=habit_id,
                habit_name=habit_name,
                current_streak=current_streak,
                best_streak=best_streak_val,
                adherence_7d=adherence_7d,
                adherence_30d=adherence_30d,
                total_completions=total_completions,
                days_since_start=days_since_start,
                completion_rate=completion_rate,
            )
            
            logger.debug(f"✅ Stats para {habit_id}: streak={current_streak}, aderência={adherence_30d}%")
            return stats
            
        except Exception as e:
            logger.error(f"get_habit_stats falhou para {habit_id}: {e}")
            return HabitStats(habit_id=habit_id, habit_name="")

    # ─────────────────────────────────────────────────────────────────────────
    # CALENDÁRIO
    # ─────────────────────────────────────────────────────────────────────────

    def calendar(self, habit_id: str, days: int = _CALENDAR_DAYS) -> list[CalendarDay]:
        """
        Retorna o calendário dos últimos N dias com status de cada dia.
        
        Args:
            habit_id: ID do hábito
            days: Número de dias
            
        Returns:
            Lista de objetos CalendarDay
            
        Example:
            >>> calendar = habit_service.calendar(habit_id, days=21)
            >>> for day in calendar:
            ...     print(f"{day.weekday}: {day.status_icon}")
        """
        if not habit_id:
            logger.warning("calendar: habit_id não informado")
            return []

        if days <= 0:
            logger.warning(f"calendar: days inválido: {days}")
            return []

        try:
            # Busca registros dos últimos N dias
            records = self.db.get_habit_records(habit_id, days=days)
            
            # Extrai datas concluídas
            completed_dates = set(self._extract_dates_from_records(records))
            
            # Gera calendário
            result = []
            today = date.today()
            
            for i in range(days - 1, -1, -1):
                current_date = today - timedelta(days=i)
                date_str = current_date.isoformat()
                
                result.append(
                    CalendarDay(
                        date=date_str,
                        completed=date_str in completed_dates,
                        weekday=_WEEKDAYS_PT[current_date.weekday()],
                        is_future=current_date > today,
                        is_today=current_date == today,
                        day_number=current_date.day,
                    )
                )

            logger.debug(f"✅ Calendário gerado para {habit_id}: {days} dias")
            return result

        except Exception as e:
            logger.error(f"calendar falhou para {habit_id}: {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # REGISTRO COM XP
    # ─────────────────────────────────────────────────────────────────────────

    def log(
        self,
        habit_id: str,
        observation: str = "",
    ) -> LogResult:
        """
        Registra um hábito como concluído e credita XP.
        
        Args:
            habit_id: ID do hábito
            observation: Observação opcional
            
        Returns:
            Objeto LogResult com resultado do registro
            
        Example:
            >>> result = habit_service.log(habit_id)
            >>> if result.ok:
            ...     print(f"✅ Hábito registrado! +{result.xp_earned} XP")
            ...     if result.has_bonus:
            ...         print(result.bonus_message)
        """
        if not habit_id:
            logger.warning("log: habit_id não informado")
            return LogResult(ok=False, error_message="habit_id não informado")

        try:
            # Verifica se hábito existe e está ativo
            if not self.is_habit_active(habit_id):
                logger.warning(f"log: hábito não encontrado ou inativo: {habit_id}")
                return LogResult(ok=False, error_message="Hábito não encontrado ou inativo")
            
            # Busca nome do hábito
            habit = self.get_habit_by_id(habit_id)
            habit_name = habit.nome if habit else ""
            
            # Registra no banco
            ok = self.db.register_habit(habit_id, observacao=observation)
            
            if not ok:
                logger.warning(f"log: falha ao registrar hábito {habit_id}")
                return LogResult(ok=False, habit_name=habit_name, error_message="Falha ao registrar hábito")

            # Calcula streak atual
            current_streak = self.streak(habit_id)
            
            # Calcula XP e bônus
            xp_earned, bonus_message = self._calculate_xp_bonus(current_streak)

            # Credita XP
            self.db.add_xp(xp_earned, motivo=f"habito_{habit_id[:8]}")

            logger.info(f"✅ Hábito registrado: {habit_name} (+{xp_earned} XP, streak={current_streak})")
            
            return LogResult(
                ok=True,
                xp_earned=xp_earned,
                streak=current_streak,
                bonus_message=bonus_message,
                habit_name=habit_name,
            )

        except Exception as e:
            logger.error(f"log falhou para {habit_id}: {e}")
            return LogResult(ok=False, error_message=str(e))

    def _calculate_xp_bonus(self, streak: int) -> tuple[int, str]:
        """
        Calcula XP total (base + bônus) baseado no streak.
        
        Args:
            streak: Streak atual
            
        Returns:
            Tupla (xp_total, bonus_message)
        """
        xp_earned = _XP_PER_HABIT
        bonus_message = ""

        # Bônus por streak
        if streak == 7:
            xp_earned += _BONUS_STREAK_7
            bonus_message = f"🔥 7 dias seguidos! +{_BONUS_STREAK_7} XP bônus"
        elif streak == 30:
            xp_earned += _BONUS_STREAK_30
            bonus_message = f"🏆 30 dias! +{_BONUS_STREAK_30} XP bônus"
        elif streak == 100:
            bonus = 500
            xp_earned += bonus
            bonus_message = f"👑 100 dias! +{bonus} XP bônus"
        elif streak == 365:
            bonus = 2000
            xp_earned += bonus
            bonus_message = f"🌟 1 ano! +{bonus} XP bônus"
        elif streak > 0 and streak % 10 == 0:
            bonus = streak * _BONUS_STREAK_10_MULTIPLIER
            xp_earned += bonus
            bonus_message = f"⭐ {streak} dias! +{bonus} XP bônus"

        return xp_earned, bonus_message

    # ─────────────────────────────────────────────────────────────────────────
    # SUGESTÕES
    # ─────────────────────────────────────────────────────────────────────────

    def suggestions(self, health_mode: str) -> list[HabitSuggestion]:
        """
        Retorna sugestões de hábitos para um pilar.
        
        Args:
            health_mode: Modo de saúde (general/fitness/bariatric/glp1)
            
        Returns:
            Lista de objetos HabitSuggestion
            
        Example:
            >>> suggestions = habit_service.suggestions("general")
            >>> for s in suggestions:
            ...     print(f"{s.icon} {s.name} ({s.category})")
        """
        if not health_mode:
            logger.warning("suggestions: health_mode não informado")
            return _SUGGESTIONS.get("general", [])

        suggestions = _SUGGESTIONS.get(health_mode, _SUGGESTIONS["general"])
        logger.debug(f"✅ {len(suggestions)} sugestões para {health_mode}")
        return suggestions

    def initialize_default_habits(self, health_mode: str) -> int:
        """
        Cria hábitos padrão do pilar se o paciente não tiver nenhum.
        
        Args:
            health_mode: Modo de saúde (general/fitness/bariatric/glp1)
            
        Returns:
            Número de hábitos criados
            
        Example:
            >>> count = habit_service.initialize_default_habits("general")
            >>> print(f"{count} hábitos criados")
        """
        if not health_mode:
            logger.warning("initialize_default_habits: health_mode não informado")
            return 0

        try:
            # Verifica se já existem hábitos
            existing_habits = self.db.get_habits()
            
            if existing_habits:
                logger.debug(f"initialize_default_habits: {len(existing_habits)} hábitos já existem")
                return 0

            # Cria hábitos sugeridos
            suggestions = self.suggestions(health_mode)
            created_count = 0

            for suggestion in suggestions:
                habit = self.db.create_habit(
                    nome=suggestion.name,
                    categoria=suggestion.category,
                    icone=suggestion.icon,
                    frequencia=suggestion.frequency,
                )
                if habit:
                    created_count += 1
                    logger.debug(f"✅ Hábito criado: {suggestion.name}")

            logger.info(f"✅ {created_count} hábitos padrão criados para {health_mode}")
            return created_count

        except Exception as e:
            logger.error(f"initialize_default_habits falhou para {health_mode}: {e}")
            return 0


__all__ = [
    "HabitService",
    "HabitSuggestion",
    "CalendarDay",
    "LogResult",
    "HabitStats",
]
