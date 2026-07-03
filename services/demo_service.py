"""
Melshape — Demo Service.

Gerencia a criação e configuração do usuário demo.
Reutilizável em múltiplas views (landing, onboarding, etc.).

Princípios:
- Single Responsibility: apenas gerencia demo user
- Reutilizável: pode ser chamado de qualquer view
- Tipagem forte: Protocol, dataclasses, type hints completos
- Logging: todas as operações são logadas
- Tratamento de erros: nunca quebra a aplicação

Example:
    >>> from services.demo_service import DemoService
    >>> demo = DemoService(db)
    >>> if demo.ensure_demo_user():
    ...     demo.login_demo_user()
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

import streamlit as st

import config
from core.database import Database

logger = logging.getLogger("Melshape.DemoService")


# ─────────────────────────────────────────────────────────────────────────────
# PROTOCOLS
# ─────────────────────────────────────────────────────────────────────────────

class UserLike(Protocol):
    """Protocol para objeto de usuário (dataclass ou dict)."""
    
    def to_dict(self) -> dict[str, Any]: ...


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DemoConfig:
    """Configuração do perfil demo."""
    
    email: str
    password: str
    name: str
    gender: str
    onboarding_done: bool
    health_mode: str
    current_weight: float
    goal_weight: float
    height: int
    age: int
    activity_level: str
    goal: str
    
    @classmethod
    def default(cls) -> DemoConfig:
        """Retorna configuração demo padrão."""
        return cls(
            email=config.DEMO_EMAIL,
            password=config.DEMO_PASSWORD,
            name="Visitante Demo",
            gender="female",
            onboarding_done=True,
            health_mode="general",
            current_weight=78.0,
            goal_weight=70.0,
            height=165,
            age=32,
            activity_level="moderate",
            goal="lose",
        )


# ─────────────────────────────────────────────────────────────────────────────
# DEMO SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class DemoService:
    """
    Serviço para gerenciar usuário demo.
    
    Attributes:
        db: Instância do Database
        config: Configuração do demo
    
    Example:
        >>> demo_service = DemoService(db)
        >>> if demo_service.ensure_demo_user():
        ...     print("Demo user pronto!")
    """
    
    def __init__(self, db: Database, demo_config: DemoConfig | None = None) -> None:
        """
        Inicializa o DemoService.
        
        Args:
            db: Instância do Database
            demo_config: Configuração do demo (opcional, usa padrão se None)
        """
        self.db = db
        self.config = demo_config or DemoConfig.default()
        logger.debug("✅ DemoService inicializado")
    
    def ensure_demo_user(self) -> bool:
        """
        Garante que o usuário demo existe e está configurado.
        
        Se o usuário não existir, cria e configura.
        Se já existir, apenas retorna True.
        
        Returns:
            True se o usuário demo está pronto para login, False caso contrário
        
        Example:
            >>> if demo.ensure_demo_user():
            ...     demo.login_demo_user()
        """
        try:
            # Verifica se já existe
            user = self.db.get_user(self.config.email, self.config.password)
            if user:
                logger.debug("✅ Usuário demo já existe")
                return True
            
            # Cria usuário demo
            logger.info("🔄 Criando usuário demo...")
            created = self.db.create_user(
                self.config.email,
                self.config.password,
                self.config.name,
                gender=self.config.gender,
            )
            
            if not created:
                logger.error("❌ Falha ao criar usuário demo")
                return False
            
            # Busca usuário criado
            user = self.db.get_user(self.config.email, self.config.password)
            if not user:
                logger.error("❌ Usuário demo não encontrado após criação")
                return False
            
            # Configura perfil do usuário
            self._setup_demo_profile()
            
            logger.info("✅ Usuário demo configurado com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao garantir usuário demo: {e}", exc_info=True)
            return False
    
    def login_demo_user(self) -> bool:
        """
        Faz login do usuário demo na sessão.
        
        Returns:
            True se login foi bem-sucedido, False caso contrário
        
        Example:
            >>> if demo.login_demo_user():
            ...     st.session_state.page = "home"
            ...     st.rerun()
        """
        try:
            if st.session_state.get("user"):
                logger.debug("✅ Usuário já logado na sessão")
                return True
            
            user = self.db.get_user(self.config.email, self.config.password)
            if not user:
                logger.error("❌ Usuário demo não encontrado para login")
                return False
            
            st.session_state.user = self._user_to_dict(user)
            logger.info("✅ Login demo realizado com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao fazer login demo: {e}", exc_info=True)
            return False
    
    def _setup_demo_profile(self) -> None:
        """
        Configura o perfil do usuário demo.
        
        Atualiza dados como peso, altura, idade, modo de saúde, etc.
        """
        try:
            self.db.update_user({
                "onboarding_done": self.config.onboarding_done,
                "health_mode": self.config.health_mode,
                "current_weight": self.config.current_weight,
                "goal_weight": self.config.goal_weight,
                "height": self.config.height,
                "age": self.config.age,
                "activity_level": self.config.activity_level,
                "goal": self.config.goal,
            })
            logger.debug("✅ Perfil demo configurado")
        except Exception as e:
            logger.error(f"❌ Erro ao configurar perfil demo: {e}", exc_info=True)
    
    def _user_to_dict(self, user: UserLike | dict[str, Any] | Any) -> dict[str, Any]:
        """
        Converte objeto de usuário para dicionário.
        
        Args:
            user: Objeto de usuário (pode ser dataclass, dict ou outro tipo)
        
        Returns:
            Dicionário com dados do usuário
        
        Example:
            >>> user_dict = demo._user_to_dict(user)
            >>> print(user_dict["email"])
        """
        if hasattr(user, "to_dict"):
            return user.to_dict()
        if isinstance(user, dict):
            return user
        return {"id": str(user)}


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTS
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    "DemoService",
    "DemoConfig",
    "UserLike",
]
