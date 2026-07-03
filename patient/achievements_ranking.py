"""
Melshape — Ranking de Gamificação.
View usada: vw_ranking_gamificacao
"""
import streamlit as st
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

from views.components.cards import empty_state, metric_card

logger = logging.getLogger("Melshape.Ranking")

MEDALHAS = {1: "🥇", 2: "🥈", 3: "🥉"}


@dataclass
class RankingEntry:
    """Entrada do ranking."""
    position: int
    name: str
    xp: int
    level: str
    badges: int
    is_user: bool = False


@dataclass
class RankingStats:
    """Estatísticas do ranking."""
    total_participants: int = 0
    user_position: Optional[int] = None
    avg_xp: int = 0
    top_xp: int = 0


class RankingRenderer:
    """Renderer dedicado para ranking."""
    
    def __init__(self, db, user: Dict[str, Any]):
        self.db = db
        self.user = user
        self.user_name = user.get("name", "")
        self.user_id = self._get_user_id()
        
        # Cache de dados para evitar múltiplas consultas
        self._ranking_cache: Optional[List[Dict]] = None
    
    def _get_user_id(self) -> Optional[str]:
        """Obtém ID do usuário de forma segura."""
        if hasattr(self.db, "uid"):
            try:
                return self.db.uid()
            except Exception as e:
                logger.debug(f"Erro ao obter user_id: {e}")
        return None
    
    def render(self) -> None:
        """Renderiza ranking completo."""
        ranking_data = self._buscar_ranking()
        
        if not ranking_data:
            self._render_empty_state()
            return
        
        # Calcula estatísticas
        stats = self._calcular_estatisticas(ranking_data)
        
        # Mostra estatísticas gerais
        self._render_stats_gerais(stats)
        
        # Mostra posição do usuário
        self._render_user_position(stats)
        
        # Mostra lista do ranking
        self._render_ranking_list(ranking_data)
    
    @st.cache_data(ttl=60)
    def _buscar_ranking(_self) -> List[Dict]:
        """Busca ranking do banco (com cache)."""
        if not (_self._is_real_db() and hasattr(_self.db, "client")):
            return []
        
        try:
            response = (
                _self.db.client
                .table("vw_ranking_gamificacao")
                .select("nome_completo,xp_total,nivel,total_badges")
                .order("xp_total", desc=True)
                .limit(50)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Erro ao buscar ranking: {e}", exc_info=True)
            return []
    
    def _is_real_db(self) -> bool:
        """Verifica se o banco é real (não mock)."""
        return hasattr(self.db, "is_real") and self.db.is_real
    
    def _calcular_estatisticas(self, ranking: List[Dict]) -> RankingStats:
        """Calcula estatísticas do ranking."""
        if not ranking:
            return RankingStats()
        
        # Encontra posição do usuário
        user_position = None
        for idx, row in enumerate(ranking):
            nome = row.get("nome_completo", "")
            if self._is_current_user(nome, row):
                user_position = idx + 1
                break
        
        # Calcula métricas
        xp_values = [int(row.get("xp_total") or 0) for row in ranking]
        
        return RankingStats(
            total_participants=len(ranking),
            user_position=user_position,
            avg_xp=sum(xp_values) // len(xp_values) if xp_values else 0,
            top_xp=max(xp_values) if xp_values else 0,
        )
    
    def _is_current_user(self, nome: str, row: Dict) -> bool:
        """Verifica se a linha pertence ao usuário atual."""
        # Tenta identificar por user_id primeiro
        if self.user_id and hasattr(row, "get"):
            row_user_id = row.get("perfil_id") or row.get("user_id")
            if row_user_id and row_user_id == self.user_id:
                return True
        
        # Fallback para nome
        return nome == self.user_name
    
    def _render_stats_gerais(self, stats: RankingStats) -> None:
        """Renderiza estatísticas gerais do ranking."""
        col1, col2, col3 = st.columns(3)
        
        with col1:
            metric_card(
                str(stats.total_participants),
                "Participantes",
                "👥"
            )
        
        with col2:
            metric_card(
                self._format_number(stats.avg_xp),
                "XP Médio",
                "📊"
            )
        
        with col3:
            metric_card(
                self._format_number(stats.top_xp),
                "Top XP",
                "🏆"
            )
        
        st.divider()
    
    def _format_number(self, value: int) -> str:
        """Formata número com separadores de milhar."""
        return f"{value:,}".replace(",", ".")
    
    def _render_empty_state(self) -> None:
        """Renderiza estado vazio do ranking."""
        empty_state(
            "🏆", "Ranking em construção",
            "Seja o primeiro a aparecer aqui!",
        )
        
        # Mostra XP do usuário mesmo sem ranking
        if hasattr(self.db, "get_xp"):
            try:
                xp_proprio = self.db.get_xp()
                if xp_proprio > 0:
                    metric_card(
                        self._format_number(xp_proprio),
                        "Seu XP total",
                        "⭐"
                    )
            except Exception as e:
                logger.debug(f"Erro ao buscar XP do usuário: {e}")
    
    def _render_user_position(self, stats: RankingStats) -> None:
        """Renderiza posição do usuário no ranking."""
        if not stats.user_position:
            return
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="
                border-color: var(--primary); margin-bottom: 1rem;">
                <div style="font-size: 0.76rem; color: var(--text-muted);
                    margin-bottom: 0.3rem;">Sua posição</div>
                <div style="font-size: 2.2rem; font-weight: 800; color: var(--primary);">
                    #{stats.user_position}
                </div>
                <div style="font-size: 0.80rem; color: var(--text-muted);">
                    de {stats.total_participants} participantes
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_ranking_list(self, ranking: List[Dict]) -> None:
        """Renderiza lista do ranking."""
        st.markdown(
            f"""
            <div style="font-size: 0.85rem; color: var(--text-muted);
                margin-bottom: 0.8rem;">
                Top <b>{len(ranking)}</b> · atualizado agora
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        for idx, row in enumerate(ranking):
            entry = self._create_ranking_entry(idx, row)
            self._render_ranking_entry(entry)
    
    def _create_ranking_entry(self, idx: int, row: Dict) -> RankingEntry:
        """Cria objeto de entrada do ranking."""
        return RankingEntry(
            position=idx + 1,
            name=row.get("nome_completo", "—"),
            xp=self._parse_int(row.get("xp_total")),
            level=row.get("nivel", "Iniciante"),
            badges=self._parse_int(row.get("total_badges")),
            is_user=self._is_current_user(row.get("nome_completo", ""), row)
        )
    
    def _parse_int(self, value: Any) -> int:
        """Converte valor para int de forma segura."""
        try:
            return int(value or 0)
        except (ValueError, TypeError):
            return 0
    
    def _render_ranking_entry(self, entry: RankingEntry) -> None:
        """Renderiza uma entrada do ranking."""
        medalha = self._get_medalha(entry.position)
        cor_borda = self._get_cor_borda(entry)
        bg = "background: var(--primary-light);" if entry.is_user else ""
        
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 0.75rem;
                padding: 0.7rem 0.85rem; border: 1px solid var(--border);
                border-radius: 12px; margin-bottom: 0.5rem;
                background: var(--surface); {cor_borda} {bg}">
                <div style="font-size: 1.3rem; width: 32px; text-align: center;
                    flex-shrink: 0;">{medalha}</div>
                <div style="flex: 1;">
                    <div style="font-weight: {"800" if entry.is_user else "600"};
                        font-size: 0.92rem; color: var(--text);">
                        {entry.name}{"  👈 você" if entry.is_user else ""}
                    </div>
                    <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.15rem;">
                        {entry.level} · {entry.badges} badges
                    </div>
                </div>
                <div style="font-weight: 700; color: var(--primary);
                    font-size: 0.95rem;">{self._format_number(entry.xp)} XP</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _get_medalha(self, position: int) -> str:
        """Retorna medalha ou número da posição."""
        return MEDALHAS.get(position, f"#{position}")
    
    def _get_cor_borda(self, entry: RankingEntry) -> str:
        """Retorna cor da borda baseada na posição."""
        if entry.is_user:
            return "border-color: var(--primary); border-width: 2px;"
        elif entry.position <= 3:
            return "border-color: var(--warning); border-width: 2px;"
        elif entry.position <= 10:
            return "border-color: var(--primary);"
        else:
            return ""


# Interface compatível com o sistema existente
def render_ranking(db, user: Dict[str, Any]) -> None:
    """Função principal para renderização do ranking."""
    renderer = RankingRenderer(db, user)
    renderer.render()
