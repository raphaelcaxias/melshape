"""
Melshape — Journey Story Repository.

Gerencia a narrativa da jornada do paciente: o "porquê", fotos de evolução,
conquistas específicas da jornada e eventos de vida.

Princípios:
- Motivo: o "porquê" do paciente (capturado no onboarding)
- Fotos: registro visual da evolução
- Conquistas: marcos específicos da jornada (≠ badges globais)
- Eventos: momentos marcantes registrados pelo paciente
- Fallback automático: Supabase → MockDB
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Modelos: dataclasses imutáveis para todas as entidades
- Validação: dados são validados antes de salvar
- Logging: todas as operações são logadas

Arquitetura:
    JourneyStoryRepository
    ├── get_motivations(journey_id) -> list[JourneyMotivation]
    ├── save_motivation(journey_id, motivo, emocional) -> JourneyMotivation | None
    ├── save_photo(url, legenda, peso_na_data) -> EvolutionPhoto | None
    ├── get_photos() -> list[EvolutionPhoto]
    ├── delete_photo(photo_id) -> bool
    ├── get_journey_achievements(journey_id) -> list[JourneyAchievement]
    ├── register_journey_achievement(journey_id, titulo, descricao) -> JourneyAchievement | None
    ├── get_life_events() -> list[LifeEvent]
    ├── register_life_event(titulo, descricao, tipo, data_evento) -> LifeEvent | None
    └── delete_life_event(event_id) -> bool
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

logger = logging.getLogger("Melshape.JourneyStory")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DA NARRATIVA DA JORNADA
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class JourneyMotivation:
    """
    Modelo de motivo da jornada (o "porquê" do paciente).
    
    Attributes:
        id: ID único do motivo
        journey_id: ID da jornada
        user_id: ID do usuário
        motivo: Texto do motivo
        emocional: Se o motivo é emocional ou prático
        criado_em: Timestamp de criação
    """
    id: str
    journey_id: str
    user_id: str
    motivo: str
    emocional: bool = True
    criado_em: str = field(default_factory=lambda: date.today().isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JourneyMotivation:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            journey_id=data.get("jornada_id", data.get("journey_id", "")),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            motivo=data.get("motivo", ""),
            emocional=data.get("emocional", True),
            criado_em=data.get("criado_em", date.today().isoformat()),
        )
    
    @property
    def tipo_label(self) -> str:
        """Retorna o rótulo do tipo de motivo."""
        return "💚 Emocional" if self.emocional else "🎯 Prático"
    
    @property
    def is_emotional(self) -> bool:
        """Verifica se o motivo é emocional."""
        return self.emocional


@dataclass(frozen=True)
class EvolutionPhoto:
    """
    Modelo de foto de evolução do paciente.
    
    Attributes:
        id: ID único da foto
        user_id: ID do usuário
        url: URL da foto
        legenda: Legenda da foto
        peso_na_data: Peso na data da foto
        data_foto: Data da foto (YYYY-MM-DD)
        criado_em: Timestamp de criação
    """
    id: str
    user_id: str
    url: str
    legenda: str = ""
    peso_na_data: float | None = None
    data_foto: str = field(default_factory=lambda: date.today().isoformat())
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionPhoto:
        """Cria uma instância a partir de um dicionário."""
        peso = data.get("peso_na_data")
        if peso is not None:
            try:
                peso = float(peso)
            except (ValueError, TypeError):
                peso = None
        
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            url=data.get("url_foto", data.get("url", "")),
            legenda=data.get("legenda", ""),
            peso_na_data=peso,
            data_foto=data.get("data_foto", date.today().isoformat()),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )
    
    @property
    def photo_age_days(self) -> int:
        """Calcula dias desde a foto."""
        try:
            photo_date = datetime.strptime(self.data_foto, "%Y-%m-%d").date()
            delta = (date.today() - photo_date).days
            return max(0, delta)
        except Exception:
            return 0
    
    @property
    def has_weight(self) -> bool:
        """Verifica se a foto tem peso registrado."""
        return self.peso_na_data is not None and self.peso_na_data > 0


@dataclass(frozen=True)
class JourneyAchievement:
    """
    Modelo de conquista específica da jornada.
    
    Attributes:
        id: ID único da conquista
        journey_id: ID da jornada
        user_id: ID do usuário
        titulo: Título da conquista
        descricao: Descrição da conquista
        conquistado_em: Data da conquista (YYYY-MM-DD)
        criado_em: Timestamp de criação
    """
    id: str
    journey_id: str
    user_id: str
    titulo: str
    descricao: str = ""
    conquistado_em: str = field(default_factory=lambda: date.today().isoformat())
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JourneyAchievement:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            journey_id=data.get("jornada_id", data.get("journey_id", "")),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            titulo=data.get("titulo", ""),
            descricao=data.get("descricao", ""),
            conquistado_em=data.get("conquistado_em", date.today().isoformat()),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )


@dataclass(frozen=True)
class LifeEvent:
    """
    Modelo de evento de vida do paciente.
    
    Attributes:
        id: ID único do evento
        user_id: ID do usuário
        titulo: Título do evento
        descricao: Descrição do evento
        tipo: Tipo do evento (marco/celebracao/desafio/dificuldade/inicio)
        data_evento: Data do evento (YYYY-MM-DD)
        criado_em: Timestamp de criação
    """
    id: str
    user_id: str
    titulo: str
    descricao: str = ""
    tipo: str = "marco"
    data_evento: str = field(default_factory=lambda: date.today().isoformat())
    criado_em: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LifeEvent:
        """Cria uma instância a partir de um dicionário."""
        return cls(
            id=data.get("id", ""),
            user_id=data.get("user_id", data.get("perfil_id", "")),
            titulo=data.get("titulo", ""),
            descricao=data.get("descricao", ""),
            tipo=data.get("tipo", "marco"),
            data_evento=data.get("data_evento", date.today().isoformat()),
            criado_em=data.get("criado_em", datetime.now(timezone.utc).isoformat()),
        )
    
    @property
    def tipo_label(self) -> str:
        """Retorna o rótulo do tipo de evento."""
        labels = {
            "marco": "🏆 Marco",
            "celebracao": "🎉 Celebração",
            "desafio": "💪 Desafio",
            "dificuldade": "⚠️ Dificuldade",
            "inicio": "🚀 Início",
        }
        return labels.get(self.tipo, self.tipo)
    
    @property
    def days_since_event(self) -> int:
        """Calcula dias desde o evento."""
        try:
            event_date = datetime.strptime(self.data_evento, "%Y-%m-%d").date()
            delta = (date.today() - event_date).days
            return max(0, delta)
        except Exception:
            return 0


# ─────────────────────────────────────────────────────────────────────────────
# JOURNEY STORY REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────

class JourneyStoryRepository:
    """
    Mixin para gerenciamento da narrativa da jornada.
    
    Requer que a classe base tenha:
        - self.client (Supabase client)
        - self.is_real (bool)
        - self.uid() -> str
        - self.mock (dict)
    
    Example:
        >>> class Database(JourneyStoryRepository):
        ...     def __init__(self):
        ...         self.client = None
        ...         self.is_real = False
        ...         self.mock = {"motivos_jornada": {}}
        ...     
        ...     def uid(self) -> str:
        ...         return "user@example.com"
        
        >>> db = Database()
        >>> motivation = db.save_motivation("journey_id", "Quero ter energia para brincar com meus filhos")
        >>> if motivation:
        ...     print(f"Motivo salvo: {motivation.id}")
    """

    # ─────────────────────────────────────────────────────────────────────────
    # MOTIVOS DA JORNADA
    # ─────────────────────────────────────────────────────────────────────────

    def get_motivations(self, journey_id: str) -> list[JourneyMotivation]:
        """
        Retorna os motivos da jornada.
        
        Args:
            journey_id: ID da jornada
            
        Returns:
            Lista de objetos JourneyMotivation
            
        Example:
            >>> motivations = db.get_motivations("journey_id")
            >>> for m in motivations:
            ...     print(f"{m.motivo} ({m.tipo_label})")
        """
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("motivos_jornada")
                    .select("*")
                    .eq("jornada_id", journey_id)
                    .order("criado_em")
                    .execute()
                )
                
                return [self._build_motivation_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_motivations Supabase: {e}")
        
        # Fallback MockDB
        key = f"motivos_{journey_id}"
        motivations_data = self.mock.get(key, [])
        
        return [self._build_motivation_from_data(row) for row in motivations_data]

    def save_motivation(
        self,
        journey_id: str,
        motivo: str,
        emocional: bool = True,
    ) -> JourneyMotivation | None:
        """
        Salva o "porquê" do paciente ao iniciar a jornada.
        
        Args:
            journey_id: ID da jornada
            motivo: Texto do motivo
            emocional: Se o motivo é emocional ou prático
            
        Returns:
            Objeto JourneyMotivation criado ou None se falhar
            
        Example:
            >>> motivation = db.save_motivation(
            ...     "journey_id",
            ...     "Quero ter energia para brincar com meus filhos",
            ...     emocional=True
            ... )
            >>> if motivation:
            ...     print(f"Motivo salvo: {motivation.id}")
        """
        uid = self.uid()
        
        # Validações
        if not journey_id or not journey_id.strip():
            logger.warning("❌ journey_id é obrigatório")
            return None
        
        if not motivo or not motivo.strip():
            logger.warning("❌ Motivo é obrigatório")
            return None
        
        motivation_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                response = self.client.table("motivos_jornada").insert({
                    "id": motivation_id,
                    "jornada_id": journey_id,
                    "perfil_id": uid,
                    "motivo": motivo,
                    "emocional": emocional,
                }).execute()
                
                if response.data:
                    motivation = self._build_motivation_from_data(response.data[0])
                    logger.info(f"✅ Motivo salvo no Supabase: {motivo[:50]}...")
                    return motivation
                
            except Exception as e:
                logger.error(f"save_motivation Supabase: {e}")
        
        # Fallback MockDB
        key = f"motivos_{journey_id}"
        motivation_data = {
            "id": motivation_id,
            "journey_id": journey_id,
            "user_id": uid,
            "motivo": motivo,
            "emocional": emocional,
            "criado_em": date.today().isoformat(),
        }
        
        self.mock.setdefault(key, []).append(motivation_data)
        
        motivation = self._build_motivation_from_data(motivation_data)
        logger.info(f"✅ Motivo salvo no MockDB: {motivo[:50]}...")
        return motivation

    # ─────────────────────────────────────────────────────────────────────────
    # FOTOS DE EVOLUÇÃO
    # ─────────────────────────────────────────────────────────────────────────

    def save_photo(
        self,
        url: str,
        legenda: str = "",
        peso_na_data: float | None = None,
    ) -> EvolutionPhoto | None:
        """
        Salva uma foto de evolução do paciente.
        
        Args:
            url: URL da foto
            legenda: Legenda opcional
            peso_na_data: Peso na data da foto
            
        Returns:
            Objeto EvolutionPhoto criado ou None se falhar
            
        Example:
            >>> photo = db.save_photo(
            ...     "https://storage.com/foto1.jpg",
            ...     "Início da jornada",
            ...     78.5
            ... )
            >>> if photo:
            ...     print(f"Foto salva: {photo.id}")
        """
        uid = self.uid()
        
        # Validações
        if not url or not url.strip():
            logger.warning("❌ URL é obrigatória")
            return None
        
        if peso_na_data is not None and peso_na_data <= 0:
            logger.warning(f"❌ Peso deve ser positivo: {peso_na_data}")
            return None
        
        photo_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                payload = {
                    "id": photo_id,
                    "perfil_id": uid,
                    "url_foto": url,
                    "data_foto": date.today().isoformat(),
                }
                
                if legenda:
                    payload["legenda"] = legenda
                
                if peso_na_data is not None:
                    payload["peso_na_data"] = peso_na_data
                
                response = self.client.table("fotos_evolucao").insert(payload).execute()
                
                if response.data:
                    photo = self._build_photo_from_data(response.data[0])
                    logger.info(f"✅ Foto salva no Supabase: {photo.id}")
                    return photo
                
            except Exception as e:
                logger.error(f"save_photo Supabase: {e}")
        
        # Fallback MockDB
        key = f"fotos_{uid}"
        photo_data = {
            "id": photo_id,
            "user_id": uid,
            "url": url,
            "legenda": legenda,
            "peso_na_data": peso_na_data,
            "data_foto": date.today().isoformat(),
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
        
        self.mock.setdefault(key, []).append(photo_data)
        
        photo = self._build_photo_from_data(photo_data)
        logger.info(f"✅ Foto salva no MockDB: {photo.id}")
        return photo

    def get_photos(self) -> list[EvolutionPhoto]:
        """
        Retorna as fotos de evolução do paciente.
        
        Returns:
            Lista de objetos EvolutionPhoto (ordenados por data descendente)
            
        Example:
            >>> photos = db.get_photos()
            >>> for p in photos:
            ...     print(f"{p.data_foto}: {p.legenda}")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("fotos_evolucao")
                    .select("*")
                    .eq("perfil_id", uid)
                    .order("data_foto", desc=True)
                    .execute()
                )
                
                return [self._build_photo_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_photos Supabase: {e}")
        
        # Fallback MockDB
        key = f"fotos_{uid}"
        photos_data = self.mock.get(key, [])
        
        # Ordena por data_foto descendente
        sorted_photos = sorted(
            photos_data,
            key=lambda x: x.get("data_foto", ""),
            reverse=True
        )
        
        return [self._build_photo_from_data(row) for row in sorted_photos]

    def delete_photo(self, photo_id: str) -> bool:
        """
        Remove uma foto de evolução.
        
        Args:
            photo_id: ID da foto
            
        Returns:
            True se removida com sucesso, False caso contrário
            
        Example:
            >>> success = db.delete_photo(photo_id)
            >>> if success:
            ...     print("Foto removida!")
        """
        if not photo_id:
            logger.warning("❌ photo_id é obrigatório")
            return False
        
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                self.client.table("fotos_evolucao").delete().eq("id", photo_id).execute()
                logger.info(f"✅ Foto removida no Supabase: {photo_id}")
                return True
                
            except Exception as e:
                logger.error(f"delete_photo Supabase: {e}")
        
        # Fallback MockDB
        key = f"fotos_{uid}"
        photos = self.mock.get(key, [])
        
        for i, photo in enumerate(photos):
            if photo.get("id") == photo_id:
                photos.pop(i)
                logger.info(f"✅ Foto removida no MockDB: {photo_id}")
                return True
        
        logger.warning(f"❌ Foto não encontrada: {photo_id}")
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # CONQUISTAS DA JORNADA
    # ─────────────────────────────────────────────────────────────────────────

    def get_journey_achievements(self, journey_id: str) -> list[JourneyAchievement]:
        """
        Retorna as conquistas específicas da jornada (≠ badges globais).
        
        Args:
            journey_id: ID da jornada
            
        Returns:
            Lista de objetos JourneyAchievement (ordenados por data descendente)
            
        Example:
            >>> achievements = db.get_journey_achievements("journey_id")
            >>> for a in achievements:
            ...     print(f"{a.titulo} - {a.conquistado_em}")
        """
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("conquistas_jornada")
                    .select("*")
                    .eq("jornada_id", journey_id)
                    .order("conquistado_em", desc=True)
                    .execute()
                )
                
                return [self._build_achievement_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_journey_achievements Supabase: {e}")
        
        # Fallback MockDB
        key = f"conq_j_{journey_id}"
        achievements_data = self.mock.get(key, [])
        
        # Ordena por conquistado_em descendente
        sorted_achievements = sorted(
            achievements_data,
            key=lambda x: x.get("conquistado_em", ""),
            reverse=True
        )
        
        return [self._build_achievement_from_data(row) for row in sorted_achievements]

    def register_journey_achievement(
        self,
        journey_id: str,
        titulo: str,
        descricao: str = "",
    ) -> JourneyAchievement | None:
        """
        Registra uma conquista específica da jornada.
        
        Args:
            journey_id: ID da jornada
            titulo: Título da conquista
            descricao: Descrição da conquista
            
        Returns:
            Objeto JourneyAchievement criado ou None se falhar
            
        Example:
            >>> achievement = db.register_journey_achievement(
            ...     "journey_id",
            ...     "Etapa 1 concluída!",
            ...     "Primeiros passos da jornada"
            ... )
            >>> if achievement:
            ...     print(f"Conquista registrada: {achievement.id}")
        """
        uid = self.uid()
        
        # Validações
        if not journey_id or not journey_id.strip():
            logger.warning("❌ journey_id é obrigatório")
            return None
        
        if not titulo or not titulo.strip():
            logger.warning("❌ Título é obrigatório")
            return None
        
        achievement_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                payload = {
                    "id": achievement_id,
                    "jornada_id": journey_id,
                    "perfil_id": uid,
                    "titulo": titulo,
                    "conquistado_em": date.today().isoformat(),
                }
                
                if descricao:
                    payload["descricao"] = descricao
                
                response = self.client.table("conquistas_jornada").insert(payload).execute()
                
                if response.data:
                    achievement = self._build_achievement_from_data(response.data[0])
                    logger.info(f"✅ Conquista registrada no Supabase: {titulo}")
                    return achievement
                
            except Exception as e:
                logger.error(f"register_journey_achievement Supabase: {e}")
        
        # Fallback MockDB
        key = f"conq_j_{journey_id}"
        achievement_data = {
            "id": achievement_id,
            "journey_id": journey_id,
            "user_id": uid,
            "titulo": titulo,
            "descricao": descricao,
            "conquistado_em": date.today().isoformat(),
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
        
        self.mock.setdefault(key, []).append(achievement_data)
        
        achievement = self._build_achievement_from_data(achievement_data)
        logger.info(f"✅ Conquista registrada no MockDB: {titulo}")
        return achievement

    # ─────────────────────────────────────────────────────────────────────────
    # EVENTOS DE VIDA
    # ─────────────────────────────────────────────────────────────────────────

    def get_life_events(self) -> list[LifeEvent]:
        """
        Retorna os eventos de vida do paciente.
        
        Returns:
            Lista de objetos LifeEvent (ordenados por data descendente)
            
        Example:
            >>> events = db.get_life_events()
            >>> for e in events:
            ...     print(f"{e.data_evento}: {e.titulo} ({e.tipo_label})")
        """
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                response = (
                    self.client.table("eventos_vida")
                    .select("*")
                    .eq("perfil_id", uid)
                    .order("data_evento", desc=True)
                    .limit(50)
                    .execute()
                )
                
                return [self._build_event_from_data(row) for row in (response.data or [])]
                
            except Exception as e:
                logger.error(f"get_life_events Supabase: {e}")
        
        # Fallback MockDB
        key = f"ev_vida_{uid}"
        events_data = self.mock.get(key, [])
        
        # Ordena por data_evento descendente
        sorted_events = sorted(
            events_data,
            key=lambda x: x.get("data_evento", ""),
            reverse=True
        )
        
        return [self._build_event_from_data(row) for row in sorted_events]

    def register_life_event(
        self,
        titulo: str,
        descricao: str = "",
        tipo: str = "marco",
        data_evento: str = "",
    ) -> LifeEvent | None:
        """
        Registra um evento de vida do paciente.
        
        Args:
            titulo: Título do evento
            descricao: Descrição do evento
            tipo: Tipo do evento (marco/celebracao/desafio/dificuldade/inicio)
            data_evento: Data do evento (YYYY-MM-DD, padrão: hoje)
            
        Returns:
            Objeto LifeEvent criado ou None se falhar
            
        Example:
            >>> event = db.register_life_event(
            ...     "Completei minha primeira semana!",
            ...     "7 dias consecutivos de check-in",
            ...     "marco"
            ... )
            >>> if event:
            ...     print(f"Evento registrado: {event.id}")
        """
        uid = self.uid()
        data = data_evento or date.today().isoformat()
        
        # Validações
        if not titulo or not titulo.strip():
            logger.warning("❌ Título é obrigatório")
            return None
        
        valid_tipos = {"marco", "celebracao", "desafio", "dificuldade", "inicio"}
        if tipo not in valid_tipos:
            logger.warning(f"❌ Tipo de evento inválido: {tipo}")
            return None
        
        # Valida formato da data
        try:
            datetime.strptime(data, "%Y-%m-%d")
        except ValueError:
            logger.warning(f"❌ Data inválida: {data} (use YYYY-MM-DD)")
            return None
        
        event_id = str(uuid.uuid4())
        
        if self.is_real and self.client:
            try:
                payload = {
                    "id": event_id,
                    "perfil_id": uid,
                    "titulo": titulo,
                    "tipo": tipo,
                    "data_evento": data,
                }
                
                if descricao:
                    payload["descricao"] = descricao
                
                response = self.client.table("eventos_vida").insert(payload).execute()
                
                if response.data:
                    event = self._build_event_from_data(response.data[0])
                    logger.info(f"✅ Evento registrado no Supabase: {titulo}")
                    return event
                
            except Exception as e:
                logger.error(f"register_life_event Supabase: {e}")
        
        # Fallback MockDB
        key = f"ev_vida_{uid}"
        event_data = {
            "id": event_id,
            "user_id": uid,
            "titulo": titulo,
            "descricao": descricao,
            "tipo": tipo,
            "data_evento": data,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
        
        self.mock.setdefault(key, []).append(event_data)
        
        event = self._build_event_from_data(event_data)
        logger.info(f"✅ Evento registrado no MockDB: {titulo}")
        return event

    def delete_life_event(self, event_id: str) -> bool:
        """
        Remove um evento de vida.
        
        Args:
            event_id: ID do evento
            
        Returns:
            True se removido com sucesso, False caso contrário
            
        Example:
            >>> success = db.delete_life_event(event_id)
            >>> if success:
            ...     print("Evento removido!")
        """
        if not event_id:
            logger.warning("❌ event_id é obrigatório")
            return False
        
        uid = self.uid()
        
        if self.is_real and self.client:
            try:
                self.client.table("eventos_vida").delete().eq("id", event_id).execute()
                logger.info(f"✅ Evento removido no Supabase: {event_id}")
                return True
                
            except Exception as e:
                logger.error(f"delete_life_event Supabase: {e}")
        
        # Fallback MockDB
        key = f"ev_vida_{uid}"
        events = self.mock.get(key, [])
        
        for i, event in enumerate(events):
            if event.get("id") == event_id:
                events.pop(i)
                logger.info(f"✅ Evento removido no MockDB: {event_id}")
                return True
        
        logger.warning(f"❌ Evento não encontrado: {event_id}")
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS DE CONVERSÃO
    # ─────────────────────────────────────────────────────────────────────────

    def _build_motivation_from_data(self, data: dict[str, Any]) -> JourneyMotivation:
        """Converte um dicionário para um objeto JourneyMotivation."""
        return JourneyMotivation.from_dict(data)

    def _build_photo_from_data(self, data: dict[str, Any]) -> EvolutionPhoto:
        """Converte um dicionário para um objeto EvolutionPhoto."""
        return EvolutionPhoto.from_dict(data)

    def _build_achievement_from_data(self, data: dict[str, Any]) -> JourneyAchievement:
        """Converte um dicionário para um objeto JourneyAchievement."""
        return JourneyAchievement.from_dict(data)

    def _build_event_from_data(self, data: dict[str, Any]) -> LifeEvent:
        """Converte um dicionário para um objeto LifeEvent."""
        return LifeEvent.from_dict(data)


__all__ = [
    "JourneyStoryRepository",
    "JourneyMotivation",
    "EvolutionPhoto",
    "JourneyAchievement",
    "LifeEvent",
]
