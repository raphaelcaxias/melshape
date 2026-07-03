"""
Melshape — Onboarding do Paciente.

4 passos em ~2 minutos:
  1. Escolha do pilar (general, fitness, bariatric, glp1)
  2. Dados pessoais (peso, altura, idade, gênero, objetivo)
  3. Por que você começou (salvo em motivos_jornada)
  4. Hábitos iniciais criados automaticamente

Regra: o paciente deve sentir que o sistema já o conhece
antes de chegar à home.
"""
import streamlit as st
from typing import Dict, Any, Optional, List
import logging

from views.components.cards import alert
from views.patient.onboarding_steps import (
    _step_pilar, _step_dados, _step_porque, _step_habitos
)

logger = logging.getLogger("Melshape.Onboarding")


# Constantes
STEPS = ["Pilar", "Dados", "Porquê", "Hábitos"]
TOTAL_STEPS = len(STEPS)
MIN_STEP = 1
MAX_STEP = TOTAL_STEPS

# Chaves de session state
SESSION_KEY_STEP = "onboarding_step"
SESSION_KEY_MODE = "onboarding_mode"


class OnboardingRenderer:
    """Renderer dedicado para onboarding."""
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user or {}
        self.db = services.get("db")
        self._init_session_state()
    
    def _init_session_state(self) -> None:
        """Inicializa estado do onboarding na sessão com tratamento de erros."""
        try:
            if SESSION_KEY_STEP not in st.session_state:
                st.session_state[SESSION_KEY_STEP] = MIN_STEP
            if SESSION_KEY_MODE not in st.session_state:
                st.session_state[SESSION_KEY_MODE] = ""
        except Exception as e:
            logger.error(f"Erro ao inicializar session state: {e}", exc_info=True)
            # Fallback: usa variáveis locais
            self._step_fallback = MIN_STEP
            self._mode_fallback = ""
    
    def render(self) -> None:
        """Renderiza fluxo de onboarding."""
        step = self._get_step_atual()
        
        # Valida step
        if not self._validar_step(step):
            self._render_erro_step(step)
            return
        
        # Barra de progresso
        self._render_progress_bar(step)
        
        # Renderiza passo atual com tratamento de erros
        self._render_step_atual(step)
    
    def _get_step_atual(self) -> int:
        """Obtém step atual de forma segura."""
        try:
            step = st.session_state.get(SESSION_KEY_STEP, MIN_STEP)
            return int(step) if step is not None else MIN_STEP
        except (ValueError, TypeError) as e:
            logger.warning(f"Erro ao obter step atual: {e}")
            return MIN_STEP
    
    def _validar_step(self, step: int) -> bool:
        """Valida se o step está no intervalo válido."""
        return MIN_STEP <= step <= MAX_STEP
    
    def _render_erro_step(self, step: int) -> None:
        """Renderiza mensagem de erro quando step é inválido."""
        logger.error(f"Step inválido recebido: {step}")
        alert(
            "❌ Erro no fluxo de onboarding. Por favor, recarregue a página.",
            "error",
        )
        
        # Tenta resetar para o passo 1
        if st.button("🔄 Reiniciar onboarding", use_container_width=True):
            try:
                st.session_state[SESSION_KEY_STEP] = MIN_STEP
                st.rerun()
            except Exception as e:
                logger.error(f"Erro ao reiniciar onboarding: {e}", exc_info=True)
    
    def _render_step_atual(self, step: int) -> None:
        """Renderiza o passo atual com tratamento de erros."""
        try:
            if step == 1:
                self._render_step_pilar()
            elif step == 2:
                self._render_step_dados()
            elif step == 3:
                self._render_step_porque()
            elif step == 4:
                self._render_step_habitos()
        except Exception as e:
            logger.error(f"Erro ao renderizar passo {step}: {e}", exc_info=True)
            alert(f"❌ Erro ao carregar passo {step}. Tente recarregar a página.", "error")
    
    def _render_step_pilar(self) -> None:
        """Renderiza passo 1: escolha do pilar."""
        try:
            _step_pilar()
        except Exception as e:
            logger.error(f"Erro no passo pilar: {e}", exc_info=True)
            alert("❌ Erro ao carregar seleção de pilar.", "error")
    
    def _render_step_dados(self) -> None:
        """Renderiza passo 2: dados pessoais."""
        try:
            _step_dados(self.user)
        except Exception as e:
            logger.error(f"Erro no passo dados: {e}", exc_info=True)
            alert("❌ Erro ao carregar formulário de dados.", "error")
    
    def _render_step_porque(self) -> None:
        """Renderiza passo 3: porquê."""
        try:
            _step_porque(self.db, self.user)
        except Exception as e:
            logger.error(f"Erro no passo porquê: {e}", exc_info=True)
            alert("❌ Erro ao carregar formulário de porquê.", "error")
    
    def _render_step_habitos(self) -> None:
        """Renderiza passo 4: hábitos iniciais."""
        try:
            _step_habitos(self.db, self.user)
        except Exception as e:
            logger.error(f"Erro no passo hábitos: {e}", exc_info=True)
            alert("❌ Erro ao carregar criação de hábitos.", "error")
    
    def _render_progress_bar(self, step: int) -> None:
        """Renderiza barra de progresso com validações."""
        pct = self._calcular_percentual_progresso(step)
        nome_step = self._get_nome_step(step)
        
        st.markdown(
            f"""
            <div style="margin-bottom: 1.6rem;">
                <div style="display: flex; justify-content: space-between;
                    font-size: 0.76rem; color: var(--text-muted); margin-bottom: 0.4rem;">
                    <span>Passo {step} de {TOTAL_STEPS}: <b>{nome_step}</b></span>
                    <span>{pct}%</span>
                </div>
                <div class="progress-track">
                    <div class="progress-fill" style="width: {pct}%;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _calcular_percentual_progresso(self, step: int) -> int:
        """Calcula percentual de progresso de forma segura."""
        if TOTAL_STEPS <= 0:
            return 0
        
        try:
            pct = int((step - MIN_STEP) / TOTAL_STEPS * 100)
            return min(100, max(0, pct))  # Garante entre 0 e 100
        except Exception as e:
            logger.debug(f"Erro ao calcular percentual: {e}")
            return 0
    
    def _get_nome_step(self, step: int) -> str:
        """Obtém nome do step de forma segura."""
        try:
            idx = step - MIN_STEP
            if 0 <= idx < len(STEPS):
                return STEPS[idx]
            return "—"
        except Exception as e:
            logger.debug(f"Erro ao obter nome do step {step}: {e}")
            return "—"


# Função principal de compatibilidade
def render(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = OnboardingRenderer(services, user)
    renderer.render()
