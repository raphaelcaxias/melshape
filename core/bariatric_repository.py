"""
Melshape — Bariatric Repository.

Gerencia o acompanhamento de pacientes pós-cirurgia bariátrica:
cirurgia, fases e histórico.

Princípios:
- Cirurgia: registro da cirurgia do paciente
- Fase: acompanhamento da fase atual (líquida/pastosa/branda/sólida/manutenção)
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Modelos: dataclasses imutáveis para todas as entidades
- Validação: dados são validados antes de salvar
- Logging: todas as operações são logadas

Arquitetura:
    BariatricRepository
    ├── get_surgery() -> BariatricSurgery | None
    ├── register_surgery(tipo, data_cirurgia, peso_pre, observacoes) -> BariatricSurgery | None
    ├── get_current_phase() -> BariatricPhase | None
    ├── register_phase(fase, observacao) -> BariatricPhase | None
    ├── get_phases_history() -> list[BariatricPhase]
    └── get_days_since_surgery() -> int
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import config

logger = logging.getLogger("Melshape.BariatricRepo")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS BARIÁTRICOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BariatricSurgery:
    """
    Modelo de cirurgia bariátrica do paciente.
    
    Attributes:
        id: ID único do registro
        user_id: ID do usuário
        tipo: Tipo de cirurgia (sleeve/bypass/band/balloon/other)
        data_cirurgia: Data da cirurgia (YYYY-MM-DD)
        peso_pre: Peso pré-cirurgia (kg)
        observacoes: Observações opcionais
        criado_em: Timestamp de criação
    """
    id: str
    user_id: str
    tipo: str
    data_cirurgia: str
    peso_pre: float
    observacoes: str = ""
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BariatricSurgery:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            tipo=data.get("tipo_cirurgia", data.get("tipo", "")),
            data_cirurgia=data.get("data_cirurgia", ""),
            peso_pre=float(data.get("peso_pre_cirurgia", data.get("peso_pre", 0))),
            observacoes=data.get("observacoes", ""),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )
    
    @property
    def tipo_label(self) -> str:
        """Retorna o rótulo do tipo de cirurgia."""
        return config.BARIATRIC_TYPES.get(self.tipo, self.tipo)
    
    @property
    def days_since_surgery(self) -> int:
        """Calcula dias desde a cirurgia."""
        try:
            surgery_date = datetime.strptime(self.data_cirurgia, "%Y-%m-%d").date()
            delta = (date.today() - surgery_date).days
            return max(0, delta)
        except Exception:
            return 0
    
    @property
    def current_phase_estimate(self) -> str:
        """Estima a fase atual baseado nos dias desde a cirurgia."""
        days = self.days_since_surgery
        
        if days <= 14:
            return "liquid"
        elif days <= 30:
            return "pasty"
        elif days <= 60:
            return "soft"
        elif days <= 180:
            return "solid"
        else:
            return "maintenance"


@dataclass(frozen=True)
class BariatricPhase:
    """
    Modelo de registro de fase bariátrica.
    
    Attributes:
        id: ID único do registro
        user_id: ID do usuário
        fase: Fase (liquid/pasty/soft/solid/maintenance)
        iniciada_em: Data de início da fase (YYYY-MM-DD)
        observacao: Observação opcional
        finalizada_em: Data de finalização (se aplicável)
        criado_em: Timestamp de criação
    """
    id: str
    user_id: str
    fase: str
    iniciada_em: str
    observacao: str = ""
    finalizada_em: str | None = None
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BariatricPhase:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            fase=data.get("fase", ""),
            iniciada_em=data.get("iniciada_em", ""),
            observacao=data.get("observacao", ""),
            finalizada_em=data.get("finalizada_em"),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )
    
    @property
    def fase_label(self) -> str:
        """Retorna o rótulo da fase."""
        phase_info = config.BARIATRIC_PHASES.get(self.fase, {})
        return phase_info.get("name", self.fase)
    
    @property
    def phase_duration(self) -> int:
        """Calcula duração da fase em dias."""
        try:
            start_date = datetime.strptime(self.iniciada_em, "%Y-%m-%d").date()
            
            if self.finalizada_em:
                end_date = datetime.strptime(self.finalizada_em, "%Y-%m-%d").date()
            else:
                end_date = date.today()
            
            delta = (end_date - start_date).days
            return max(0, delta)
        except Exception:
            return 0
    
    @property
    def max_ml(self) -> int:
        """Retorna volume máximo recomendado para a fase."""
        phase_info = config.BARIATRIC_PHASES.get(self.fase, {})
        return phase_info.get("max_ml", 0)
    
    @property
    def max_cal(self) -> int:
        """Retorna calorias máximas recomendadas para a fase."""
        phase_info = config.BARIATRIC_PHASES.get(self.fase, {})
        return phase_info.get("max_cal", 0)


# ─────────────────────────────────────────────────────────────────────────────
# BARIATRIC REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────

class BariatricRepository:
    """
    Mixin para gerenciamento bariátrico.
    
    Requer que a classe base tenha:
        - self.client (Supabase client)
        - self.is_real (bool)
        - self.uid() -> str
        - self.mock (dict)
    
    Example:
        >>> class Database(BariatricRepository):
        ...     def __init__(self):
        ...         self.client = None
        ...         self.is_real = False
        ...         self.mock = {"cirurgias": {}}
        ...     
        ...     def uid(self) -> str:
        ...         return "user@example.com"
        
        >>> db = Database()
        >>> surgery = db.register_surgery("sleeve", "2026-01-15", 120.0)
        >>> if surgery:
        ...     print(f"Cirurgia registrada: {surgery.tipo_label}")
    """

    # ─────────────────────────────────────────────────────────────────────────
    # CIRURGIA
    # ─────────────────────────────────────────────────────────────────────────

    def get_surgery(self) -> BariatricSurgery | None:
        """
        Retorna os dados da cirurgia do paciente.
        
        Returns:
            Objeto BariatricSurgery ou None
            
        Example:
            >>> surgery = db.get_surgery()
            >>> if surgery:
            ...     print(f"Cirurgia: {surgery.tipo_label} em {surgery.data_cirurgia}")
            ...     print(f"Dias desde cirurgia: {surgery.days_since_surgery}")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("cirurgias")
                    .select("*")
                    .eq("perfil_id", uid)
                    .order("data_cirurgia", desc=True)
                    .limit(1)
                    .execute()
                )
                
                if response.data:
                    return self._build_surgery_from_data(response.data[0])
                
            except Exception as e:
                logger.error(f"get_surgery Supabase: {e}")
        
        # Fallback MockDB
        surgery_data = self.mock.get(f"cirurgia_{uid}")
        
        if surgery_data:
            return self._build_surgery_from_data(surgery_data)
        
        return None

    def register_surgery(
        self,
        tipo: str,
        data_cirurgia: str,
        peso_pre: float,
        observacoes: str = "",
    ) -> BariatricSurgery | None:
        """
        Registra a cirurgia do paciente.
        
        Args:
            tipo: Tipo de cirurgia (sleeve/bypass/band/balloon/other)
            data_cirurgia: Data da cirurgia (YYYY-MM-DD)
            peso_pre: Peso pré-cirurgia (kg)
            observacoes: Observações opcionais
            
        Returns:
            Objeto BariatricSurgery criado ou None se falhar
            
        Example:
            >>> surgery = db.register_surgery("sleeve", "2026-01-15", 120.0)
            >>> if surgery:
            ...     print(f"Cirurgia registrada: {surgery.id}")
        """
        uid = self.uid()
        
        # Validações
        valid_tipos = set(config.BARIATRIC_TYPES.keys())
        if tipo not in valid_tipos:
            logger.warning(f"❌ Tipo de cirurgia inválido: {tipo}")
            return None
        
        if not data_cirurgia:
            logger.warning("❌ Data da cirurgia é obrigatória")
            return None
        
        # Valida formato da data
        try:
            datetime.strptime(data_cirurgia, "%Y-%m-%d")
        except ValueError:
            logger.warning(f"❌ Data inválida: {data_cirurgia} (use YYYY-MM-DD)")
            return None
        
        if peso_pre <= 0:
            logger.warning(f"❌ Peso pré-cirurgia deve ser positivo: {peso_pre}")
            return None
        
        # Verifica se já existe cirurgia
        existing = self.get_surgery()
        surgery_id = existing.id if existing else str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                if existing:
                    # Atualiza cirurgia existente
                    self.client.table("cirurgias").update({
                        "tipo_cirurgia": tipo,
                        "data_cirurgia": data_cirurgia,
                        "peso_pre_cirurgia": peso_pre,
                        "observacoes": observacoes or None,
                    }).eq("id", surgery_id).execute()
                    
                    logger.info(f"✅ Cirurgia atualizada no Supabase: {tipo}")
                else:
                    # Cria nova cirurgia
                    self.client.table("cirurgias").insert({
                        "id": surgery_id,
                        "perfil_id": uid,
                        "tipo_cirurgia": tipo,
                        "data_cirurgia": data_cirurgia,
                        "peso_pre_cirurgia": peso_pre,
                        "observacoes": observacoes or None,
                    }).execute()
                    
                    logger.info(f"✅ Cirurgia registrada no Supabase: {tipo}")
                
                # Atualiza perfil do usuário
                self.update_user({
                    "health_mode": "bariatric",
                })
                
                # Busca dados atualizados
                response = (
                    self.client.table("cirurgias")
                    .select("*")
                    .eq("id", surgery_id)
                    .limit(1)
                    .execute()
                )
                
                if response.data:
                    return self._build_surgery_from_data(response.data[0])
                
            except Exception as e:
                logger.error(f"register_surgery Supabase: {e}")
        
        # Fallback MockDB
        surgery_data = {
            "id": surgery_id,
            "user_id": uid,
            "tipo_cirurgia": tipo,
            "data_cirurgia": data_cirurgia,
            "peso_pre_cirurgia": peso_pre,
            "observacoes": observacoes,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
        
        self.mock[f"cirurgia_{uid}"] = surgery_data
        
        # Atualiza perfil no mock
        self.update_user({
            "health_mode": "bariatric",
        })
        
        surgery = self._build_surgery_from_data(surgery_data)
        logger.info(f"✅ Cirurgia registrada no MockDB: {tipo}")
        return surgery

    def get_days_since_surgery(self) -> int:
        """
        Calcula dias desde a cirurgia.
        
        Returns:
            Número de dias desde a cirurgia (0 se não houver registro)
            
        Example:
            >>> days = db.get_days_since_surgery()
            >>> print(f"Dias desde cirurgia: {days}")
        """
        surgery = self.get_surgery()
        
        if not surgery:
            return 0
        
        return surgery.days_since_surgery

    # ─────────────────────────────────────────────────────────────────────────
    # FASES
    # ─────────────────────────────────────────────────────────────────────────

    def get_current_phase(self) -> BariatricPhase | None:
        """
        Retorna a fase atual do paciente.
        
        Returns:
            Objeto BariatricPhase ou None
            
        Example:
            >>> phase = db.get_current_phase()
            >>> if phase:
            ...     print(f"Fase: {phase.fase_label}")
            ...     print(f"Volume máximo: {phase.max_ml}ml")
            ...     print(f"Calorias máximas: {phase.max_cal} kcal")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("fases_bariatricas")
                    .select("*")
                    .eq("perfil_id", uid)
                    .order("iniciada_em", desc=True)
                    .limit(1)
                    .execute()
                )
                
                if response.data:
                    return self._build_phase_from_data(response.data[0])
                
            except Exception as e:
                logger.error(f"get_current_phase Supabase: {e}")
        
        # Fallback MockDB
        phase_data = self.mock.get(f"fase_bar_{uid}")
        
        if phase_data:
            return self._build_phase_from_data(phase_data)
        
        return None

    def register_phase(
        self,
        fase: str,
        observacao: str = "",
    ) -> BariatricPhase | None:
        """
        Registra uma nova fase do paciente.
        
        Args:
            fase: Fase (liquid/pasty/soft/solid/maintenance)
            observacao: Observação opcional
            
        Returns:
            Objeto BariatricPhase criado ou None se falhar
            
        Example:
            >>> phase = db.register_phase("solid", "Tolerando bem alimentos sólidos")
            >>> if phase:
            ...     print(f"Fase registrada: {phase.fase_label}")
        """
        uid = self.uid()
        
        # Validações
        valid_fases = set(config.BARIATRIC_PHASES.keys())
        if fase not in valid_fases:
            logger.warning(f"❌ Fase inválida: {fase}")
            return None
        
        # Finaliza fase anterior se existir
        current_phase = self.get_current_phase()
        if current_phase and current_phase.fase != fase:
            self._finalize_phase(current_phase.id)
        
        phase_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                response = self.client.table("fases_bariatricas").insert({
                    "id": phase_id,
                    "perfil_id": uid,
                    "fase": fase,
                    "iniciada_em": date.today().isoformat(),
                    "observacao": observacao or None,
                }).execute()
                
                if response.data:
                    # Atualiza perfil do usuário
                    self.update_user({
                        "bariatric_phase": fase,
                    })
                    
                    phase = self._build_phase_from_data(response.data[0])
                    logger.info(f"✅ Fase registrada no Supabase: {fase}")
                    return phase
                
            except Exception as e:
                logger.error(f"register_phase Supabase: {e}")
        
        # Fallback MockDB
        phase_data = {
            "id": phase_id,
            "user_id": uid,
            "fase": fase,
            "iniciada_em": date.today().isoformat(),
            "observacao": observacao,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
        
        self.mock[f"fase_bar_{uid}"] = phase_data
        
        # Atualiza perfil no mock
        self.update_user({
            "bariatric_phase": fase,
        })
        
        phase = self._build_phase_from_data(phase_data)
        logger.info(f"✅ Fase registrada no MockDB: {fase}")
        return phase

    def _finalize_phase(self, phase_id: str) -> bool:
        """
        Finaliza uma fase (define finalizada_em).
        
        Args:
            phase_id: ID da fase a ser finalizada
            
        Returns:
            True se finalizada com sucesso, False caso contrário
        """
        if self.is_real and self.client:
            try:
                self.client.table("fases_bariatricas").update({
                    "finalizada_em": date.today().isoformat(),
                }).eq("id", phase_id).execute()
                
                logger.debug(f"✅ Fase finalizada no Supabase: {phase_id}")
                return True
                
            except Exception as e:
                logger.error(f"_finalize_phase Supabase: {e}")
        
        # Fallback MockDB
        # No MockDB, não temos histórico completo, então apenas logamos
        logger.debug(f"✅ Fase finalizada no MockDB: {phase_id}")
        return True

    def get_phases_history(self) -> list[BariatricPhase]:
        """
        Retorna o histórico de fases do paciente.
        
        Returns:
            Lista de objetos BariatricPhase (ordenados por data descendente)
            
        Example:
            >>> history = db.get_phases_history()
            >>> for phase in history:
            ...     print(f"{phase.fase_label} - {phase.iniciada_em} ({phase.phase_duration} dias)")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("fases_bariatricas")
                    .select("*")
                    .eq("perfil_id", uid)
                    .order("iniciada_em", desc=True)
                    .limit(20)
                    .execute()
                )
                
                return [self._build_phase_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_phases_history Supabase: {e}")
        
        # Fallback MockDB
        phase_data = self.mock.get(f"fase_bar_{uid}")
        
        if phase_data:
            return [self._build_phase_from_data(phase_data)]
        
        return []

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS DE CONVERSÃO
    # ─────────────────────────────────────────────────────────────────────────

    def _build_surgery_from_data(self, data: dict[str, Any]) -> BariatricSurgery:
        """Converte um dicionário para um objeto BariatricSurgery."""
        return BariatricSurgery.from_dict(data)

    def _build_phase_from_data(self, data: dict[str, Any]) -> BariatricPhase:
        """Converte um dicionário para um objeto BariatricPhase."""
        return BariatricPhase.from_dict(data)


__all__ = [
    "BariatricRepository",
    "BariatricSurgery",
    "BariatricPhase",
]
