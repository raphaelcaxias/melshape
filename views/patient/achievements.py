"""
Melshape — Tela de Conquistas, Ranking e Desafios.

Views usadas:
  vw_ranking_gamificacao   → ranking global de XP
  vw_conquistas_usuario    → badges do paciente
  vw_recompensa_pendente   → XP a resgatar

Tabelas:
  badges                   → catálogo completo de badges
  desafios, desafios_usuario → desafios ativos e progresso
"""
import streamlit as st
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from services.gamification_service import GamificationService, ACHIEVEMENTS
from views.components.cards import (
    section_header, empty_state, metric_card,
    achievement_card, challenge_card, show_new_achievements,
)
from views.patient.achievements_ranking import render_ranking
from views.patient.achievements_challenges import render_desafios


@dataclass
class AchievementStats:
    """Estatísticas de conquistas do usuário."""
    xp: int = 0
    level_number: int = 1
    level_name: str = "Iniciante"
    level_icon: str = "🌱"
    total_badges: int = 0
    streak: int = 0
    progress_pct: int = 0
    next_level: Optional[str] = None
    xp_to_next: int = 0


class AchievementsRenderer:
    """Renderer dedicado para tela de conquistas."""
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user
        self.db = services.get("db")
        self.gami = GamificationService(self.db)
        
        # Cache de dados para evitar múltiplas consultas ao banco no mesmo render
        self._raw_stats: Dict[str, Any] = {}
        self._user_achievements: List[Dict[str, Any]] = []
    
    def render(self) -> None:
        """Renderiza tela completa de conquistas."""
        section_header("🏆 Conquistas", "Seu histórico de vitórias e evolução")
        
        # 1. Busca dados do banco UMA ÚNICA VEZ por ciclo de renderização
        self._fetch_data()
        
        # 2. Verifica conquistas novas ao entrar
        novos = self.gami.check_achievements(self.user)
        show_new_achievements(novos) # Correção do typo: novs -> novos
        
        # 3. Renderiza componentes
        self._render_stats()
        
        tab_badges, tab_desafios, tab_ranking = st.tabs([
            "🏅 Badges",
            "🎯 Desafios",
            "🏆 Ranking",
        ])
        
        with tab_badges:
            self._render_badges_tab()
        
        with tab_desafios:
            render_desafios(self.db, self.gami)
        
        with tab_ranking:
            render_ranking(self.db, self.user)

    def _fetch_data(self) -> None:
        """Busca dados do banco e armazena na instância para evitar múltiplas queries."""
        try:
            self._raw_stats = self.gami.quick_stats() or {}
            self._user_achievements = self.db.get_achievements() or []
        except Exception as e:
            st.error(f"Erro ao carregar dados de gamificação: {e}")
            self._raw_stats = {}
            self._user_achievements = []
    
    def _render_stats(self) -> None:
        """Renderiza cabeçalho com estatísticas do usuário."""
        stats = self._get_stats()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            metric_card(str(stats.xp), "XP Total", "⭐")
        
        with col2:
            metric_card(
                f'{stats.level_icon} {stats.level_number}',
                stats.level_name,
                "🎖️"
            )
        
        with col3:
            metric_card(str(stats.total_badges), "Badges", "🏅")
        
        with col4:
            metric_card(
                f'{stats.streak}d',
                "Sequência",
                "🔥",
                "success" if stats.streak >= 7 else ""
            )
        
        self._render_xp_progress(stats)
        st.divider()
    
    def _render_xp_progress(self, stats: AchievementStats) -> None:
        """Renderiza barra de progresso de XP."""
        if stats.next_level:
            progress_text = f"→ <b>{stats.next_level}</b> — faltam <b>{stats.xp_to_next} XP</b>"
        else:
            progress_text = "🎉 <b>Nível máximo alcançado!</b>"
        
        st.markdown(
            f"""
            <div style="margin: 0.6rem 0;">
                <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.4rem;">
                    {progress_text}
                </div>
                <div style="background: var(--surface-2); border-radius: 8px; height: 10px; overflow: hidden;">
                    <div style="background: linear-gradient(90deg, #f59e0b, #fbbf24); height: 100%; width: {stats.progress_pct}%; border-radius: 8px; transition: width 0.5s ease;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _get_stats(self) -> AchievementStats:
        """Mapeia o dicionário raw para o dataclass AchievementStats."""
        return AchievementStats(
            xp=self._raw_stats.get("xp", 0),
            level_number=self._raw_stats.get("level_number", 1),
            level_name=self._raw_stats.get("level_name", "Iniciante"),
            level_icon=self._raw_stats.get("level_icon", "🌱"),
            total_badges=self._raw_stats.get("total_badges", 0),
            streak=self._raw_stats.get("streak", 0),
            progress_pct=min(self._raw_stats.get("progress_pct", 0), 100), # Garante que não passe de 100%
            next_level=self._raw_stats.get("next_level"),
            xp_to_next=self._raw_stats.get("xp_to_next", 0),
        )
    
    def _render_badges_tab(self) -> None:
        """Renderiza aba de badges."""
        conquistadas = {
            a.get("achievement_name", "") 
            for a in self._user_achievements
        }
        
        total_cat = len(ACHIEVEMENTS)
        total_ganhas = len(conquistadas)
        
        st.markdown(
            f"""
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
                Você desbloqueou <b>{total_ganhas}</b> de <b>{total_cat}</b> conquistas disponíveis.
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        desbloqueadas = [a for a in ACHIEVEMENTS if a["name"] in conquistadas]
        bloqueadas = [a for a in ACHIEVEMENTS if a["name"] not in conquistadas]
        
        if not desbloqueadas and not bloqueadas:
            empty_state("🏅", "Sem badges no catálogo", "O catálogo de conquistas está vazio.")
            return

        if desbloqueadas:
            self._render_badge_grid(desbloqueadas, is_locked=False)
        
        if bloqueadas:
            self._render_badge_grid(bloqueadas, is_locked=True)
    
    def _render_badge_grid(self, badges: List[Dict], is_locked: bool) -> None:
        """Renderiza um grid de badges (desbloqueadas ou bloqueadas)."""
        title = "🔒 Em progresso" if is_locked else "✨ Conquistadas"
        opacity = "0.6" if is_locked else "1"
        
        st.markdown(
            f"""
            <div style="font-size: 0.75rem; font-weight: 700; letter-spacing: 0.06em; 
                color: var(--text-faint); text-transform: uppercase; 
                margin: 1rem 0 0.5rem;">
                {title}
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Usa 3 colunas para um grid mais denso e visualmente agradável
        cols = st.columns(3) 
        for idx, badge in enumerate(badges):
            with cols[idx % 3]:
                if not is_locked:
                    achievement_card(badge["title"], f'+{badge.get("xp", 0)} XP')
                else:
                    st.markdown(
                        f"""
                        <div style="background: var(--surface-2); border: 1px solid var(--border); 
                            border-radius: 12px; padding: 0.8rem; margin-bottom: 0.5rem; 
                            opacity: {opacity}; transition: transform 0.2s;">
                            <div style="font-size: 1.2rem;">🔒</div>
                            <div style="font-size: 0.85rem; font-weight: 600; 
                                color: var(--text-muted); margin-top: 0.3rem;">
                                {badge["title"]}
                            </div>
                            <div style="font-size: 0.75rem; color: var(--text-faint); margin-top: 0.2rem;">
                                {badge.get("desc", "Desafio oculto")}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )


def render(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Função principal de renderização (Entry point)."""
    renderer = AchievementsRenderer(services, user)
    renderer.render()
