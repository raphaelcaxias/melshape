"""
Melshape — Evolution Service.

Serviço de evolução completa do paciente: medidas corporais, fotos,
indicadores clínicos, estagnação, hall da fama, carteira gamificada,
histórico de XP e consentimentos LGPD.

Princípios:
- Dados consolidados: todas as medidas em um só lugar
- Visualização de progresso: antes/depois, evolução temporal
- Estagnação: detecção de platôs de peso
- Gamificação: carteira de moedas e hall da fama
- LGPD: consentimentos e revogação
- Fallback automático: Supabase → MockDB (completo)
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para todas as entidades
- Análise temporal: comparação e tendências

Tabelas/Views utilizadas:
    - medidas_corporais: medidas do corpo
    - fotos_evolucao: fotos de progresso
    - indicadores_clinicos: exames laboratoriais
    - vw_estagnacao_clinica: detecção de estagnação
    - vw_campeoes_transformacao: hall da fama
    - carteira_gamificacao: moedas e recompensas
    - historico_xp: histórico de XP
    - consentimentos: LGPD consentimentos

Arquitetura:
    EvolutionService
    ├── Body Measures
    │   ├── get_medidas(days) -> list[MedidaCorporal]
    │   ├── salvar_medida(data) -> bool
    │   ├── get_latest_medida() -> MedidaCorporal | None
    │   └── compare_medidas() -> MedidaComparison | None
    ├── Photos
    │   ├── get_fotos() -> list[FotoEvolucao]
    │   ├── salvar_foto(url, legenda, peso) -> bool
    │   └── get_latest_foto() -> FotoEvolucao | None
    ├── Clinical Indicators
    │   ├── get_indicadores(days) -> list[IndicadorClinico]
    │   ├── salvar_indicador(data) -> bool
    │   └── get_latest_indicador() -> IndicadorClinico | None
    ├── Stagnation
    │   ├── get_estagnacao() -> EstagnacaoInfo | None
    │   └── _detect_stagnation() -> EstagnacaoInfo | None
    ├── Hall of Fame
    │   └── get_campeoes(limit) -> list[HallOfFameEntry]
    ├── Wallet
    │   ├── get_carteira() -> CarteiraInfo
    │   └── resgatar_recompensa(recompensa_id) -> bool
    ├── XP History
    │   └── get_historico_xp(days) -> list[XPEntry]
    ├── LGPD Consents
    │   ├── get_consentimentos() -> list[Consentimento]
    │   ├── assinar_consentimento(tipo, versao) -> bool
    │   ├── revogar_consentimento(consentimento_id) -> bool
    │   └── has_active_consent(tipo) -> bool
    └── Utilities
        ├── _query(table, select, filters, order, desc, limit) -> list
        ├── _safe_float(value) -> float
        ├── _safe_date(date_str) -> str
        └── _calculate_change(current, previous) -> float | None
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any

from core.database import Database

logger = logging.getLogger("Melshape.Evolution")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Períodos padrão
_DEFAULT_MEASURES_DAYS: int = 90
_DEFAULT_INDICATORS_DAYS: int = 365
_DEFAULT_XP_DAYS: int = 30

# Thresholds de estagnação
_ESTAGNACAO_WARNING_DAYS: int = 7
_ESTAGNACAO_CRITICAL_DAYS: int = 14
_ESTAGNACAO_VARIATION_THRESHOLD: float = 0.3  # kg

# Limites do hall da fama
_HALL_OF_FAME_LIMIT: int = 10

# XP por ações específicas
_XP_MEDIDA: int = 10
_XP_FOTO: int = 10
_XP_INDICADOR: int = 15

# Moedas por ações
_MOEDAS_CHECKIN: int = 5
_MOEDAS_META: int = 50
_MOEDAS_STREAK: int = 20


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class ConsentmentType(str, Enum):
    """Tipos de consentimento LGPD."""
    TERMS = "termos"
    PRIVACY = "privacidade"
    MARKETING = "marketing"
    DATA_PROCESSING = "tratamento_dados"
    HEALTH_DATA = "dados_saude"
    
    @property
    def label(self) -> str:
        """Retorna label do tipo."""
        labels = {
            "termos": "Termos de Uso",
            "privacidade": "Política de Privacidade",
            "marketing": "Comunicações de Marketing",
            "tratamento_dados": "Tratamento de Dados",
            "dados_saude": "Dados de Saúde",
        }
        return labels.get(self.value, self.value)
    
    @property
    def is_required(self) -> bool:
        """Verifica se o consentimento é obrigatório."""
        return self.value in ["termos", "privacidade", "tratamento_dados", "dados_saude"]


class StagnationLevel(str, Enum):
    """Níveis de estagnação."""
    NORMAL = "normal"
    WARNING = "atencao"
    CRITICAL = "critico"
    
    @property
    def icon(self) -> str:
        """Retorna ícone do nível."""
        icons = {
            "normal": "🟢",
            "atencao": "🟡",
            "critico": "🔴",
        }
        return icons.get(self.value, "🟢")
    
    @property
    def label(self) -> str:
        """Retorna label do nível."""
        labels = {
            "normal": "Normal",
            "atencao": "Atenção",
            "critico": "Crítico",
        }
        return labels.get(self.value, "Normal")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MedidaCorporal:
    """
    Modelo de medida corporal.
    
    Attributes:
        id: ID da medida
        user_id: ID do usuário
        data_medicao: Data da medida
        peso: Peso (kg)
        cintura: Circunferência da cintura (cm)
        quadril: Circunferência do quadril (cm)
        braco: Circunferência do braço (cm)
        coxa: Circunferência da coxa (cm)
        gordura: Percentual de gordura (%)
        created_at: Timestamp de criação
    """
    id: str
    user_id: str
    data_medicao: str
    peso: float | None = None
    cintura: float | None = None
    quadril: float | None = None
    braco: float | None = None
    coxa: float | None = None
    gordura: float | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MedidaCorporal:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            data_medicao=data.get("data_medicao", date.today().isoformat()),
            peso=_safe_float(data.get("peso")),
            cintura=_safe_float(data.get("circunferencia_cintura")),
            quadril=_safe_float(data.get("circunferencia_quadril")),
            braco=_safe_float(data.get("circunferencia_braco")),
            coxa=_safe_float(data.get("circunferencia_coxa")),
            gordura=_safe_float(data.get("percentual_gordura")),
            created_at=data.get("criado_em", data.get("created_at", datetime.now(timezone.utc).isoformat())),
        )
    
    @property
    def has_peso(self) -> bool:
        """Verifica se tem peso registrado."""
        return self.peso is not None and self.peso > 0
    
    @property
    def has_medidas(self) -> bool:
        """Verifica se tem medidas registradas."""
        return any([
            self.cintura is not None and self.cintura > 0,
            self.quadril is not None and self.quadril > 0,
            self.braco is not None and self.braco > 0,
            self.coxa is not None and self.coxa > 0,
            self.gordura is not None and self.gordura > 0,
        ])
    
    @property
    def relacao_cintura_quadril(self) -> float | None:
        """Calcula relação cintura/quadril."""
        if self.cintura and self.quadril and self.quadril > 0:
            return round(self.cintura / self.quadril, 2)
        return None
    
    @property
    def days_ago(self) -> int:
        """Calcula dias desde a medição."""
        try:
            medicao_date = datetime.strptime(self.data_medicao, "%Y-%m-%d").date()
            return (date.today() - medicao_date).days
        except Exception:
            return 0
    
    @property
    def summary_text(self) -> str:
        """Retorna texto resumido da medida."""
        parts = []
        if self.has_peso:
            parts.append(f"{self.peso:.1f}kg")
        if self.cintura:
            parts.append(f"cintura {self.cintura:.0f}cm")
        if self.gordura:
            parts.append(f"{self.gordura:.1f}% gordura")
        return " | ".join(parts) if parts else "Sem dados"


@dataclass(frozen=True)
class MedidaComparison:
    """
    Comparação entre duas medidas corporais.
    
    Attributes:
        previous: Medida anterior
        current: Medida atual
        weight_change: Mudança de peso (kg)
        waist_change: Mudança de cintura (cm)
        hip_change: Mudança de quadril (cm)
        fat_change: Mudança de gordura (%)
        days_between: Dias entre as medições
    """
    previous: MedidaCorporal
    current: MedidaCorporal
    weight_change: float | None = None
    waist_change: float | None = None
    hip_change: float | None = None
    fat_change: float | None = None
    days_between: int = 0
    
    @property
    def has_weight_comparison(self) -> bool:
        """Verifica se há comparação de peso."""
        return self.weight_change is not None
    
    @property
    def weight_trend(self) -> str:
        """Retorna tendência de peso."""
        if self.weight_change is None:
            return "neutro"
        if self.weight_change < -0.5:
            return "perda"
        elif self.weight_change > 0.5:
            return "ganho"
        return "estavel"
    
    @property
    def weight_trend_icon(self) -> str:
        """Retorna ícone da tendência de peso."""
        icons = {
            "perda": "📉",
            "ganho": "📈",
            "estavel": "➡️",
            "neutro": "❓",
        }
        return icons.get(self.weight_trend, "❓")
    
    @property
    def summary_text(self) -> str:
        """Retorna texto resumido da comparação."""
        parts = []
        if self.has_weight_comparison:
            signal = "+" if self.weight_change > 0 else ""
            parts.append(f"Peso: {signal}{self.weight_change:.1f}kg")
        if self.waist_change is not None:
            signal = "+" if self.waist_change > 0 else ""
            parts.append(f"Cintura: {signal}{self.waist_change:.1f}cm")
        return " | ".join(parts) if parts else "Sem dados comparáveis"


@dataclass(frozen=True)
class FotoEvolucao:
    """
    Modelo de foto de evolução.
    
    Attributes:
        id: ID da foto
        user_id: ID do usuário
        url: URL da foto
        legenda: Legenda da foto
        peso_na_data: Peso na data da foto
        data_foto: Data da foto
        created_at: Timestamp de criação
    """
    id: str
    user_id: str
    url: str
    legenda: str = ""
    peso_na_data: float | None = None
    data_foto: str = field(default_factory=lambda: date.today().isoformat())
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FotoEvolucao:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            url=data.get("url_foto", data.get("url", "")),
            legenda=data.get("legenda", ""),
            peso_na_data=_safe_float(data.get("peso_na_data")),
            data_foto=data.get("data_foto", date.today().isoformat()),
            created_at=data.get("criado_em", data.get("created_at", datetime.now(timezone.utc).isoformat())),
        )
    
    @property
    def has_peso(self) -> bool:
        """Verifica se tem peso registrado."""
        return self.peso_na_data is not None and self.peso_na_data > 0
    
    @property
    def days_ago(self) -> int:
        """Calcula dias desde a foto."""
        try:
            foto_date = datetime.strptime(self.data_foto, "%Y-%m-%d").date()
            return (date.today() - foto_date).days
        except Exception:
            return 0
    
    @property
    def display_text(self) -> str:
        """Retorna texto para exibição."""
        parts = [self.data_foto]
        if self.legenda:
            parts.append(self.legenda)
        if self.has_peso:
            parts.append(f"{self.peso_na_data:.1f}kg")
        return " — ".join(parts)


@dataclass(frozen=True)
class IndicadorClinico:
    """
    Modelo de indicador clínico (exame).
    
    Attributes:
        id: ID do indicador
        user_id: ID do usuário
        data_coleta: Data da coleta
        glicemia: Glicemia em jejum (mg/dL)
        colesterol_total: Colesterol total (mg/dL)
        hdl: HDL (mg/dL)
        ldl: LDL (mg/dL)
        triglicerideos: Triglicerídeos (mg/dL)
        vitamina_d: Vitamina D (ng/mL)
        vitamina_b12: Vitamina B12 (pg/mL)
        ferritina: Ferritina (ng/mL)
        tsh: TSH (mUI/L)
        created_at: Timestamp de criação
    """
    id: str
    user_id: str
    data_coleta: str
    glicemia: float | None = None
    colesterol_total: float | None = None
    hdl: float | None = None
    ldl: float | None = None
    triglicerideos: float | None = None
    vitamina_d: float | None = None
    vitamina_b12: float | None = None
    ferritina: float | None = None
    tsh: float | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IndicadorClinico:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            data_coleta=data.get("data_coleta", date.today().isoformat()),
            glicemia=_safe_float(data.get("glicemia_jejum")),
            colesterol_total=_safe_float(data.get("colesterol_total")),
            hdl=_safe_float(data.get("colesterol_hdl")),
            ldl=_safe_float(data.get("colesterol_ldl")),
            triglicerideos=_safe_float(data.get("triglicerideos")),
            vitamina_d=_safe_float(data.get("vitamina_d")),
            vitamina_b12=_safe_float(data.get("vitamina_b12")),
            ferritina=_safe_float(data.get("ferritina")),
            tsh=_safe_float(data.get("tsh")),
            created_at=data.get("criado_em", data.get("created_at", datetime.now(timezone.utc).isoformat())),
        )
    
    @property
    def has_glicemia(self) -> bool:
        """Verifica se tem glicemia registrada."""
        return self.glicemia is not None and self.glicemia > 0
    
    @property
    def has_colesterol(self) -> bool:
        """Verifica se tem colesterol registrado."""
        return self.colesterol_total is not None and self.colesterol_total > 0
    
    @property
    def has_vitaminas(self) -> bool:
        """Verifica se tem vitaminas registradas."""
        return (
            (self.vitamina_d is not None and self.vitamina_d > 0) or
            (self.vitamina_b12 is not None and self.vitamina_b12 > 0)
        )
    
    @property
    def risco_cardiovascular(self) -> str | None:
        """Avalia risco cardiovascular simplificado."""
        if not self.has_colesterol or not self.has_glicemia:
            return None
        
        if self.colesterol_total > 240 or self.glicemia > 126:
            return "alto"
        elif self.colesterol_total > 200 or self.glicemia > 100:
            return "moderado"
        return "baixo"
    
    @property
    def risco_icon(self) -> str:
        """Retorna ícone do risco cardiovascular."""
        icons = {
            "alto": "🔴",
            "moderado": "🟡",
            "baixo": "🟢",
        }
        return icons.get(self.risco_cardiovascular or "", "❓")
    
    @property
    def days_ago(self) -> int:
        """Calcula dias desde a coleta."""
        try:
            coleta_date = datetime.strptime(self.data_coleta, "%Y-%m-%d").date()
            return (date.today() - coleta_date).days
        except Exception:
            return 0
    
    @property
    def summary_text(self) -> str:
        """Retorna texto resumido do indicador."""
        parts = []
        if self.has_glicemia:
            parts.append(f"Glicemia: {self.glicemia:.0f}mg/dL")
        if self.has_colesterol:
            parts.append(f"Col: {self.colesterol_total:.0f}mg/dL")
        if self.vitamina_d:
            parts.append(f"VitD: {self.vitamina_d:.0f}ng/mL")
        return " | ".join(parts) if parts else "Sem dados"


@dataclass(frozen=True)
class EstagnacaoInfo:
    """
    Informações sobre estagnação de peso.
    
    Attributes:
        dias_estagnado: Dias sem evolução de peso
        peso_inicial: Peso no início da estagnação
        peso_atual: Peso atual
        variacao: Variação no período
        level: Nível de estagnação
    """
    dias_estagnado: int
    peso_inicial: float | None = None
    peso_atual: float | None = None
    variacao: float | None = None
    level: StagnationLevel = StagnationLevel.NORMAL
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EstagnacaoInfo:
        """Cria uma instância a partir de um dicionário."""
        dias = int(data.get("dias_estagnado", 0))
        
        # Determina nível
        if dias >= _ESTAGNACAO_CRITICAL_DAYS:
            level = StagnationLevel.CRITICAL
        elif dias >= _ESTAGNACAO_WARNING_DAYS:
            level = StagnationLevel.WARNING
        else:
            level = StagnationLevel.NORMAL
        
        return cls(
            dias_estagnado=dias,
            peso_inicial=_safe_float(data.get("peso_inicial")),
            peso_atual=_safe_float(data.get("peso_atual")),
            variacao=_safe_float(data.get("variacao")),
            level=level,
        )
    
    @property
    def is_warning(self) -> bool:
        """Verifica se é um alerta de atenção."""
        return self.level == StagnationLevel.WARNING
    
    @property
    def is_critical(self) -> bool:
        """Verifica se é um alerta crítico."""
        return self.level == StagnationLevel.CRITICAL
    
    @property
    def is_normal(self) -> bool:
        """Verifica se está normal."""
        return self.level == StagnationLevel.NORMAL
    
    @property
    def nivel_label(self) -> str:
        """Retorna label do nível de estagnação."""
        return f"{self.level.icon} {self.level.label}"
    
    @property
    def mensagem(self) -> str:
        """Retorna mensagem contextual sobre estagnação."""
        if self.is_critical:
            return (
                f"⏸️ Seu peso está estagnado há {self.dias_estagnado} dias. "
                f"Isso pode indicar adaptação metabólica — "
                f"considere revisar o plano com seu profissional."
            )
        elif self.is_warning:
            return (
                f"📊 {self.dias_estagnado} dias sem variação de peso. "
                f"Normal em alguns momentos da jornada — mantenha a consistência."
            )
        return "📈 Sem sinais de estagnação. Continue assim!"
    
    @property
    def variacao_label(self) -> str:
        """Retorna label da variação."""
        if self.variacao is None:
            return "—"
        if self.variacao > 0:
            return f"+{self.variacao:.1f}kg"
        elif self.variacao < 0:
            return f"{self.variacao:.1f}kg"
        return "0kg"


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
    rank: int
    
    @classmethod
    def from_dict(cls, data: dict[str, Any], rank: int = 0) -> HallOfFameEntry:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            patient_id=data.get("perfil_id", data.get("patient_id", "")),
            patient_name=data.get("nome_completo", data.get("patient_name", "Paciente")),
            weight_loss=float(data.get("perda_peso", 0)),
            weight_loss_pct=float(data.get("perda_peso_pct", 0)),
            days=int(data.get("dias_jornada", 0)),
            transformation_score=int(data.get("score_transformacao", 0)),
            rank=rank,
        )
    
    @property
    def medal_icon(self) -> str:
        """Retorna ícone da medalha baseado no rank."""
        if self.rank == 1:
            return "🥇"
        elif self.rank == 2:
            return "🥈"
        elif self.rank == 3:
            return "🥉"
        return f"#{self.rank}"
    
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
        total_earned = moedas + (total_resgatado * 100)  # Estimativa
        
        # Calcula nível baseado em moedas totais
        level = 1
        if total_earned >= 1000:
            level = 5
        elif total_earned >= 500:
            level = 4
        elif total_earned >= 200:
            level = 3
        elif total_earned >= 100:
            level = 2
        
        return cls(
            moedas=moedas,
            recompensas_resgatadas=resgatadas,
            total_resgatado=total_resgatado,
            total_earned=total_earned,
            level=level,
        )
    
    @property
    def has_moedas(self) -> bool:
        """Verifica se tem moedas."""
        return self.moedas > 0
    
    @property
    def level_icon(self) -> str:
        """Retorna ícone do nível."""
        icons = {
            1: "🥉",
            2: "🥈",
            3: "🥇",
            4: "💎",
            5: "👑",
        }
        return icons.get(self.level, "🥉")
    
    @property
    def level_label(self) -> str:
        """Retorna label do nível."""
        labels = {
            1: "Iniciante",
            2: "Intermediário",
            3: "Avançado",
            4: "Expert",
            5: "Mestre",
        }
        return labels.get(self.level, "Iniciante")
    
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
            xp_ganho=int(data.get("xp_ganho", 0)),
            motivo=data.get("motivo", ""),
            created_at=data.get("criado_em", data.get("created_at", datetime.now(timezone.utc).isoformat())),
        )
    
    @property
    def motivo_label(self) -> str:
        """Retorna label do motivo."""
        labels = {
            "checkin": "✅ Check-in",
            "refeicao": "🍽️ Refeição",
            "pesagem": "⚖️ Pesagem",
            "habito": "📋 Hábito",
            "meta": "🎯 Meta",
            "medidas_corporais": "📏 Medidas",
            "foto_evolucao": "📸 Foto",
            "indicador_clinico": "🔬 Exame",
            "recomeco": "🌱 Recomeço",
        }
        return labels.get(self.motivo, self.motivo)
    
    @property
    def days_ago(self) -> int:
        """Calcula dias desde a entrada."""
        try:
            created_date = datetime.fromisoformat(self.created_at.replace("Z", "+00:00")).date()
            return (date.today() - created_date).days
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
        """Retorna label do tipo."""
        try:
            consent_type = ConsentmentType(self.tipo)
            return consent_type.label
        except ValueError:
            return self.tipo
    
    @property
    def is_required(self) -> bool:
        """Verifica se o consentimento é obrigatório."""
        try:
            consent_type = ConsentmentType(self.tipo)
            return consent_type.is_required
        except ValueError:
            return False


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _safe_float(value: Any) -> float | None:
    """
    Converte valor para float com segurança.
    
    Args:
        value: Valor a ser convertido
        
    Returns:
        Valor float ou None
    """
    if value is None:
        return None
    try:
        result = float(value)
        return result if result > 0 else None
    except (ValueError, TypeError):
        return None


def _safe_date(date_str: Any) -> str:
    """
    Converte data para string com segurança.
    
    Args:
        date_str: Data a ser convertida
        
    Returns:
        String da data ou ""
    """
    if not date_str:
        return ""
    try:
        return str(date_str)[:10]
    except (ValueError, TypeError, AttributeError):
        return str(date_str)


def _calculate_change(current: float | None, previous: float | None) -> float | None:
    """
    Calcula mudança entre dois valores.
    
    Args:
        current: Valor atual
        previous: Valor anterior
        
    Returns:
        Mudança ou None
    """
    if current is None or previous is None:
        return None
    return round(current - previous, 2)


# ─────────────────────────────────────────────────────────────────────────────
# EVOLUTION SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class EvolutionService:
    """
    Serviço de evolução completa do paciente.
    
    Gerencia medidas, fotos, exames, estagnação e gamificação.
    
    Example:
        >>> db = Database()
        >>> evolution = EvolutionService(db)
        >>> medidas = evolution.get_medidas(days=90)
        >>> for m in medidas:
        ...     print(f"{m.data_medicao}: {m.peso}kg")
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o serviço de evolução.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        self._uid = db.uid
        logger.debug("✅ EvolutionService inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # QUERY HELPER
    # ─────────────────────────────────────────────────────────────────────────

    def _query(
        self,
        table: str,
        select: str,
        filters: dict[str, Any] | None = None,
        order: str | None = None,
        desc: bool = True,
        limit: int = 100,
    ) -> list[dict]:
        """
        Helper genérico de query com fallback silencioso.
        
        Args:
            table: Nome da tabela/view
            select: Campos a selecionar
            filters: Filtros (ex: {"perfil_id": uid, "gte:data": cutoff})
            order: Campo para ordenação
            desc: Ordenação descendente
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
                else:
                    q = q.eq(col, val)
            
            if order:
                q = q.order(order, desc=desc)
            
            return q.limit(limit).execute().data or []
            
        except Exception as e:
            logger.warning(f"_query({table}): {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # MEDIDAS CORPORAIS
    # ─────────────────────────────────────────────────────────────────────────

    def get_medidas(self, days: int = _DEFAULT_MEASURES_DAYS) -> list[MedidaCorporal]:
        """
        Retorna medidas corporais dos últimos N dias.
        
        Args:
            days: Número de dias
            
        Returns:
            Lista de objetos MedidaCorporal
        """
        uid = self._uid()
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        
        # Tenta Supabase
        rows = self._query(
            "medidas_corporais",
            "*",
            filters={"perfil_id": uid, "gte:data_medicao": cutoff},
            order="data_medicao",
            desc=True,
        )
        
        if rows:
            return [MedidaCorporal.from_dict(row) for row in rows]
        
        # Fallback MockDB
        try:
            medidas = self.db.mock.get("medidas_corporais", [])
            patient_medidas = [
                m for m in medidas
                if m.get("user_id") == uid and m.get("data_medicao", "") >= cutoff
            ]
            patient_medidas.sort(key=lambda x: x.get("data_medicao", ""), reverse=True)
            return [MedidaCorporal.from_dict(m) for m in patient_medidas]
        except Exception as e:
            logger.warning(f"get_medidas MockDB: {e}")
        
        return []

    def get_latest_medida(self) -> MedidaCorporal | None:
        """
        Retorna a medida mais recente.
        
        Returns:
            Objeto MedidaCorporal ou None
        """
        medidas = self.get_medidas(days=365)
        return medidas[0] if medidas else None

    def compare_medidas(self) -> MedidaComparison | None:
        """
        Compara as duas últimas medidas corporais.
        
        Returns:
            Objeto MedidaComparison ou None
        """
        medidas = self.get_medidas(days=365)
        
        if len(medidas) < 2:
            return None
        
        current = medidas[0]
        previous = medidas[1]
        
        # Calcula mudanças
        weight_change = _calculate_change(current.peso, previous.peso)
        waist_change = _calculate_change(current.cintura, previous.cintura)
        hip_change = _calculate_change(current.quadril, previous.quadril)
        fat_change = _calculate_change(current.gordura, previous.gordura)
        
        # Calcula dias entre medições
        try:
            current_date = datetime.strptime(current.data_medicao, "%Y-%m-%d").date()
            previous_date = datetime.strptime(previous.data_medicao, "%Y-%m-%d").date()
            days_between = (current_date - previous_date).days
        except Exception:
            days_between = 0
        
        return MedidaComparison(
            previous=previous,
            current=current,
            weight_change=weight_change,
            waist_change=waist_change,
            hip_change=hip_change,
            fat_change=fat_change,
            days_between=days_between,
        )

    def salvar_medida(self, data: dict[str, Any]) -> bool:
        """
        Salva uma medida corporal.
        
        Args:
            data: Dicionário com dados da medida
            
        Returns:
            True se salvo com sucesso
        """
        uid = self._uid()
        
        if not (self.db.is_real and self.db.client):
            return self._salvar_medida_mock(data)
        
        try:
            payload = {
                "perfil_id": uid,
                "data_medicao": data.get("data_medicao", date.today().isoformat()),
                "peso": data.get("peso"),
                "circunferencia_cintura": data.get("cintura"),
                "circunferencia_quadril": data.get("quadril"),
                "circunferencia_braco": data.get("braco"),
                "circunferencia_coxa": data.get("coxa"),
                "percentual_gordura": data.get("gordura"),
            }
            
            # Remove valores None
            payload = {k: v for k, v in payload.items() if v is not None}
            
            self.db.client.table("medidas_corporais").insert(payload).execute()
            
            # Adiciona XP
            self.db.add_xp(_XP_MEDIDA, motivo="medidas_corporais")
            
            logger.info(f"✅ Medida salva: {payload.get('peso', 'sem peso')}kg")
            return True
            
        except Exception as e:
            logger.error(f"salvar_medida: {e}")
            return self._salvar_medida_mock(data)

    def _salvar_medida_mock(self, data: dict[str, Any]) -> bool:
        """Salva medida no MockDB."""
        try:
            medidas = self.db.mock.setdefault("medidas_corporais", [])
            medidas.append({
                "user_id": self._uid(),
                "data_medicao": data.get("data_medicao", date.today().isoformat()),
                "peso": data.get("peso"),
                "circunferencia_cintura": data.get("cintura"),
                "circunferencia_quadril": data.get("quadril"),
                "circunferencia_braco": data.get("braco"),
                "circunferencia_coxa": data.get("coxa"),
                "percentual_gordura": data.get("gordura"),
                "criado_em": datetime.now(timezone.utc).isoformat(),
            })
            self.db.add_xp(_XP_MEDIDA, motivo="medidas_corporais")
            logger.info(f"✅ Medida salva no MockDB")
            return True
        except Exception as e:
            logger.error(f"_salvar_medida_mock: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # FOTOS
    # ─────────────────────────────────────────────────────────────────────────

    def get_fotos(self) -> list[FotoEvolucao]:
        """
        Retorna fotos de evolução do paciente.
        
        Returns:
            Lista de objetos FotoEvolucao (ordenados por data descendente)
        """
        uid = self._uid()
        
        # Tenta Supabase
        rows = self._query(
            "fotos_evolucao",
            "*",
            filters={"perfil_id": uid},
            order="data_foto",
            desc=True,
        )
        
        if rows:
            return [FotoEvolucao.from_dict(row) for row in rows]
        
        # Fallback MockDB
        try:
            fotos = self.db.mock.get("fotos_evolucao", {})
            patient_fotos = fotos.get(uid, [])
            patient_fotos.sort(key=lambda x: x.get("data_foto", ""), reverse=True)
            return [FotoEvolucao.from_dict(f) for f in patient_fotos]
        except Exception as e:
            logger.warning(f"get_fotos MockDB: {e}")
        
        return []

    def get_latest_foto(self) -> FotoEvolucao | None:
        """
        Retorna a foto mais recente.
        
        Returns:
            Objeto FotoEvolucao ou None
        """
        fotos = self.get_fotos()
        return fotos[0] if fotos else None

    def salvar_foto(self, url: str, legenda: str = "", peso: float = 0.0) -> bool:
        """
        Salva uma foto de evolução.
        
        Args:
            url: URL da foto
            legenda: Legenda da foto
            peso: Peso na data da foto
            
        Returns:
            True se salva com sucesso
        """
        if not url.strip():
            logger.warning("salvar_foto: URL vazia")
            return False
        
        uid = self._uid()
        
        if not (self.db.is_real and self.db.client):
            return self._salvar_foto_mock(url, legenda, peso)
        
        try:
            self.db.client.table("fotos_evolucao").insert({
                "perfil_id": uid,
                "url_foto": url.strip(),
                "legenda": legenda.strip() or None,
                "peso_na_data": peso or None,
                "data_foto": date.today().isoformat(),
            }).execute()
            
            self.db.add_xp(_XP_FOTO, motivo="foto_evolucao")
            
            logger.info(f"✅ Foto salva: {url[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"salvar_foto: {e}")
            return self._salvar_foto_mock(url, legenda, peso)

    def _salvar_foto_mock(self, url: str, legenda: str, peso: float) -> bool:
        """Salva foto no MockDB."""
        try:
            uid = self._uid()
            fotos = self.db.mock.setdefault("fotos_evolucao", {})
            fotos.setdefault(uid, []).append({
                "url": url.strip(),
                "legenda": legenda.strip(),
                "peso_na_data": peso or None,
                "data_foto": date.today().isoformat(),
                "criado_em": datetime.now(timezone.utc).isoformat(),
            })
            self.db.add_xp(_XP_FOTO, motivo="foto_evolucao")
            logger.info(f"✅ Foto salva no MockDB")
            return True
        except Exception as e:
            logger.error(f"_salvar_foto_mock: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # INDICADORES CLÍNICOS
    # ─────────────────────────────────────────────────────────────────────────

    def get_indicadores(self, days: int = _DEFAULT_INDICATORS_DAYS) -> list[IndicadorClinico]:
        """
        Retorna indicadores clínicos dos últimos N dias.
        
        Args:
            days: Número de dias
            
        Returns:
            Lista de objetos IndicadorClinico
        """
        uid = self._uid()
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        
        # Tenta Supabase
        rows = self._query(
            "indicadores_clinicos",
            "*",
            filters={"perfil_id": uid, "gte:data_coleta": cutoff},
            order="data_coleta",
            desc=True,
        )
        
        if rows:
            return [IndicadorClinico.from_dict(row) for row in rows]
        
        # Fallback MockDB
        try:
            indicadores = self.db.mock.get("indicadores_clinicos", [])
            patient_indicadores = [
                i for i in indicadores
                if i.get("user_id") == uid and i.get("data_coleta", "") >= cutoff
            ]
            patient_indicadores.sort(key=lambda x: x.get("data_coleta", ""), reverse=True)
            return [IndicadorClinico.from_dict(i) for i in patient_indicadores]
        except Exception as e:
            logger.warning(f"get_indicadores MockDB: {e}")
        
        return []

    def get_latest_indicador(self) -> IndicadorClinico | None:
        """
        Retorna o indicador clínico mais recente.
        
        Returns:
            Objeto IndicadorClinico ou None
        """
        indicadores = self.get_indicadores(days=365)
        return indicadores[0] if indicadores else None

    def salvar_indicador(self, data: dict[str, Any]) -> bool:
        """
        Salva um indicador clínico (exame).
        
        Args:
            data: Dicionário com dados do indicador
            
        Returns:
            True se salvo com sucesso
        """
        uid = self._uid()
        
        if not (self.db.is_real and self.db.client):
            return self._salvar_indicador_mock(data)
        
        try:
            payload = {
                "perfil_id": uid,
                "data_coleta": data.get("data_coleta", date.today().isoformat()),
                "glicemia_jejum": data.get("glicemia"),
                "colesterol_total": data.get("colesterol_total"),
                "colesterol_hdl": data.get("hdl"),
                "colesterol_ldl": data.get("ldl"),
                "triglicerideos": data.get("triglicerideos"),
                "vitamina_d": data.get("vitamina_d"),
                "vitamina_b12": data.get("b12"),
                "ferritina": data.get("ferritina"),
                "tsh": data.get("tsh"),
            }
            
            # Remove valores None
            payload = {k: v for k, v in payload.items() if v is not None}
            
            self.db.client.table("indicadores_clinicos").insert(payload).execute()
            
            self.db.add_xp(_XP_INDICADOR, motivo="indicador_clinico")
            
            logger.info(f"✅ Indicador salvo: glicemia {data.get('glicemia', '—')}")
            return True
            
        except Exception as e:
            logger.error(f"salvar_indicador: {e}")
            return self._salvar_indicador_mock(data)

    def _salvar_indicador_mock(self, data: dict[str, Any]) -> bool:
        """Salva indicador no MockDB."""
        try:
            indicadores = self.db.mock.setdefault("indicadores_clinicos", [])
            indicadores.append({
                "user_id": self._uid(),
                "data_coleta": data.get("data_coleta", date.today().isoformat()),
                "glicemia_jejum": data.get("glicemia"),
                "colesterol_total": data.get("colesterol_total"),
                "colesterol_hdl": data.get("hdl"),
                "colesterol_ldl": data.get("ldl"),
                "triglicerideos": data.get("triglicerideos"),
                "vitamina_d": data.get("vitamina_d"),
                "vitamina_b12": data.get("b12"),
                "ferritina": data.get("ferritina"),
                "tsh": data.get("tsh"),
                "criado_em": datetime.now(timezone.utc).isoformat(),
            })
            self.db.add_xp(_XP_INDICADOR, motivo="indicador_clinico")
            logger.info(f"✅ Indicador salvo no MockDB")
            return True
        except Exception as e:
            logger.error(f"_salvar_indicador_mock: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # ESTAGNAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def get_estagnacao(self) -> EstagnacaoInfo | None:
        """
        Detecta estagnação de peso.
        
        Returns:
            Objeto EstagnacaoInfo ou None
        """
        # Tenta view do Supabase
        uid = self._uid()
        
        if self.db.is_real and self.db.client:
            try:
                rows = self._query(
                    "vw_estagnacao_clinica",
                    "*",
                    filters={"perfil_id": uid},
                    limit=1,
                )
                
                if rows:
                    return EstagnacaoInfo.from_dict(rows[0])
            except Exception as e:
                logger.warning(f"get_estagnacao view: {e}")
        
        # Fallback: detecção manual
        return self._detect_stagnation()

    def _detect_stagnation(self) -> EstagnacaoInfo | None:
        """
        Detecta estagnação manualmente a partir das pesagens.
        
        Returns:
            Objeto EstagnacaoInfo ou None
        """
        try:
            # Busca pesagens recentes
            weights = self.db.get_weights(days=30)
            
            if weights.empty or len(weights) < 3:
                return None
            
            # Pega últimos 14 dias
            recent = weights.tail(14)
            
            if len(recent) < 3:
                return None
            
            # Calcula variação
            first_weight = float(recent.iloc[0]["weight"])
            last_weight = float(recent.iloc[-1]["weight"])
            variation = last_weight - first_weight
            
            # Conta dias sem variação significativa
            days_stagnant = 0
            for i in range(1, len(recent)):
                current = float(recent.iloc[i]["weight"])
                previous = float(recent.iloc[i - 1]["weight"])
                
                if abs(current - previous) < _ESTAGNACAO_VARIATION_THRESHOLD:
                    days_stagnant += 1
            
            if days_stagnant < 3:
                return None
            
            # Determina nível
            if days_stagnant >= _ESTAGNACAO_CRITICAL_DAYS:
                level = StagnationLevel.CRITICAL
            elif days_stagnant >= _ESTAGNACAO_WARNING_DAYS:
                level = StagnationLevel.WARNING
            else:
                level = StagnationLevel.NORMAL
            
            return EstagnacaoInfo(
                dias_estagnado=days_stagnant,
                peso_inicial=first_weight,
                peso_atual=last_weight,
                variacao=round(variation, 1),
                level=level,
            )
            
        except Exception as e:
            logger.warning(f"_detect_stagnation: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # HALL DA FAMA
    # ─────────────────────────────────────────────────────────────────────────

    def get_campeoes(self, limit: int = _HALL_OF_FAME_LIMIT) -> list[HallOfFameEntry]:
        """
        Retorna o Hall da Fama (top pacientes por transformação).
        
        Args:
            limit: Número máximo de entradas
            
        Returns:
            Lista de objetos HallOfFameEntry
        """
        # Tenta view do Supabase
        if self.db.is_real and self.db.client:
            try:
                rows = self._query(
                    "vw_campeoes_transformacao",
                    "*",
                    order="score_transformacao",
                    desc=True,
                    limit=limit,
                )
                
                if rows:
                    return [HallOfFameEntry.from_dict(row, rank=i + 1) for i, row in enumerate(rows)]
            except Exception as e:
                logger.warning(f"get_campeoes view: {e}")
        
        # Fallback MockDB
        try:
            campeoes = self.db.mock.get("campeoes_transformacao", [])
            campeoes_sorted = sorted(
                campeoes,
                key=lambda x: x.get("score_transformacao", 0),
                reverse=True,
            )[:limit]
            return [HallOfFameEntry.from_dict(c, rank=i + 1) for i, c in enumerate(campeoes_sorted)]
        except Exception as e:
            logger.warning(f"get_campeoes MockDB: {e}")
        
        return []

    # ─────────────────────────────────────────────────────────────────────────
    # CARTEIRA GAMIFICADA
    # ─────────────────────────────────────────────────────────────────────────

    def get_carteira(self) -> CarteiraInfo:
        """
        Retorna informações da carteira gamificada.
        
        Returns:
            Objeto CarteiraInfo
        """
        uid = self._uid()
        
        # Tenta Supabase
        if self.db.is_real and self.db.client:
            try:
                rows = self._query(
                    "carteira_gamificacao",
                    "*",
                    filters={"perfil_id": uid},
                    limit=1,
                )
                
                if rows:
                    return CarteiraInfo.from_dict(rows[0])
            except Exception as e:
                logger.warning(f"get_carteira Supabase: {e}")
        
        # Fallback: estima baseado em XP
        try:
            xp = self.db.get_xp()
            moedas = xp // 10  # 1 moeda a cada 10 XP
            
            return CarteiraInfo(
                moedas=moedas,
                recompensas_resgatadas=[],
                total_resgatado=0,
                total_earned=moedas,
                level=1,
            )
        except Exception as e:
            logger.warning(f"get_carteira fallback: {e}")
        
        return CarteiraInfo()

    def resgatar_recompensa(self, recompensa_id: str, custo: int) -> bool:
        """
        Resgata uma recompensa da carteira.
        
        Args:
            recompensa_id: ID da recompensa
            custo: Custo em moedas
            
        Returns:
            True se resgatada com sucesso
        """
        carteira = self.get_carteira()
        
        if carteira.moedas < custo:
            logger.warning(f"resgatar_recompensa: moedas insuficientes ({carteira.moedas} < {custo})")
            return False
        
        uid = self._uid()
        
        if self.db.is_real and self.db.client:
            try:
                # Atualiza carteira
                self.db.client.table("carteira_gamificacao").update({
                    "moedas": carteira.moedas - custo,
                }).eq("perfil_id", uid).execute()
                
                # Registra resgate
                self.db.client.table("recompensas_resgatadas").insert({
                    "perfil_id": uid,
                    "recompensa_id": recompensa_id,
                    "custo": custo,
                }).execute()
                
                logger.info(f"✅ Recompensa resgatada: {recompensa_id} ({custo} moedas)")
                return True
            except Exception as e:
                logger.error(f"resgatar_recompensa: {e}")
        
        # Fallback MockDB
        try:
            carteiras = self.db.mock.setdefault("carteira_gamificacao", {})
            carteira_data = carteiras.get(uid, {"moedas": carteira.moedas})
            carteira_data["moedas"] -= custo
            
            resgatadas = carteira_data.get("recompensas_resgatadas", [])
            resgatadas.append(recompensa_id)
            carteira_data["recompensas_resgatadas"] = resgatadas
            
            carteiras[uid] = carteira_data
            
            logger.info(f"✅ Recompensa resgatada no MockDB: {recompensa_id}")
            return True
        except Exception as e:
            logger.error(f"resgatar_recompensa MockDB: {e}")
        
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # HISTÓRICO XP
    # ─────────────────────────────────────────────────────────────────────────

    def get_historico_xp(self, days: int = _DEFAULT_XP_DAYS) -> list[XPEntry]:
        """
        Retorna histórico de XP dos últimos N dias.
        
        Args:
            days: Número de dias
            
        Returns:
            Lista de objetos XPEntry
        """
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
        try:
            historico = self.db.mock.get("historico_xp", [])
            patient_historico = [
                x for x in historico
                if x.get("user_id") == uid and x.get("criado_em", "") >= cutoff
            ]
            patient_historico.sort(key=lambda x: x.get("criado_em", ""), reverse=True)
            return [XPEntry.from_dict(x) for x in patient_historico]
        except Exception as e:
            logger.warning(f"get_historico_xp MockDB: {e}")
        
        return []

    def get_xp_summary(self, days: int = 30) -> dict[str, Any]:
        """
        Retorna resumo de XP do período.
        
        Args:
            days: Número de dias
            
        Returns:
            Dicionário com total, média diária, etc.
        """
        entries = self.get_historico_xp(days=days)
        
        if not entries:
            return {
                "total": 0,
                "media_diaria": 0,
                "dias_ativos": 0,
                "top_motivo": "—",
            }
        
        total = sum(e.xp_ganho for e in entries)
        dias_ativos = len(set(e.created_at[:10] for e in entries))
        media_diaria = total / days if days > 0 else 0
        
        # Top motivo
        motivos: dict[str, int] = {}
        for entry in entries:
            motivos[entry.motivo] = motivos.get(entry.motivo, 0) + entry.xp_ganho
        
        top_motivo = max(motivos.items(), key=lambda x: x[1])[0] if motivos else "—"
        
        return {
            "total": total,
            "media_diaria": round(media_diaria, 1),
            "dias_ativos": dias_ativos,
            "top_motivo": top_motivo,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # CONSENTIMENTOS LGPD
    # ─────────────────────────────────────────────────────────────────────────

    def get_consentimentos(self) -> list[Consentimento]:
        """
        Retorna todos os consentimentos do usuário.
        
        Returns:
            Lista de objetos Consentimento
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
        try:
            consentimentos = self.db.mock.get("consentimentos", [])
            patient_consentimentos = [
                c for c in consentimentos
                if c.get("user_id") == uid
            ]
            return [Consentimento.from_dict(c) for c in patient_consentimentos]
        except Exception as e:
            logger.warning(f"get_consentimentos MockDB: {e}")
        
        return []

    def has_active_consent(self, tipo: str) -> bool:
        """
        Verifica se o usuário tem consentimento ativo para um tipo.
        
        Args:
            tipo: Tipo de consentimento
            
        Returns:
            True se tem consentimento ativo
        """
        consentimentos = self.get_consentimentos()
        
        for consent in consentimentos:
            if consent.tipo == tipo and consent.is_active:
                return True
        
        return False

    def assinar_consentimento(self, tipo: str, versao: str) -> bool:
        """
        Assina um consentimento LGPD.
        
        Args:
            tipo: Tipo de consentimento
            versao: Versão do documento
            
        Returns:
            True se assinado com sucesso
        """
        if not tipo or not versao:
            logger.warning("assinar_consentimento: tipo ou versão não informados")
            return False
        
        uid = self._uid()
        
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
            True se revogado com sucesso
        """
        if not consentimento_id:
            logger.warning("revogar_consentimento: consentimento_id não informado")
            return False
        
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

    def get_required_consents_status(self) -> dict[str, bool]:
        """
        Retorna status dos consentimentos obrigatórios.
        
        Returns:
            Dicionário com tipo -> status (True se ativo)
        """
        consentimentos = self.get_consentimentos()
        
        status = {}
        for consent_type in ConsentmentType:
            if consent_type.is_required:
                has_active = any(
                    c.tipo == consent_type.value and c.is_active
                    for c in consentimentos
                )
                status[consent_type.value] = has_active
        
        return status


__all__ = [
    "EvolutionService",
    "MedidaCorporal",
    "MedidaComparison",
    "FotoEvolucao",
    "IndicadorClinico",
    "EstagnacaoInfo",
    "HallOfFameEntry",
    "CarteiraInfo",
    "XPEntry",
    "Consentimento",
    "ConsentmentType",
    "StagnationLevel",
]
