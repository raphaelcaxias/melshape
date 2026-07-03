"""
Melshape — Professional Service.

Serviço para profissionais de saúde: gestão de pacientes, resumos,
pacientes em risco e dashboard executivo.

Princípios:
- Pacientes: lista de pacientes vinculados ao profissional
- Resumo: visão rápida do estado do paciente
- Risco: identificação de pacientes que precisam de atenção
- Executivo: métricas agregadas para clínicas
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Modelos: dataclasses imutáveis para todas as entidades

Views utilizadas:
    - vw_dashboard_paciente: resumo do paciente
    - vw_prioridade_intervencao: pacientes em risco
    - vw_resumo_executivo: métricas da clínica

Arquitetura:
    ProfessionalService
    ├── Pacientes
    │   ├── get_patients(pro_email, limit) -> list[PatientSummary]
    │   ├── get_patient_summary(perfil_id) -> PatientSummary
    │   └── get_patient_count(pro_email) -> int
    ├── Risco
    │   ├── get_patients_at_risk(limit) -> list[RiskPatient]
    │   ├── get_patients_by_risk_level() -> dict[str, list[RiskPatient]]
    │   └── get_active_patients(pro_email, days) -> int
    ├── Executivo
    │   └── get_executive_summary() -> ExecutiveSummary
    ├── Autenticação
    │   ├── authenticate(email, password) -> Professional | None
    │   └── get_by_email(email) -> Professional | None
    └── Vínculo
        ├── link_patient(pro_email, paciente_email) -> bool
        └── unlink_patient(paciente_email) -> bool
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.database import Database
from core.models import Professional

logger = logging.getLogger("Melshape.Professional")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DO SERVIÇO PROFISSIONAL
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PatientSummary:
    """
    Modelo de resumo do paciente para o profissional.
    
    Attributes:
        id: ID do paciente
        nome_completo: Nome completo
        email: Email do paciente
        tipo_jornada: Modo de saúde (general/fitness/bariatric/glp1)
        peso_atual: Peso atual (kg)
        peso_desejado: Peso objetivo (kg)
        altura: Altura (cm)
        idade: Idade (anos)
        genero: Gênero (female/male/other)
        criado_em: Data de criação
        onboarding_concluido: Se onboarding foi concluído
        ultimo_acesso: Data do último acesso
        profissional_id: ID do profissional vinculado
        ultimo_peso: Último peso registrado
        data_ultimo_peso: Data do último peso
        peso_anterior: Peso anterior (para cálculo de variação)
        variacao_peso: Variação de peso (kg)
        streak: Dias consecutivos de check-in
    """
    id: str
    nome_completo: str
    email: str = ""
    tipo_jornada: str = "general"
    peso_atual: float | None = None
    peso_desejado: float | None = None
    altura: int | None = None
    idade: int | None = None
    genero: str = "female"
    criado_em: str = ""
    onboarding_concluido: bool = False
    ultimo_acesso: str | None = None
    profissional_id: str | None = None
    ultimo_peso: float | None = None
    data_ultimo_peso: str | None = None
    peso_anterior: float | None = None
    variacao_peso: float | None = None
    streak: int = 0
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PatientSummary:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            nome_completo=data.get("nome_completo", ""),
            email=data.get("email", ""),
            tipo_jornada=data.get("tipo_jornada", data.get("health_mode", "general")),
            peso_atual=data.get("peso_atual", data.get("current_weight")),
            peso_desejado=data.get("peso_desejado", data.get("goal_weight")),
            altura=data.get("altura", data.get("height")),
            idade=data.get("idade", data.get("age")),
            genero=data.get("genero", data.get("gender", "female")),
            criado_em=data.get("criado_em", data.get("created_at", "")),
            onboarding_concluido=data.get("onboarding_concluido", data.get("onboarding_done", False)),
            ultimo_acesso=data.get("ultimo_acesso"),
            profissional_id=data.get("profissional_id", data.get("professional_id")),
            ultimo_peso=data.get("ultimo_peso"),
            data_ultimo_peso=data.get("data_ultimo_peso"),
            peso_anterior=data.get("peso_anterior"),
            variacao_peso=data.get("variacao_peso"),
            streak=data.get("streak", 0),
        )
    
    @property
    def has_recent_weight(self) -> bool:
        """Verifica se tem peso registrado recentemente."""
        return self.ultimo_peso is not None and self.ultimo_peso > 0
    
    @property
    def weight_change_label(self) -> str:
        """Retorna rótulo da variação de peso."""
        if self.variacao_peso is None:
            return "—"
        if self.variacao_peso > 0:
            return f"+{self.variacao_peso:.1f} kg"
        elif self.variacao_peso < 0:
            return f"{self.variacao_peso:.1f} kg"
        return "0 kg"


@dataclass(frozen=True)
class RiskPatient:
    """
    Modelo de paciente em risco.
    
    Attributes:
        id: ID do paciente
        nome_completo: Nome completo
        email: Email do paciente
        score_prioridade: Score de prioridade (0-100)
        risco_abandono: Percentual de risco de abandono (0-100)
        score_engajamento: Score de engajamento (0-100)
        score_adesao: Score de adesão (0-100)
    """
    id: str
    nome_completo: str
    email: str = ""
    score_prioridade: int = 0
    risco_abandono: int = 0
    score_engajamento: int = 0
    score_adesao: int = 0
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RiskPatient:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            nome_completo=data.get("nome_completo", ""),
            email=data.get("email", ""),
            score_prioridade=int(data.get("score_prioridade", 0)),
            risco_abandono=int(data.get("risco_abandono", 0)),
            score_engajamento=int(data.get("score_engajamento", 0)),
            score_adesao=int(data.get("score_adesao", 0)),
        )
    
    @property
    def risk_level(self) -> str:
        """Retorna nível de risco baseado no score."""
        if self.score_prioridade >= 70:
            return "critical"
        elif self.score_prioridade >= 50:
            return "high"
        elif self.score_prioridade >= 30:
            return "medium"
        return "low"
    
    @property
    def risk_level_label(self) -> str:
        """Retorna rótulo do nível de risco."""
        labels = {
            "critical": "🔴 Crítico",
            "high": "🟠 Alto",
            "medium": "🟡 Médio",
            "low": "🟢 Baixo",
        }
        return labels.get(self.risk_level, "🟢 Baixo")


@dataclass(frozen=True)
class ExecutiveSummary:
    """
    Modelo de resumo executivo para clínicas.
    
    Attributes:
        total_pacientes: Total de pacientes
        pacientes_ativos: Pacientes com onboarding concluído
        pacientes_inativos: Pacientes sem onboarding
        pacientes_em_risco: Pacientes com risco alto/crítico
        aderencia_media: Percentual médio de aderência
        consistencia_media: Percentual médio de consistência
        risco_abandono_medio: Percentual médio de risco de abandono
        receita_mensal: Receita mensal estimada
        score_transformacao_medio: Score médio de transformação
        score_engajamento_medio: Score médio de engajamento
    """
    total_pacientes: int = 0
    pacientes_ativos: int = 0
    pacientes_inativos: int = 0
    pacientes_em_risco: int = 0
    aderencia_media: float = 0.0
    consistencia_media: float = 0.0
    risco_abandono_medio: float = 0.0
    receita_mensal: float = 0.0
    score_transformacao_medio: float = 0.0
    score_engajamento_medio: float = 0.0
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutiveSummary:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            total_pacientes=int(data.get("total_pacientes", 0)),
            pacientes_ativos=int(data.get("pacientes_ativos", 0)),
            pacientes_inativos=int(data.get("pacientes_inativos", 0)),
            pacientes_em_risco=int(data.get("pacientes_em_risco", 0)),
            aderencia_media=float(data.get("aderencia_media", 0.0)),
            consistencia_media=float(data.get("consistencia_media", 0.0)),
            risco_abandono_medio=float(data.get("risco_abandono_medio", 0.0)),
            receita_mensal=float(data.get("receita_mensal", 0.0)),
            score_transformacao_medio=float(data.get("score_transformacao_medio", 0.0)),
            score_engajamento_medio=float(data.get("score_engajamento_medio", 0.0)),
        )
    
    @property
    def active_rate(self) -> float:
        """Calcula taxa de pacientes ativos."""
        if self.total_pacientes == 0:
            return 0.0
        return (self.pacientes_ativos / self.total_pacientes) * 100


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Thresholds de risco
_RISK_CRITICAL: int = 70
_RISK_HIGH: int = 50
_RISK_MEDIUM: int = 30

# Limite padrão de pacientes
_DEFAULT_PATIENT_LIMIT: int = 50
_DEFAULT_RISK_LIMIT: int = 20


# ─────────────────────────────────────────────────────────────────────────────
# PROFESSIONAL SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class ProfessionalService:
    """
    Serviço para profissionais de saúde.
    
    Gerencia pacientes vinculados, resumos clínicos e autenticação.
    
    Example:
        >>> db = Database()
        >>> pro_service = ProfessionalService(db)
        >>> patients = pro_service.get_patients("doctor@example.com")
        >>> for p in patients:
        ...     print(f"{p.nome_completo} - {p.tipo_jornada}")
    """

    def __init__(self, db: Database) -> None:
        """
        Inicializa o serviço profissional.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        logger.debug("✅ ProfessionalService inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # PACIENTES
    # ─────────────────────────────────────────────────────────────────────────

    def get_patients(
        self,
        pro_email: str,
        limit: int = _DEFAULT_PATIENT_LIMIT,
        include_inactive: bool = False,
    ) -> list[PatientSummary]:
        """
        Retorna pacientes vinculados ao profissional.
        
        Args:
            pro_email: Email do profissional
            limit: Número máximo de pacientes
            include_inactive: Incluir pacientes inativos
            
        Returns:
            Lista de objetos PatientSummary
            
        Example:
            >>> patients = pro_service.get_patients("doctor@example.com", limit=20)
            >>> for p in patients:
            ...     print(f"{p.nome_completo} - {p.tipo_jornada}")
        """
        # Validação
        if not pro_email or not pro_email.strip():
            logger.warning("get_patients: pro_email não informado")
            return []

        # 1. Tenta Supabase
        if self.db.is_real and self.db.client:
            try:
                query = (
                    self.db.client.table("perfis")
                    .select(
                        "id, nome_completo, email, tipo_jornada, "
                        "peso_atual, criado_em, onboarding_concluido, "
                        "ultimo_acesso, profissional_id"
                    )
                    .eq("profissional_id", pro_email)
                    .order("nome_completo")
                    .limit(limit)
                )

                if not include_inactive:
                    query = query.eq("onboarding_concluido", True)

                response = query.execute()
                patients_data = response.data or []
                
                # Converte para PatientSummary e adiciona métricas
                patients = []
                for p_data in patients_data:
                    patient = PatientSummary.from_dict(p_data)
                    # Adiciona resumo rápido
                    quick_summary = self._get_patient_quick_summary(patient.id)
                    patient = PatientSummary(
                        **{**patient.__dict__, **quick_summary}
                    )
                    patients.append(patient)
                
                logger.info(f"✅ {len(patients)} pacientes encontrados para {pro_email}")
                return patients

            except Exception as e:
                logger.error(f"get_patients Supabase: {e}")

        # 2. Fallback MockDB
        patients = self._get_patients_from_mock(pro_email, include_inactive, limit)
        logger.info(f"✅ {len(patients)} pacientes encontrados no MockDB para {pro_email}")
        return patients

    def _get_patients_from_mock(
        self,
        pro_email: str,
        include_inactive: bool,
        limit: int,
    ) -> list[PatientSummary]:
        """
        Busca pacientes no MockDB.
        
        Args:
            pro_email: Email do profissional
            include_inactive: Incluir pacientes inativos
            limit: Número máximo de pacientes
            
        Returns:
            Lista de objetos PatientSummary
        """
        # Busca todos os usuários
        all_users = self.db.get_all_users() if hasattr(self.db, 'get_all_users') else []
        
        # Se não existir get_all_users, usa método alternativo
        if not all_users:
            # Fallback: busca via get_user com email vazio não funciona
            # Então retorna lista vazia
            logger.warning("get_all_users não disponível no Database")
            return []
        
        patients = []
        for user_data in all_users:
            if user_data.get("professional_id") == pro_email:
                # Filtra inativos se necessário
                if not include_inactive and not user_data.get("onboarding_done", False):
                    continue
                
                patient = PatientSummary.from_dict(user_data)
                patients.append(patient)
                
                if len(patients) >= limit:
                    break

        return patients

    def get_patient_summary(self, perfil_id: str) -> PatientSummary:
        """
        Retorna resumo completo do paciente para o profissional.
        
        Args:
            perfil_id: ID do paciente
            
        Returns:
            Objeto PatientSummary com resumo completo
            
        Example:
            >>> summary = pro_service.get_patient_summary("patient_id")
            >>> print(f"Peso: {summary.peso_atual} kg")
        """
        if not perfil_id or not perfil_id.strip():
            logger.warning("get_patient_summary: perfil_id não informado")
            return PatientSummary(id="", nome_completo="")

        # 1. Tenta Supabase via view
        if self.db.is_real and self.db.client:
            try:
                response = (
                    self.db.client.table("vw_dashboard_paciente")
                    .select("*")
                    .eq("perfil_id", perfil_id)
                    .limit(1)
                    .execute()
                )

                if response.data:
                    logger.debug(f"✅ Patient summary (view): {perfil_id}")
                    return PatientSummary.from_dict(response.data[0])

            except Exception as e:
                logger.warning(f"get_patient_summary view falhou: {e}")

        # 2. Tenta Supabase via tabelas individuais
        if self.db.is_real and self.db.client:
            try:
                summary_data = self._build_patient_summary_from_tables(perfil_id)
                if summary_data:
                    return PatientSummary.from_dict(summary_data)
            except Exception as e:
                logger.warning(f"get_patient_summary tables falhou: {e}")

        # 3. Fallback MockDB
        return self._get_patient_summary_from_mock(perfil_id)

    def _build_patient_summary_from_tables(self, perfil_id: str) -> dict[str, Any]:
        """
        Constrói resumo do paciente a partir de tabelas individuais.
        
        Args:
            perfil_id: ID do paciente
            
        Returns:
            Dicionário com resumo
        """
        summary = {}

        # Busca perfil
        profile_response = (
            self.db.client.table("perfis")
            .select("nome_completo, tipo_jornada, peso_atual, peso_desejado, altura, idade, genero")
            .eq("id", perfil_id)
            .limit(1)
            .execute()
        )

        if profile_response.data:
            summary.update(profile_response.data[0])

        # Busca últimas pesagens
        weights_response = (
            self.db.client.table("pesagens")
            .select("peso, data_pesagem")
            .eq("perfil_id", perfil_id)
            .order("data_pesagem", desc=True)
            .limit(2)
            .execute()
        )

        if weights_response.data:
            weights = weights_response.data
            summary["ultimo_peso"] = weights[0]["peso"]
            summary["data_ultimo_peso"] = weights[0]["data_pesagem"]

            if len(weights) > 1:
                summary["peso_anterior"] = weights[1]["peso"]
                summary["variacao_peso"] = round(weights[0]["peso"] - weights[1]["peso"], 1)

        # Busca streak de check-in
        try:
            checkins_response = (
                self.db.client.table("checkins")
                .select("data_checkin")
                .eq("perfil_id", perfil_id)
                .order("data_checkin", desc=True)
                .limit(30)
                .execute()
            )

            dates = [c["data_checkin"] for c in (checkins_response.data or [])]
            streak = self._calculate_streak_from_dates(dates)
            summary["streak"] = streak

        except Exception as e:
            logger.warning(f"Erro ao calcular streak: {e}")

        return summary

    def _calculate_streak_from_dates(self, dates: list[str]) -> int:
        """
        Calcula streak a partir de lista de datas.
        
        Args:
            dates: Lista de datas em formato YYYY-MM-DD
            
        Returns:
            Número de dias consecutivos
        """
        if not dates:
            return 0
        
        streak = 0
        check_date = date.today()

        for d in dates:
            try:
                checkin_date = datetime.strptime(d, "%Y-%m-%d").date()
                if checkin_date == check_date:
                    streak += 1
                    check_date -= timedelta(days=1)
                elif checkin_date < check_date:
                    break
            except Exception:
                continue

        return streak

    def _get_patient_summary_from_mock(self, perfil_id: str) -> PatientSummary:
        """
        Busca resumo do paciente no MockDB.
        
        Args:
            perfil_id: ID do paciente
            
        Returns:
            Objeto PatientSummary
        """
        # Busca paciente
        all_users = self.db.get_all_users() if hasattr(self.db, 'get_all_users') else []
        
        user_data = None
        for u in all_users:
            if u.get("id") == perfil_id or u.get("email") == perfil_id:
                user_data = u
                break
        
        if not user_data:
            logger.warning(f"Paciente não encontrado: {perfil_id}")
            return PatientSummary(id=perfil_id, nome_completo="")
        
        return PatientSummary.from_dict(user_data)

    def _get_patient_quick_summary(self, perfil_id: str) -> dict[str, Any]:
        """
        Retorna resumo rápido para lista de pacientes.
        
        Args:
            perfil_id: ID do paciente
            
        Returns:
            Dicionário com resumo rápido
        """
        try:
            summary = self.get_patient_summary(perfil_id)
            return {
                "ultimo_peso": summary.ultimo_peso,
                "streak": summary.streak,
                "data_ultimo_peso": summary.data_ultimo_peso,
            }
        except Exception as e:
            logger.debug(f"Erro ao obter quick summary: {e}")
            return {}

    # ─────────────────────────────────────────────────────────────────────────
    # PACIENTES EM RISCO
    # ─────────────────────────────────────────────────────────────────────────

    def get_patients_at_risk(self, limit: int = _DEFAULT_RISK_LIMIT) -> list[RiskPatient]:
        """
        Retorna pacientes em risco de abandono.
        
        Args:
            limit: Número máximo de pacientes
            
        Returns:
            Lista de objetos RiskPatient (ordenados por prioridade)
            
        Example:
            >>> at_risk = pro_service.get_patients_at_risk(limit=10)
            >>> for p in at_risk:
            ...     print(f"{p.nome_completo} - Risco: {p.risco_abandono}%")
        """
        if self.db.is_real and self.db.client:
            try:
                response = (
                    self.db.client.table("vw_prioridade_intervencao")
                    .select(
                        "id, nome_completo, email, score_prioridade, "
                        "risco_abandono, score_engajamento, score_adesao"
                    )
                    .order("score_prioridade", desc=True)
                    .limit(limit)
                    .execute()
                )

                patients_data = response.data or []
                patients = [RiskPatient.from_dict(p) for p in patients_data]
                
                logger.info(f"✅ {len(patients)} pacientes em risco identificados")
                return patients

            except Exception as e:
                logger.warning(f"get_patients_at_risk view falhou: {e}")

        # Fallback MockDB
        return self._get_risk_patients_from_mock(limit)

    def _get_risk_patients_from_mock(self, limit: int) -> list[RiskPatient]:
        """
        Busca pacientes em risco no MockDB.
        
        Args:
            limit: Número máximo de pacientes
            
        Returns:
            Lista de objetos RiskPatient
        """
        # Busca todos os usuários
        all_users = self.db.get_all_users() if hasattr(self.db, 'get_all_users') else []
        
        risk_patients = []

        for user_data in all_users:
            email = user_data.get("email", "")
            
            # Simula risco baseado em dados
            risk_score = 0

            if not user_data.get("onboarding_done", False):
                risk_score += 40

            if not user_data.get("current_weight"):
                risk_score += 30

            # Verifica se tem refeições recentes
            meals = self.db.get_meals(30) if hasattr(self.db, 'get_meals') else []
            recent_meals = [m for m in meals if m.get("user_id") == email]

            if not recent_meals:
                risk_score += 30

            if risk_score >= 50:
                risk_patient = RiskPatient(
                    id=email,
                    nome_completo=user_data.get("name", ""),
                    email=email,
                    score_prioridade=risk_score,
                    risco_abandono=risk_score,
                    score_engajamento=100 - risk_score,
                    score_adesao=100 - risk_score,
                )
                risk_patients.append(risk_patient)

        # Ordena por score descendente
        risk_patients.sort(key=lambda x: x.score_prioridade, reverse=True)
        return risk_patients[:limit]

    def get_patients_by_risk_level(self) -> dict[str, list[RiskPatient]]:
        """
        Retorna pacientes agrupados por nível de risco.
        
        Returns:
            Dicionário com listas por nível: "critical", "high", "medium", "low"
            
        Example:
            >>> by_risk = pro_service.get_patients_by_risk_level()
            >>> print(f"Críticos: {len(by_risk['critical'])}")
        """
        patients = self.get_patients_at_risk(limit=100)

        levels = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
        }

        for p in patients:
            level = p.risk_level
            levels[level].append(p)

        logger.debug(
            f"✅ Pacientes por risco: "
            f"C={len(levels['critical'])}, "
            f"A={len(levels['high'])}, "
            f"M={len(levels['medium'])}, "
            f"B={len(levels['low'])}"
        )
        return levels

    # ─────────────────────────────────────────────────────────────────────────
    # DASHBOARD EXECUTIVO
    # ─────────────────────────────────────────────────────────────────────────

    def get_executive_summary(self) -> ExecutiveSummary:
        """
        Retorna resumo executivo para a clínica.
        
        Returns:
            Objeto ExecutiveSummary com métricas agregadas
            
        Example:
            >>> summary = pro_service.get_executive_summary()
            >>> print(f"Total de pacientes: {summary.total_pacientes}")
        """
        if self.db.is_real and self.db.client:
            try:
                response = (
                    self.db.client.table("vw_resumo_executivo")
                    .select("*")
                    .limit(1)
                    .execute()
                )

                if response.data:
                    logger.debug("✅ Executive summary (view)")
                    return ExecutiveSummary.from_dict(response.data[0])

            except Exception as e:
                logger.warning(f"get_executive_summary view falhou: {e}")

        # Fallback: calcula localmente
        return self._build_executive_summary_local()

    def _build_executive_summary_local(self) -> ExecutiveSummary:
        """
        Constrói resumo executivo localmente (fallback).
        
        Returns:
            Objeto ExecutiveSummary com métricas agregadas
        """
        # Busca todos os usuários
        all_users = self.db.get_all_users() if hasattr(self.db, 'get_all_users') else []
        
        # Filtra apenas pacientes (não profissionais)
        patients = [u for u in all_users if u.get("user_type") != "professional"]

        # Calcula métricas
        total = len(patients)
        onboarding_done = sum(1 for p in patients if p.get("onboarding_done", False))
        has_weight = sum(1 for p in patients if p.get("current_weight"))

        return ExecutiveSummary(
            total_pacientes=total,
            pacientes_ativos=onboarding_done,
            pacientes_inativos=total - onboarding_done,
            pacientes_em_risco=0,  # Seria calculado separadamente
            aderencia_media=round((onboarding_done / total * 100) if total else 0, 1),
            consistencia_media=round((has_weight / total * 100) if total else 0, 1),
            risco_abandono_medio=20.0,  # Valor padrão para fallback
            receita_mensal=0.0,
            score_transformacao_medio=50.0,
            score_engajamento_medio=50.0,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # AUTENTICAÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def authenticate(self, email: str, password: str) -> Professional | None:
        """
        Autentica um profissional.
        
        Args:
            email: Email do profissional
            password: Senha
            
        Returns:
            Objeto Professional ou None
            
        Example:
            >>> pro = pro_service.authenticate("doctor@example.com", "password123")
            >>> if pro:
            ...     print(f"Bem-vindo, {pro.name}!")
        """
        # Validação
        if not email or not password:
            logger.warning("authenticate: email ou password não informados")
            return None
        
        professional = self.db.get_professional(email, password)

        if professional:
            logger.info(f"✅ Profissional autenticado: {email}")
            return professional

        logger.warning(f"❌ Falha na autenticação: {email}")
        return None

    def get_by_email(self, email: str) -> Professional | None:
        """
        Busca profissional por email (sem autenticação).
        
        Args:
            email: Email do profissional
            
        Returns:
            Objeto Professional ou None
            
        Example:
            >>> pro = pro_service.get_by_email("doctor@example.com")
            >>> if pro:
            ...     print(f"Profissional encontrado: {pro.name}")
        """
        if not email or not email.strip():
            logger.warning("get_by_email: email não informado")
            return None
        
        # Usa método do Database
        professional = self.db.get_professional_by_email(email)
        
        if professional:
            logger.debug(f"✅ Profissional encontrado: {email}")
            return professional

        logger.debug(f"❌ Profissional não encontrado: {email}")
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # VÍNCULO PACIENTE-PROFISSIONAL
    # ─────────────────────────────────────────────────────────────────────────

    def link_patient(self, pro_email: str, paciente_email: str) -> bool:
        """
        Vincula um paciente a um profissional.
        
        Args:
            pro_email: Email do profissional
            paciente_email: Email do paciente
            
        Returns:
            True se vinculado com sucesso, False caso contrário
            
        Example:
            >>> success = pro_service.link_patient("doctor@example.com", "patient@example.com")
            >>> if success:
            ...     print("Paciente vinculado ao profissional!")
        """
        # Validações
        if not pro_email or not pro_email.strip():
            logger.warning("link_patient: pro_email não informado")
            return False
        
        if not paciente_email or not paciente_email.strip():
            logger.warning("link_patient: paciente_email não informado")
            return False

        # 1. Tenta Supabase
        if self.db.is_real and self.db.client:
            try:
                # Busca clinic_id do profissional para propagar ao paciente
                clinic_id = pro_email  # default: solo
                try:
                    r = self.db.client.table("profissionais").select("clinic_id").eq("email", pro_email).limit(1).execute()
                    if r.data:
                        clinic_id = r.data[0].get("clinic_id") or pro_email
                except Exception:
                    pass

                self.db.client.table("perfis").update({
                    "profissional_id": pro_email,
                    "clinic_id": clinic_id,
                }).eq("email", paciente_email).execute()

                logger.info(f"✅ Paciente {paciente_email} vinculado a {pro_email} clinic={clinic_id} (Supabase)")
                return True

            except Exception as e:
                logger.error(f"link_patient Supabase: {e}")

        # 2. Fallback MockDB
        # Busca paciente
        all_users = self.db.get_all_users() if hasattr(self.db, 'get_all_users') else []
        patient_data = None
        
        for u in all_users:
            if u.get("email") == paciente_email:
                patient_data = u
                break

        if patient_data:
            # Atualiza via update_user
            success = self.db.update_user({"professional_id": pro_email})
            if success:
                logger.info(f"✅ Paciente {paciente_email} vinculado a {pro_email} (MockDB)")
                return True

        logger.warning(f"❌ Paciente {paciente_email} não encontrado")
        return False

    def unlink_patient(self, paciente_email: str) -> bool:
        """
        Desvincula um paciente do profissional.
        
        Args:
            paciente_email: Email do paciente
            
        Returns:
            True se desvinculado com sucesso, False caso contrário
            
        Example:
            >>> success = pro_service.unlink_patient("patient@example.com")
            >>> if success:
            ...     print("Paciente desvinculado!")
        """
        if not paciente_email or not paciente_email.strip():
            logger.warning("unlink_patient: paciente_email não informado")
            return False

        # 1. Tenta Supabase
        if self.db.is_real and self.db.client:
            try:
                self.db.client.table("perfis").update({
                    "profissional_id": None,
                }).eq("email", paciente_email).execute()

                logger.info(f"✅ Paciente {paciente_email} desvinculado (Supabase)")
                return True

            except Exception as e:
                logger.error(f"unlink_patient Supabase: {e}")

        # 2. Fallback MockDB
        # Atualiza via update_user
        success = self.db.update_user({"professional_id": None})
        if success:
            logger.info(f"✅ Paciente {paciente_email} desvinculado (MockDB)")
            return True

        logger.warning(f"❌ Paciente {paciente_email} não encontrado")
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # MÉTODOS AUXILIARES
    # ─────────────────────────────────────────────────────────────────────────

    def get_patient_count(self, pro_email: str) -> int:
        """
        Retorna o número de pacientes vinculados ao profissional.
        
        Args:
            pro_email: Email do profissional
            
        Returns:
            Número de pacientes
            
        Example:
            >>> count = pro_service.get_patient_count("doctor@example.com")
            >>> print(f"Total de pacientes: {count}")
        """
        if not pro_email or not pro_email.strip():
            logger.warning("get_patient_count: pro_email não informado")
            return 0
        
        patients = self.get_patients(pro_email, limit=1000, include_inactive=True)
        count = len(patients)
        
        logger.debug(f"get_patient_count: {count} pacientes para {pro_email}")
        return count

    def get_active_patients(self, pro_email: str, days: int = 30) -> int:
        """
        Retorna o número de pacientes ativos (com atividade nos últimos N dias).
        
        Args:
            pro_email: Email do profissional
            days: Número de dias para considerar ativo
            
        Returns:
            Número de pacientes ativos
            
        Example:
            >>> active = pro_service.get_active_patients("doctor@example.com", days=7)
            >>> print(f"Pacientes ativos na última semana: {active}")
        """
        if not pro_email or not pro_email.strip():
            logger.warning("get_active_patients: pro_email não informado")
            return 0
        
        if days <= 0:
            logger.warning(f"get_active_patients: days inválido: {days}")
            return 0
        
        patients = self.get_patients(pro_email, limit=1000, include_inactive=True)
        active_count = 0

        cutoff = date.today() - timedelta(days=days)

        for p in patients:
            if p.ultimo_acesso:
                try:
                    last_date = datetime.fromisoformat(p.ultimo_acesso).date()
                    if last_date >= cutoff:
                        active_count += 1
                except Exception as e:
                    logger.debug(f"Erro ao processar ultimo_acesso: {e}")
                    continue

        logger.debug(f"get_active_patients: {active_count} ativos nos últimos {days} dias")
        return active_count


__all__ = [
    "ProfessionalService",
    "PatientSummary",
    "RiskPatient",
    "ExecutiveSummary",
]
