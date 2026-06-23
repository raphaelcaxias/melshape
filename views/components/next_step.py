"""
Melshape — Componente "Próximo Passo".

Responde em todas as telas:
1. O que faço agora? (ação principal)
2. O que ganho se continuar? (próxima conquista)
3. Quem me acompanha? (profissional)

Prioridade: check-in > hábito pendente > contexto pilar > jornada > água
Injetado no topo de qualquer tela do paciente via render_next_step(services, user).
"""
import streamlit as st
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
import logging

from services.gamification_service import GamificationService, ACHIEVEMENTS

logger = logging.getLogger("Melshape.NextStep")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Limiares
HYDRATION_GOAL_ML = 2000
HYDRATION_ALERT_ML = 1500
STREAK_DESTAQUE = 7

# Mapeamento de urgência para cores
URGENCY_COLORS = {
    "alta": "var(--error)",
    "media": "var(--warning)",
    "baixa": "var(--info)",
    "ok": "var(--success)",
}

# Fallbacks
DEFAULT_ICON = "⭐"
DEFAULT_TEXT = "Continue sua jornada"
DEFAULT_URGENCY = "ok"
DEFAULT_MARCO_TITLE = "Continue consistente"
DEFAULT_MARCO_DESC = "Cada dia conta"


@dataclass
class NextStepAction:
    """Ação do próximo passo."""
    text: str = DEFAULT_TEXT
    icon: str = DEFAULT_ICON
    page: Optional[str] = None
    hub_tipo: Optional[str] = None
    urgency: str = DEFAULT_URGENCY


@dataclass
class NextStepMarco:
    """Próximo marco a ser alcançado."""
    title: str = DEFAULT_MARCO_TITLE
    description: str = DEFAULT_MARCO_DESC


class NextStepRenderer:
    """Renderer dedicado para o componente de próximo passo."""
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services or {}
        self.user = user or {}
        self.db = services.get("db")
        self.gami = self._init_gamification_service()
    
    def _init_gamification_service(self) -> GamificationService:
        """Inicializa GamificationService com fallback."""
        try:
            gami = self.services.get("gamification")
            if gami:
                return gami
            return GamificationService(self.db)
        except Exception as e:
            logger.error(f"Erro ao inicializar GamificationService: {e}", exc_info=True)
            return None
    
    def render(self) -> None:
        """Renderiza o card de próximo passo com tratamento de erros."""
        try:
            action = self._decide_action()
            marco = self._get_next_marco()
            professional = self._get_professional()
            
            self._render_card(action, marco, professional)
        except Exception as e:
            logger.error(f"Erro ao renderizar próximo passo: {e}", exc_info=True)
            # Renderiza card mínimo em caso de erro
            self._render_card_minimo()
    
    def _render_card_minimo(self) -> None:
        """Renderiza card mínimo em caso de erro."""
        try:
            action = NextStepAction(
                text="Continue sua jornada",
                icon="⭐",
                urgency="ok",
            )
            marco = NextStepMarco()
            self._render_card(action, marco, None)
        except Exception as e:
            logger.error(f"Erro ao renderizar card mínimo: {e}", exc_info=True)
    
    def _decide_action(self) -> NextStepAction:
        """Decide qual ação deve ser tomada."""
        # 1. Check-in pendente — prioridade máxima
        if not self._has_checkin_today():
            return NextStepAction(
                text="Faça seu check-in de hoje (30 segundos)",
                icon="✅",
                page="checkin",
                urgency="alta",
            )
        
        # 2. Hábito pendente
        pendentes = self._get_pending_habits()
        if pendentes:
            return self._build_habit_action(pendentes[0])
        
        # 3. Contexto por pilar
        health_mode = self.user.get("health_mode", "general")
        pilar_action = self._get_pilar_action(health_mode)
        if pilar_action:
            return pilar_action
        
        # 4. Água abaixo de 1,5L
        hydration = self._get_hydration()
        if hydration < HYDRATION_ALERT_ML:
            return self._build_hydration_action(hydration)
        
        # 5. Streak abaixo de 7
        streak = self._get_streak()
        if streak < STREAK_DESTAQUE:
            return self._build_streak_action(streak)
        
        # 6. Tudo em dia
        return self._build_all_done_action(streak)
    
    def _has_checkin_today(self) -> bool:
        """Verifica se check-in foi feito hoje."""
        if not self.db:
            return False
        
        try:
            checkin = self.db.get_checkin_today()
            return checkin is not None
        except Exception as e:
            logger.error(f"Erro ao verificar check-in: {e}", exc_info=True)
            return False
    
    def _get_hydration(self) -> int:
        """Obtém hidratação de hoje."""
        if not self.db:
            return 0
        
        try:
            hydration = self.db.get_hydration_today()
            return int(hydration) if hydration is not None else 0
        except Exception as e:
            logger.error(f"Erro ao obter hidratação: {e}", exc_info=True)
            return 0
    
    def _get_streak(self) -> int:
        """Obtém streak de check-ins."""
        if not self.db:
            return 0
        
        try:
            streak = self.db.get_checkin_streak()
            return int(streak) if streak is not None else 0
        except Exception as e:
            logger.error(f"Erro ao obter streak: {e}", exc_info=True)
            return 0
    
    @st.cache_data(ttl=30)
    def _get_pending_habits(_self) -> List[Dict]:
        """Obtém hábitos pendentes de hoje (com cache)."""
        if not _self.db:
            return []
        
        try:
            habitos = _self.db.get_habitos()
            feitos = _self.db.get_registros_hoje()
            
            if not isinstance(habitos, list) or not isinstance(feitos, (list, set)):
                return []
            
            feitos_set = set(feitos)
            return [h for h in habitos if h.get("id") not in feitos_set]
        except Exception as e:
            logger.error(f"Erro ao obter hábitos pendentes: {e}", exc_info=True)
            return []
    
    def _build_habit_action(self, habit: Dict) -> NextStepAction:
        """Constrói ação para hábito pendente."""
        try:
            nome = habit.get("nome", "hábito")
            icone = habit.get("icone", "📋")
            
            return NextStepAction(
                text=f"Complete seu hábito: {nome}",
                icon=icone,
                page="habits",
                urgency="media",
            )
        except Exception as e:
            logger.error(f"Erro ao construir ação de hábito: {e}", exc_info=True)
            return NextStepAction(text="Complete seus hábitos", icon="📋", page="habits", urgency="media")
    
    def _build_hydration_action(self, hydration: int) -> NextStepAction:
        """Constrói ação para hidratação."""
        try:
            falta = HYDRATION_GOAL_ML - hydration
            return NextStepAction(
                text=f"Beba mais {falta:.0f}ml de água para atingir a meta",
                icon="💧",
                page="meals",
                hub_tipo="hydration",
                urgency="baixa",
            )
        except Exception as e:
            logger.error(f"Erro ao construir ação de hidratação: {e}", exc_info=True)
            return NextStepAction(text="Beba mais água", icon="💧", page="meals", urgency="baixa")
    
    def _build_streak_action(self, streak: int) -> NextStepAction:
        """Constrói ação para streak."""
        try:
            faltam = STREAK_DESTAQUE - streak
            return NextStepAction(
                text=f"Mais {faltam} dia(s) para completar {STREAK_DESTAQUE} dias seguidos!",
                icon="🔥",
                urgency="ok",
            )
        except Exception as e:
            logger.error(f"Erro ao construir ação de streak: {e}", exc_info=True)
            return NextStepAction(text="Continue sua sequência", icon="🔥", urgency="ok")
    
    def _build_all_done_action(self, streak: int) -> NextStepAction:
        """Constrói ação quando tudo está em dia."""
        try:
            return NextStepAction(
                text=f"🔥 {streak} dias seguidos! Continue assim.",
                icon="⭐",
                urgency="ok",
            )
        except Exception as e:
            logger.error(f"Erro ao construir ação de tudo em dia: {e}", exc_info=True)
            return NextStepAction(text="Continue assim!", icon="⭐", urgency="ok")
    
    def _get_pilar_action(self, health_mode: str) -> Optional[NextStepAction]:
        """Obtém ação baseada no pilar do usuário."""
        try:
            if health_mode == "glp1":
                return self._get_glp1_action()
            
            if health_mode == "bariatric":
                return self._get_bariatric_action()
            
            if health_mode == "fitness":
                return self._get_fitness_action()
            
            return None
        except Exception as e:
            logger.error(f"Erro ao obter ação do pilar '{health_mode}': {e}", exc_info=True)
            return None
    
    def _get_glp1_action(self) -> Optional[NextStepAction]:
        """Obtém ação para pilar GLP-1."""
        try:
            from services.glp1_service import GLP1Service
            
            medication = self.user.get("glp1_medication", "")
            proxima = GLP1Service(self.db).proxima_dose(medication)
            
            if proxima and proxima.lower() in ("hoje", "amanhã"):
                return NextStepAction(
                    text=f"Próxima dose GLP-1: {proxima}",
                    icon="💉",
                    page="glp1",
                    urgency="media",
                )
        except Exception as e:
            logger.error(f"Erro ao obter ação GLP-1: {e}", exc_info=True)
        
        return None
    
    def _get_bariatric_action(self) -> Optional[NextStepAction]:
        """Obtém ação para pilar bariátrico."""
        try:
            from config import BARIATRIC_PHASES
            
            fase_key = self.user.get("bariatric_phase", "liquid")
            fase_data = BARIATRIC_PHASES.get(fase_key, {})
            
            if fase_data:
                nome = fase_data.get("name", "")
                max_ml = fase_data.get("max_ml", "")
                
                return NextStepAction(
                    text=f"Fase {nome} — máx {max_ml}ml por refeição",
                    icon="🔪",
                    page="bariatric",
                    urgency="baixa",
                )
        except Exception as e:
            logger.error(f"Erro ao obter ação bariátrica: {e}", exc_info=True)
        
        return None
    
    def _get_fitness_action(self) -> Optional[NextStepAction]:
        """Obtém ação para pilar fitness."""
        try:
            treino = self.db.get_workout_today()
            
            if not treino:
                return NextStepAction(
                    text="Registre seu treino de hoje",
                    icon="🏋️",
                    page="habits",
                    urgency="media",
                )
        except Exception as e:
            logger.error(f"Erro ao obter ação fitness: {e}", exc_info=True)
        
        return None
    
    @st.cache_data(ttl=60)
    def _get_next_marco(_self) -> NextStepMarco:
        """Obtém o próximo marco a ser alcançado (com cache)."""
        # 1. Próxima conquista de gamificação
        marco = _self._get_next_achievement()
        if marco:
            return marco
        
        # 2. Próxima etapa da jornada
        marco = _self._get_next_journey_stage()
        if marco:
            return marco
        
        # 3. Fallback
        return NextStepMarco()
    
    def _get_next_achievement(self) -> Optional[NextStepMarco]:
        """Obtém próxima conquista não alcançada."""
        try:
            conquistas = self.db.get_achievements()
            
            if not isinstance(conquistas, list):
                return None
            
            conquistadas = {
                a.get("achievement_name") for a in conquistas if a.get("achievement_name")
            }
            
            for achievement in ACHIEVEMENTS:
                if achievement.get("name") not in conquistadas:
                    return NextStepMarco(
                        title=achievement.get("title", ""),
                        description=achievement.get("desc", ""),
                    )
        except Exception as e:
            logger.error(f"Erro ao obter próxima conquista: {e}", exc_info=True)
        
        return None
    
    def _get_next_journey_stage(self) -> Optional[NextStepMarco]:
        """Obtém próxima etapa da jornada."""
        try:
            jornada = self.db.get_jornada_ativa()
            
            if not jornada:
                return None
            
            from services.journey_service import JourneyService
            
            health_mode = self.user.get("health_mode", "general")
            progresso = JourneyService(self.db).progresso_jornada(
                jornada.get("id"), health_mode
            )
            
            proxima = progresso.get("etapa_seguinte")
            
            if proxima:
                return NextStepMarco(
                    title=proxima.get("nome", ""),
                    description=proxima.get("descricao", ""),
                )
        except Exception as e:
            logger.error(f"Erro ao obter próxima etapa da jornada: {e}", exc_info=True)
        
        return None
    
    def _get_professional(self) -> Optional[str]:
        """Obtém o nome do profissional vinculado."""
        try:
            return (
                self.user.get("professional_name") or 
                self.user.get("professional_id")
            )
        except Exception as e:
            logger.debug(f"Erro ao obter profissional: {e}")
            return None
    
    def _render_card(
        self,
        action: NextStepAction,
        marco: NextStepMarco,
        professional: Optional[str],
    ) -> None:
        """Renderiza o card de próximo passo."""
        try:
            color = URGENCY_COLORS.get(action.urgency, "var(--border)")
            
            # HTML do marco
            marco_html = self._build_marco_html(marco)
            
            # HTML do profissional
            pro_html = self._build_professional_html(professional)
            
            # Renderiza card
            st.markdown(
                f"""
                <div class="fade-in" style="background: var(--surface-2);
                    border-radius: 16px; padding: 0.85rem 1.1rem;
                    margin-bottom: 1.1rem; border: 1px solid var(--border);
                    border-left: 4px solid {color};">
                    <div style="display: flex; align-items: center;
                        justify-content: space-between; flex-wrap: wrap; gap: 0.6rem;">
                        <div style="display: flex; align-items: center; gap: 0.7rem;">
                            <span style="font-size: 1.5rem;">{action.icon}</span>
                            <div>
                                <div style="font-size: 0.72rem; color: var(--text-faint);
                                    font-weight: 700; text-transform: uppercase;
                                    letter-spacing: 0.06em;">
                                    Próximo passo
                                </div>
                                <div style="font-weight: 700; font-size: 0.94rem;
                                    color: var(--text);">
                                    {action.text}
                                </div>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 0.7rem;
                            flex-wrap: wrap;">
                            {pro_html}
                            {marco_html}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            
            # Botão de ação
            if action.page:
                self._render_action_button(action)
        except Exception as e:
            logger.error(f"Erro ao renderizar card: {e}", exc_info=True)
    
    def _build_marco_html(self, marco: NextStepMarco) -> str:
        """Constrói HTML do marco."""
        try:
            if not marco or not marco.title:
                return ""
            
            return (
                f'<span style="font-size: 0.76rem; color: var(--primary);'
                f'background: var(--primary-light); padding: 0.18rem 0.65rem;'
                f'border-radius: 9999px; border: 1px solid var(--primary-border);'
                f'white-space: nowrap;">→ {marco.title}</span>'
            )
        except Exception as e:
            logger.debug(f"Erro ao construir HTML do marco: {e}")
            return ""
    
    def _build_professional_html(self, professional: Optional[str]) -> str:
        """Constrói HTML do profissional."""
        try:
            if not professional:
                return ""
            
            return (
                f'<span style="font-size: 0.78rem; color: var(--text-muted);">'
                f'👤 {professional}</span>'
            )
        except Exception as e:
            logger.debug(f"Erro ao construir HTML do profissional: {e}")
            return ""
    
    def _render_action_button(self, action: NextStepAction) -> None:
        """Renderiza botão de ação."""
        try:
            if st.button(
                f'{action.icon} Fazer agora',
                type="primary",
                use_container_width=True,
                key="next_step_cta",
            ):
                self._navegar_para_pagina(action.page, action.hub_tipo)
        except Exception as e:
            logger.error(f"Erro ao renderizar botão de ação: {e}", exc_info=True)
    
    def _navegar_para_pagina(self, page: str, hub_tipo: Optional[str]) -> None:
        """Navega para página com tratamento de erros."""
        try:
            st.session_state.page = page
            
            if hub_tipo:
                st.session_state.hub_tipo = hub_tipo
            
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao navegar para '{page}': {e}", exc_info=True)
            st.error("❌ Erro ao navegar. Tente novamente.")


# Função principal de compatibilidade
def render_next_step(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Renderiza o card de próximo passo."""
    renderer = NextStepRenderer(services, user)
    renderer.render()
