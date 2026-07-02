"""
Melshape — Clinical Repository.

Gerencia as ações clínicas do profissional sobre o paciente:
condutas, observações, prescrições e modelos de refeição.

Princípios:
- Conduta: decisão clínica registrada pelo profissional
- Observação: anotação livre sobre o paciente (pública ou privada)
- Prescrição: plano alimentar vinculado ao paciente
- Modelo: template de refeição criado pelo profissional
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Modelos: dataclasses imutáveis para todas as entidades
- Validação: dados são validados antes de salvar
- Logging: todas as operações são logadas

Arquitetura:
    ClinicalRepository
    ├── register_conduct(perfil_id, titulo, descricao, tipo) -> ClinicalConduct | None
    ├── get_conducts(perfil_id, limit) -> list[ClinicalConduct]
    ├── resolve_conduct(conduta_id) -> bool
    ├── register_observation(perfil_id, observacao, privada) -> ClinicalObservation | None
    ├── get_observations(perfil_id) -> list[ClinicalObservation]
    ├── create_prescription(perfil_id, objetivo, validade_dias) -> DietaryPrescription | None
    ├── get_active_prescription(perfil_id) -> DietaryPrescription | None
    ├── deactivate_prescription(prescription_id) -> bool
    ├── get_professional_templates() -> list[MealTemplate]
    └── create_meal_template(nome, descricao, calorias, protein, carbs, fat) -> MealTemplate | None
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import streamlit as st

logger = logging.getLogger("Melshape.ClinicalRepo")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS CLÍNICOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ClinicalConduct:
    """
    Modelo de conduta clínica registrada pelo profissional.
    
    Attributes:
        id: ID único da conduta
        patient_id: ID do paciente
        professional_id: ID do profissional
        titulo: Título da conduta
        descricao: Descrição detalhada
        tipo: Tipo (orientacao/ajuste_dieta/alerta/encaminhamento/elogio/revisao)
        data_conduta: Data da conduta (YYYY-MM-DD)
        resolvido: Se a conduta foi resolvida
        resolvido_em: Data de resolução (se aplicável)
        criado_em: Timestamp de criação
    """
    id: str
    patient_id: str
    professional_id: str
    titulo: str
    descricao: str
    tipo: str = "orientacao"
    data_conduta: str = field(default_factory=lambda: date.today().isoformat())
    resolvido: bool = False
    resolvido_em: str | None = None
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClinicalConduct:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            patient_id=data.get("patient_id", data.get("perfil_id", "")),
            professional_id=data.get("professional_id", data.get("profissional_id", "")),
            titulo=data.get("titulo", ""),
            descricao=data.get("descricao", ""),
            tipo=data.get("tipo", "orientacao"),
            data_conduta=data.get("data_conduta", date.today().isoformat()),
            resolvido=data.get("resolvido", False),
            resolvido_em=data.get("resolvido_em"),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )
    
    @property
    def tipo_label(self) -> str:
        """Retorna o rótulo do tipo de conduta."""
        labels = {
            "orientacao": "📋 Orientação",
            "ajuste_dieta": "🍽️ Ajuste de Dieta",
            "alerta": "⚠️ Alerta",
            "encaminhamento": "🔄 Encaminhamento",
            "elogio": "👏 Elogio",
            "revisao": "🔍 Revisão",
        }
        return labels.get(self.tipo, self.tipo)
    
    @property
    def is_resolved(self) -> bool:
        """Verifica se a conduta foi resolvida."""
        return self.resolvido


@dataclass(frozen=True)
class ClinicalObservation:
    """
    Modelo de observação clínica sobre o paciente.
    
    Attributes:
        id: ID único da observação
        patient_id: ID do paciente
        professional_id: ID do profissional
        observacao: Texto da observação
        privada: Se é visível apenas para o profissional
        criado_em: Timestamp de criação
    """
    id: str
    patient_id: str
    professional_id: str
    observacao: str
    privada: bool = True
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClinicalObservation:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            patient_id=data.get("patient_id", data.get("perfil_id", "")),
            professional_id=data.get("professional_id", data.get("profissional_id", "")),
            observacao=data.get("observacao", ""),
            privada=data.get("privada", True),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )
    
    @property
    def visibility_label(self) -> str:
        """Retorna o rótulo da visibilidade."""
        return "🔒 Privada" if self.privada else "👁️ Pública"


@dataclass(frozen=True)
class DietaryPrescription:
    """
    Modelo de prescrição alimentar do profissional.
    
    Attributes:
        id: ID único da prescrição
        patient_id: ID do paciente
        professional_id: ID do profissional
        objetivo: Objetivo da prescrição
        data_inicio: Data de início (YYYY-MM-DD)
        validade_dias: Dias de validade
        ativa: Se a prescrição está ativa
        finalizada_em: Data de finalização (se aplicável)
        criado_em: Timestamp de criação
    """
    id: str
    patient_id: str
    professional_id: str
    objetivo: str
    data_inicio: str = field(default_factory=lambda: date.today().isoformat())
    validade_dias: int = 30
    ativa: bool = True
    finalizada_em: str | None = None
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DietaryPrescription:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            patient_id=data.get("patient_id", data.get("perfil_id", "")),
            professional_id=data.get("professional_id", data.get("profissional_id", "")),
            objetivo=data.get("objetivo", ""),
            data_inicio=data.get("data_inicio", date.today().isoformat()),
            validade_dias=int(data.get("validade_dias", 30)),
            ativa=data.get("ativa", True),
            finalizada_em=data.get("finalizada_em"),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )
    
    @property
    def data_fim(self) -> str:
        """Calcula data de validade da prescrição."""
        try:
            start_date = datetime.strptime(self.data_inicio, "%Y-%m-%d").date()
            end_date = start_date + timedelta(days=self.validade_dias)
            return end_date.isoformat()
        except Exception:
            return self.data_inicio
    
    @property
    def dias_restantes(self) -> int:
        """Calcula dias restantes de validade."""
        try:
            end_date = datetime.strptime(self.data_fim, "%Y-%m-%d").date()
            delta = (end_date - date.today()).days
            return max(0, delta)
        except Exception:
            return 0
    
    @property
    def is_expired(self) -> bool:
        """Verifica se a prescrição expirou."""
        return self.dias_restantes == 0
    
    @property
    def is_active(self) -> bool:
        """Verifica se a prescrição está ativa e não expirou."""
        return self.ativa and not self.is_expired


@dataclass(frozen=True)
class MealTemplate:
    """
    Modelo de template de refeição criado pelo profissional.
    
    Attributes:
        id: ID único do template
        professional_id: ID do profissional
        nome: Nome do template
        descricao: Descrição do template
        calorias: Calorias totais (kcal)
        protein: Proteína (g)
        carbs: Carboidratos (g)
        fat: Gorduras (g)
        fiber: Fibras (g)
        criado_em: Timestamp de criação
    """
    id: str
    professional_id: str
    nome: str
    descricao: str = ""
    calorias: float = 0.0
    protein: float = 0.0
    carbs: float = 0.0
    fat: float = 0.0
    fiber: float = 0.0
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MealTemplate:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            professional_id=data.get("professional_id", data.get("profissional_id", "")),
            nome=data.get("nome", ""),
            descricao=data.get("descricao", ""),
            calorias=float(data.get("calorias", 0)),
            protein=float(data.get("protein", data.get("proteina", 0))),
            carbs=float(data.get("carbs", data.get("carboidratos", 0))),
            fat=float(data.get("fat", data.get("gorduras", 0))),
            fiber=float(data.get("fiber", data.get("fibras", 0))),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )
    
    @property
    def macro_summary(self) -> str:
        """Retorna resumo dos macros."""
        return f"P: {self.protein:.0f}g | C: {self.carbs:.0f}g | G: {self.fat:.0f}g"


# ─────────────────────────────────────────────────────────────────────────────
# CLINICAL REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────

class ClinicalRepository:
    """
    Mixin para gerenciamento clínico do profissional.
    
    Requer que a classe base tenha:
        - self.client (Supabase client)
        - self.is_real (bool)
        - self.uid() -> str (para paciente)
        - self.mock (dict)
    
    Example:
        >>> class Database(ClinicalRepository):
        ...     def __init__(self):
        ...         self.client = None
        ...         self.is_real = False
        ...         self.mock = {"condutas_clinicas": {}}
        ...     
        ...     def uid(self) -> str:
        ...         return "patient@example.com"
        
        >>> db = Database()
        >>> conduct = db.register_conduct("patient_id", "Aumentar proteína", "1.8g/kg", "ajuste_dieta")
        >>> if conduct:
        ...     print(f"Conduta registrada: {conduct.id}")
    """

    def _pro_uid(self) -> str:
        """
        Retorna o ID do profissional logado.
        
        Returns:
            Email do profissional ou ID
        """
        pro = st.session_state.get("professional")
        if pro:
            return getattr(pro, "email", "") or pro.get("email", "")
        return self.uid()

    # ─────────────────────────────────────────────────────────────────────────
    # CONDUTAS CLÍNICAS
    # ─────────────────────────────────────────────────────────────────────────

    def register_conduct(
        self,
        patient_id: str,
        titulo: str,
        descricao: str,
        tipo: str = "orientacao",
    ) -> ClinicalConduct | None:
        """
        Registra uma conduta clínica para o paciente.
        
        Args:
            patient_id: ID do paciente
            titulo: Título da conduta
            descricao: Descrição detalhada
            tipo: Tipo (orientacao/ajuste_dieta/alerta/encaminhamento/elogio/revisao)
            
        Returns:
            Objeto ClinicalConduct criado ou None se falhar
            
        Example:
            >>> conduct = db.register_conduct(
            ...     "patient_id",
            ...     "Aumentar proteína",
            ...     "Ajustar para 1.8g/kg de peso",
            ...     "ajuste_dieta"
            ... )
            >>> if conduct:
            ...     print(f"Conduta registrada: {conduct.id}")
        """
        pro_id = self._pro_uid()
        
        # Validações
        if not patient_id or not patient_id.strip():
            logger.warning("❌ patient_id é obrigatório")
            return None
        
        if not titulo or not titulo.strip():
            logger.warning("❌ Título é obrigatório")
            return None
        
        if not descricao or not descricao.strip():
            logger.warning("❌ Descrição é obrigatória")
            return None
        
        valid_tipos = {"orientacao", "ajuste_dieta", "alerta", "encaminhamento", "elogio", "revisao"}
        if tipo not in valid_tipos:
            logger.warning(f"❌ Tipo de conduta inválido: {tipo}")
            return None
        
        conduct_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                self.client.table("condutas_clinicas").insert({
                    "id": conduct_id,
                    "perfil_id": patient_id,
                    "profissional_id": pro_id,
                    "titulo": titulo,
                    "descricao": descricao,
                    "tipo": tipo,
                    "data_conduta": date.today().isoformat(),
                    "resolvido": False,
                }).execute()
                
                conduct_data = {
                    "id": conduct_id,
                    "patient_id": patient_id,
                    "professional_id": pro_id,
                    "titulo": titulo,
                    "descricao": descricao,
                    "tipo": tipo,
                    "data_conduta": date.today().isoformat(),
                    "resolvido": False,
                }
                
                conduct = self._build_conduct_from_data(conduct_data)
                logger.info(f"✅ Conduta registrada no Supabase: {titulo}")
                return conduct
                
            except Exception as e:
                logger.error(f"register_conduct Supabase: {e}")
        
        # Fallback MockDB
        key = f"condutas_{patient_id}"
        conduct_data = {
            "id": conduct_id,
            "patient_id": patient_id,
            "professional_id": pro_id,
            "titulo": titulo,
            "descricao": descricao,
            "tipo": tipo,
            "data_conduta": date.today().isoformat(),
            "resolvido": False,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
        
        self.mock.setdefault(key, []).append(conduct_data)
        
        conduct = self._build_conduct_from_data(conduct_data)
        logger.info(f"✅ Conduta registrada no MockDB: {titulo}")
        return conduct

    def get_conducts(self, patient_id: str, limit: int = 20) -> list[ClinicalConduct]:
        """
        Retorna condutas registradas para o paciente.
        
        Args:
            patient_id: ID do paciente
            limit: Número máximo de condutas
            
        Returns:
            Lista de objetos ClinicalConduct (ordenados por data descendente)
            
        Example:
            >>> conducts = db.get_conducts("patient_id", limit=5)
            >>> for c in conducts:
            ...     print(f"{c.data_conduta}: {c.titulo} ({c.tipo_label})")
        """
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("condutas_clinicas")
                    .select("*")
                    .eq("perfil_id", patient_id)
                    .order("data_conduta", desc=True)
                    .limit(limit)
                    .execute()
                )
                
                return [self._build_conduct_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_conducts Supabase: {e}")
        
        # Fallback MockDB
        key = f"condutas_{patient_id}"
        conducts_data = self.mock.get(key, [])
        
        # Ordena por data_conduta descendente
        sorted_conducts = sorted(
            conducts_data,
            key=lambda x: x.get("data_conduta", ""),
            reverse=True
        )
        
        return [self._build_conduct_from_data(row) for row in sorted_conducts[:limit]]

    def resolve_conduct(self, conduct_id: str) -> bool:
        """
        Marca uma conduta como resolvida.
        
        Args:
            conduct_id: ID da conduta
            
        Returns:
            True se resolvida com sucesso, False caso contrário
            
        Example:
            >>> success = db.resolve_conduct(conduct_id)
            >>> if success:
            ...     print("Conduta resolvida!")
        """
        if not conduct_id:
            logger.warning("❌ conduct_id é obrigatório")
            return False
        
        if self.is_real and self.client:
            try:
                self.client.table("condutas_clinicas").update({
                    "resolvido": True,
                    "resolvido_em": date.today().isoformat(),
                }).eq("id", conduct_id).execute()
                
                logger.info(f"✅ Conduta resolvida no Supabase: {conduct_id}")
                return True
                
            except Exception as e:
                logger.error(f"resolve_conduct Supabase: {e}")
        
        # Fallback MockDB - busca em todas as chaves de condutas
        for key in self.mock.keys():
            if key.startswith("condutas_"):
                conducts = self.mock[key]
                for conduct in conducts:
                    if conduct.get("id") == conduct_id:
                        conduct["resolvido"] = True
                        conduct["resolvido_em"] = date.today().isoformat()
                        logger.info(f"✅ Conduta resolvida no MockDB: {conduct_id}")
                        return True
        
        logger.warning(f"❌ Conduta não encontrada: {conduct_id}")
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # OBSERVAÇÕES
    # ─────────────────────────────────────────────────────────────────────────

    def register_observation(
        self,
        patient_id: str,
        observacao: str,
        privada: bool = True,
    ) -> ClinicalObservation | None:
        """
        Registra uma observação sobre o paciente.
        
        Args:
            patient_id: ID do paciente
            observacao: Texto da observação
            privada: Se é visível apenas para o profissional
            
        Returns:
            Objeto ClinicalObservation criado ou None se falhar
            
        Example:
            >>> obs = db.register_observation(
            ...     "patient_id",
            ...     "Paciente relatou boa adesão à dieta",
            ...     privada=False
            ... )
            >>> if obs:
            ...     print(f"Observação registrada: {obs.id}")
        """
        pro_id = self._pro_uid()
        
        # Validações
        if not patient_id or not patient_id.strip():
            logger.warning("❌ patient_id é obrigatório")
            return None
        
        if not observacao or not observacao.strip():
            logger.warning("❌ Observação é obrigatória")
            return None
        
        observation_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                self.client.table("observacoes_profissionais").insert({
                    "id": observation_id,
                    "perfil_id": patient_id,
                    "profissional_id": pro_id,
                    "observacao": observacao,
                    "privada": privada,
                }).execute()
                
                obs_data = {
                    "id": observation_id,
                    "patient_id": patient_id,
                    "professional_id": pro_id,
                    "observacao": observacao,
                    "privada": privada,
                }
                
                observation = self._build_observation_from_data(obs_data)
                logger.info(f"✅ Observação registrada no Supabase: {observacao[:50]}...")
                return observation
                
            except Exception as e:
                logger.error(f"register_observation Supabase: {e}")
        
        # Fallback MockDB
        key = f"obs_{patient_id}"
        obs_data = {
            "id": observation_id,
            "patient_id": patient_id,
            "professional_id": pro_id,
            "observacao": observacao,
            "privada": privada,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
        
        self.mock.setdefault(key, []).append(obs_data)
        
        observation = self._build_observation_from_data(obs_data)
        logger.info(f"✅ Observação registrada no MockDB: {observacao[:50]}...")
        return observation

    def get_observations(self, patient_id: str) -> list[ClinicalObservation]:
        """
        Retorna observações registradas para o paciente.
        
        Args:
            patient_id: ID do paciente
            
        Returns:
            Lista de objetos ClinicalObservation (ordenados por data descendente)
            
        Example:
            >>> observations = db.get_observations("patient_id")
            >>> for o in observations:
            ...     print(f"{o.criado_em}: {o.observacao} ({o.visibility_label})")
        """
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("observacoes_profissionais")
                    .select("*")
                    .eq("perfil_id", patient_id)
                    .order("criado_em", desc=True)
                    .limit(50)
                    .execute()
                )
                
                return [self._build_observation_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_observations Supabase: {e}")
        
        # Fallback MockDB
        key = f"obs_{patient_id}"
        obs_data = self.mock.get(key, [])
        
        # Ordena por criado_em descendente
        sorted_obs = sorted(
            obs_data,
            key=lambda x: x.get("criado_em", ""),
            reverse=True
        )
        
        return [self._build_observation_from_data(row) for row in sorted_obs]

    # ─────────────────────────────────────────────────────────────────────────
    # PRESCRIÇÕES
    # ─────────────────────────────────────────────────────────────────────────

    def create_prescription(
        self,
        patient_id: str,
        objetivo: str,
        validade_dias: int = 30,
    ) -> DietaryPrescription | None:
        """
        Cria uma nova prescrição alimentar para o paciente.
        
        Args:
            patient_id: ID do paciente
            objetivo: Objetivo da prescrição
            validade_dias: Dias de validade (padrão: 30)
            
        Returns:
            Objeto DietaryPrescription criado ou None se falhar
            
        Example:
            >>> presc = db.create_prescription(
            ...     "patient_id",
            ...     "Déficit calórico moderado com alta proteína",
            ...     validade_dias=30
            ... )
            >>> if presc:
            ...     print(f"Prescrição criada: {presc.id}")
        """
        pro_id = self._pro_uid()
        
        # Validações
        if not patient_id or not patient_id.strip():
            logger.warning("❌ patient_id é obrigatório")
            return None
        
        if not objetivo or not objetivo.strip():
            logger.warning("❌ Objetivo é obrigatório")
            return None
        
        if validade_dias <= 0:
            logger.warning(f"❌ validade_dias deve ser positivo: {validade_dias}")
            return None
        
        # Desativa prescrição anterior se existir
        existing = self.get_active_prescription(patient_id)
        if existing:
            logger.info(f"⚠️ Desativando prescrição anterior: {existing.id}")
            self.deactivate_prescription(existing.id)
        
        prescription_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                response = self.client.table("prescricoes_alimentares").insert({
                    "id": prescription_id,
                    "perfil_id": patient_id,
                    "profissional_id": pro_id,
                    "objetivo": objetivo,
                    "data_inicio": date.today().isoformat(),
                    "validade_dias": validade_dias,
                    "ativa": True,
                }).execute()
                
                if response.data:
                    prescription = self._build_prescription_from_data(response.data[0])
                    logger.info(f"✅ Prescrição criada no Supabase: {objetivo[:50]}...")
                    return prescription
                
            except Exception as e:
                logger.error(f"create_prescription Supabase: {e}")
        
        # Fallback MockDB
        presc_data = {
            "id": prescription_id,
            "patient_id": patient_id,
            "professional_id": pro_id,
            "objetivo": objetivo,
            "data_inicio": date.today().isoformat(),
            "validade_dias": validade_dias,
            "ativa": True,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
        
        self.mock[f"prescricao_{patient_id}"] = presc_data
        
        prescription = self._build_prescription_from_data(presc_data)
        logger.info(f"✅ Prescrição criada no MockDB: {objetivo[:50]}...")
        return prescription

    def get_active_prescription(self, patient_id: str) -> DietaryPrescription | None:
        """
        Retorna a prescrição ativa do paciente.
        
        Args:
            patient_id: ID do paciente
            
        Returns:
            Objeto DietaryPrescription ou None
            
        Example:
            >>> presc = db.get_active_prescription("patient_id")
            >>> if presc:
            ...     print(f"Prescrição ativa: {presc.objetivo}")
            ...     print(f"Dias restantes: {presc.dias_restantes}")
        """
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("prescricoes_alimentares")
                    .select("*")
                    .eq("perfil_id", patient_id)
                    .eq("ativa", True)
                    .order("data_inicio", desc=True)
                    .limit(1)
                    .execute()
                )
                
                if response.data:
                    return self._build_prescription_from_data(response.data[0])
                
            except Exception as e:
                logger.error(f"get_active_prescription Supabase: {e}")
        
        # Fallback MockDB
        presc_data = self.mock.get(f"prescricao_{patient_id}")
        
        if presc_data and presc_data.get("ativa"):
            return self._build_prescription_from_data(presc_data)
        
        return None

    def deactivate_prescription(self, prescription_id: str) -> bool:
        """
        Desativa uma prescrição.
        
        Args:
            prescription_id: ID da prescrição
            
        Returns:
            True se desativada com sucesso, False caso contrário
            
        Example:
            >>> success = db.deactivate_prescription(prescription_id)
            >>> if success:
            ...     print("Prescrição desativada!")
        """
        if not prescription_id:
            logger.warning("❌ prescription_id é obrigatório")
            return False
        
        if self.is_real and self.client:
            try:
                self.client.table("prescricoes_alimentares").update({
                    "ativa": False,
                    "finalizada_em": date.today().isoformat(),
                }).eq("id", prescription_id).execute()
                
                logger.info(f"✅ Prescrição desativada no Supabase: {prescription_id}")
                return True
                
            except Exception as e:
                logger.error(f"deactivate_prescription Supabase: {e}")
        
        # Fallback MockDB - busca em todas as chaves de prescrições
        for key in self.mock.keys():
            if key.startswith("prescricao_"):
                presc = self.mock[key]
                if presc.get("id") == prescription_id:
                    presc["ativa"] = False
                    presc["finalizada_em"] = date.today().isoformat()
                    logger.info(f"✅ Prescrição desativada no MockDB: {prescription_id}")
                    return True
        
        logger.warning(f"❌ Prescrição não encontrada: {prescription_id}")
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # MODELOS DE REFEIÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def get_professional_templates(self) -> list[MealTemplate]:
        """
        Retorna os modelos de refeição do profissional logado.
        
        Returns:
            Lista de objetos MealTemplate
            
        Example:
            >>> templates = db.get_professional_templates()
            >>> for t in templates:
            ...     print(f"{t.nome}: {t.calorias} kcal - {t.macro_summary}")
        """
        pro_id = self._pro_uid()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("modelos_refeicao")
                    .select("*")
                    .eq("profissional_id", pro_id)
                    .order("criado_em", desc=True)
                    .execute()
                )
                
                return [self._build_template_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_professional_templates Supabase: {e}")
        
        # Fallback MockDB
        key = f"modelos_{pro_id}"
        templates_data = self.mock.get(key, [])
        
        return [self._build_template_from_data(row) for row in templates_data]

    def create_meal_template(
        self,
        nome: str,
        descricao: str = "",
        calorias: float = 0.0,
        protein: float = 0.0,
        carbs: float = 0.0,
        fat: float = 0.0,
        fiber: float = 0.0,
    ) -> MealTemplate | None:
        """
        Cria um novo modelo de refeição para o profissional.
        
        Args:
            nome: Nome do template
            descricao: Descrição do template
            calorias: Calorias totais (kcal)
            protein: Proteína (g)
            carbs: Carboidratos (g)
            fat: Gorduras (g)
            fiber: Fibras (g)
            
        Returns:
            Objeto MealTemplate criado ou None se falhar
            
        Example:
            >>> template = db.create_meal_template(
            ...     "Café da Manhã Proteico",
            ...     "Ovos, aveia e frutas",
            ...     calorias=450,
            ...     protein=30,
            ...     carbs=45,
            ...     fat=15,
            ...     fiber=8
            ... )
            >>> if template:
            ...     print(f"Template criado: {template.nome}")
        """
        pro_id = self._pro_uid()
        
        # Validações
        if not nome or not nome.strip():
            logger.warning("❌ Nome é obrigatório")
            return None
        
        if calorias < 0 or protein < 0 or carbs < 0 or fat < 0 or fiber < 0:
            logger.warning("❌ Valores nutricionais não podem ser negativos")
            return None
        
        template_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                response = self.client.table("modelos_refeicao").insert({
                    "id": template_id,
                    "profissional_id": pro_id,
                    "nome": nome,
                    "descricao": descricao or None,
                    "calorias": calorias,
                    "proteina": protein,
                    "carboidratos": carbs,
                    "gorduras": fat,
                    "fibras": fiber,
                }).execute()
                
                if response.data:
                    template = self._build_template_from_data(response.data[0])
                    logger.info(f"✅ Template criado no Supabase: {nome}")
                    return template
                
            except Exception as e:
                logger.error(f"create_meal_template Supabase: {e}")
        
        # Fallback MockDB
        key = f"modelos_{pro_id}"
        template_data = {
            "id": template_id,
            "professional_id": pro_id,
            "nome": nome,
            "descricao": descricao,
            "calorias": calorias,
            "proteina": protein,
            "carboidratos": carbs,
            "gorduras": fat,
            "fibras": fiber,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
        
        self.mock.setdefault(key, []).append(template_data)
        
        template = self._build_template_from_data(template_data)
        logger.info(f"✅ Template criado no MockDB: {nome}")
        return template

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS DE CONVERSÃO
    # ─────────────────────────────────────────────────────────────────────────

    def _build_conduct_from_data(self, data: dict[str, Any]) -> ClinicalConduct:
        """Converte um dicionário para um objeto ClinicalConduct."""
        return ClinicalConduct.from_dict(data)

    def _build_observation_from_data(self, data: dict[str, Any]) -> ClinicalObservation:
        """Converte um dicionário para um objeto ClinicalObservation."""
        return ClinicalObservation.from_dict(data)

    def _build_prescription_from_data(self, data: dict[str, Any]) -> DietaryPrescription:
        """Converte um dicionário para um objeto DietaryPrescription."""
        return DietaryPrescription.from_dict(data)

    def _build_template_from_data(self, data: dict[str, Any]) -> MealTemplate:
        """Converte um dicionário para um objeto MealTemplate."""
        return MealTemplate.from_dict(data)


__all__ = [
    "ClinicalRepository",
    "ClinicalConduct",
    "ClinicalObservation",
    "DietaryPrescription",
    "MealTemplate",
]
