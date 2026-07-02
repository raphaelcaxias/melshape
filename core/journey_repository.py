"""
Melshape — Journey Repository.

Gerencia a jornada do paciente: criação, etapas, marcos, eventos e metas.
A jornada é o coração da experiência do paciente no MelShape.

Princípios:
- Jornada ativa: apenas uma jornada ativa por paciente
- Etapas: sequência de passos que o paciente deve cumprir
- Marcos: conquistas automáticas ao atingir critérios
- Eventos: linha do tempo de ações do paciente
- Metas: objetivos vinculados à jornada
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Modelos: dataclasses imutáveis para todas as entidades
- Validação: dados são validados antes de salvar
- Logging: todas as operações são logadas

Arquitetura:
    JourneyRepository
    ├── get_journey_ativa() -> Journey | None
    ├── create_journey(tipo, nome, objetivo) -> Journey | None
    ├── get_stages(journey_id) -> list[Stage]
    ├── get_current_stage(journey_id) -> Stage | None
    ├── complete_stage(stage_id) -> bool
    ├── get_milestones(journey_id) -> list[Milestone]
    ├── register_milestone(journey_id, titulo, descricao) -> bool
    ├── get_events(journey_id, limit) -> list[Event]
    ├── register_event(journey_id, tipo, descricao) -> bool
    ├── get_goals(journey_id) -> list[Goal]
    └── create_goal(journey_id, titulo, valor_alvo, unidade, prazo) -> bool
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

logger = logging.getLogger("Melshape.JourneyRepo")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DA JORNADA
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Journey:
    """
    Modelo de jornada do paciente.
    
    Attributes:
        id: ID único da jornada
        user_id: ID do usuário
        tipo: Tipo da jornada (general/fitness/bariatric/glp1)
        nome: Nome da jornada
        objetivo: Objetivo da jornada
        ativa: Se a jornada está ativa
        iniciada_em: Data de início
        finalizada_em: Data de finalização (se aplicável)
    """
    id: str
    user_id: str
    tipo: str
    nome: str
    objetivo: str = ""
    ativa: bool = True
    iniciada_em: str = field(default_factory=lambda: date.today().isoformat())
    finalizada_em: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Journey:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            tipo=data.get("tipo", "general"),
            nome=data.get("nome", ""),
            objetivo=data.get("objetivo", ""),
            ativa=data.get("ativa", True),
            iniciada_em=data.get("iniciada_em", date.today().isoformat()),
            finalizada_em=data.get("finalizada_em"),
        )


@dataclass(frozen=True)
class Stage:
    """
    Modelo de etapa da jornada.
    
    Attributes:
        id: ID único da etapa
        journey_id: ID da jornada
        ordem: Ordem da etapa na sequência
        nome: Nome da etapa
        descricao: Descrição da etapa
        concluida: Se a etapa foi concluída
        concluida_em: Data de conclusão
    """
    id: str
    journey_id: str
    ordem: int
    nome: str
    descricao: str = ""
    concluida: bool = False
    concluida_em: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Stage:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            journey_id=data.get("jornada_id", data.get("journey_id", "")),
            ordem=data.get("ordem", 0),
            nome=data.get("nome", ""),
            descricao=data.get("descricao", ""),
            concluida=data.get("concluida", False),
            concluida_em=data.get("concluida_em"),
        )


@dataclass(frozen=True)
class Milestone:
    """
    Modelo de marco da jornada.
    
    Attributes:
        id: ID único do marco
        journey_id: ID da jornada
        titulo: Título do marco
        descricao: Descrição do marco
        data_marco: Data do marco
    """
    id: str
    journey_id: str
    titulo: str
    descricao: str = ""
    data_marco: str = field(default_factory=lambda: date.today().isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Milestone:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            journey_id=data.get("jornada_id", data.get("journey_id", "")),
            titulo=data.get("titulo", ""),
            descricao=data.get("descricao", ""),
            data_marco=data.get("data_marco", date.today().isoformat()),
        )


@dataclass(frozen=True)
class Event:
    """
    Modelo de evento da jornada (linha do tempo).
    
    Attributes:
        id: ID único do evento
        journey_id: ID da jornada
        tipo: Tipo do evento (checkin/pesagem/refeicao/marco/conquista)
        descricao: Descrição do evento
        criado_em: Timestamp de criação
    """
    id: str
    journey_id: str
    tipo: str
    descricao: str
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            journey_id=data.get("jornada_id", data.get("journey_id", "")),
            tipo=data.get("tipo", ""),
            descricao=data.get("descricao", ""),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )


@dataclass(frozen=True)
class Goal:
    """
    Modelo de meta da jornada.
    
    Attributes:
        id: ID único da meta
        journey_id: ID da jornada
        user_id: ID do usuário
        titulo: Título da meta
        valor_alvo: Valor alvo
        valor_atual: Valor atual
        unidade: Unidade da meta (kg/dias/% etc)
        prazo: Prazo da meta (YYYY-MM-DD)
        concluida: Se a meta foi concluída
        criado_em: Timestamp de criação
    """
    id: str
    journey_id: str
    user_id: str
    titulo: str
    valor_alvo: float
    valor_atual: float = 0.0
    unidade: str = ""
    prazo: str | None = None
    concluida: bool = False
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Goal:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            journey_id=data.get("jornada_id", data.get("journey_id", "")),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            titulo=data.get("titulo", ""),
            valor_alvo=float(data.get("valor_alvo", 0)),
            valor_atual=float(data.get("valor_atual", 0)),
            unidade=data.get("unidade", ""),
            prazo=data.get("prazo"),
            concluida=data.get("concluida", False),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )


# ─────────────────────────────────────────────────────────────────────────────
# JOURNEY REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────

class JourneyRepository:
    """
    Mixin para gerenciamento da jornada do paciente.
    
    Requer que a classe base tenha:
        - self.client (Supabase client)
        - self.is_real (bool)
        - self.uid() -> str
        - self.mock (dict)
    
    Example:
        >>> class Database(JourneyRepository):
        ...     def __init__(self):
        ...         self.client = None
        ...         self.is_real = False
        ...         self.mock = {"jornadas": []}
        ...     
        ...     def uid(self) -> str:
        ...         return "user@example.com"
        
        >>> db = Database()
        >>> journey = db.create_journey("general", "Minha Jornada", "Perder 10kg")
        >>> if journey:
        ...     print(f"Jornada criada: {journey.id}")
    """

    # ─────────────────────────────────────────────────────────────────────────
    # JORNADA ATIVA
    # ─────────────────────────────────────────────────────────────────────────

    def get_journey_ativa(self) -> Journey | None:
        """
        Retorna a jornada ativa do paciente.
        
        Returns:
            Objeto Journey ou None se não houver jornada ativa
            
        Example:
            >>> journey = db.get_journey_ativa()
            >>> if journey:
            ...     print(f"Jornada: {journey.nome} - {journey.tipo}")
            ... else:
            ...     print("Nenhuma jornada ativa")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("jornadas")
                    .select("*")
                    .eq("perfil_id", uid)
                    .eq("ativa", True)
                    .limit(1)
                    .execute()
                )
                
                if response.data:
                    return self._build_journey_from_data(response.data[0])
                
            except Exception as e:
                logger.error(f"get_journey_ativa Supabase: {e}")
        
        # Fallback MockDB
        for journey_data in self.mock.get("jornadas", []):
            if journey_data.get("user_id") == uid and journey_data.get("ativa"):
                return self._build_journey_from_data(journey_data)
        
        logger.debug(f"Nenhuma jornada ativa para: {uid}")
        return None

    def create_journey(
        self,
        tipo: str,
        nome: str,
        objetivo: str = "",
    ) -> Journey | None:
        """
        Cria uma nova jornada ativa para o paciente.
        
        Args:
            tipo: Tipo da jornada (general/fitness/bariatric/glp1)
            nome: Nome da jornada
            objetivo: Objetivo da jornada (opcional)
            
        Returns:
            Objeto Journey criado ou None se já existir jornada ativa
            
        Example:
            >>> journey = db.create_journey("general", "Minha Jornada", "Perder 10kg")
            >>> if journey:
            ...     print(f"Jornada criada: {journey.id}")
            ... else:
            ...     print("Já existe uma jornada ativa")
        """
        uid = self.uid()
        
        # Validações
        if not nome or not nome.strip():
            logger.warning("❌ Nome da jornada é obrigatório")
            return None
        
        valid_tipos = {"general", "fitness", "bariatric", "glp1"}
        if tipo not in valid_tipos:
            logger.warning(f"❌ Tipo de jornada inválido: {tipo}")
            return None
        
        # Verifica se já existe jornada ativa
        existing = self.get_journey_ativa()
        if existing:
            logger.warning("❌ Já existe jornada ativa")
            return existing
        
        journey_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                response = self.client.table("jornadas").insert({
                    "id": journey_id,
                    "perfil_id": uid,
                    "tipo": tipo,
                    "nome": nome,
                    "objetivo": objetivo or None,
                    "ativa": True,
                    "iniciada_em": date.today().isoformat(),
                }).execute()
                
                if response.data:
                    journey = self._build_journey_from_data(response.data[0])
                    logger.info(f"✅ Jornada criada no Supabase: {journey.id}")
                    return journey
                
            except Exception as e:
                logger.error(f"create_journey Supabase: {e}")
        
        # Fallback MockDB
        journey_data = {
            "id": journey_id,
            "user_id": uid,
            "tipo": tipo,
            "nome": nome,
            "objetivo": objetivo,
            "ativa": True,
            "iniciada_em": date.today().isoformat(),
        }
        
        self.mock.setdefault("jornadas", []).append(journey_data)
        
        journey = self._build_journey_from_data(journey_data)
        logger.info(f"✅ Jornada criada no MockDB: {journey.id}")
        return journey

    # ─────────────────────────────────────────────────────────────────────────
    # ETAPAS
    # ─────────────────────────────────────────────────────────────────────────

    def get_stages(self, journey_id: str) -> list[Stage]:
        """
        Retorna todas as etapas de uma jornada.
        
        Args:
            journey_id: ID da jornada
            
        Returns:
            Lista de objetos Stage (ordenados por ordem)
            
        Example:
            >>> stages = db.get_stages(journey_id)
            >>> for stage in stages:
            ...     print(f"{stage.ordem}: {stage.nome} - {stage.concluida}")
        """
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("etapas_jornada")
                    .select("*")
                    .eq("jornada_id", journey_id)
                    .order("ordem")
                    .execute()
                )
                
                return [self._build_stage_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_stages Supabase: {e}")
        
        # Fallback MockDB
        stages_data = self.mock.get(f"etapas_{journey_id}", [])
        return [self._build_stage_from_data(row) for row in stages_data]

    def get_current_stage(self, journey_id: str) -> Stage | None:
        """
        Retorna a primeira etapa não concluída da jornada.
        
        Args:
            journey_id: ID da jornada
            
        Returns:
            Objeto Stage ou None se todas concluídas
            
        Example:
            >>> stage = db.get_current_stage(journey_id)
            >>> if stage:
            ...     print(f"Etapa atual: {stage.nome}")
            ... else:
            ...     print("Todas as etapas concluídas!")
        """
        stages = self.get_stages(journey_id)
        
        for stage in stages:
            if not stage.concluida:
                return stage
        
        # Retorna a última etapa se todas estiverem concluídas
        return stages[-1] if stages else None

    def complete_stage(self, stage_id: str) -> bool:
        """
        Marca uma etapa como concluída.
        
        Args:
            stage_id: ID da etapa
            
        Returns:
            True se concluída com sucesso, False caso contrário
            
        Example:
            >>> success = db.complete_stage(stage_id)
            >>> if success:
            ...     print("Etapa concluída!")
        """
        if not stage_id:
            logger.warning("❌ stage_id é obrigatório")
            return False
        
        if self.is_real and self.client:
            try:
                self.client.table("etapas_jornada").update({
                    "concluida": True,
                    "concluida_em": date.today().isoformat(),
                }).eq("id", stage_id).execute()
                
                logger.info(f"✅ Etapa concluída no Supabase: {stage_id}")
                return True
                
            except Exception as e:
                logger.error(f"complete_stage Supabase: {e}")
        
        # Fallback MockDB
        for journey_key in self.mock.keys():
            if journey_key.startswith("etapas_"):
                stages = self.mock[journey_key]
                for stage in stages:
                    if stage.get("id") == stage_id:
                        stage["concluida"] = True
                        stage["concluida_em"] = date.today().isoformat()
                        logger.info(f"✅ Etapa concluída no MockDB: {stage_id}")
                        return True
        
        logger.warning(f"❌ Etapa não encontrada: {stage_id}")
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # MARCOS
    # ─────────────────────────────────────────────────────────────────────────

    def get_milestones(self, journey_id: str) -> list[Milestone]:
        """
        Retorna todos os marcos de uma jornada.
        
        Args:
            journey_id: ID da jornada
            
        Returns:
            Lista de objetos Milestone
            
        Example:
            >>> milestones = db.get_milestones(journey_id)
            >>> for milestone in milestones:
            ...     print(f"{milestone.titulo} - {milestone.data_marco}")
        """
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("marcos")
                    .select("*")
                    .eq("jornada_id", journey_id)
                    .order("data_marco", desc=True)
                    .execute()
                )
                
                return [self._build_milestone_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_milestones Supabase: {e}")
        
        # Fallback MockDB
        milestones_data = self.mock.get(f"marcos_{journey_id}", [])
        return [self._build_milestone_from_data(row) for row in milestones_data]

    def register_milestone(
        self,
        journey_id: str,
        titulo: str,
        descricao: str = "",
    ) -> bool:
        """
        Registra um novo marco na jornada.
        
        Args:
            journey_id: ID da jornada
            titulo: Título do marco
            descricao: Descrição do marco
            
        Returns:
            True se registrado com sucesso, False caso contrário
            
        Example:
            >>> success = db.register_milestone(journey_id, "🔥 7 Dias Seguidos", "Uma semana sem falhar!")
            >>> if success:
            ...     print("Marco registrado!")
        """
        if not journey_id or not titulo:
            logger.warning("❌ journey_id e titulo são obrigatórios")
            return False
        
        milestone_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                self.client.table("marcos").insert({
                    "id": milestone_id,
                    "jornada_id": journey_id,
                    "titulo": titulo,
                    "descricao": descricao or None,
                    "data_marco": date.today().isoformat(),
                }).execute()
                
                logger.info(f"✅ Marco registrado no Supabase: {titulo}")
                return True
                
            except Exception as e:
                logger.error(f"register_milestone Supabase: {e}")
        
        # Fallback MockDB
        key = f"marcos_{journey_id}"
        self.mock.setdefault(key, []).append({
            "id": milestone_id,
            "jornada_id": journey_id,
            "titulo": titulo,
            "descricao": descricao,
            "data_marco": date.today().isoformat(),
        })
        
        logger.info(f"✅ Marco registrado no MockDB: {titulo}")
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # EVENTOS
    # ─────────────────────────────────────────────────────────────────────────

    def get_events(self, journey_id: str, limit: int = 10) -> list[Event]:
        """
        Retorna os eventos de uma jornada (linha do tempo).
        
        Args:
            journey_id: ID da jornada
            limit: Número máximo de eventos
            
        Returns:
            Lista de objetos Event (ordenados por data descendente)
            
        Example:
            >>> events = db.get_events(journey_id, limit=5)
            >>> for event in events:
            ...     print(f"{event.descricao} - {event.criado_em}")
        """
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("eventos_jornada")
                    .select("*")
                    .eq("jornada_id", journey_id)
                    .order("criado_em", desc=True)
                    .limit(limit)
                    .execute()
                )
                
                return [self._build_event_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_events Supabase: {e}")
        
        # Fallback MockDB
        events_data = self.mock.get(f"eventos_{journey_id}", [])
        # Ordena por criado_em descendente
        sorted_events = sorted(
            events_data,
            key=lambda x: x.get("criado_em", ""),
            reverse=True
        )
        return [self._build_event_from_data(row) for row in sorted_events[:limit]]

    def register_event(
        self,
        journey_id: str,
        tipo: str,
        descricao: str,
    ) -> bool:
        """
        Registra um novo evento na linha do tempo da jornada.
        
        Args:
            journey_id: ID da jornada
            tipo: Tipo do evento (checkin/pesagem/refeicao/marco/conquista)
            descricao: Descrição do evento
            
        Returns:
            True se registrado com sucesso, False caso contrário
            
        Example:
            >>> success = db.register_event(journey_id, "checkin", "Check-in diário realizado")
            >>> if success:
            ...     print("Evento registrado!")
        """
        if not journey_id or not tipo or not descricao:
            logger.warning("❌ journey_id, tipo e descricao são obrigatórios")
            return False
        
        valid_tipos = {"checkin", "pesagem", "refeicao", "marco", "conquista", "meta", "etapa"}
        if tipo not in valid_tipos:
            logger.warning(f"❌ Tipo de evento inválido: {tipo}")
            return False
        
        event_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                self.client.table("eventos_jornada").insert({
                    "id": event_id,
                    "jornada_id": journey_id,
                    "tipo": tipo,
                    "descricao": descricao,
                }).execute()
                
                logger.info(f"✅ Evento registrado no Supabase: {tipo}")
                return True
                
            except Exception as e:
                logger.error(f"register_event Supabase: {e}")
        
        # Fallback MockDB
        key = f"eventos_{journey_id}"
        self.mock.setdefault(key, []).append({
            "id": event_id,
            "jornada_id": journey_id,
            "tipo": tipo,
            "descricao": descricao,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        })
        
        logger.info(f"✅ Evento registrado no MockDB: {tipo}")
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # METAS
    # ─────────────────────────────────────────────────────────────────────────

    def get_goals(self, journey_id: str) -> list[Goal]:
        """
        Retorna todas as metas de uma jornada.
        
        Args:
            journey_id: ID da jornada
            
        Returns:
            Lista de objetos Goal
            
        Example:
            >>> goals = db.get_goals(journey_id)
            >>> for goal in goals:
            ...     print(f"{goal.titulo}: {goal.valor_atual}/{goal.valor_alvo} {goal.unidade}")
        """
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("metas")
                    .select("*")
                    .eq("jornada_id", journey_id)
                    .order("criado_em", desc=True)
                    .execute()
                )
                
                return [self._build_goal_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_goals Supabase: {e}")
        
        # Fallback MockDB
        goals_data = self.mock.get(f"metas_{journey_id}", [])
        return [self._build_goal_from_data(row) for row in goals_data]

    def create_goal(
        self,
        journey_id: str,
        titulo: str,
        valor_alvo: float,
        unidade: str,
        prazo: str = "",
    ) -> bool:
        """
        Cria uma nova meta para a jornada.
        
        Args:
            journey_id: ID da jornada
            titulo: Título da meta
            valor_alvo: Valor alvo
            unidade: Unidade da meta (kg/dias/% etc)
            prazo: Prazo da meta (YYYY-MM-DD)
            
        Returns:
            True se criada com sucesso, False caso contrário
            
        Example:
            >>> success = db.create_goal(
            ...     journey_id,
            ...     "Perder 5 kg",
            ...     5.0,
            ...     "kg",
            ...     "2026-12-31"
            ... )
            >>> if success:
            ...     print("Meta criada!")
        """
        uid = self.uid()
        
        # Validações
        if not journey_id or not titulo or not unidade:
            logger.warning("❌ journey_id, titulo e unidade são obrigatórios")
            return False
        
        if valor_alvo <= 0:
            logger.warning(f"❌ valor_alvo deve ser positivo: {valor_alvo}")
            return False
        
        goal_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                self.client.table("metas").insert({
                    "id": goal_id,
                    "jornada_id": journey_id,
                    "perfil_id": uid,
                    "titulo": titulo,
                    "valor_alvo": valor_alvo,
                    "valor_atual": 0.0,
                    "unidade": unidade,
                    "prazo": prazo or None,
                    "concluida": False,
                }).execute()
                
                logger.info(f"✅ Meta criada no Supabase: {titulo}")
                return True
                
            except Exception as e:
                logger.error(f"create_goal Supabase: {e}")
        
        # Fallback MockDB
        key = f"metas_{journey_id}"
        self.mock.setdefault(key, []).append({
            "id": goal_id,
            "jornada_id": journey_id,
            "user_id": uid,
            "titulo": titulo,
            "valor_alvo": valor_alvo,
            "valor_atual": 0.0,
            "unidade": unidade,
            "prazo": prazo,
            "concluida": False,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        })
        
        logger.info(f"✅ Meta criada no MockDB: {titulo}")
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS DE CONVERSÃO
    # ─────────────────────────────────────────────────────────────────────────

    def _build_journey_from_data(self, data: dict[str, Any]) -> Journey:
        """Converte um dicionário para um objeto Journey."""
        return Journey.from_dict(data)

    def _build_stage_from_data(self, data: dict[str, Any]) -> Stage:
        """Converte um dicionário para um objeto Stage."""
        return Stage.from_dict(data)

    def _build_milestone_from_data(self, data: dict[str, Any]) -> Milestone:
        """Converte um dicionário para um objeto Milestone."""
        return Milestone.from_dict(data)

    def _build_event_from_data(self, data: dict[str, Any]) -> Event:
        """Converte um dicionário para um objeto Event."""
        return Event.from_dict(data)

    def _build_goal_from_data(self, data: dict[str, Any]) -> Goal:
        """Converte um dicionário para um objeto Goal."""
        return Goal.from_dict(data)


__all__ = [
    "JourneyRepository",
    "Journey",
    "Stage",
    "Milestone",
    "Event",
    "Goal",
]
