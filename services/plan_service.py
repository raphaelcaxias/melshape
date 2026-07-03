"""
Melshape — Plan Service.

Gerencia planos de assinatura, trial e paywall.
Controla acesso a funcionalidades baseado no plano do usuário.

Princípios:
- Plano efetivo: considera expiração do trial
- Feature flags: controle granular de acesso
- Paywall: exibe bloqueio para funcionalidades premium
- Trial: período de teste gratuito com contagem regressiva
- Tipagem forte: todos os métodos são tipados (Python 3.10+)
- Validação: dados são validados antes de processar
- Logging: todas as operações são logadas
- Separação: lógica de negócio separada de UI

Planos:
    - free: gratuito (funcionalidades básicas)
    - trial: período de teste (10 dias, acesso completo)
    - pro: assinatura mensal (acesso completo)
    - clinic: plano para clínicas (gestão de equipe)

Arquitetura:
    PlanService
    ├── Plano Atual
    │   ├── get_plan(user) -> str
    │   ├── trial_days_remaining(user) -> int
    │   ├── is_trial_active(user) -> bool
    │   └── is_pro(user) -> bool
    ├── Verificação de Acesso
    │   ├── can_use(user, feature) -> bool
    │   └── get_allowed_features(user) -> list[str]
    └── UI
        ├── trial_banner(user) -> None
        ├── show_paywall(feature_name, user) -> None
        └── render_plan_details(user) -> None
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import streamlit as st

import config
from core.models import User

logger = logging.getLogger("Melshape.Plan")


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DE PLANOS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Feature:
    """
    Modelo de funcionalidade do sistema.
    
    Attributes:
        name: Nome interno da feature
        display_name: Nome exibido ao usuário
        allowed_plans: Lista de planos que têm acesso
        description: Descrição da funcionalidade
    """
    name: str
    display_name: str
    allowed_plans: list[str]
    description: str = ""
    
    def is_allowed(self, plan: str) -> bool:
        """Verifica se o plano tem acesso à feature."""
        return plan in self.allowed_plans


@dataclass(frozen=True)
class PlanInfo:
    """
    Informações completas de um plano.
    
    Attributes:
        name: Nome interno do plano
        display_name: Nome exibido ao usuário
        icon: Ícone representativo
        description: Descrição do plano
        price: Preço mensal (0 para free/trial)
    """
    name: str
    display_name: str
    icon: str
    description: str
    price: float = 0.0
    
    @property
    def is_paid(self) -> bool:
        """Verifica se o plano é pago."""
        return self.price > 0


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

# Thresholds de configuração
_TRIAL_WARNING_DAYS: int = 3  # Exibe banner quando restam X dias
_DEMO_EMAIL: str = config.DEMO_EMAIL

# Features disponíveis no sistema
FEATURES: list[Feature] = [
    Feature(
        name="charts",
        display_name="Gráficos",
        allowed_plans=[config.PLAN_TRIAL, config.PLAN_PRO, config.PLAN_CLINIC],
        description="Visualização gráfica de dados"
    ),
    Feature(
        name="export",
        display_name="Exportação",
        allowed_plans=[config.PLAN_PRO, config.PLAN_CLINIC],
        description="Exportar dados em CSV/PDF"
    ),
    Feature(
        name="professional",
        display_name="Profissional",
        allowed_plans=[config.PLAN_PRO, config.PLAN_CLINIC],
        description="Acompanhamento profissional"
    ),
    Feature(
        name="evolution",
        display_name="Evolução",
        allowed_plans=[config.PLAN_TRIAL, config.PLAN_PRO, config.PLAN_CLINIC],
        description="Histórico de evolução"
    ),
    Feature(
        name="glp1",
        display_name="GLP-1",
        allowed_plans=[config.PLAN_TRIAL, config.PLAN_PRO, config.PLAN_CLINIC],
        description="Acompanhamento GLP-1"
    ),
    Feature(
        name="bariatric",
        display_name="Bariátrica",
        allowed_plans=[config.PLAN_TRIAL, config.PLAN_PRO, config.PLAN_CLINIC],
        description="Acompanhamento bariátrico"
    ),
    Feature(
        name="gamification",
        display_name="Gamificação",
        allowed_plans=[config.PLAN_TRIAL, config.PLAN_PRO, config.PLAN_CLINIC],
        description="Conquistas e níveis"
    ),
    Feature(
        name="notifications",
        display_name="Notificações",
        allowed_plans=[config.PLAN_PRO, config.PLAN_CLINIC],
        description="Notificações push e email"
    ),
    Feature(
        name="executive",
        display_name="Dashboard Executivo",
        allowed_plans=[config.PLAN_CLINIC],
        description="Dashboard para clínicas"
    ),
]

# Informações dos planos
PLANS: list[PlanInfo] = [
    PlanInfo(
        name=config.PLAN_FREE,
        display_name="Gratuito",
        icon="🔓",
        description="Funcionalidades básicas",
        price=0.0
    ),
    PlanInfo(
        name=config.PLAN_TRIAL,
        display_name="Trial",
        icon="✨",
        description=f"{config.TRIAL_DAYS} dias de acesso completo",
        price=0.0
    ),
    PlanInfo(
        name=config.PLAN_PRO,
        display_name="Pro",
        icon="🚀",
        description="Acesso completo",
        price=config.PRO_PRICE
    ),
    PlanInfo(
        name=config.PLAN_CLINIC,
        display_name="Clínica",
        icon="🏥",
        description="Gestão de equipe",
        price=config.CLINIC_PRICE
    ),
]

# Dicionário para acesso rápido
_FEATURES_MAP: dict[str, Feature] = {f.name: f for f in FEATURES}
_PLANS_MAP: dict[str, PlanInfo] = {p.name: p for p in PLANS}


# ─────────────────────────────────────────────────────────────────────────────
# PLAN SERVICE
# ─────────────────────────────────────────────────────────────────────────────

class PlanService:
    """
    Serviço de planos e paywall.
    
    Gerencia planos de assinatura, trial e controle de acesso.
    
    Example:
        >>> db = Database()
        >>> plan_service = PlanService(db)
        >>> user = User.from_dict(st.session_state.user)
        >>> if plan_service.can_use(user, "charts"):
        ...     # Exibe gráficos
        ... else:
        ...     plan_service.show_paywall("Gráficos", user)
    """

    def __init__(self, db: Any) -> None:
        """
        Inicializa o serviço de planos.
        
        Args:
            db: Instância do Database
        """
        self.db = db
        logger.debug("✅ PlanService inicializado")

    # ─────────────────────────────────────────────────────────────────────────
    # PLANO ATUAL
    # ─────────────────────────────────────────────────────────────────────────

    def get_plan(self, user: User | dict[str, Any] | None) -> str:
        """
        Retorna o plano atual do usuário.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Nome do plano (free/trial/pro/clinic)
            
        Example:
            >>> plan = plan_service.get_plan(user)
            >>> print(f"Plano: {plan}")
        """
        if not user:
            logger.debug("get_plan: usuário não autenticado")
            return config.PLAN_FREE

        # Converte para User se necessário
        u = self._ensure_user(user)
        effective = u.effective_plan()
        
        logger.debug(f"get_plan: {effective}")
        return effective

    def trial_days_remaining(self, user: User | dict[str, Any] | None) -> int:
        """
        Calcula dias restantes do trial.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Número de dias restantes (0 se expirado ou não for trial)
            
        Example:
            >>> days = plan_service.trial_days_remaining(user)
            >>> if days > 0:
            ...     print(f"Trial expira em {days} dias")
        """
        if not user:
            return 0

        u = self._ensure_user(user)
        days = u.trial_days_remaining()
        
        logger.debug(f"trial_days_remaining: {days} dias")
        return days

    def is_trial_active(self, user: User | dict[str, Any] | None) -> bool:
        """
        Verifica se o trial está ativo.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            True se trial ativo, False caso contrário
            
        Example:
            >>> if plan_service.is_trial_active(user):
            ...     print("Trial ativo!")
        """
        plan = self.get_plan(user)
        is_active = plan == config.PLAN_TRIAL
        
        logger.debug(f"is_trial_active: {is_active}")
        return is_active

    def is_pro(self, user: User | dict[str, Any] | None) -> bool:
        """
        Verifica se o usuário tem plano Pro ou superior.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            True se Pro/Clinic, False caso contrário
        """
        if not user:
            return False
            
        plan = self.get_plan(user)
        is_pro = plan in [config.PLAN_PRO, config.PLAN_CLINIC]
        
        logger.debug(f"is_pro: {is_pro}")
        return is_pro

    def _ensure_user(self, user: User | dict[str, Any]) -> User:
        """
        Converte dict para User se necessário.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            Objeto User
        """
        if isinstance(user, User):
            return user
        return User.from_dict(user)

    # ─────────────────────────────────────────────────────────────────────────
    # VERIFICAÇÃO DE ACESSO
    # ─────────────────────────────────────────────────────────────────────────

    def can_use(self, user: User | dict[str, Any] | None, feature: str) -> bool:
        """
        Verifica se o usuário tem acesso à funcionalidade.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            feature: Nome da funcionalidade (charts/export/professional/etc)
            
        Returns:
            True se tem acesso, False caso contrário
            
        Example:
            >>> if plan_service.can_use(user, "charts"):
            ...     # Exibe gráficos
            ... else:
            ...     # Exibe paywall
        """
        # Validação
        if not feature:
            logger.warning("can_use: feature não especificada")
            return False
        
        # Usuário demo tem acesso total
        if user and self._is_demo_user(user):
            logger.debug(f"can_use: {feature} - DEMO (acesso total)")
            return True

        plan = self.get_plan(user)
        feature_obj = _FEATURES_MAP.get(feature)
        
        if not feature_obj:
            logger.warning(f"can_use: feature desconhecida: {feature}")
            return False
        
        has_access = feature_obj.is_allowed(plan)
        
        logger.debug(f"can_use: {feature} - {plan} -> {has_access}")
        return has_access

    def get_allowed_features(self, user: User | dict[str, Any] | None) -> list[str]:
        """
        Retorna lista de features disponíveis para o usuário.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Returns:
            Lista de nomes de features disponíveis
            
        Example:
            >>> features = plan_service.get_allowed_features(user)
            >>> print(f"Features disponíveis: {', '.join(features)}")
        """
        # Usuário demo tem acesso total
        if user and self._is_demo_user(user):
            allowed = [f.name for f in FEATURES]
            logger.debug(f"get_allowed_features: {len(allowed)} features (DEMO)")
            return allowed
        
        plan = self.get_plan(user)
        allowed = [f.name for f in FEATURES if f.is_allowed(plan)]
        
        logger.debug(f"get_allowed_features: {len(allowed)} features para {plan}")
        return allowed

    def _is_demo_user(self, user: User | dict[str, Any]) -> bool:
        """
        Verifica se o usuário é o usuário demo.
        
        Args:
            user: Objeto User ou dicionário
            
        Returns:
            True se for usuário demo
        """
        if isinstance(user, User):
            return user.email == _DEMO_EMAIL
        return user.get("email") == _DEMO_EMAIL

    # ─────────────────────────────────────────────────────────────────────────
    # UI — BANNER DE TRIAL
    # ─────────────────────────────────────────────────────────────────────────

    def trial_banner(self, user: User | dict[str, Any] | None) -> None:
        """
        Exibe banner de trial na parte superior da tela.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Example:
            >>> plan_service.trial_banner(user)
        """
        if not user:
            return

        plan = self.get_plan(user)

        # Exibe apenas se for trial ou free (trial expirado)
        if plan == config.PLAN_FREE:
            self._show_trial_expired_banner()
            return

        if plan != config.PLAN_TRIAL:
            return

        days = self.trial_days_remaining(user)

        # Exibe apenas se dias <= threshold ou se expirou
        if 0 < days <= _TRIAL_WARNING_DAYS:
            self._show_trial_warning_banner(days)
        elif days == 0:
            self._show_trial_expired_banner()

    def _show_trial_warning_banner(self, days: int) -> None:
        """Exibe banner de aviso de trial próximo ao fim."""
        st.warning(
            f"⏳ **{days} dia(s)** de trial restantes. "
            f"Assine para não perder seu progresso.",
            icon="⚠️",
        )
        if st.button("🚀 Assinar Pro →", key="trial_warning_cta"):
            st.session_state.page = "profile"
            st.rerun()

    def _show_trial_expired_banner(self) -> None:
        """Exibe banner de trial expirado."""
        st.warning(
            "⏰ Seu trial expirou. Assine o Pro para continuar com acesso completo.",
            icon="🔒",
        )
        if st.button("🚀 Assinar agora →", key="trial_expired_cta", type="primary"):
            st.session_state.page = "profile"
            st.rerun()

    # ─────────────────────────────────────────────────────────────────────────
    # UI — PAYWALL
    # ─────────────────────────────────────────────────────────────────────────

    def show_paywall(self, feature_name: str, user: User | dict[str, Any] | None) -> None:
        """
        Exibe tela de paywall para features bloqueadas.
        
        Args:
            feature_name: Nome da feature (exibido ao usuário)
            user: Objeto User ou dicionário com dados do usuário
            
        Example:
            >>> plan_service.show_paywall("Gráficos Avançados", user)
        """
        if not feature_name:
            logger.warning("show_paywall: feature_name não especificado")
            return

        self._render_paywall_html(feature_name)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            # Tenta checkout real do Mercado Pago
            try:
                from services.payment_service import PaymentService
                email = ""
                name = ""
                if isinstance(user, dict):
                    email = user.get("email", "")
                    name = user.get("name", "")
                elif user:
                    email = getattr(user, "email", "")
                    name = getattr(user, "name", "")

                pay_svc = PaymentService(self.db)
                if pay_svc.is_configured and email:
                    html = pay_svc.get_checkout_button_html(
                        email, name, plan="pro",
                        label="🚀 Assinar o Melshape Pro",
                    )
                    st.markdown(html, unsafe_allow_html=True)
                    return
            except Exception as _pe:
                logger.debug(f"show_paywall MP fallback: {_pe}")

            # Fallback: botão que redireciona para perfil
            if st.button(
                "🚀 Assinar o Melshape Pro",
                type="primary",
                use_container_width=True,
                key=f"paywall_{feature_name}",
            ):
                st.session_state.page = "profile"
                st.rerun()


    def _render_paywall_html(self, feature_name: str) -> None:
        """Renderiza HTML do paywall."""
        pro_price = config.PRO_PRICE
        
        st.markdown(
            f"""
            <div style="text-align:center;padding:3rem 1.5rem;">
                <div style="font-size:3rem;margin-bottom:1rem;">🔒</div>
                <h3 style="font-family:var(--font-display);color:var(--text);margin-bottom:0.5rem;">
                    {feature_name}
                </h3>
                <p style="color:var(--text-muted);max-width:400px;margin:0 auto 1.5rem;">
                    Este recurso está disponível no plano 
                    <b>Melshape Pro</b> por apenas 
                    <b>R$ {pro_price:.2f}/mês</b>.
                </p>
                <div style="display:flex;flex-direction:column;gap:0.5rem;max-width:300px;margin:0 auto;">
                    <button style="background:linear-gradient(135deg,var(--primary),var(--primary-dark));
                           color:white;border:none;padding:0.75rem 1.5rem;border-radius:var(--radius-md);
                           font-weight:600;cursor:pointer;font-size:1rem;">
                        🚀 Assinar o Melshape Pro
                    </button>
                    <div style="font-size:0.78rem;color:var(--text-muted);margin-top:0.5rem;">
                        ✨ Inicie com {config.TRIAL_DAYS} dias de trial grátis
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # UI — PLANO DETALHADO
    # ─────────────────────────────────────────────────────────────────────────

    def render_plan_details(self, user: User | dict[str, Any] | None) -> None:
        """
        Renderiza detalhes do plano atual do usuário.
        
        Args:
            user: Objeto User ou dicionário com dados do usuário
            
        Example:
            >>> plan_service.render_plan_details(user)
        """
        if not user:
            st.info("Faça login para ver seu plano.")
            return

        plan = self.get_plan(user)
        plan_info = _PLANS_MAP.get(plan)
        
        if not plan_info:
            logger.warning(f"render_plan_details: plano desconhecido: {plan}")
            return
        
        # Renderiza card do plano
        self._render_plan_card(plan_info)
        
        # Dias restantes para trial
        if plan == config.PLAN_TRIAL:
            self._render_trial_progress(user)

    def _render_plan_card(self, plan_info: PlanInfo) -> None:
        """Renderiza card do plano."""
        price_text = f"R$ {plan_info.price:.2f}/mês" if plan_info.is_paid else "Gratuito"
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="margin-bottom:1rem;">
                <div style="display:flex;align-items:center;gap:0.8rem;">
                    <span style="font-size:2rem;">{plan_info.icon}</span>
                    <div>
                        <div style="font-weight:800;font-size:1.1rem;color:var(--text);">
                            {plan_info.icon} {plan_info.display_name}
                        </div>
                        <div style="font-size:0.80rem;color:var(--text-muted);">
                            {plan_info.description} • {price_text}
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    def _render_trial_progress(self, user: User | dict[str, Any]) -> None:
        """Renderiza progresso do trial."""
        days = self.trial_days_remaining(user)
        
        if days > 0:
            progress = days / config.TRIAL_DAYS
            st.progress(progress, text=f"⏳ {days} dias restantes")
        else:
            st.warning("⏳ Trial expirado. Assine o Pro para continuar.")

    # ─────────────────────────────────────────────────────────────────────────
    # MÉTODOS AUXILIARES
    # ─────────────────────────────────────────────────────────────────────────

    def get_feature(self, feature_name: str) -> Feature | None:
        """
        Busca uma feature pelo nome.
        
        Args:
            feature_name: Nome da feature
            
        Returns:
            Objeto Feature ou None
            
        Example:
            >>> feature = plan_service.get_feature("charts")
            >>> if feature:
            ...     print(f"{feature.display_name}: {feature.description}")
        """
        return _FEATURES_MAP.get(feature_name)

    def get_plan_info(self, plan_name: str) -> PlanInfo | None:
        """
        Busca informações de um plano.
        
        Args:
            plan_name: Nome do plano
            
        Returns:
            Objeto PlanInfo ou None
            
        Example:
            >>> plan = plan_service.get_plan_info("pro")
            >>> if plan:
            ...     print(f"{plan.display_name}: R$ {plan.price:.2f}/mês")
        """
        return _PLANS_MAP.get(plan_name)

    def get_all_features(self) -> list[Feature]:
        """
        Retorna todas as features disponíveis.
        
        Returns:
            Lista de objetos Feature
        """
        return FEATURES

    def get_all_plans(self) -> list[PlanInfo]:
        """
        Retorna todos os planos disponíveis.
        
        Returns:
            Lista de objetos PlanInfo
        """
        return PLANS


__all__ = [
    "PlanService",
    "Feature",
    "PlanInfo",
    "FEATURES",
    "PLANS",
]
