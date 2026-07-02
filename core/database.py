"""
Melshape — Camada de Dados Principal.

Gerencia acesso ao Supabase com fallback para MockDB (desenvolvimento/demo).
Implementa o padrão Repository para todas as entidades.

Princípios:
- Repository Pattern: cada entidade tem seu próprio repositório
- Fallback inteligente: Supabase → MockDB automaticamente
- Injeção de dependência: serviços recebem db via construtor
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Logging: operações de dados são logadas
- Session State: isolado do resto da aplicação
- Imutabilidade: modelos são frozen dataclasses

Arquitetura:
    Database (classe principal)
    ├── RecordsMixin (refeições, peso, hidratação, check-in, gamificação)
    ├── JourneyRepository (jornada, etapas, marcos, metas)
    ├── HabitRepository (hábitos, registros)
    ├── ProfessionalAuthMixin (autenticação profissional)
    ├── GLP1Repository (doses, sintomas, protocolo GLP-1)
    ├── BariatricRepository (cirurgia, fases bariátricas)
    ├── NotificationRepository (fila, histórico, lembretes)
    ├── ClinicalRepository (condutas, observações, prescrições)
    └── JourneyStoryRepository (motivos, fotos, conquistas, eventos)

Padrões:
- Repository Pattern: abstrai acesso a dados
- Strategy Pattern: Supabase vs MockDB
- Factory Method: criação de modelos a partir de dicts
"""
from __future__ import annotations

import copy
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Protocol, Self, runtime_checkable

import streamlit as st

import config
from core.bariatric_repository import BariatricRepository
from core.clinical_repository import ClinicalRepository
from core.database_pro_auth import ProfessionalAuthMixin
from core.database_records import RecordsMixin
from core.glp1_repository import GLP1Repository
from core.habit_repository import HabitRepository
from core.journey_repository import JourneyRepository
from core.journey_story_repository import JourneyStoryRepository
from core.models import (
    ActivityLevel,
    Gender,
    Goal,
    HealthMode,
    Plan,
    Professional,
    User,
)
from core.notification_repository import NotificationRepository
from core.security import hash_password, verify_password

logger = logging.getLogger("Melshape.Database")

# ─────────────────────────────────────────────────────────────────────────────
# PROTOCOLS (Interfaces)
# ─────────────────────────────────────────────────────────────────────────────

@runtime_checkable
class DatabaseProtocol(Protocol):
    """
    Protocol para operações de banco de dados.
    
    Define o contrato que qualquer implementação de banco deve seguir.
    Permite trocar entre Supabase e MockDB transparentemente.
    """
    
    @property
    def is_real(self) -> bool:
        """True se conectado ao Supabase, False se MockDB."""
        ...
    
    def uid(self) -> str:
        """Retorna o ID do usuário logado."""
        ...
    
    def get_user(self, email: str, password: str) -> User | None:
        """Autentica um paciente."""
        ...
    
    def create_user(
        self,
        email: str,
        password: str,
        name: str,
        gender: Gender = Gender.FEMALE,
    ) -> User | None:
        """Cria um novo paciente e retorna o objeto criado."""
        ...
    
    def update_user(self, data: dict[str, Any]) -> bool:
        """Atualiza dados do usuário logado."""
        ...
    
    def delete_user(self, email: str) -> bool:
        """Remove um paciente (LGPD)."""
        ...
    
    def reset_password(self, email: str, new_password: str) -> bool:
        """Define uma nova senha para o usuário."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# MOCKDB (Classe Separada)
# ─────────────────────────────────────────────────────────────────────────────

class MockDB:
    """
    Banco de dados em memória para desenvolvimento/demo.
    
    Armazena dados no session_state do Streamlit.
    Não persiste entre sessões ou reinicializações.
    
    Attributes:
        _data: Dicionário com todos os dados mock
    """
    
    DEFAULTS: dict[str, Any] = {
        "users": {},
        "professionals": {},
        "meals": [],
        "weights": [],
        "supplements": [],
        "workouts": [],
        "achievements": [],
        "hydration": [],
        "symptoms": [],
        "sleep": [],
        "cycles": [],
        "checkins": [],
        "jornadas": [],
        "habitos": [],
        "doses_glp1": [],
        "sintomas_glp1": [],
        "cirurgias": {},
        "fases_bariatricas": {},
        "fila_notificacoes": {},
        "condutas_clinicas": {},
        "observacoes_profissionais": {},
        "prescricoes_alimentares": {},
        "fotos_evolucao": {},
        "eventos_vida": {},
        "motivos_jornada": {},
    }
    
    def __init__(self) -> None:
        """Inicializa o MockDB no session_state."""
        if "mock_db" not in st.session_state:
            st.session_state.mock_db = copy.deepcopy(self.DEFAULTS)
            logger.info("✅ MockDB inicializado")
    
    @property
    def data(self) -> dict[str, Any]:
        """Retorna o dicionário de dados."""
        return st.session_state.mock_db
    
    def get_collection(self, name: str) -> Any:
        """Retorna uma coleção específica."""
        return self.data.get(name, {} if name.endswith("s") and not name.endswith("ss") else [])
    
    def clear(self) -> None:
        """Limpa todos os dados (útil para testes)."""
        st.session_state.mock_db = copy.deepcopy(self.DEFAULTS)
        logger.info("🗑️ MockDB limpo")


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE (CLASSE PRINCIPAL)
# ─────────────────────────────────────────────────────────────────────────────

class Database(
    RecordsMixin,
    JourneyRepository,
    HabitRepository,
    ProfessionalAuthMixin,
    GLP1Repository,
    BariatricRepository,
    NotificationRepository,
    ClinicalRepository,
    JourneyStoryRepository,
):
    """
    Abstração de banco de dados: Supabase → MockDB automático.
    
    Herda todos os mixins para fornecer uma interface unificada.
    Em produção, conecta ao Supabase. Em desenvolvimento, usa MockDB.
    
    Attributes:
        is_real: True se conectado ao Supabase
        client: Cliente Supabase (ou None)
        _mock_db: Instância do MockDB
        
    Example:
        >>> db = Database()
        >>> user = db.get_user("user@example.com", "password")
        >>> if user:
        ...     print(f"Bem-vindo, {user.name}!")
    """
    
    def __init__(self) -> None:
        """Inicializa conexão com Supabase ou MockDB."""
        self.is_real: bool = False
        self.client: Any = None
        self._mock_db: MockDB = MockDB()
        
        # Tenta conectar ao Supabase
        self._connect_supabase()
    
    def _connect_supabase(self) -> None:
        """Tenta conectar ao Supabase com health check."""
        try:
            # Verifica se as credenciais existem
            if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
                logger.info("ℹ️ Secrets Supabase não encontrados — usando MockDB")
                return
            
            # Importa e cria cliente
            from supabase import create_client
            
            self.client = create_client(
                st.secrets["SUPABASE_URL"],
                st.secrets["SUPABASE_KEY"]
            )
            
            # Health check: tenta uma operação simples
            self.client.table("perfis").select("count", count="exact").limit(1).execute()
            
            self.is_real = True
            logger.info("✅ Supabase conectado com sucesso")
            
        except ImportError:
            logger.warning("⚠️ Supabase não instalado — usando MockDB")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao conectar Supabase: {e} — usando MockDB")
            self.is_real = False
            self.client = None
    
    @property
    def mock(self) -> dict[str, Any]:
        """Retorna o dicionário MockDB (compatibilidade)."""
        return self._mock_db.data
    
    # ─────────────────────────────────────────────────────────────────────────
    # UID (User ID)
    # ─────────────────────────────────────────────────────────────────────────
    
    def uid(self) -> str:
        """
        Retorna o ID do usuário logado.
        
        Para Supabase: busca perfil_id do session_state ou auth.
        Para MockDB: retorna email do usuário.
        
        Returns:
            ID do usuário (perfil_id ou email)
            
        Example:
            >>> user_id = db.uid()
            >>> print(f"User ID: {user_id}")
        """
        # 1. Verifica se já temos o perfil_id em cache
        cached_pid = st.session_state.get("perfil_id")
        if cached_pid:
            return cached_pid
        
        # 2. Para Supabase: busca via auth
        if self.is_real and self.client:
            try:
                # Busca usuário autenticado
                auth_response = self.client.auth.get_user()
                
                if auth_response and auth_response.user:
                    user_id = auth_response.user.id
                    
                    # Busca perfil no banco
                    profile_response = (
                        self.client.table("perfis")
                        .select("id")
                        .eq("usuario_id", user_id)
                        .single()
                        .execute()
                    )
                    
                    if profile_response.data:
                        profile_id = profile_response.data["id"]
                        st.session_state["perfil_id"] = profile_id
                        logger.debug(f"UID resolvido via Supabase: {profile_id}")
                        return profile_id
                        
            except Exception as e:
                logger.debug(f"uid() Supabase fallback: {e}")
        
        # 3. Fallback: email do usuário no session_state
        user = st.session_state.get("user")
        if user and isinstance(user, dict):
            email = user.get("email", "anon")
            logger.debug(f"UID resolvido via session_state: {email}")
            return email
        
        logger.debug("UID não encontrado, retornando 'anon'")
        return "anon"
    
    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS DE FILTRO
    # ─────────────────────────────────────────────────────────────────────────
    
    def _filter_user(self, items: list[dict], uid: str) -> list[dict]:
        """
        Filtra lista por user_id.
        
        Args:
            items: Lista de dicionários
            uid: ID do usuário
            
        Returns:
            Lista filtrada
        """
        return [item for item in items if item.get("user_id") == uid]
    
    def _filter_days(
        self,
        items: list[dict],
        days: int | None,
        date_field: str = "log_date",
    ) -> list[dict]:
        """
        Filtra lista por dias recentes.
        
        Args:
            items: Lista de dicionários
            days: Número de dias (None = sem filtro)
            date_field: Nome do campo de data
            
        Returns:
            Lista filtrada
            
        Example:
            >>> meals = db._filter_days(all_meals, days=7)
            >>> # Retorna apenas refeições dos últimos 7 dias
        """
        if not days:
            return items
        
        cutoff = date.today() - timedelta(days=days)
        result = []
        
        for item in items:
            try:
                date_str = item.get(date_field, "2000-01-01")
                item_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                if item_date >= cutoff:
                    result.append(item)
            except (ValueError, TypeError) as e:
                logger.debug(f"Erro ao filtrar data: {e}")
                continue
        
        return result
    
    def _make_model(self, cls: type, row: dict[str, Any]) -> Any:
        """
        Cria uma instância de modelo a partir de um dicionário.
        
        Filtra apenas campos que existem no modelo.
        
        Args:
            cls: Classe do modelo (dataclass)
            row: Dicionário com dados
            
        Returns:
            Instância do modelo
            
        Example:
            >>> user = db._make_model(User, {"email": "user@example.com", "name": "João"})
        """
        import dataclasses
        
        # Obtém campos válidos da dataclass
        if dataclasses.is_dataclass(cls):
            valid_fields = {f.name for f in dataclasses.fields(cls)}
            filtered_data = {k: v for k, v in row.items() if k in valid_fields}
            
            # Usa from_dict se disponível
            if hasattr(cls, "from_dict"):
                return cls.from_dict(filtered_data)
            
            return cls(**filtered_data)
        
        # Fallback para classes não-dataclass
        return cls(**row)
    
    # ─────────────────────────────────────────────────────────────────────────
    # AUTENTICAÇÃO
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_user(self, email: str, password: str) -> User | None:
        """
        Autentica um paciente.
        
        Args:
            email: Email do usuário
            password: Senha em texto puro
            
        Returns:
            User se autenticado, None caso contrário
            
        Example:
            >>> user = db.get_user("user@example.com", "password123")
            >>> if user:
            ...     print(f"Bem-vindo, {user.name}!")
            ... else:
            ...     print("Credenciais inválidas")
        """
        email_lower = email.lower().strip()
        
        # 1. Tenta Supabase
        if self.is_real and self.client:
            try:
                # Autentica no Supabase Auth
                auth_response = self.client.auth.sign_in_with_password({
                    "email": email_lower,
                    "password": password,
                })
                
                if auth_response.user:
                    # Busca perfil completo
                    profile_response = (
                        self.client.table("perfis")
                        .select("*")
                        .eq("usuario_id", auth_response.user.id)
                        .single()
                        .execute()
                    )
                    
                    profile_data = profile_response.data or {}
                    
                    # Cache do perfil_id
                    st.session_state["perfil_id"] = profile_data.get("id", "")
                    
                    # Constrói objeto User
                    user = self._build_user_from_supabase(email_lower, profile_data)
                    
                    logger.info(f"✅ Login Supabase: {email_lower}")
                    return user
                    
            except Exception as e:
                logger.warning(f"Login Supabase falhou: {e}")
        
        # 2. Fallback MockDB
        mock_user_data = self.mock["users"].get(email_lower)
        
        if mock_user_data:
            # Verifica senha
            stored_hash = mock_user_data.get("password_hash", "")
            
            if verify_password(password, stored_hash):
                user = User.from_dict(mock_user_data)
                logger.info(f"✅ Login MockDB: {email_lower}")
                return user
        
        logger.warning(f"❌ Login falhou: {email_lower}")
        return None
    
    def _build_user_from_supabase(self, email: str, profile: dict[str, Any]) -> User:
        """
        Constrói objeto User a partir de dados do Supabase.
        
        Args:
            email: Email do usuário
            profile: Dados do perfil
            
        Returns:
            Instância de User
        """
        # Determina plano baseado em trial_end
        plan = Plan.TRIAL if profile.get("trial_end") else Plan.FREE
        
        # Converte strings para Enums
        try:
            gender = Gender(profile.get("genero", "female"))
            health_mode = HealthMode(profile.get("tipo_jornada", "general"))
            activity_level = ActivityLevel(profile.get("nivel_atividade", "moderate"))
            goal = Goal(profile.get("objetivo", "lose"))
        except ValueError as e:
            logger.warning(f"Erro ao converter Enums: {e}")
            gender = Gender.FEMALE
            health_mode = HealthMode.GENERAL
            activity_level = ActivityLevel.MODERATE
            goal = Goal.LOSE
        
        # Converte timestamp
        created_at_str = profile.get("criado_em")
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str)
            except ValueError:
                created_at = datetime.now(timezone.utc)
        else:
            created_at = datetime.now(timezone.utc)
        
        return User(
            email=email,
            name=profile.get("nome_completo", email.split("@")[0]),
            password_hash="",  # Não armazenamos no cliente
            plan=plan,
            gender=gender,
            health_mode=health_mode,
            current_weight=profile.get("peso_atual"),
            goal_weight=profile.get("peso_desejado"),
            height=profile.get("altura"),
            age=profile.get("idade"),
            activity_level=activity_level,
            goal=goal,
            onboarding_done=profile.get("onboarding_concluido", False),
            dark_mode=profile.get("dark_mode", False),
            trial_end=profile.get("trial_end"),
            professional_id=profile.get("profissional_id"),
            created_at=created_at,
        )
    
    def create_user(
        self,
        email: str,
        password: str,
        name: str,
        gender: Gender = Gender.FEMALE,
    ) -> User | None:
        """
        Cria um novo paciente e retorna o objeto criado.
        
        Args:
            email: Email do usuário
            password: Senha em texto puro
            name: Nome completo
            gender: Gênero
            
        Returns:
            User criado ou None se já existe
            
        Example:
            >>> user = db.create_user("new@example.com", "password123", "Maria")
            >>> if user:
            ...     print(f"Usuário criado: {user.email}")
            ... else:
            ...     print("Email já cadastrado")
        """
        email_lower = email.lower().strip()
        
        # 1. Tenta Supabase
        if self.is_real and self.client:
            try:
                # Cria usuário no Supabase Auth
                auth_response = self.client.auth.sign_up({
                    "email": email_lower,
                    "password": password,
                    "options": {"data": {"name": name}},
                })
                
                if auth_response.user:
                    # Calcula trial_end
                    trial_end = (
                        datetime.now(timezone.utc) + timedelta(days=config.TRIAL_DAYS)
                    ).isoformat()
                    
                    # Cria perfil
                    self.client.table("perfis").insert({
                        "usuario_id": auth_response.user.id,
                        "nome_completo": name,
                        "genero": gender.value,
                        "onboarding_concluido": False,
                        "tipo_jornada": "general",
                        "trial_end": trial_end,
                    }).execute()
                    
                    # Busca perfil criado
                    profile_response = (
                        self.client.table("perfis")
                        .select("*")
                        .eq("usuario_id", auth_response.user.id)
                        .single()
                        .execute()
                    )
                    
                    user = self._build_user_from_supabase(
                        email_lower,
                        profile_response.data or {}
                    )
                    
                    logger.info(f"✅ Usuário criado no Supabase: {email_lower}")
                    return user
                    
            except Exception as e:
                logger.warning(f"Cadastro Supabase falhou: {e}")
        
        # 2. Fallback MockDB
        if email_lower in self.mock["users"]:
            logger.warning(f"❌ Email já existe: {email_lower}")
            return None
        
        # Cria usuário mock
        user = User.create_trial_user(
            email=email_lower,
            name=name,
            password_hash=hash_password(password),
            gender=gender,
        )
        
        self.mock["users"][email_lower] = user.to_dict()
        
        logger.info(f"✅ Usuário criado no MockDB: {email_lower}")
        return user
    
    def update_user(self, data: dict[str, Any]) -> bool:
        """
        Atualiza dados do usuário logado.
        
        Args:
            data: Dicionário com campos a atualizar
            
        Returns:
            True se atualizado com sucesso
            
        Example:
            >>> success = db.update_user({"name": "Novo Nome", "current_weight": 75.0})
            >>> if success:
            ...     print("Dados atualizados!")
        """
        uid = self.uid()
        
        # Mapeamento de campos Python → Supabase
        field_map = {
            "name": "nome_completo",
            "health_mode": "tipo_jornada",
            "current_weight": "peso_atual",
            "goal_weight": "peso_desejado",
            "height": "altura",
            "age": "idade",
            "gender": "genero",
            "activity_level": "nivel_atividade",
            "goal": "objetivo",
            "dark_mode": "dark_mode",
            "onboarding_done": "onboarding_concluido",
            "professional_id": "profissional_id",
        }
        
        # 1. Tenta Supabase
        if self.is_real and self.client:
            try:
                # Converte campos para formato do Supabase
                payload = {}
                for key, value in data.items():
                    # Converte Enum para string
                    if hasattr(value, "value"):
                        value = value.value
                    
                    # Mapeia nome do campo
                    db_field = field_map.get(key, key)
                    payload[db_field] = value
                
                # Atualiza no banco
                self.client.table("perfis").update(payload).eq("id", uid).execute()
                
                logger.info(f"✅ Usuário atualizado no Supabase: {uid}")
                return True
                
            except Exception as e:
                logger.warning(f"update_user Supabase falhou: {e}")
        
        # 2. Fallback MockDB
        user_dict = st.session_state.get("user")
        
        if user_dict and isinstance(user_dict, dict):
            email = user_dict.get("email")
            
            if email:
                email_lower = email.lower()
                mock_user = self.mock["users"].get(email_lower)
                
                if mock_user is not None:
                    # Atualiza MockDB
                    mock_user.update(data)
                    
                    # Atualiza session_state
                    user_dict.update(data)
                    st.session_state.user = user_dict
                    
                    logger.info(f"✅ Usuário atualizado no MockDB: {email_lower}")
                    return True
        
        logger.warning(f"❌ Falha ao atualizar usuário: {uid}")
        return False
    
    def delete_user(self, email: str) -> bool:
        """
        Remove um paciente (LGPD — direito de exclusão).
        
        Args:
            email: Email do usuário a ser removido
            
        Returns:
            True se removido com sucesso
            
        Example:
            >>> success = db.delete_user("user@example.com")
            >>> if success:
            ...     print("Usuário removido conforme LGPD")
        """
        email_lower = email.lower().strip()
        
        # 1. Tenta Supabase
        if self.is_real and self.client:
            try:
                # Remove perfil
                self.client.table("perfis").delete().eq("email", email_lower).execute()
                
                # Nota: Em produção, também remover do Supabase Auth
                # Requer service_role key ou Edge Function
                
                logger.info(f"✅ Usuário removido do Supabase: {email_lower}")
                return True
                
            except Exception as e:
                logger.warning(f"delete_user Supabase falhou: {e}")
        
        # 2. Fallback MockDB
        if email_lower in self.mock["users"]:
            del self.mock["users"][email_lower]
            logger.info(f"✅ Usuário removido do MockDB: {email_lower}")
            return True
        
        logger.warning(f"❌ Usuário não encontrado: {email_lower}")
        return True  # Retorna True mesmo se não existir (idempotente)
    
    def reset_password(self, email: str, new_password: str) -> bool:
        """
        Define uma nova senha para o usuário.
        
        Args:
            email: Email do usuário
            new_password: Nova senha (já validada)
            
        Returns:
            True se alterada com sucesso
            
        Example:
            >>> success = db.reset_password("user@example.com", "newpassword123")
            >>> if success:
            ...     print("Senha alterada com sucesso!")
        """
        email_lower = email.lower().strip()
        
        # 1. Tenta Supabase
        if self.is_real and self.client:
            try:
                # Nota: Supabase requer permissão service_role para atualizar senha
                # Em produção, use Edge Function com service_role key
                self.client.auth.update_user({"password": new_password})
                
                logger.info(f"✅ Senha resetada no Supabase: {email_lower}")
                return True
                
            except Exception as e:
                logger.warning(f"reset_password Supabase falhou: {e}")
        
        # 2. Fallback MockDB
        mock_user = self.mock["users"].get(email_lower)
        
        if mock_user:
            mock_user["password_hash"] = hash_password(new_password)
            logger.info(f"✅ Senha resetada no MockDB: {email_lower}")
            return True
        
        logger.warning(f"❌ Usuário não encontrado para reset: {email_lower}")
        return False
    
    # ─────────────────────────────────────────────────────────────────────────
    # UTILITÁRIOS
    # ─────────────────────────────────────────────────────────────────────────
    
    def health_check(self) -> bool:
        """
        Verifica se o banco de dados está saudável.
        
        Returns:
            True se saudável, False caso contrário
            
        Example:
            >>> if db.health_check():
            ...     print("Banco de dados OK")
            ... else:
            ...     print("Problemas com o banco")
        """
        if self.is_real and self.client:
            try:
                # Tenta uma operação simples
                self.client.table("perfis").select("count", count="exact").limit(1).execute()
                return True
            except Exception as e:
                logger.error(f"Health check falhou: {e}")
                return False
        
        # MockDB sempre está saudável
        return True
    
    def get_stats(self) -> dict[str, int]:
        """
        Retorna estatísticas do banco de dados.
        
        Returns:
            Dicionário com contagens
            
        Example:
            >>> stats = db.get_stats()
            >>> print(f"Usuários: {stats['users']}")
        """
        if self.is_real and self.client:
            try:
                # Busca contagens do Supabase
                users_count = (
                    self.client.table("perfis")
                    .select("count", count="exact")
                    .execute()
                )
                
                return {
                    "users": users_count.count or 0,
                    "type": "supabase",
                }
            except Exception as e:
                logger.warning(f"get_stats falhou: {e}")
        
        # MockDB
        return {
            "users": len(self.mock["users"]),
            "professionals": len(self.mock["professionals"]),
            "meals": len(self.mock["meals"]),
            "type": "mockdb",
        }


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTS PÚBLICOS
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    "Database",
    "DatabaseProtocol",
    "MockDB",
]
