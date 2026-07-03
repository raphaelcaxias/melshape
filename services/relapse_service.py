"""
Melshape — Relapse Service.

Protocolo de Recaída: recaída não é falha — é parte da jornada.

Detecta quando o streak zerou após uma sequência significativa e oferece
um fluxo ativo de recomeço: reconhece sem punir, lembra o porquê da
jornada, registra o recomeço como evento positivo e dá XP proporcional
ao histórico (voltar do zero não significa ter perdido tudo).

Princípios:
- Nunca punir: recaída é oportunidade, não fracasso
- Reconhecer o histórico: o paciente já provou que consegue
- Acolher: mensagens motivacionais, não críticas
- XP proporcional: quanto maior o streak anterior, maior o XP de recomeço
- Registrar o recomeço: como evento positivo na linha do tempo
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para todas as entidades

Arquitetura:
    RelapseService
    ├── Detection
    │   ├── detect(user) -> RelapseInfo | None
    │   ├── _get_best_streak() -> int
    │   ├── _get_days_without_checkin() -> int
    │   ├── _calculate_xp_reward(best_streak) -> int
    │   └── _generate_recovery_message(best_streak) -> str
    ├── Recovery Action
    │   ├── register_recovery(user, relapse_info) -> RecoveryResult
    │   ├── _grant_recovery_xp(user, xp) -> bool
    │   ├── _register_recovery_event(user, relapse_info) -> bool
    │   └── _create_recovery_notification(user, relapse_info) -> bool
    ├── Journey Reason
    │   └── get_journey_reason(user) -> str | None
    └── Statistics
        └── get_relapse_stats(user) -> RelapseStats
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any

from core.database import Database

logger = logging.getLogger("Melshape.Relapse")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Streak mínimo para considerar recaída
_MIN_STREAK_FOR_RELAPSE: int = 3

# Dias de ausência para considerar recaída
_MIN_ABSENCE_DAYS: int = 1

# XP por recomeço (base, antes do bônus)
_BASE_RECOVERY_XP: int = 25

# XP máximo de recomeço
_MAX_RECOVERY_XP: int = 200

# Bônus por streak histórico
_RECOVERY_XP_BONUS: dict[int, int] = {
    7: 50,
    14: 75,
    30: 100,
    60: 125,
    90: 150,
}

# Dias para buscar histórico de check-ins
_HISTORY_DAYS: int = 365

# Thresholds para níveis de recaída
_THRESHOLD_LEGENDARY: int = 90
_THRESHOLD_HIGH: int = 30
_THRESHOLD_MEDIUM: int = 7

# Mensagens motivacionais por nível de streak
_RECOVERY_MESSAGES: dict[str, list[str]] = {
    "low": [
        "🌱 Cada recomeço é uma nova oportunidade. Você já foi mais longe antes.",
        "🌱 Recomeçar é parte da jornada. Estamos aqui com você.",
        "🌱 Sua sequência anterior provou que você consegue. Vamos de novo.",
    ],
    "medium": [
        "💪 Você já mostrou que tem força. Hoje é dia 1 de algo ainda maior.",
        "💪 {streak} dias não desaparecem. Eles são prova do que você é capaz.",
        "💪 O que você já construiu não se perde. É base para o próximo ciclo.",
    ],
    "high": [
        "🔥 {streak} dias! Você já provou que consegue. Agora é sobre continuar.",
        "🔥 Sua sequência de {streak} dias não foi em vão. Ela mostrou seu potencial.",
        "🔥 {streak} dias de consistência. Isso não é sorte — é você.",
    ],
    "legendary": [
        "👑 {streak} dias! Você é lendário. Recomeçar é uma escolha de campeão.",
        "👑 {streak} dias provam que você tem o que é preciso. Confie no processo.",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class RelapseLevel(str, Enum):
    """Níveis de recaída baseados no streak anterior."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    LEGENDARY = "legendary"
    
    @classmethod
    def from_streak(cls, streak: int) -> RelapseLevel:
        """Determina o nível baseado no streak."""
        if streak >= _THRESHOLD_LEGENDARY:
            return cls.LEGENDARY
        elif streak >= _THRESHOLD_HIGH:
            return cls.HIGH
        elif streak >= _THRESHOLD_MEDIUM:
            return cls.MEDIUM
        return cls.LOW
    
    @property
    def icon(self) -> str:
        """Retorna ícone do nível."""
        icons = {
            "low": "🌱",
            "medium": "💪",
            "high": "🔥",
            "legendary": "👑",
        }
        return icons.get(self.value, "🌱")
    
    @property
    def label(self) -> str:
        """Retorna label do nível."""
        labels = {
            "low": "Iniciante",
            "medium": "Intermediário",
            "high": "Avançado",
            "legendary": "Lendário",
        }
        return labels.get(self.value, "Iniciante")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DO SERVIÇO DE RECAÍDA
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RelapseInfo:
    """
    Informações sobre uma recaída detectada.
    
    Attributes:
        best_streak: Melhor streak já alcançado
        days_without_checkin: Dias sem check-in
        recovery_xp: XP a ser ganho no recomeço
        recovery_message: Mensagem motivacional para o recomeço
        detected_at: Data da detecção
        level: Nível da recaída
    """
    best_streak: int
    days_without_checkin: int
    recovery_xp: int
    recovery_message: str
    detected_at: str = field(default_factory=lambda: date.today().isoformat())
    level: RelapseLevel = RelapseLevel.LOW
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RelapseInfo:
        """Cria uma instância a partir de um dicionário."""
        level_str = data.get("level", "low")
        try:
            level = RelapseLevel(level_str)
        except ValueError:
            level = RelapseLevel.LOW
        
        return cls(
            best_streak=int(data.get("best_streak", 0)),
            days_without_checkin=int(data.get("days_without_checkin", 0)),
            recovery_xp=int(data.get("recovery_xp", _BASE_RECOVERY_XP)),
            recovery_message=data.get("recovery_message", ""),
            detected_at=data.get("detected_at", date.today().isoformat()),
            level=level,
        )
    
    @property
    def is_significant(self) -> bool:
        """Verifica se a recaída é significativa (streak >= 7)."""
        return self.best_streak >= _THRESHOLD_MEDIUM
    
    @property
    def is_major(self) -> bool:
        """Verifica se é uma recaída importante (streak >= 30)."""
        return self.best_streak >= _THRESHOLD_HIGH
    
    @property
    def is_legendary(self) -> bool:
        """Verifica se é uma recaída lendária (streak >= 90)."""
        return self.best_streak >= _THRESHOLD_LEGENDARY
    
    @property
    def formatted_message(self) -> str:
        """Retorna mensagem formatada com dados do streak."""
        return self.recovery_message.format(streak=self.best_streak)
    
    @property
    def days_label(self) -> str:
        """Retorna label dos dias de ausência."""
        if self.days_without_checkin == 0:
            return "Recomeço hoje"
        elif self.days_without_checkin == 1:
            return "1 dia sem check-in"
        return f"{self.days_without_checkin} dias sem check-in"
    
    @property
    def level_icon(self) -> str:
        """Retorna ícone do nível."""
        return self.level.icon
    
    @property
    def level_label(self) -> str:
        """Retorna label do nível."""
        return self.level.label


@dataclass(frozen=True)
class RecoveryResult:
    """
    Resultado do processo de recomeço.
    
    Attributes:
        success: Se o recomeço foi registrado com sucesso
        xp_granted: XP concedido
        notification_created: Se notificação foi criada
        event_registered: Se evento foi registrado
        relapse_info: Informações da recaída
        error_message: Mensagem de erro (se houver)
    """
    success: bool = False
    xp_granted: int = 0
    notification_created: bool = False
    event_registered: bool = False
    relapse_info: RelapseInfo | None = None
    error_message: str = ""
    
    @property
    def has_xp(self) -> bool:
        """Verifica se XP foi concedido."""
        return self.xp_granted > 0
    
    @property
    def has_any_action(self) -> bool:
        """Verifica se alguma ação foi executada."""
        return self.has_xp or self.notification_created or self.event_registered
    
    @property
    def action_count(self) -> int:
        """Retorna quantidade de ações executadas."""
        return sum([
            self.has_xp,
            self.notification_created,
            self.event_registered,
        ])
    
    @property
    def summary_text(self) -> str:
        """Retorna texto resumido do resultado."""
        if not self.success:
            return f"❌ Recomeço não registrado: {self.error_message}"
        
        parts = []
        if self.has_xp:
            parts.append(f"+{self.xp_granted} XP")
        if self.notification_created:
            parts.append("📬 Notificação")
        if self.event_registered:
            parts.append("📝 Evento registrado")
        
        if parts:
            return "✅ Recomeço: " + " + ".join(parts)
        return "✅ Recomeço registrado"


@dataclass(frozen=True)
class RelapseStats:
    """
    Estatísticas de recaídas do paciente.
    
    Attributes:
        total_relapses: Total de recaídas registradas
        average_best_streak: Média dos melhores streaks
        max_best_streak: Maior streak já alcançado
        last_relapse_date: Data da última recaída
        recovery_xp_total: XP total ganho com recomeços
        days_since_last_relapse: Dias desde a última recaída
    """
    total_relapses: int = 0
    average_best_streak: float = 0.0
    max_best_streak: int = 0
    last_relapse_date: str | None = None
    recovery_xp_total: int = 0
    days_since_last_relapse: int | None = None
    
    @property
    def has_relapses(self) -> bool:
        """Verifica se há recaídas registradas."""
        return self.total_relapses > 0
    
    @property
    def is_resilient(self) -> bool:
        """Verifica se o paciente é resiliente (vários recomeços)."""
        return self.total_relapses >= 3
    
    @property
    def resilience_label(self) -> str:
        """Retorna label de resiliência."""
        if self.total_relapses >= 5:
            return "🏆 Muito resiliente"
        elif self.total_relapses >= 3:
            return "💪 Resiliente"
        elif self.total_relapses >= 1:
            return "🌱 Em recuperação"
        return "✨ Sem recaídas"
    
    @property
    def last_relapse_label(self) -> str:
        """Retorna label da última recaída."""
        if self.days_since_last_relapse is None:
            return "Nunca"
        elif self.days_since_last_relapse == 0:
            return "Hoje"
        elif self.days_since_last_relapse == 1:
            return "Ontem"
        return f"{self.days_since_last_relapse} dias atrás"


@dataclass(frozen=True)
class RecoveryAction:
    """
    Modelo de ação de recomeço.
    
    Attributes:
        action_type: Tipo da ação (xp/notification/event)
        description: Descrição da ação
        success: Se a ação foi bem-sucedida
        details: Detalhes adicionais
    """
    action_type: str
    description: str
    success: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    
    @property
    def icon(self) -> str:
        """Retorna ícone da ação."""
        icons = {
            "xp": "⭐",
            "notification": "📬",
            "event": "📝",
        }
        return icons.get(self.action_type, "•")
    
    @property
    def display_text(self) -> str:
        """Retorna texto formatado para exibição."""
        status = "✅" if self.success else "❌"
        return f"{self.icon} {status} {self.description}"


# ─────────────────────────────────────────────────────────────────────────────
# RELAPSE SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class RelapseService:
    """
    Serviço de protocolo de recaída.
    
    Detecta recaídas e oferece um fluxo ativo de recomeço.
    
    Example:
        >>> db = Database()
        >>> relapse_service = RelapseService(db)
        >>> user = st.session_state.user
        >>> relapse_info = relapse_service.detect(user)
        >>> if relapse_info:
        ...     print(f"Recaída detectada! Melhor streak: {relapse_info.best_streak}")
        ...     result = relapse_service.register_recovery(user, relapse_info)
        ...     print(result.summary_text)
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o serviço de recaída.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        logger.debug("✅ RelapseService inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # DETECTION
    # ─────────────────────────────────────────────────────────────────────────

    def detect(self, user: dict[str, Any] | Any) -> RelapseInfo | None:
        """
        Detecta se o usuário está em situação de recaída.
        
        Condições:
            1. Streak atual == 0
            2. Já teve um streak >= 3 dias
            3. Está há pelo menos 1 dia sem check-in (ou hoje ainda não fez)
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Objeto RelapseInfo ou None se não for recaída
            
        Example:
            >>> relapse = relapse_service.detect(user)
            >>> if relapse:
            ...     print(f"Recaída: {relapse.best_streak} dias perdidos")
        """
        if not user:
            logger.warning("detect: user não informado")
            return None

        try:
            # 1. Verifica streak atual
            current_streak = self.db.get_checkin_streak()
            
            # Se tem streak, não é recaída
            if current_streak > 0:
                logger.debug("detect: streak atual > 0, sem recaída")
                return None

            # 2. Verifica melhor streak histórico
            best_streak = self._get_best_streak()
            
            # Nunca teve um streak significativo
            if best_streak < _MIN_STREAK_FOR_RELAPSE:
                logger.debug(f"detect: melhor streak ({best_streak}) < {_MIN_STREAK_FOR_RELAPSE}")
                return None

            # 3. Verifica dias sem check-in
            days_without = self._get_days_without_checkin()
            
            if days_without < _MIN_ABSENCE_DAYS:
                # Se zerou hoje, mas ainda pode registrar
                checkin_today = self.db.get_checkin_today()
                if not checkin_today:
                    # Hoje ainda não fez check-in, mas pode fazer
                    logger.debug("detect: hoje ainda não fez check-in, mas pode fazer ainda")
                    # Considera como recaída iminente
                    days_without = 1
                else:
                    return None

            # 4. Calcula XP de recomeço
            recovery_xp = self._calculate_xp_reward(best_streak)
            
            # 5. Determina nível
            level = RelapseLevel.from_streak(best_streak)
            
            # 6. Gera mensagem de recomeço
            recovery_message = self._generate_recovery_message(best_streak)

            relapse = RelapseInfo(
                best_streak=best_streak,
                days_without_checkin=days_without,
                recovery_xp=recovery_xp,
                recovery_message=recovery_message,
                level=level,
            )

            logger.info(
                f"🔄 Recaída detectada: streak {best_streak} → 0, "
                f"nível {level.value}, +{recovery_xp} XP"
            )
            return relapse

        except Exception as e:
            logger.error(f"detect falhou: {e}", exc_info=True)
            return None

    def _get_best_streak(self) -> int:
        """
        Calcula o melhor streak histórico de check-ins.
        
        Returns:
            Maior sequência já alcançada
        """
        try:
            # Busca todos os check-ins do usuário
            checkins = self.db.get_checkins(days=_HISTORY_DAYS)
            
            if not checkins:
                logger.debug("_get_best_streak: nenhum check-in encontrado")
                return 0
            
            # Extrai datas
            dates = self._extract_checkin_dates(checkins)
            
            if not dates:
                return 0
            
            # Calcula melhor streak
            best = self._calculate_best_streak(dates)
            
            logger.debug(f"_get_best_streak: melhor streak = {best}")
            return best

        except Exception as e:
            logger.warning(f"_get_best_streak: {e}")
            return 0

    def _extract_checkin_dates(self, checkins: list[Any]) -> list[date]:
        """
        Extrai datas de uma lista de check-ins.
        
        Args:
            checkins: Lista de check-ins (objetos ou dicts)
            
        Returns:
            Lista de datas ordenadas
        """
        dates = []
        
        for checkin in checkins:
            # Tenta extrair data
            if hasattr(checkin, "data_checkin"):
                date_str = checkin.data_checkin
            elif isinstance(checkin, dict):
                date_str = checkin.get("data_checkin")
            else:
                continue
            
            if date_str:
                try:
                    parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    dates.append(parsed_date)
                except Exception as e:
                    logger.debug(f"Erro ao parsear data {date_str}: {e}")
        
        # Remove duplicatas e ordena
        return sorted(set(dates))

    def _calculate_best_streak(self, dates: list[date]) -> int:
        """Delegado para streak_utils.calculate_best_streak (módulo canônico)."""
        from services.streak_utils import calculate_best_streak
        return calculate_best_streak(dates)


    def _get_days_without_checkin(self) -> int:
        """
        Calcula dias desde o último check-in.
        
        Returns:
            Número de dias sem check-in
        """
        try:
            # Busca último check-in
            checkins = self.db.get_checkins(days=30)
            
            if not checkins:
                # Nunca fez check-in
                return 0
            
            # Extrai datas
            dates = self._extract_checkin_dates(checkins)
            
            if not dates:
                return 0
            
            # Pega a data mais recente
            last_date = max(dates)
            
            # Calcula diferença
            days_without = (date.today() - last_date).days
            
            return max(0, days_without)

        except Exception as e:
            logger.warning(f"_get_days_without_checkin: {e}")
            return 0

    def _calculate_xp_reward(self, best_streak: int) -> int:
        """
        Calcula XP de recomeço baseado no melhor streak.
        
        Quanto maior o streak anterior, maior o XP de recomeço.
        
        Args:
            best_streak: Melhor streak já alcançado
            
        Returns:
            XP a ser concedido
        """
        xp = _BASE_RECOVERY_XP

        # Bônus por streak (itera em ordem crescente)
        for threshold in sorted(_RECOVERY_XP_BONUS.keys()):
            if best_streak >= threshold:
                bonus = _RECOVERY_XP_BONUS[threshold]
                xp = max(xp, _BASE_RECOVERY_XP + bonus)

        # Limita ao máximo
        result = min(_MAX_RECOVERY_XP, xp)
        
        logger.debug(f"_calculate_xp_reward: streak={best_streak}, xp={result}")
        return result

    def _generate_recovery_message(self, best_streak: int) -> str:
        """
        Gera mensagem motivacional para recomeço.
        
        Args:
            best_streak: Melhor streak já alcançado
            
        Returns:
            Mensagem motivacional
        """
        # Determina nível
        level = RelapseLevel.from_streak(best_streak)

        # Escolhe mensagem
        messages = _RECOVERY_MESSAGES.get(level.value, _RECOVERY_MESSAGES["low"])
        message = random.choice(messages)
        
        return message

    # ─────────────────────────────────────────────────────────────────────────
    # RECOVERY ACTION
    # ─────────────────────────────────────────────────────────────────────────

    def register_recovery(
        self,
        user: dict[str, Any] | Any,
        relapse_info: RelapseInfo,
    ) -> RecoveryResult:
        """
        Registra o recomeço do paciente.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            relapse_info: Informações da recaída detectada
            
        Returns:
            Objeto RecoveryResult com resultado do processo
            
        Example:
            >>> relapse = relapse_service.detect(user)
            >>> if relapse:
            ...     result = relapse_service.register_recovery(user, relapse)
            ...     print(result.summary_text)
        """
        if not user:
            logger.warning("register_recovery: user não informado")
            return RecoveryResult(success=False, error_message="user não informado")

        if not relapse_info:
            logger.warning("register_recovery: relapse_info não informado")
            return RecoveryResult(success=False, error_message="relapse_info não informado")

        try:
            # 1. Concede XP
            xp_granted = relapse_info.recovery_xp
            xp_success = self._grant_recovery_xp(user, xp_granted)

            # 2. Registra evento de vida
            event_success = self._register_recovery_event(user, relapse_info)

            # 3. Cria notificação
            notif_success = self._create_recovery_notification(user, relapse_info)

            success = xp_success or event_success or notif_success

            if success:
                logger.info(
                    f"✅ Recomeço registrado: +{xp_granted} XP, "
                    f"streak anterior: {relapse_info.best_streak}, "
                    f"nível: {relapse_info.level.value}"
                )

            return RecoveryResult(
                success=success,
                xp_granted=xp_granted if xp_success else 0,
                notification_created=notif_success,
                event_registered=event_success,
                relapse_info=relapse_info,
            )

        except Exception as e:
            logger.error(f"register_recovery falhou: {e}", exc_info=True)
            return RecoveryResult(
                success=False,
                error_message=str(e),
                relapse_info=relapse_info,
            )

    def _grant_recovery_xp(
        self,
        user: dict[str, Any] | Any,
        xp: int,
    ) -> bool:
        """
        Concede XP de recomeço ao paciente.
        
        Args:
            user: Dados do usuário
            xp: XP a ser concedido
            
        Returns:
            True se concedido com sucesso
        """
        if xp <= 0:
            logger.warning("_grant_recovery_xp: xp <= 0")
            return False

        try:
            # Usa método do Database
            uid = self.db.uid()
            result = self.db.add_xp(xp, motivo="recomeco")
            
            if result:
                logger.info(f"✅ XP de recomeço concedido: +{xp} para {uid}")
            else:
                logger.warning(f"❌ Falha ao conceder XP de recomeço: {xp}")
            
            return result

        except Exception as e:
            logger.error(f"_grant_recovery_xp: {e}")
            return False

    def _register_recovery_event(
        self,
        user: dict[str, Any] | Any,
        relapse_info: RelapseInfo,
    ) -> bool:
        """
        Registra o recomeço como evento de vida.
        
        Args:
            user: Dados do usuário
            relapse_info: Informações da recaída
            
        Returns:
            True se registrado com sucesso
        """
        try:
            # Verifica se o método existe
            if not hasattr(self.db, "register_life_event"):
                logger.warning("_register_recovery_event: método register_life_event não disponível")
                return False
            
            # Registra evento de vida
            titulo = f"Recomeço após {relapse_info.best_streak} dias"
            descricao = (
                f"Voltei depois de {relapse_info.days_without_checkin} dias. "
                f"Meu melhor streak foi de {relapse_info.best_streak} dias "
                f"e isso prova que consigo."
            )
            
            result = self.db.register_life_event(
                titulo=titulo,
                descricao=descricao,
                tipo="inicio",
            )
            
            if result:
                logger.info(f"✅ Evento de recomeço registrado: {titulo}")
            else:
                logger.warning(f"❌ Falha ao registrar evento de recomeço")
            
            return result

        except Exception as e:
            logger.error(f"_register_recovery_event: {e}")
            return False

    def _create_recovery_notification(
        self,
        user: dict[str, Any] | Any,
        relapse_info: RelapseInfo,
    ) -> bool:
        """
        Cria notificação motivacional de recomeço.
        
        Args:
            user: Dados do usuário
            relapse_info: Informações da recaída
            
        Returns:
            True se criada com sucesso
        """
        try:
            # Obtém nome do usuário
            if isinstance(user, dict):
                name = user.get("name", "Você")
            else:
                name = getattr(user, "name", "Você")
            
            first_name = name.split()[0] if name else "Você"
            
            # Gera mensagem
            mensagem = (
                f"🌱 {first_name}, bem-vindo de volta! "
                f"Sua sequência anterior de {relapse_info.best_streak} dias "
                f"prova que você consegue. "
                f"Hoje é dia 1 de algo ainda maior. +{relapse_info.recovery_xp} XP pelo recomeço!"
            )
            
            # Cria notificação
            result = self.db.create_notification(mensagem, tipo="recomeco")
            
            if result:
                logger.info(f"✅ Notificação de recomeço criada")
            else:
                logger.warning(f"❌ Falha ao criar notificação de recomeço")
            
            return result

        except Exception as e:
            logger.error(f"_create_recovery_notification: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # JOURNEY REASON
    # ─────────────────────────────────────────────────────────────────────────

    def get_journey_reason(self, user: dict[str, Any] | Any) -> str | None:
        """
        Retorna o "porquê" da jornada do paciente.
        
        Útil para exibir no momento de recaída como lembrete do propósito.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Motivo da jornada ou None
            
        Example:
            >>> reason = relapse_service.get_journey_reason(user)
            >>> if reason:
            ...     print(f"💛 Lembre-se: {reason}")
        """
        if not user:
            logger.warning("get_journey_reason: user não informado")
            return None

        try:
            # Busca jornada ativa
            journey = self.db.get_journey_ativa()
            if not journey:
                logger.debug("get_journey_reason: nenhuma jornada ativa")
                return None

            journey_id = journey.id if hasattr(journey, "id") else journey.get("id", "")
            if not journey_id:
                return None

            # Verifica se o método existe
            if not hasattr(self.db, "get_motivations"):
                logger.warning("get_journey_reason: método get_motivations não disponível")
                return None
            
            # Busca motivos da jornada
            motivations = self.db.get_motivations(journey_id)
            
            if not motivations:
                logger.debug("get_journey_reason: nenhum motivo registrado")
                return None

            # Retorna o primeiro motivo
            first_motivation = motivations[0]
            motivo = first_motivation.motivo if hasattr(first_motivation, "motivo") else first_motivation.get("motivo", "")
            
            logger.debug(f"get_journey_reason: {motivo[:50]}...")
            return motivo

        except Exception as e:
            logger.warning(f"get_journey_reason: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # STATISTICS
    # ─────────────────────────────────────────────────────────────────────────

    def get_relapse_stats(self, user: dict[str, Any] | Any) -> RelapseStats:
        """
        Retorna estatísticas de recaídas do paciente.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Objeto RelapseStats com estatísticas
            
        Example:
            >>> stats = relapse_service.get_relapse_stats(user)
            >>> print(f"Total de recaídas: {stats.total_relapses}")
            >>> print(f"Melhor streak: {stats.max_best_streak}")
        """
        if not user:
            logger.warning("get_relapse_stats: user não informado")
            return RelapseStats()

        try:
            # Verifica se o método existe
            if not hasattr(self.db, "get_life_events"):
                logger.warning("get_relapse_stats: método get_life_events não disponível")
                return RelapseStats()
            
            # Busca eventos de vida do tipo "inicio" (recomeços)
            events = self.db.get_life_events()
            
            recovery_events = [
                e for e in events
                if (e.tipo if hasattr(e, "tipo") else e.get("tipo")) == "inicio"
                or "Recomeço" in (e.titulo if hasattr(e, "titulo") else e.get("titulo", ""))
            ]
            
            total_relapses = len(recovery_events)
            
            # Calcula streaks
            best_streak = self._get_best_streak()
            
            # Última recaída
            last_relapse = None
            days_since_last = None
            
            if recovery_events:
                last_event = recovery_events[0]
                last_relapse = (
                    last_event.data_evento 
                    if hasattr(last_event, "data_evento") 
                    else last_event.get("data_evento")
                )
                
                if last_relapse:
                    try:
                        last_date = datetime.strptime(last_relapse, "%Y-%m-%d").date()
                        days_since_last = (date.today() - last_date).days
                    except Exception:
                        pass
            
            # XP total (estimado)
            recovery_xp_total = total_relapses * _BASE_RECOVERY_XP
            
            # Se houver recaídas, calcula média
            avg_streak = 0.0
            if total_relapses > 0:
                # Estima média baseada no melhor streak
                avg_streak = best_streak // 2 if best_streak > 0 else 0

            stats = RelapseStats(
                total_relapses=total_relapses,
                average_best_streak=float(avg_streak),
                max_best_streak=best_streak,
                last_relapse_date=last_relapse,
                recovery_xp_total=recovery_xp_total,
                days_since_last_relapse=days_since_last,
            )
            
            logger.debug(
                f"✅ Estatísticas de recaída: {total_relapses} recaídas, "
                f"melhor streak: {best_streak}"
            )
            return stats

        except Exception as e:
            logger.error(f"get_relapse_stats falhou: {e}")
            return RelapseStats()


__all__ = [
    "RelapseService",
    "RelapseInfo",
    "RecoveryResult",
    "RelapseStats",
    "RecoveryAction",
    "RelapseLevel",
]
