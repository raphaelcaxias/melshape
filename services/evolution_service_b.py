"""
Melshape — Evolution Service B.

Extensão do EvolutionService com funcionalidades complementares:
  - Hall da Fama (campeões da transformação)
  - Carteira gamificada (moedas e recompensas)
  - Histórico de XP
  - Consentimentos LGPD

Usado por: evolution_service.py (herdado por EvolutionService)

Princípios:
- Fallback automático: Supabase → MockDB (decorator @safe_db_query)
- Tipagem forte: Protocol para Database, Enum para tipos, TypedDict para retornos
- Validação: parâmetros validados antes de processar
- Logging: todas as operações são logadas
- Imutabilidade: dataclasses frozen para todas as entidades
- Cache: consultas repetidas são cacheadas

Tabelas/Views utilizadas:
    - vw_campeoes_transformacao: hall da fama
    - carteira_gamificacao: moedas e recompensas
    - historico_xp: histórico de XP
    - consentimentos: LGPD consentimentos
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from functools import lru_cache, wraps
from typing import Any, Callable, Protocol, TypedDict, TypeVar, cast, runtime_checkable

logger = logging.getLogger("Melshape.EvolutionB")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

_HALL_OF_FAME_LIMIT: int = 10
_DEFAULT_XP_DAYS: int = 30

# Thresholds de nível da carteira
_LEVEL_THRESHOLDS: tuple[tuple[int, int], ...] = (
    (1000, 5),  # Mestre
    (500, 4),   # Expert
    (200, 3),   # Avançado
    (100, 2),   # Intermediário
)
_DEFAULT_LEVEL: int = 1


# ─────────────────────────────────────────────────────────────────────────────
# TIPOS
# ─────────────────────────────────────────────────────────────────────────────

class ConsentType(str, Enum):
    """Tipos de consentimento LGPD."""
    LGPD = "lgpd"
    TERMS = "terms"
    MARKETING = "marketing"
    DATA_SHARING = "data_sharing"
    
    @property
    def label(self) -> str:
        return {
            ConsentType.LGPD: "Política de Privacidade",
            ConsentType.TERMS: "Termos de Uso",
            ConsentType.MARKETING: "Comunicações de Marketing",
            ConsentType.DATA_SHARING: "Compartilhamento de Dados",
        }[self]


class XPMotivo(str, Enum):
    """Motivos de ganho de XP."""
    CHECKIN = "checkin"
    REFEICAO = "refeicao"
    PESAGEM = "pesagem"
    HABITO = "habito"
    META = "meta"
    MEDIDAS = "medidas_corporais"
    FOTO = "foto_evolucao"
    EXAME = "indicador_clinico"
    RECOMEÇO = "recomeco"
    
    @property
    def label(self) -> str:
        return {
            XPMotivo.CHECKIN: "✅ Check-in",
            XPMotivo.REFEICAO: "🍽️ Refeição",
            XPMotivo.PESAGEM: "⚖️ Pesagem",
            XPMotivo.HABITO: "📋 Hábito",
            XPMotivo.META: "🎯 Meta",
            XPMotivo.MEDIDAS: "📏 Medidas",
            XPMotivo.FOTO: "📸 Foto",
            XPMotivo.EXAME: "🔬 Exame",
            XPMotivo.RECOMEÇO: "🌱 Recomeço",
        }[self]


@runtime_checkable
class Database(Protocol):
    """Protocol para interface do banco de dados."""
    is_real: bool
    client: Any
    mock: dict[str, Any]
    
    def uid(self) -> str: ...


class XPSummary(TypedDict):
    """Resumo de XP do período."""
    total: int
    media_diaria: float
    dias_ativos: int
    top_motivo: str


# Tipo genérico para funções de query
T = TypeVar("T")


# ─────────────────────────────────────────────────────────────────────────────
# DECORATORS
# ─────────────────────────────────────────────────────────────────────────────

def safe_db_query(default_value: T) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator para tratamento seguro de queries ao banco.
    
    Encapsula try/except e logging, retornando valor padrão em caso de erro.
    
    Args:
        default_value: Valor a ser retornado em caso de erro
    
    Returns:
        Decorator que encapsula a função
    
    Example:
        @safe_db_query([])
        def get_data(self) -> list:
            return self._query("table", "*")
    """
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
            try:
                return fn(self, *args, **kwargs)
            except Exception as e:
                logger.warning(f"{fn.__name__}: {e}")
                return default_value
        return cast(Callable[..., T], wrapper)
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class HallOfFameEntry:
    """
    Entrada do Hall da Fama.
    
    Attributes:
        patient_id: ID do paciente
        patient_name: Nome do paciente
        weight_loss: Perda de peso (kg)
        weight_loss_pct: Perda de peso (%)
        days: Dias de jornada
        transformation_score: Score de transformação
        rank: Posição no ranking
    """
    patient_id: str
    patient_name: str
    weight_loss: float
    weight_loss_pct: float
    days: int
    transformation_score: int
    rank: int = 0
    
    @classmethod
    def from_dict(cls, data: dict[str, Any], rank: int = 0) -> HallOfFameEntry:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            patient_id=data.get("perfil_id", data.get("patient_id", "")),
            patient_name=data.get("nome_completo", data.get("patient_name", "Paciente")),
            weight_loss=float(data.get("peso_perdido", data.get("weight_loss", 0))),
            weight_loss_pct=float(data.get("peso_perdido_pct", data.get("weight_loss_pct", 0))),
            days=int(data.get("dias_jornada", data.get("days", 0))),
            transformation_score=int(data.get("score_transformacao", data.get("transformation_score", 0))),
            rank=rank,
        )
    
    @property
    def medal_icon(self) -> str:
        """Retorna ícone da medalha baseado no rank."""
        return {1: "🥇", 2: "🥈", 3: "🥉"}.get(self.rank, f"#{self.rank}")
    
    @property
    def display_text(self) -> str:
        """Retorna texto para exibição."""
        return f"{self.medal_icon} {self.patient_name}: {self.weight_loss:.1f}kg em {self.days} dias"


@dataclass(frozen=True)
class CarteiraInfo:
    """
    Informações da carteira gamificada.
    
    Attributes:
        moedas: Quantidade de moedas
        recompensas_resgatadas: Lista de recompensas resgatadas
        total_resgatado: Total de recompensas resgatadas
        total_earned: Total de moedas ganhas
        level: Nível da carteira
    """
    moedas: int = 0
    recompensas_resgatadas: list[str] = field(default_factory=list)
    total_resgatado: int = 0
    total_earned: int = 0
    level: int = 1
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CarteiraInfo:
        """Cria uma instância a partir de um dicionário."""
        resgatadas = data.get("recompensas_resgatadas", [])
        if isinstance(resgatadas, str):
            try:
                resgatadas = json.loads(resgatadas)
            except Exception:
                resgatadas = []
        
        moedas = int(data.get("moedas", 0))
        total_resgatado = len(resgatadas)
        total_earned = moedas + (total_resgatado * 100)
        level = cls._calculate_level(total_earned)
        
        return cls(
            moedas=moedas,
            recompensas_resgatadas=resgatadas,
            total_resgatado=total_resgatado,
            total_earned=total_earned,
            level=level,
        )
    
    @staticmethod
    def _calculate_level(total_earned: int) -> int:
        """Calcula nível baseado no total ganho."""
        for threshold, level in _LEVEL_THRESHOLDS:
            if total_earned >= threshold:
                return level
        return _DEFAULT_LEVEL
    
    @property
    def has_moedas(self) -> bool:
        """Verifica se tem moedas."""
        return self.moedas > 0
    
    @property
    def level_icon(self) -> str:
        """Retorna ícone do nível."""
        return {1: "🥉", 2: "🥈", 3: "🥇", 4: "💎", 5: "👑"}.get(self.level, "🥉")
    
    @property
    def level_label(self) -> str:
        """Retorna label do nível."""
        return {
            1: "Iniciante",
            2: "Intermediário",
            3: "Avançado",
            4: "Expert",
            5: "Mestre",
        }.get(self.level, "Iniciante")
    
    @property
    def mensagem(self) -> str:
        """Retorna mensagem contextual sobre moedas."""
        if self.moedas >= 500:
            return f"Você tem {self.moedas} moedas — saldo excelente para resgatar recompensas!"
        elif self.moedas >= 100:
            return f"{self.moedas} moedas acumuladas. Continue engajado para resgatar benefícios."
        else:
            return f"{self.moedas} moedas. Faça check-ins e complete hábitos para acumular mais."


@dataclass(frozen=True)
class XPEntry:
    """
    Entrada do histórico de XP.
    
    Attributes:
        id: ID da entrada
        user_id: ID do usuário
        xp_ganho: XP ganho
        motivo: Motivo do XP
        created_at: Timestamp de criação
    """
    id: str
    user_id: str
    xp_ganho: int
    motivo: str
    created_at: str
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> XPEntry:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            xp_ganho=int(data.get("xp_ganho", data.get("xp", 0))),
            motivo=data.get("motivo", ""),
            created_at=data.get("criado_em", data.get("created_at", datetime.now(timezone.utc).isoformat())),
        )
    
    @property
    def motivo_label(self) -> str:
        """Retorna label do motivo."""
        try:
            return XPMotivo(self.motivo).label
        except ValueError:
            return self.motivo
    
    @property
    def days_ago(self) -> int:
        """Calcula dias desde a entrada."""
        try:
            created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00")).date()
            return (date.today() - created).days
        except Exception:
            return 0


@dataclass(frozen=True)
class Consentimento:
    """
    Modelo de consentimento LGPD.
    
    Attributes:
        id: ID do consentimento
        user_id: ID do usuário
        tipo: Tipo de consentimento
        versao: Versão do documento
        assinado_em: Data da assinatura
        revogado: Se foi revogado
        revogado_em: Data da revogação
        created_at: Timestamp de criação
    """
    id: str
    user_id: str
    tipo: str
    versao: str
    assinado_em: str
    revogado: bool = False
    revogado_em: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Consentimento:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            tipo=data.get("tipo", ""),
            versao=data.get("versao", ""),
            assinado_em=data.get("assinado_em", date.today().isoformat()),
            revogado=data.get("revogado", False),
            revogado_em=data.get("revogado_em"),
            created_at=data.get("criado_em", data.get("created_at", datetime.now(timezone.utc).isoformat())),
        )
    
    @property
    def is_active(self) -> bool:
        """Verifica se o consentimento está ativo."""
        return not self.revogado
    
    @property
    def tipo_label(self) -> str:
        """Retorna label do tipo de consentimento."""
        try:
            return ConsentType(self.tipo).label
        except ValueError:
            return self.tipo


# ─────────────────────────────────────────────────────────────────────────────
# EVOLUTION SERVICE B
# ─────────────────────────────────────────────────────────────────────────────

class EvolutionServiceB:
    """
    Serviço de evolução B — extensão do EvolutionService.
    
    Fornece funcionalidades complementares: hall da fama, carteira, XP e consentimentos.
    
    Example:
        >>> db = Database()
        >>> evolution_b = EvolutionServiceB(db)
        >>> campeoes = evolution_b.get_campeoes(limit=10)
        >>> for c in campeoes:
        ...     print(f"{c.medal_icon} {c.patient_name}: {c.weight_loss:.1f}kg")
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o serviço de evolução B.
        
        Args:
            db: Instância do Database
        
        Raises:
            ValueError: Se db for None
        """
        if db is None:
            raise ValueError("Database instance cannot be None")
        self.db = db
        logger.debug("✅ EvolutionServiceB inicializado")

    def _uid(self) -> str:
        """Retorna o ID do usuário logado."""
        return self.db.uid()

    def _query(
        self,
        table: str,
        select: str,
        filters: dict[str, Any] | None = None,
        order: str | None = None,
        desc: bool = True,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Helper genérico de query com fallback silencioso.
        
        Args:
            table: Nome da tabela
            select: Colunas a selecionar
            filters: Filtros (suporta operadores gte:, lte:)
            order: Coluna para ordenar
            desc: Ordem descendente
            limit: Limite de resultados
        
        Returns:
            Lista de dicionários com resultados
        """
        if not (self.db.is_real and self.db.client):
            return []
        
        try:
            q = self.db.client.table(table).select(select)
            
            for col, val in (filters or {}).items():
                if col.startswith("gte:"):
                    q = q.gte(col[4:], val)
                elif col.startswith("lte:"):
                    q = q.lte(col[4:], val)
                elif col.startswith("in:"):
                    q = q.in_(col[3:], val)
                else:
                    q = q.eq(col, val)
            
            if order:
                q = q.order(order, desc=desc)
            
            return q.limit(limit).execute().data or []
            
        except Exception as e:
            logger.warning(f"_query({table}): {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # HALL DA FAMA
    # ─────────────────────────────────────────────────────────────────────────

    @safe_db_query([])
    def get_campeoes(self, limit: int = _HALL_OF_FAME_LIMIT) -> list[HallOfFameEntry]:
        """
        Retorna o Hall da Fama (top pacientes por transformação).
        
        Args:
            limit: Número máximo de entradas (padrão: 10)
        
        Returns:
            Lista de objetos HallOfFameEntry ordenados por rank
        
        Example:
            >>> campeoes = evolution_b.get_campeoes(limit=10)
            >>> for c in campeoes:
            ...     print(f"{c.medal_icon} {c.patient_name}")
        """
        if limit <= 0:
            logger.warning(f"get_campeoes: limit inválido ({limit}), usando {_HALL_OF_FAME_LIMIT}")
            limit = _HALL_OF_FAME_LIMIT
        
        # Tenta view do Supabase
        rows = self._query(
            "vw_campeoes_transformacao",
            "*",
            order="score_transformacao",
            desc=True,
            limit=limit,
        )
        
        if rows:
            return [HallOfFameEntry.from_dict(row, rank=i + 1) for i, row in enumerate(rows)]
        
        # Fallback MockDB
        campeoes = self.db.mock.get("campeoes_transformacao", [])
        campeoes_sorted = sorted(
            campeoes,
            key=lambda x: x.get("score_transformacao", 0),
            reverse=True,
        )[:limit]
        return [HallOfFameEntry.from_dict(c, rank=i + 1) for i, c in enumerate(campeoes_sorted)]

    # ─────────────────────────────────────────────────────────────────────────
    # CARTEIRA GAMIFICADA
    # ─────────────────────────────────────────────────────────────────────────

    @safe_db_query(CarteiraInfo())
    def get_carteira(self) -> CarteiraInfo:
        """
        Retorna informações da carteira gamificada.
        
        Returns:
            Objeto CarteiraInfo com moedas, nível e recompensas
        
        Example:
            >>> carteira = evolution_b.get_carteira()
            >>> print(f"Moedas: {carteira.moedas}")
            >>> print(f"Nível: {carteira.level_label}")
        """
        uid = self._uid()
        
        # Tenta Supabase
        rows = self._query(
            "carteira_gamificacao",
            "*",
            filters={"perfil_id": uid},
            limit=1,
        )
        
        if rows:
            return CarteiraInfo.from_dict(rows[0])
        
        # Fallback MockDB
        carteiras = self.db.mock.get("carteira_gamificacao", {})
        carteira_data = carteiras.get(uid, {"moedas": 0})
        return CarteiraInfo.from_dict(carteira_data)

    # ─────────────────────────────────────────────────────────────────────────
    # HISTÓRICO XP
    # ─────────────────────────────────────────────────────────────────────────

    @safe_db_query([])
    def get_historico_xp(self, days: int = _DEFAULT_XP_DAYS) -> list[XPEntry]:
        """
        Retorna histórico de XP dos últimos N dias.
        
        Args:
            days: Número de dias (padrão: 30)
        
        Returns:
            Lista de objetos XPEntry ordenados por data (mais recente primeiro)
        
        Example:
            >>> historico = evolution_b.get_historico_xp(days=30)
            >>> for entry in historico:
            ...     print(f"{entry.motivo_label}: +{entry.xp_ganho} XP")
        """
        if days <= 0:
            logger.warning(f"get_historico_xp: days inválido ({days}), usando {_DEFAULT_XP_DAYS}")
            days = _DEFAULT_XP_DAYS
        
        uid = self._uid()
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        
        # Tenta Supabase
        rows = self._query(
            "historico_xp",
            "*",
            filters={"perfil_id": uid, "gte:criado_em": cutoff},
            order="criado_em",
            desc=True,
        )
        
        if rows:
            return [XPEntry.from_dict(row) for row in rows]
        
        # Fallback MockDB
        historico = self.db.mock.get("historico_xp", [])
        patient_historico = [
            x for x in historico
            if x.get("user_id") == uid and x.get("criado_em", "") >= cutoff
        ]
        patient_historico.sort(key=lambda x: x.get("criado_em", ""), reverse=True)
        return [XPEntry.from_dict(x) for x in patient_historico]

    @lru_cache(maxsize=32)
    def get_xp_summary(self, days: int = 30) -> XPSummary:
        """
        Retorna resumo de XP do período (cacheado).
        
        Args:
            days: Número de dias (padrão: 30)
        
        Returns:
            XPSummary com total, média diária, dias ativos e top motivo
        
        Example:
            >>> summary = evolution_b.get_xp_summary(days=30)
            >>> print(f"Total: {summary['total']} XP")
            >>> print(f"Média diária: {summary['media_diaria']:.1f} XP")
        """
        entries = self.get_historico_xp(days=days)
        
        if not entries:
            return XPSummary(
                total=0,
                media_diaria=0.0,
                dias_ativos=0,
                top_motivo="—",
            )
        
        total = sum(e.xp_ganho for e in entries)
        dias_ativos = len(set(e.created_at[:10] for e in entries))
        media_diaria = total / days if days > 0 else 0.0
        
        motivos: dict[str, int] = {}
        for entry in entries:
            motivos[entry.motivo] = motivos.get(entry.motivo, 0) + entry.xp_ganho
        
        top_motivo = max(motivos.items(), key=lambda x: x[1])[0] if motivos else "—"
        
        return XPSummary(
            total=total,
            media_diaria=round(media_diaria, 1),
            dias_ativos=dias_ativos,
            top_motivo=top_motivo,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # CONSENTIMENTOS LGPD
    # ─────────────────────────────────────────────────────────────────────────

    @safe_db_query([])
    def get_consentimentos(self) -> list[Consentimento]:
        """
        Retorna todos os consentimentos do usuário.
        
        Returns:
            Lista de objetos Consentimento ordenados por data (mais recente primeiro)
        
        Example:
            >>> consentimentos = evolution_b.get_consentimentos()
            >>> for c in consentimentos:
            ...     print(f"{c.tipo_label}: {'Ativo' if c.is_active else 'Revogado'}")
        """
        uid = self._uid()
        
        # Tenta Supabase
        rows = self._query(
            "consentimentos",
            "*",
            filters={"perfil_id": uid},
            order="assinado_em",
            desc=True,
        )
        
        if rows:
            return [Consentimento.from_dict(row) for row in rows]
        
        # Fallback MockDB
        consentimentos = self.db.mock.get("consentimentos", [])
        patient_consentimentos = [c for c in consentimentos if c.get("user_id") == uid]
        return [Consentimento.from_dict(c) for c in patient_consentimentos]

    def assinar_consentimento(self, tipo: str, versao: str) -> bool:
        """
        Assina um consentimento LGPD.
        
        Args:
            tipo: Tipo de consentimento (use ConsentType enum)
            versao: Versão do documento
        
        Returns:
            True se assinado com sucesso, False caso contrário
        
        Example:
            >>> success = evolution_b.assinar_consentimento("lgpd", "2.0")
            >>> if success:
            ...     print("Consentimento assinado!")
        """
        if not tipo or not versao:
            logger.warning("assinar_consentimento: tipo ou versão não informados")
            return False
        
        uid = self._uid()
        
        # Tenta Supabase
        if self.db.is_real and self.db.client:
            try:
                self.db.client.table("consentimentos").insert({
                    "perfil_id": uid,
                    "tipo": tipo,
                    "versao": versao,
                    "assinado_em": date.today().isoformat(),
                    "revogado": False,
                }).execute()
                
                logger.info(f"✅ Consentimento assinado: {tipo} v{versao}")
                return True
            except Exception as e:
                logger.error(f"assinar_consentimento: {e}")
        
        # Fallback MockDB
        try:
            consentimentos = self.db.mock.setdefault("consentimentos", [])
            consentimentos.append({
                "user_id": uid,
                "tipo": tipo,
                "versao": versao,
                "assinado_em": date.today().isoformat(),
                "revogado": False,
                "criado_em": datetime.now(timezone.utc).isoformat(),
            })
            
            logger.info(f"✅ Consentimento assinado no MockDB: {tipo} v{versao}")
            return True
        except Exception as e:
            logger.error(f"assinar_consentimento MockDB: {e}")
        
        return False

    def revogar_consentimento(self, consentimento_id: str) -> bool:
        """
        Revoga um consentimento LGPD.
        
        Args:
            consentimento_id: ID do consentimento
        
        Returns:
            True se revogado com sucesso, False caso contrário
        
        Example:
            >>> success = evolution_b.revogar_consentimento("consent_123")
            >>> if success:
            ...     print("Consentimento revogado!")
        """
        if not consentimento_id:
            logger.warning("revogar_consentimento: consentimento_id não informado")
            return False
        
        # Tenta Supabase
        if self.db.is_real and self.db.client:
            try:
                self.db.client.table("consentimentos").update({
                    "revogado": True,
                    "revogado_em": date.today().isoformat(),
                }).eq("id", consentimento_id).execute()
                
                logger.info(f"✅ Consentimento revogado: {consentimento_id}")
                return True
            except Exception as e:
                logger.error(f"revogar_consentimento: {e}")
        
        # Fallback MockDB
        try:
            consentimentos = self.db.mock.get("consentimentos", [])
            for consent in consentimentos:
                if consent.get("id") == consentimento_id:
                    consent["revogado"] = True
                    consent["revogado_em"] = date.today().isoformat()
                    logger.info(f"✅ Consentimento revogado no MockDB: {consentimento_id}")
                    return True
        except Exception as e:
            logger.error(f"revogar_consentimento MockDB: {e}")
        
        return False

    def has_active_consent(self, tipo: str) -> bool:
        """
        Verifica se o usuário tem consentimento ativo para um tipo.
        
        Args:
            tipo: Tipo de consentimento (use ConsentType enum)
        
        Returns:
            True se tem consentimento ativo, False caso contrário
        
        Example:
            >>> if evolution_b.has_active_consent("lgpd"):
            ...     print("Usuário consentiu com LGPD")
        """
        consentimentos = self.get_consentimentos()
        return any(c.tipo == tipo and c.is_active for c in consentimentos)


__all__ = [
    "EvolutionServiceB",
    "HallOfFameEntry",
    "CarteiraInfo",
    "XPEntry",
    "Consentimento",
    "ConsentType",
    "XPMotivo",
    "XPSummary",
]
