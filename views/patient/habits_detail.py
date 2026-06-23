"""
Melshape — Detalhe de Hábito.
Calendário visual 21 dias, streak, aderência e melhor sequência.
Importado por habits.py.
"""
import streamlit as st
from typing import Dict, Any, List, Optional
import logging

from services.habit_service import HabitService
from views.components.cards import metric_card

logger = logging.getLogger("Melshape.HabitDetail")


class HabitDetailRenderer:
    """Renderer dedicado para detalhe de hábito."""
    
    # Constantes de limiares
    STREAK_DESTAQUE = 7
    STREAK_LENDA = 30
    ADERENCIA_EXCELENTE = 80
    ADERENCIA_BOM = 50
    DIAS_CALENDARIO = 21
    
    def __init__(self, svc: HabitService):
        self.svc = svc
    
    def render(self, habito: Dict[str, Any]) -> None:
        """Renderiza detalhe de um hábito."""
        habito_id = habito.get("id", "")
        nome = habito.get("nome", "")
        icone = habito.get("icone", "⭐")
        
        if not habito_id:
            logger.warning("Hábito sem ID fornecido")
            st.warning("⚠️ Hábito inválido.")
            return
        
        # Métricas
        streak = self._get_streak(habito_id)
        melhor = self._get_melhor_streak(habito_id)
        aderencia_7 = self._get_aderencia(habito_id, days=7)
        aderencia_30 = self._get_aderencia(habito_id, days=30)
        
        # Cabeçalho
        self._render_cabecalho(icone, nome)
        
        # Métricas em grid
        self._render_metricas(streak, melhor, aderencia_7, aderencia_30)
        
        # Calendário
        self._render_calendario(habito_id)
        
        # Mensagem motivacional
        self._render_mensagem_motivacional(streak, aderencia_7)
    
    def _render_cabecalho(self, icone: str, nome: str) -> None:
        """Renderiza cabeçalho do hábito."""
        st.markdown(
            f"""
            <div style="font-weight: 700; font-size: 1.05rem; color: var(--text);
                margin-bottom: 0.9rem;">
                {icone} {nome}
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    @st.cache_data(ttl=30)
    def _get_streak(_self, habito_id: str) -> int:
        """Obtém streak atual do hábito (com cache)."""
        try:
            streak = _self.svc.streak_habito(habito_id)
            return int(streak) if streak is not None else 0
        except Exception as e:
            logger.error(f"Erro ao obter streak do hábito {habito_id}: {e}", exc_info=True)
            return 0
    
    @st.cache_data(ttl=30)
    def _get_melhor_streak(_self, habito_id: str) -> int:
        """Obtém melhor streak do hábito (com cache)."""
        try:
            melhor = _self.svc.melhor_streak(habito_id)
            return int(melhor) if melhor is not None else 0
        except Exception as e:
            logger.error(f"Erro ao obter melhor streak do hábito {habito_id}: {e}", exc_info=True)
            return 0
    
    @st.cache_data(ttl=30)
    def _get_aderencia(_self, habito_id: str, days: int) -> float:
        """Obtém aderência do hábito (com cache)."""
        try:
            aderencia = _self.svc.aderencia(habito_id, days=days)
            return max(0.0, min(float(aderencia), 100.0))
        except Exception as e:
            logger.error(f"Erro ao obter aderência do hábito {habito_id}: {e}", exc_info=True)
            return 0.0
    
    def _render_metricas(self, streak: int, melhor: int,
                          aderencia_7: float, aderencia_30: float) -> None:
        """Renderiza métricas do hábito."""
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            cor = self._get_cor_streak(streak)
            metric_card(f"{streak}d", "Streak atual", "🔥", cor)
        
        with col2:
            metric_card(f"{melhor}d", "Melhor sequência", "🏆")
        
        with col3:
            cor = self._get_cor_aderencia(aderencia_7)
            metric_card(f"{aderencia_7:.0f}%", "Aderência 7d", "📊", cor)
        
        with col4:
            cor = self._get_cor_aderencia(aderencia_30)
            metric_card(f"{aderencia_30:.0f}%", "Aderência 30d", "📅", cor)
    
    def _get_cor_streak(self, streak: int) -> str:
        """Retorna cor baseada no streak."""
        if streak >= self.STREAK_DESTAQUE:
            return "success"
        elif streak >= 3:
            return "warning"
        else:
            return ""
    
    def _get_cor_aderencia(self, aderencia: float) -> str:
        """Retorna cor baseada na aderência."""
        if aderencia >= self.ADERENCIA_EXCELENTE:
            return "success"
        elif aderencia >= self.ADERENCIA_BOM:
            return "warning"
        else:
            return "error"
    
    def _render_calendario(self, habito_id: str) -> None:
        """Renderiza calendário de 21 dias."""
        st.markdown(
            """
            <div style="margin: 1rem 0 0.6rem; font-size: 0.82rem; font-weight: 700;
                color: var(--text-faint); text-transform: uppercase;
                letter-spacing: 0.06em;">
                Calendário — últimos 21 dias
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        calendario = self._get_calendario(habito_id)
        self._render_calendario_grid(calendario)
        self._render_legenda()
    
    @st.cache_data(ttl=60)
    def _get_calendario(_self, habito_id: str) -> List[Dict]:
        """Obtém calendário do hábito (com cache)."""
        try:
            calendario = _self.svc.calendario(habito_id, days=_self.DIAS_CALENDARIO)
            return calendario if isinstance(calendario, list) else []
        except Exception as e:
            logger.error(f"Erro ao obter calendário do hábito {habito_id}: {e}", exc_info=True)
            return []
    
    def _render_calendario_grid(self, calendario: List[Dict]) -> None:
        """Renderiza grid do calendário."""
        if not calendario:
            st.info("📅 Sem dados de calendário disponíveis.")
            return
        
        # Cabeçalho dos dias
        header_html = self._render_header_dias_semana()
        
        st.markdown(
            f"""
            <div style="display: grid; grid-template-columns: repeat(7, 1fr);
                gap: 4px; margin-bottom: 4px;">
                {header_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Células do calendário
        semanas = [calendario[i:i + 7] for i in range(0, len(calendario), 7)]
        
        for semana in semanas:
            cells_html = self._render_semana_cells(semana)
            
            st.markdown(
                f"""
                <div style="display: grid; grid-template-columns: repeat(7, 1fr);
                    gap: 4px; margin-bottom: 4px;">
                    {cells_html}
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    def _render_header_dias_semana(self) -> str:
        """Renderiza cabeçalho dos dias da semana."""
        dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        return "".join(
            f'<div style="text-align: center; font-size: 0.70rem;'
            f'color: var(--text-faint); font-weight: 600;">{d}</div>'
            for d in dias_semana
        )
    
    def _render_semana_cells(self, semana: List[Dict]) -> str:
        """Renderiza células de uma semana."""
        cells_html = ""
        
        for dia in semana:
            bg, bdr, txt = self._get_dia_style(dia)
            dia_num = self._extrair_dia_mes(dia.get("data", ""))
            
            cells_html += (
                f'<div style="background: {bg}; border: 1px solid {bdr};'
                f'border-radius: 6px; padding: 0.35rem;'
                f'text-align: center; min-height: 38px;">'
                f'<div style="font-size: 0.68rem; color: var(--text-faint);">'
                f'{dia_num}</div>'
                f'<div style="font-size: 0.85rem; color: #fff; font-weight: 700;">'
                f'{txt}</div>'
                f'</div>'
            )
        
        return cells_html
    
    def _get_dia_style(self, dia: Dict) -> tuple:
        """Retorna estilo (bg, border, texto) baseado no status do dia."""
        if dia.get("futuro"):
            return "var(--surface-2)", "var(--border)", ""
        elif dia.get("concluido"):
            return "var(--success)", "var(--success)", "✓"
        else:
            return "var(--error-bg)", "var(--error)", "·"
    
    def _extrair_dia_mes(self, data_str: str) -> str:
        """Extrai dia do mês da data de forma segura."""
        try:
            if len(data_str) >= 10:
                return data_str[8:10]
            return ""
        except Exception as e:
            logger.debug(f"Erro ao extrair dia do mês: {e}")
            return ""
    
    def _render_legenda(self) -> None:
        """Renderiza legenda do calendário."""
        st.markdown(
            """
            <div style="display: flex; gap: 1.2rem; margin-top: 0.6rem;
                font-size: 0.76rem; color: var(--text-muted);">
                <span style="display: flex; align-items: center; gap: 0.35rem;">
                    <span style="width: 13px; height: 13px; border-radius: 3px;
                        background: var(--success); display: inline-block;"></span>
                    Concluído
                </span>
                <span style="display: flex; align-items: center; gap: 0.35rem;">
                    <span style="width: 13px; height: 13px; border-radius: 3px;
                        background: var(--error-bg); border: 1px solid var(--error);
                        display: inline-block;"></span>
                    Não feito
                </span>
                <span style="display: flex; align-items: center; gap: 0.35rem;">
                    <span style="width: 13px; height: 13px; border-radius: 3px;
                        background: var(--surface-2); border: 1px solid var(--border);
                        display: inline-block;"></span>
                    Futuro
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_mensagem_motivacional(self, streak: int, aderencia_7: float) -> None:
        """Renderiza mensagem motivacional."""
        mensagem = self._get_mensagem_motivacional(streak, aderencia_7)
        
        if mensagem:
            st.markdown(
                f"""
                <div class="{mensagem['classe']}" style="margin-top: 0.8rem;">
                    {mensagem['texto']}
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    def _get_mensagem_motivacional(self, streak: int, aderencia_7: float) -> Optional[Dict]:
        """Retorna mensagem motivacional baseada no streak e aderência."""
        if streak >= self.STREAK_LENDA:
            return {
                "classe": "alert-success",
                "texto": "🏆 Incrível! 30+ dias seguidos. Esse hábito já é parte de você."
            }
        elif streak >= self.STREAK_DESTAQUE:
            return {
                "classe": "alert-success",
                "texto": f"🔥 {streak} dias seguidos! Você está construindo algo sólido."
            }
        elif streak == 0 and aderencia_7 < self.ADERENCIA_BOM:
            return {
                "classe": "alert-warning",
                "texto": "⚡ Aderência baixa esta semana. Que tal começar hoje?"
            }
        
        return None


# Função de compatibilidade
def render_detalhe_habito(habito: Dict[str, Any], svc: HabitService) -> None:
    """Renderiza detalhe de hábito (compatibilidade)."""
    renderer = HabitDetailRenderer(svc)
    renderer.render(habito)
