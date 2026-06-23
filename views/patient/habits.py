"""
Melshape — Tela de Hábitos.

O paciente vê seus hábitos do dia e marca com 1 clique.
Streak, aderência e calendário visual por hábito.
Cria hábitos padrão do pilar automaticamente na primeira vez.
"""
import streamlit as st
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
import logging

from services.habit_service import HabitService
from views.components.cards import (
    section_header, empty_state, metric_card,
    show_new_achievements, xp_toast, alert,
)
from views.patient.habits_detail import render_detalhe_habito
from views.patient.habits_form import _tab_novo
from views.patient.habits_suplementos import render_tab_suplementos
from views.patient.habits_treinos import render_tab_treinos

logger = logging.getLogger("Melshape.Habits")


# Constantes de categorias
CATEGORIAS = {
    "hidratacao": ("💧", "Hidratação"),
    "nutricao": ("🥩", "Nutrição"),
    "movimento": ("🚶", "Movimento"),
    "treino": ("🏋️", "Treino"),
    "sono": ("😴", "Sono"),
    "registro": ("✅", "Registro"),
    "suplementos": ("💊", "Suplementos"),
    "saude": ("🩺", "Saúde"),
    "medicamento": ("💉", "Medicamento"),
    "alimentacao": ("🍽️", "Alimentação"),
    "monitoramento": ("📊", "Monitoramento"),
    "geral": ("⭐", "Geral"),
}


@dataclass
class HabitStats:
    """Estatísticas de hábitos."""
    total: int = 0
    feitos_hoje: int = 0
    aderencia: float = 0.0
    melhor_streak: int = 0


class HabitsRenderer:
    """Renderer dedicado para tela de hábitos."""
    
    # Constantes de limiares de aderência
    ADERENCIA_EXCELENTE = 80
    ADERENCIA_BOM = 50
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user
        self.db = services.get("db")
        self.svc = self._init_habit_service()
        self.gami = services.get("gamification")
        self.health_mode = user.get("health_mode", "general")
    
    def _init_habit_service(self) -> Optional[HabitService]:
        """Inicializa HabitService com tratamento de erros."""
        if not self.db:
            logger.error("Database não disponível para HabitsRenderer")
            return None
        
        try:
            return HabitService(self.db)
        except Exception as e:
            logger.error(f"Erro ao inicializar HabitService: {e}", exc_info=True)
            return None
    
    def render(self) -> None:
        """Renderiza tela de hábitos."""
        section_header("📋 Hábitos", "Pequenas ações diárias que geram transformação")
        
        # Verifica se serviço foi inicializado
        if not self.svc:
            self._render_error_state()
            return
        
        # Inicializa hábitos padrão se necessário
        self._inicializar_habitos_padrao()
        
        # Dados
        habitos = self._get_habitos()
        feitos_hoje = self._get_registros_hoje()
        
        # Bloco de estatísticas
        self._render_stats(habitos, feitos_hoje)
        
        st.divider()
        
        # Tabs
        self._render_tabs(habitos, feitos_hoje)
    
    def _render_error_state(self) -> None:
        """Renderiza estado de erro quando serviço não está disponível."""
        alert(
            "❌ Não foi possível carregar o módulo de hábitos. "
            "Por favor, recarregue a página ou entre em contato com o suporte.",
            "error",
        )
    
    def _inicializar_habitos_padrao(self) -> None:
        """Inicializa hábitos padrão do pilar."""
        try:
            criados = self.svc.inicializar_habitos_padrao(self.health_mode)
            if criados:
                st.toast(f"✨ {criados} hábitos do seu pilar foram criados!", icon="🎉")
                # Limpa cache após criar hábitos
                st.cache_data.clear()
        except Exception as e:
            logger.error(f"Erro ao inicializar hábitos padrão: {e}", exc_info=True)
    
    @st.cache_data(ttl=60)
    def _get_habitos(_self) -> List[Dict]:
        """Obtém lista de hábitos (com cache)."""
        try:
            habitos = _self.db.get_habitos()
            return habitos or []
        except Exception as e:
            logger.error(f"Erro ao buscar hábitos: {e}", exc_info=True)
            return []
    
    @st.cache_data(ttl=30)
    def _get_registros_hoje(_self) -> Set[str]:
        """Obtém IDs de hábitos já registrados hoje (com cache)."""
        try:
            registros = _self.db.get_registros_hoje()
            return set(registros) if registros else set()
        except Exception as e:
            logger.error(f"Erro ao buscar registros de hoje: {e}", exc_info=True)
            return set()
    
    def _render_tabs(self, habitos: List[Dict], feitos_hoje: Set[str]) -> None:
        """Renderiza as 5 tabs de hábitos."""
        tab_hoje, tab_detalhe, tab_novo, tab_supl, tab_treino = st.tabs([
            "📅 Hoje",
            "📈 Detalhe",
            "➕ Novo Hábito",
            "💊 Suplementos",
            "🏋️ Treinos",
        ])
        
        with tab_hoje:
            self._render_tab_hoje(habitos, feitos_hoje)
        
        with tab_detalhe:
            self._render_tab_detalhe(habitos)
        
        with tab_novo:
            self._render_tab_novo()
        
        with tab_supl:
            self._render_tab_supl()
        
        with tab_treino:
            self._render_tab_treino()
    
    def _render_tab_hoje(self, habitos: List[Dict], feitos_hoje: Set[str]) -> None:
        """Renderiza tab de hoje com tratamento de erros."""
        try:
            from views.patient.habits_today import _tab_hoje
            _tab_hoje(habitos, feitos_hoje, self.svc, self.gami, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab Hoje: {e}", exc_info=True)
            alert("❌ Erro ao carregar hábitos de hoje.", "error")
    
    def _render_tab_detalhe(self, habitos: List[Dict]) -> None:
        """Renderiza tab de detalhe com tratamento de erros."""
        try:
            from views.patient.habits_today import _tab_detalhe
            _tab_detalhe(habitos, self.svc)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab Detalhe: {e}", exc_info=True)
            alert("❌ Erro ao carregar detalhes dos hábitos.", "error")
    
    def _render_tab_novo(self) -> None:
        """Renderiza tab de novo hábito com tratamento de erros."""
        try:
            _tab_novo(self.db, self.svc, self.health_mode)
        except Exception as e:
            logger.error(f"Erro ao renderizar formulário de novo hábito: {e}", exc_info=True)
            alert("❌ Erro ao carregar formulário de novo hábito.", "error")
    
    def _render_tab_supl(self) -> None:
        """Renderiza tab de suplementos com tratamento de erros."""
        try:
            render_tab_suplementos(self.db, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab Suplementos: {e}", exc_info=True)
            alert("❌ Erro ao carregar suplementos.", "error")
    
    def _render_tab_treino(self) -> None:
        """Renderiza tab de treinos com tratamento de erros."""
        try:
            render_tab_treinos(self.db, self.user, self.services)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab Treinos: {e}", exc_info=True)
            alert("❌ Erro ao carregar treinos.", "error")
    
    def _render_stats(self, habitos: List[Dict], feitos_hoje: Set[str]) -> None:
        """Renderiza estatísticas de hábitos."""
        if not habitos:
            return
        
        stats = self._calculate_stats(habitos, feitos_hoje)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            cor = self._get_cor_habitos_hoje(stats.feitos_hoje, stats.total)
            metric_card(
                f"{stats.feitos_hoje}/{stats.total}",
                "Hábitos hoje",
                "✅",
                cor
            )
        
        with col2:
            cor = self._get_cor_aderencia(stats.aderencia)
            metric_card(
                f"{stats.aderencia:.0f}%",
                "Aderência (7d)",
                "📊",
                cor
            )
        
        with col3:
            metric_card(
                str(stats.melhor_streak),
                "Melhor streak",
                "🔥"
            )
        
        # Mensagem de todos concluídos
        if stats.feitos_hoje == stats.total and stats.total > 0:
            alert("🎉 Todos os hábitos do dia concluídos!", "success")
    
    def _calculate_stats(self, habitos: List[Dict], feitos_hoje: Set[str]) -> HabitStats:
        """Calcula estatísticas de hábitos."""
        try:
            total = len(habitos)
            feitos = sum(1 for h in habitos if h.get("id") in feitos_hoje)
            aderencia = self._calcular_aderencia()
            melhor_streak = self._calcular_melhor_streak(habitos)
            
            return HabitStats(
                total=total,
                feitos_hoje=feitos,
                aderencia=aderencia,
                melhor_streak=melhor_streak,
            )
        except Exception as e:
            logger.error(f"Erro ao calcular estatísticas de hábitos: {e}", exc_info=True)
            return HabitStats()
    
    def _calcular_aderencia(self) -> float:
        """Calcula aderência geral com tratamento de erros."""
        try:
            aderencia = self.svc.aderencia_geral(days=7)
            return max(0.0, min(aderencia, 100.0))  # Garante entre 0 e 100
        except Exception as e:
            logger.error(f"Erro ao calcular aderência: {e}")
            return 0.0
    
    def _calcular_melhor_streak(self, habitos: List[Dict]) -> int:
        """Calcula o melhor streak entre todos os hábitos."""
        if not habitos:
            return 0
        
        try:
            streaks = []
            for h in habitos:
                habito_id = h.get("id")
                if habito_id:
                    streak = self.svc.streak_habito(habito_id)
                    streaks.append(streak)
            
            return max(streaks, default=0)
        except Exception as e:
            logger.error(f"Erro ao calcular melhor streak: {e}")
            return 0
    
    def _get_cor_habitos_hoje(self, feitos: int, total: int) -> str:
        """Retorna cor baseada no status dos hábitos de hoje."""
        if total == 0:
            return ""
        elif feitos == total:
            return "success"
        elif feitos > 0:
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


# Função principal de compatibilidade
def render(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = HabitsRenderer(services, user)
    renderer.render()
