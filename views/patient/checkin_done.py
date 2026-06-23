"""
Melshape — Check-in: tela de já feito hoje.
"""
import streamlit as st
from typing import Dict, Any, Optional
import logging

from views.components.cards import metric_card
from views.patient.checkin_result import render_resultado

logger = logging.getLogger("Melshape.CheckinDone")


class CheckinDoneRenderer:
    """Renderer para estado de check-in já realizado."""
    
    STREAK_DESTAQUE = 7  # Dias para destacar sequência
    METRIC_LABELS = {
        "humor": ("😊", "Humor"),
        "energia": ("⚡", "Energia"),
        "qualidade_sono": ("😴", "Sono"),
    }
    
    def __init__(self, checkin: Dict[str, Any], db, user: Dict[str, Any]):
        self.checkin = checkin
        self.db = db
        self.user = user
    
    def render(self) -> None:
        """Renderiza tela de check-in já feito."""
        streak = self._get_streak()
        result = st.session_state.get("ci_result")
        
        # Card principal
        self._render_success_card(streak)
        
        # Resultado do Orchestrator ou métricas simples
        if result:
            render_resultado(result, self.user)
            self._render_clear_button()
        else:
            self._render_simple_metrics()
    
    @st.cache_data(ttl=30)
    def _get_streak(_self) -> int:
        """Obtém streak de check-ins (com cache)."""
        try:
            streak = _self.db.get_checkin_streak()
            return int(streak) if streak is not None else 0
        except Exception as e:
            logger.error(f"Erro ao buscar streak: {e}", exc_info=True)
            return 0
    
    def _render_success_card(self, streak: int) -> None:
        """Renderiza card de sucesso."""
        destaque = streak >= self.STREAK_DESTAQUE
        icon = "🔥" if destaque else "✅"
        cor = "var(--warning)" if destaque else "var(--success)"
        cor_texto = "var(--warning)" if destaque else "var(--primary)"
        
        streak_texto = f"{streak} dia{'s' if streak != 1 else ''}"
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="border-color: {cor};">
                <div style="font-size: 2.2rem; margin-bottom: 0.3rem;">{icon}</div>
                <div style="font-weight: 800; font-size: 1.15rem; color: {cor};">
                    Check-in feito hoje!
                </div>
                <div style="font-size: 0.86rem; color: var(--text-muted); margin-top: 0.4rem;">
                    Sequência atual: <b style="color: {cor_texto};">{streak_texto}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Mensagem motivacional para streaks longos
        if destaque:
            st.markdown(
                f"""
                <div style="font-size: 0.82rem; color: var(--warning); 
                    margin-top: 0.5rem; text-align: center;">
                    🎉 Incrível! Você está em uma sequência impressionante!
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    def _render_clear_button(self) -> None:
        """Renderiza botão para limpar resultado."""
        if st.button(
            "🔄 Ver apenas resumo",
            key="ci_limpar_result",
            use_container_width=True,
        ):
            st.session_state.pop("ci_result", None)
            st.rerun()
    
    def _render_simple_metrics(self) -> None:
        """Renderiza métricas simples do check-in."""
        col1, col2, col3 = st.columns(3)
        
        metrics = [
            ("humor", col1),
            ("energia", col2),
            ("qualidade_sono", col3),
        ]
        
        for key, col in metrics:
            with col:
                self._render_metric_item(key)
    
    def _render_metric_item(self, key: str) -> None:
        """Renderiza um item de métrica com fallback seguro."""
        icon, label = self.METRIC_LABELS.get(key, ("📊", key))
        valor = self._parse_metric_value(self.checkin.get(key))
        
        metric_card(str(valor), label, icon)
    
    def _parse_metric_value(self, value: Any) -> str:
        """Converte valor da métrica para string de forma segura."""
        if value is None or value == "":
            return "—"
        
        try:
            # Tenta converter para número e formatar
            num = float(value)
            # Se for inteiro, retorna sem casas decimais
            if num.is_integer():
                return str(int(num))
            return f"{num:.1f}".replace(".", ",")
        except (ValueError, TypeError):
            return str(value)


# Função de compatibilidade
def _tela_ja_feito(checkin: Dict[str, Any], db, user: Dict[str, Any]) -> None:
    """Renderiza tela de check-in já feito (compatibilidade)."""
    renderer = CheckinDoneRenderer(checkin, db, user)
    renderer.render()
