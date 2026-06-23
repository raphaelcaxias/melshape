"""
Melshape — Tela Inicial (Landing Page).

Primeira impressão do produto. Deve responder em 5 segundos:
"O que é isso e por que devo me cadastrar?"

Arquitetura:
    Landing Page
    ├── Data Models (Pilar, Destaque)
    ├── Components (render_card, render_highlight)
    ├── Sections
    │   ├── HeroSection (título e tagline)
    │   ├── PilaresSection (4 pilares de jornada)
    │   ├── CTASection (botões de ação)
    │   ├── HighlightsSection (4 diferenciais)
    │   └── FooterSection (versão e disclaimer)
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
from services.demo_service import DemoService

logger = logging.getLogger("Melshape.Landing")


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Pilar:
    """
    Representa um pilar de jornada.
    
    Attributes:
        icon: Ícone visual (emoji)
        title: Título do pilar
        description: Descrição curta
        mode: Modo de saúde (general, fitness, bariatric, glp1)
    
    Example:
        >>> pilar = Pilar("⚖️", "Emagrecimento", "Hábitos reais", "general")
        >>> print(pilar.title)
        'Emagrecimento'
    """
    icon: str
    title: str
    description: str
    mode: str


@dataclass(frozen=True)
class Destaque:
    """
    Representa um diferencial do produto.
    
    Attributes:
        icon: Ícone visual (emoji)
        title: Título do destaque
        description: Descrição curta
    
    Example:
        >>> destaque = Destaque("✅", "Check-in diário", "30 segundos")
        >>> print(destaque.title)
        'Check-in diário'
    """
    icon: str
    title: str
    description: str


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

_PILARES: tuple[Pilar, ...] = (
    Pilar(
        icon="⚖️",
        title="Emagrecimento",
        description="Hábitos reais, não restrições",
        mode="general",
    ),
    Pilar(
        icon="💪",
        title="Fitness",
        description="Proteína, treino e consistência",
        mode="fitness",
    ),
    Pilar(
        icon="🔪",
        title="Pós-Bariátrica",
        description="Fases, suplementação e exames",
        mode="bariatric",
    ),
    Pilar(
        icon="💉",
        title="GLP-1",
        description="Dose, adesão e sintomas",
        mode="glp1",
    ),
)

_DESTAQUES: tuple[Destaque, ...] = (
    Destaque(
        icon="✅",
        title="Check-in diário",
        description="30 segundos. Mantém sua sequência ativa.",
    ),
    Destaque(
        icon="📊",
        title="Score de transformação",
        description="Não é caloria. É consistência medida.",
    ),
    Destaque(
        icon="👨‍⚕️",
        title="Profissional integrado",
        description="Seu nutricionista vê tudo em tempo real.",
    ),
    Destaque(
        icon="🔔",
        title="Anti-abandono",
        description="O sistema busca você quando você some.",
    ),
)

# Chaves de sessão
_SESSION_KEY_USER = "user"
_SESSION_KEY_PAGE = "page"


# ─────────────────────────────────────────────────────────────────────────────
# PROTOCOLS
# ─────────────────────────────────────────────────────────────────────────────

class ServicesDict(Protocol):
    """
    Protocol para dicionário de serviços.
    
    Define a interface mínima esperada para o parâmetro services.
    """
    
    def __getitem__(self, key: str) -> Any:
        """Obtém um serviço pelo nome."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENTS
# ─────────────────────────────────────────────────────────────────────────────

def render_card(
    icon: str,
    title: str,
    description: str,
    css_class: str = "feature-card",
) -> None:
    """
    Renderiza um card reutilizável.
    
    Args:
        icon: Ícone visual (emoji)
        title: Título do card
        description: Descrição do card
        css_class: Classe CSS a ser aplicada (padrão: feature-card)
    
    Example:
        >>> render_card("⚖️", "Emagrecimento", "Hábitos reais")
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


def render_highlight(
    icon: str,
    title: str,
    description: str,
) -> None:
    """
    Renderiza um destaque (card menor para diferenciais).
    
    Args:
        icon: Ícone visual (emoji)
        title: Título do destaque
        description: Descrição do destaque
    
    Example:
        >>> render_highlight("✅", "Check-in", "30 segundos")
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
    """
    Seção Hero (título principal e tagline).
    
    Primeira coisa que o usuário vê. Deve ser clara e direta.
    """
    
    @staticmethod
    def render() -> None:
        """
        Renderiza a seção Hero.
        
        Exibe o ícone da marca, nome e tagline principal.
        
        Example:
            >>> HeroSection.render()
        """
        logger.debug("🔄 Renderizando HeroSection")
        
        st.markdown(
            f"""
            <div class="text-center py-2xl px-md">
                <div class="text-3xl">{config.APP_ICON}</div>
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
    """
    Seção de pilares de jornada.
    
    Mostra os 4 modos de saúde suportados: emagrecimento, fitness,
    pós-bariátrica e GLP-1.
    """
    
    @staticmethod
    def render() -> None:
        """
        Renderiza a seção de pilares.
        
        Exibe 4 cards lado a lado (responsivo para mobile).
        
        Example:
            >>> PilaresSection.render()
        """
        logger.debug("🔄 Renderizando PilaresSection")
        
        cols = st.columns(4)
        for col, pilar in zip(cols, _PILARES):
            with col:
                render_card(pilar.icon, pilar.title, pilar.description)


class CTASection:
    """
    Seção de Call to Action (botões de ação).
    
    Contém os botões principais: começar, entrar, ver demo, sou profissional.
    Organizada em CTAs primários, secundários e terciários.
    """
    
    @staticmethod
    def render(db: Any) -> None:
        """
        Renderiza a seção de CTAs.
        
        Args:
            db: Instância do Database
        
        Example:
            >>> CTASection.render(db)
        """
        logger.debug("🔄 Renderizando CTASection")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Layout centralizado
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            CTASection._render_primary_cta()
            CTASection._render_secondary_ctas()
            CTASection._render_tertiary_ctas(db)
    
    @staticmethod
    def _render_primary_cta() -> None:
        """
        Renderiza CTA principal (começar grátis).
        
        Botão primário com destaque visual.
        """
        trial_days = config.PRICING.trial_days
        
        if st.button(
            f"🚀 Começar grátis — {trial_days} dias de trial",
            type="primary",
            use_container_width=True,
            key="landing_register",
        ):
            logger.info("👆 CTA primário clicado: Começar grátis")
            st.session_state[_SESSION_KEY_PAGE] = "register"
            st.rerun()
    
    @staticmethod
    def _render_secondary_ctas() -> None:
        """
        Renderiza CTAs secundários (entrar).
        
        Botão secundário para usuários que já têm conta.
        """
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
            logger.info("👆 CTA secundário clicado: Entrar")
            st.session_state[_SESSION_KEY_PAGE] = "login"
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
    def _render_tertiary_ctas(db: Any) -> None:
        """
        Renderiza CTAs terciários (ver demo e sou profissional).
        
        Botões menores para opções alternativas.
        
        Args:
            db: Instância do Database
        """
        col_demo, col_pro = st.columns(2)
        
        with col_demo:
            if st.button(
                "🎮 Ver demo",
                use_container_width=True,
                key="landing_demo",
            ):
                logger.info("👆 CTA terciário clicado: Ver demo")
                CTASection._handle_demo_click(db)
        
        with col_pro:
            if st.button(
                "🏥 Sou profissional",
                use_container_width=True,
                key="landing_pro",
            ):
                logger.info("👆 CTA terciário clicado: Sou profissional")
                st.session_state[_SESSION_KEY_PAGE] = "register_pro"
                st.rerun()
    
    @staticmethod
    def _handle_demo_click(db: Any) -> None:
        """
        Handle click no botão "Ver demo".
        
        Cria usuário demo (se necessário), faz login e redireciona para home.
        
        Args:
            db: Instância do Database
        """
        demo_service = DemoService(db)
        
        if demo_service.ensure_demo_user() and demo_service.login_demo_user():
            logger.info("✅ Demo carregada com sucesso")
            st.session_state[_SESSION_KEY_PAGE] = "home"
            st.rerun()
        else:
            logger.error("❌ Falha ao carregar demo")
            st.error("Não foi possível carregar a demo agora.")


class HighlightsSection:
    """
    Seção de destaques (diferenciais do produto).
    
    Mostra 4 diferenciais que tornam o produto único.
    """
    
    @staticmethod
    def render() -> None:
        """
        Renderiza a seção de destaques.
        
        Exibe 4 destaques lado a lado (responsivo para mobile).
        
        Example:
            >>> HighlightsSection.render()
        """
        logger.debug("🔄 Renderizando HighlightsSection")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        cols = st.columns(4)
        for col, destaque in zip(cols, _DESTAQUES):
            with col:
                render_highlight(destaque.icon, destaque.title, destaque.description)


class FooterSection:
    """
    Seção de rodapé.
    
    Exibe versão do produto e informações legais.
    """
    
    @staticmethod
    def render() -> None:
        """
        Renderiza o rodapé.
        
        Exibe versão e disclaimer de cancelamento.
        
        Example:
            >>> FooterSection.render()
        """
        logger.debug("🔄 Renderizando FooterSection")
        
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
    
    Orquestra a renderização de todas as seções na ordem correta:
    1. Hero (título e tagline)
    2. Pilares (4 modos de jornada)
    3. CTAs (botões de ação)
    4. Destaques (4 diferenciais)
    5. Footer (versão e disclaimer)
    
    Args:
        services: Dicionário de serviços (deve conter "db")
    
    Example:
        >>> render({"db": db, "nutrition": nutrition_service, ...})
    
    Raises:
        Exception: Se houver erro crítico na renderização (tratado com try/except)
    """
    logger.debug("🔄 Renderizando landing page")
    
    try:
        db = services["db"]
        
        HeroSection.render()
        PilaresSection.render()
        CTASection.render(db)
        HighlightsSection.render()
        FooterSection.render()
        
        logger.debug("✅ Landing page renderizada com sucesso")
        
    except Exception as e:
        logger.error(f"❌ Erro ao renderizar landing: {e}", exc_info=True)
        st.error("Ocorreu um erro ao carregar a página. Por favor, recarregue.")


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTS
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    "render",
    "Pilar",
    "Destaque",
    "HeroSection",
    "PilaresSection",
    "CTASection",
    "HighlightsSection",
    "FooterSection",
    "render_card",
    "render_highlight",
]
