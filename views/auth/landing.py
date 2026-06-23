"""
Melshape — Tela Inicial (Landing).

Primeira impressão do produto. Deve responder em 5 segundos:
"O que é isso e por que devo me cadastrar?"

Arquitetura:
    Landing
    ├── Data Models (Pilar, Destaque)
    ├── Demo Manager (gerencia usuário demo)
    ├── Components
    │   ├── render_card() (card reutilizável)
    │   └── render_button_group() (grupo de botões)
    ├── Sections
    │   ├── HeroSection
    │   ├── PilaresSection
    │   ├── CTASection
    │   ├── HighlightsSection
    │   └── FooterSection
    └── Main Render

Princípios:
- Clareza: mensagem única e direta
- Conversão: CTAs claros e visíveis
- Confiança: demonstra valor sem sobrecarregar
- Responsividade: adapta-se a diferentes telas
- Tipagem forte: dataclasses, Protocol, type hints completos
- Reutilização: componentes HTML extraídos
- Design System: usa classes CSS em vez de inline
- Logging: todas as operações são logadas
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

import streamlit as st

import config
from core.database import Database

logger = logging.getLogger("Melshape.Landing")


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Pilar:
    """Representa um pilar de jornada."""
    icon: str
    title: str
    description: str
    mode: str  # general, fitness, bariatric, glp1


@dataclass(frozen=True)
class Destaque:
    """Representa um diferencial do produto."""
    icon: str
    title: str
    description: str


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

_PILARES: tuple[Pilar, ...] = (
    Pilar("⚖️", "Emagrecimento", "Hábitos reais, não restrições", "general"),
    Pilar("💪", "Fitness", "Proteína, treino e consistência", "fitness"),
    Pilar("🔪", "Pós-Bariátrica", "Fases, suplementação e exames", "bariatric"),
    Pilar("💉", "GLP-1", "Dose, adesão e sintomas", "glp1"),
)

_DESTAQUES: tuple[Destaque, ...] = (
    Destaque("✅", "Check-in diário", "30 segundos. Mantém sua sequência ativa."),
    Destaque("📊", "Score de transformação", "Não é caloria. É consistência medida."),
    Destaque("👨‍⚕️", "Profissional integrado", "Seu nutricionista vê tudo em tempo real."),
    Destaque("🔔", "Anti-abandono", "O sistema busca você quando você some."),
)


# ─────────────────────────────────────────────────────────────────────────────
# PROTOCOLS
# ─────────────────────────────────────────────────────────────────────────────

class ServicesDict(Protocol):
    """Protocol para dicionário de serviços."""
    def __getitem__(self, key: str) -> Any: ...


# ─────────────────────────────────────────────────────────────────────────────
# DEMO MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class DemoManager:
    """Gerencia o usuário demo."""
    
    @staticmethod
    def ensure_demo_user(db: Database) -> bool:
        """
        Garante que o usuário demo existe e está configurado.
        
        Args:
            db: Instância do Database
        
        Returns:
            True se o usuário demo está pronto para login
        """
        try:
            # Verifica se já existe
            user = db.get_user(config.DEMO_EMAIL, config.DEMO_PASSWORD)
            if user:
                logger.debug("✅ Usuário demo já existe")
                return True
            
            # Cria usuário demo
            logger.info("🔄 Criando usuário demo...")
            ok = db.create_user(
                config.DEMO_EMAIL,
                config.DEMO_PASSWORD,
                "Visitante Demo",
                gender="female",
            )
            
            if not ok:
                logger.error("❌ Falha ao criar usuário demo")
                return False
            
            # Busca usuário criado
            user = db.get_user(config.DEMO_EMAIL, config.DEMO_PASSWORD)
            if not user:
                logger.error("❌ Usuário demo não encontrado após criação")
                return False
            
            # Configura session state
            st.session_state.user = DemoManager._user_to_dict(user)
            
            # Atualiza perfil do usuário
            DemoManager._setup_demo_profile(db)
            
            logger.info("✅ Usuário demo configurado com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao garantir usuário demo: {e}", exc_info=True)
            return False
    
    @staticmethod
    def _user_to_dict(user: Any) -> dict[str, Any]:
        """Converte usuário para dicionário."""
        if hasattr(user, "to_dict"):
            return user.to_dict()
        if isinstance(user, dict):
            return user
        return {"id": str(user)}
    
    @staticmethod
    def _setup_demo_profile(db: Database) -> None:
        """Configura perfil do usuário demo."""
        db.update_user({
            "onboarding_done": True,
            "health_mode": "general",
            "current_weight": 78.0,
            "goal_weight": 70.0,
            "height": 165,
            "age": 32,
            "activity_level": "moderate",
            "goal": "lose",
        })
    
    @staticmethod
    def login_demo_user(db: Database) -> bool:
        """
        Faz login do usuário demo.
        
        Args:
            db: Instância do Database
        
        Returns:
            True se login foi bem-sucedido
        """
        try:
            if not st.session_state.get("user"):
                user = db.get_user(config.DEMO_EMAIL, config.DEMO_PASSWORD)
                if user:
                    st.session_state.user = DemoManager._user_to_dict(user)
                    return True
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao fazer login demo: {e}", exc_info=True)
            return False


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENTS
# ─────────────────────────────────────────────────────────────────────────────

def render_card(icon: str, title: str, description: str, css_class: str = "feature-card") -> None:
    """
    Renderiza um card reutilizável.
    
    Args:
        icon: Ícone (emoji)
        title: Título do card
        description: Descrição
        css_class: Classe CSS (padrão: feature-card)
    """
    st.markdown(
        f"""
        <div class="{css_class}">
            <div class="icon">{icon}</div>
            <h3>{title}</h3>
            <p>{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_highlight(icon: str, title: str, description: str) -> None:
    """
    Renderiza um destaque (card menor).
    
    Args:
        icon: Ícone (emoji)
        title: Título
        description: Descrição
    """
    st.markdown(
        f"""
        <div class="text-center p-sm">
            <div class="text-xl">{icon}</div>
            <div class="font-bold text-base mt-sm">{title}</div>
            <div class="text-sm text-muted">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SECTIONS
# ─────────────────────────────────────────────────────────────────────────────

class HeroSection:
    """Seção Hero (título e tagline)."""
    
    @staticmethod
    def render() -> None:
        """Renderiza a seção Hero."""
        st.markdown(
            f"""
            <div class="text-center py-2xl px-md">
                <div class="text-3xl">🔥</div>
                <h1 class="text-2xl font-extrabold mt-sm">
                    {config.APP_NAME}
                </h1>
                <p class="text-lg text-muted">
                    {config.APP_TAGLINE}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )


class PilaresSection:
    """Seção de pilares de jornada."""
    
    @staticmethod
    def render() -> None:
        """Renderiza a seção de pilares."""
        cols = st.columns(4)
        for col, pilar in zip(cols, _PILARES):
            with col:
                render_card(pilar.icon, pilar.title, pilar.description)


class CTASection:
    """Seção de Call to Action."""
    
    @staticmethod
    def render(db: Database) -> None:
        """
        Renderiza a seção de CTAs.
        
        Args:
            db: Instância do Database
        """
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            CTASection._render_primary_cta()
            CTASection._render_secondary_ctas()
            CTASection._render_tertiary_ctas(db)
    
    @staticmethod
    def _render_primary_cta() -> None:
        """Renderiza CTA principal."""
        if st.button(
            f"🚀 Começar grátis — {config.PRICING.trial_days} dias de trial",
            type="primary",
            use_container_width=True,
            key="landing_register",
        ):
            st.session_state.page = "register"
            st.rerun()
    
    @staticmethod
    def _render_secondary_ctas() -> None:
        """Renderiza CTAs secundários."""
        st.markdown(
            """
            <div class="text-center my-sm text-sm text-muted">
                Já tem conta?
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        if st.button(
            "Entrar",
            use_container_width=True,
            key="landing_login",
        ):
            st.session_state.page = "login"
            st.rerun()
        
        st.markdown(
            """
            <div class="text-center my-sm text-xs text-faint">
                ou
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    @staticmethod
    def _render_tertiary_ctas(db: Database) -> None:
        """Renderiza CTAs terciários (demo e profissional)."""
        col_demo, col_pro = st.columns(2)
        
        with col_demo:
            if st.button("🎮 Ver demo", use_container_width=True, key="landing_demo"):
                CTASection._handle_demo_click(db)
        
        with col_pro:
            if st.button("🏥 Sou profissional", use_container_width=True, key="landing_pro"):
                st.session_state.page = "register_pro"
                st.rerun()
    
    @staticmethod
    def _handle_demo_click(db: Database) -> None:
        """Handle click no botão demo."""
        if DemoManager.ensure_demo_user(db) and DemoManager.login_demo_user(db):
            st.session_state.page = "home"
            st.rerun()
        else:
            st.error("Não foi possível carregar a demo agora.")


class HighlightsSection:
    """Seção de destaques."""
    
    @staticmethod
    def render() -> None:
        """Renderiza a seção de destaques."""
        st.markdown("<br>", unsafe_allow_html=True)
        
        cols = st.columns(4)
        for col, destaque in zip(cols, _DESTAQUES):
            with col:
                render_highlight(destaque.icon, destaque.title, destaque.description)


class FooterSection:
    """Seção de rodapé."""
    
    @staticmethod
    def render() -> None:
        """Renderiza o rodapé."""
        st.markdown(
            f"""
            <div class="text-center mt-xl text-xs text-faint">
                v{config.APP_VERSION} · Sem cartão · Cancele quando quiser
            </div>
            """,
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN RENDER
# ─────────────────────────────────────────────────────────────────────────────

def render(services: ServicesDict) -> None:
    """
    Renderiza a landing page completa.
    
    Args:
        services: Dicionário de serviços
    """
    logger.debug("🔄 Renderizando landing page")
    
    try:
        HeroSection.render()
        PilaresSection.render()
        CTASection.render(services["db"])
        HighlightsSection.render()
        FooterSection.render()
    except Exception as e:
        logger.error(f"❌ Erro ao renderizar landing: {e}", exc_info=True)
        st.error("Ocorreu um erro ao carregar a página. Por favor, recarregue.")


__all__ = ["render"]
