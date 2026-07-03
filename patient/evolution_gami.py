"""
Melshape — Evolução: aba conquistas (hall da fama + carteira + XP).
"""
import streamlit as st
from typing import Dict, Any, List, Optional
import pandas as pd
import logging

from services.evolution_service import EvolutionService
from services.contextualizer import ctx
from views.components.cards import empty_state, metric_card

logger = logging.getLogger("Melshape.Gami")


class GamiRenderer:
    """Renderer dedicado para aba de conquistas da evolução."""
    
    # Constantes de medalhas
    MEDALHAS = {0: "🥇", 1: "🥈", 2: "🥉"}
    
    # Constantes de limiares de moedas
    MOEDAS_EXCELENTE = 500
    MOEDAS_BOM = 100
    
    # Constantes de limites
    MAX_CAMPEOES_HALL = 5
    MAX_CAMPEOES_BUSCA = 10
    MAX_HISTORICO_XP = 30
    
    def __init__(self, svc: EvolutionService, user: Dict[str, Any]):
        self.svc = svc
        self.user = user
        self.nome = self._get_nome_usuario()
    
    def _get_nome_usuario(self) -> str:
        """Obtém nome do usuário de forma segura."""
        try:
            return self.user.get("name", "")
        except Exception as e:
            logger.debug(f"Erro ao obter nome do usuário: {e}")
            return ""
    
    def render(self) -> None:
        """Renderiza aba de conquistas."""
        # Carteira de recompensas
        self._render_carteira()
        
        # Hall da Fama
        self._render_hall_da_fama()
        
        # Histórico XP
        self._render_historico_xp()
    
    def _render_carteira(self) -> None:
        """Renderiza carteira de recompensas."""
        st.markdown("##### 💰 Carteira de Recompensas")
        
        carteira = self._get_carteira()
        moedas = self._parse_moedas(carteira)
        moedas_msg = self._formatar_mensagem_moedas(moedas)
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="margin-bottom: 1rem;">
                <div style="display: flex; align-items: center; gap: 0.8rem;">
                    <span style="font-size: 2.2rem;">🪙</span>
                    <div>
                        <div style="font-size: 1.7rem; font-weight: 800; color: var(--primary);">
                            {moedas}
                        </div>
                        <div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.2rem;">
                            {moedas_msg}
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    @st.cache_data(ttl=60)
    def _get_carteira(_self) -> Dict[str, Any]:
        """Obtém carteira de recompensas (com cache)."""
        try:
            carteira = _self.svc.get_carteira()
            return carteira or {}
        except Exception as e:
            logger.error(f"Erro ao buscar carteira: {e}", exc_info=True)
            return {}
    
    def _parse_moedas(self, carteira: Dict[str, Any]) -> int:
        """Parse moedas de forma segura."""
        try:
            moedas = carteira.get("moedas", 0)
            return int(moedas) if moedas is not None else 0
        except (ValueError, TypeError) as e:
            logger.warning(f"Erro ao parsear moedas: {e}")
            return 0
    
    def _formatar_mensagem_moedas(self, moedas: int) -> str:
        """Formata mensagem contextualizada baseada no saldo de moedas."""
        if moedas >= self.MOEDAS_EXCELENTE:
            return f"Você tem {moedas} moedas — saldo excelente para resgatar recompensas!"
        elif moedas >= self.MOEDAS_BOM:
            return f"{moedas} moedas acumuladas. Continue engajado para resgatar benefícios."
        else:
            return f"{moedas} moedas. Faça check-ins e complete hábitos para acumular mais."
    
    def _render_hall_da_fama(self) -> None:
        """Renderiza Hall da Fama."""
        st.markdown("##### 🏆 Hall da Fama — Top Transformação")
        
        campeoes = self._get_campeoes()
        
        if not campeoes:
            empty_state(
                "🏆",
                "Hall da fama em construção",
                "Seja consistente para aparecer aqui!",
            )
            return
        
        # Posição do usuário
        minha_pos = self._encontrar_posicao_usuario(campeoes)
        
        if minha_pos:
            self._render_posicao_usuario(minha_pos)
        
        # Top 5
        for i, campeao in enumerate(campeoes[:self.MAX_CAMPEOES_HALL]):
            self._render_campeao_item(i, campeao)
    
    @st.cache_data(ttl=60)
    def _get_campeoes(_self) -> List[Dict]:
        """Obtém lista de campeões (com cache)."""
        try:
            campeoes = _self.svc.get_campeoes(limit=_self.MAX_CAMPEOES_BUSCA)
            return campeoes or []
        except Exception as e:
            logger.error(f"Erro ao buscar campeões: {e}", exc_info=True)
            return []
    
    def _encontrar_posicao_usuario(self, campeoes: List[Dict]) -> Optional[int]:
        """Encontra posição do usuário no hall da fama."""
        try:
            for i, c in enumerate(campeoes):
                if c.get("nome_completo", "") == self.nome:
                    return i + 1
        except Exception as e:
            logger.debug(f"Erro ao encontrar posição do usuário: {e}")
        
        return None
    
    def _render_posicao_usuario(self, posicao: int) -> None:
        """Renderiza posição do usuário no hall da fama."""
        st.markdown(
            f"""
            <div style="font-size: 0.86rem; color: var(--primary);
                font-weight: 700; margin-bottom: 0.6rem;">
                🎯 Você está em #{posicao} no hall da fama!
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_campeao_item(self, posicao: int, campeao: Dict[str, Any]) -> None:
        """Renderiza um item do Hall da Fama."""
        medalha = self._get_medalha(posicao)
        nome = campeao.get("nome_completo", "—")
        score = self._parse_score(campeao)
        eh_eu = nome == self.nome
        
        destaque = "font-weight: 800; color: var(--primary);" if eh_eu else ""
        badge_voce = "  👈 você" if eh_eu else ""
        
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between; align-items: center;
                padding: 0.5rem 0; border-bottom: 1px solid var(--border-subtle);">
                <span style="{destaque} font-size: 0.9rem;">
                    {medalha} {nome}{badge_voce}
                </span>
                <span style="font-weight: 700; color: var(--primary); font-size: 0.9rem;">
                    {score:.0f} pts
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _get_medalha(self, posicao: int) -> str:
        """Retorna medalha ou número da posição."""
        return self.MEDALHAS.get(posicao, f"#{posicao + 1}")
    
    def _parse_score(self, campeao: Dict[str, Any]) -> float:
        """Parse score de forma segura."""
        try:
            score = campeao.get("score", 0)
            return float(score) if score is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def _render_historico_xp(self) -> None:
        """Renderiza histórico de XP."""
        st.markdown("---")
        st.markdown("##### 📈 Histórico de XP (30 dias)")
        
        historico = self._get_historico_xp()
        
        if not historico:
            empty_state(
                "📊",
                "Nenhum XP registrado",
                "Faça check-ins e complete hábitos para acumular XP",
            )
            return
        
        # Gráfico ou resumo
        if len(historico) >= 2:
            self._render_xp_grafico(historico)
        else:
            self._render_resumo_xp_simples(historico)
    
    @st.cache_data(ttl=60)
    def _get_historico_xp(_self) -> List[Dict]:
        """Obtém histórico de XP (com cache)."""
        try:
            historico = _self.svc.get_historico_xp(days=_self.MAX_HISTORICO_XP)
            return historico or []
        except Exception as e:
            logger.error(f"Erro ao buscar histórico XP: {e}", exc_info=True)
            return []
    
    def _render_resumo_xp_simples(self, historico: List[Dict]) -> None:
        """Renderiza resumo simples de XP quando há poucos dados."""
        total_xp = self._calcular_total_xp(historico)
        
        st.markdown(
            f"""
            <div style="font-size: 0.86rem; color: var(--text-muted); margin-top: 0.5rem;">
                XP total (30d): <b>{total_xp} XP</b>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_xp_grafico(self, historico: List[Dict]) -> None:
        """Renderiza gráfico de XP."""
        try:
            import plotly.express as px
            
            df = self._preparar_dataframe_xp(historico)
            
            if df.empty:
                logger.warning("DataFrame de XP está vazio")
                return
            
            fig = self._criar_grafico_xp(df)
            st.plotly_chart(fig, use_container_width=True)
            
            # Narrativa contextualizada
            total_xp = self._calcular_total_xp(historico)
            self._render_narrativa_xp(total_xp)
            
        except ImportError:
            logger.warning("Plotly não disponível para renderizar gráfico de XP")
            self._render_resumo_xp_simples(historico)
        except Exception as e:
            logger.error(f"Erro ao renderizar gráfico de XP: {e}", exc_info=True)
            self._render_resumo_xp_simples(historico)
    
    def _preparar_dataframe_xp(self, historico: List[Dict]) -> pd.DataFrame:
        """Prepara DataFrame para gráfico de XP."""
        try:
            df = pd.DataFrame(historico)
            
            if "data" not in df.columns or "xp_ganho" not in df.columns:
                logger.warning("Colunas necessárias não encontradas no histórico XP")
                return pd.DataFrame()
            
            df["data"] = pd.to_datetime(df["data"], errors="coerce")
            df = df.dropna(subset=["data", "xp_ganho"])
            
            return df
        except Exception as e:
            logger.error(f"Erro ao preparar DataFrame de XP: {e}", exc_info=True)
            return pd.DataFrame()
    
    def _criar_grafico_xp(self, df: pd.DataFrame) -> Any:
        """Cria gráfico Plotly de XP."""
        import plotly.express as px
        
        fig = px.bar(
            df,
            x="data",
            y="xp_ganho",
            title="XP ganho por dia",
            labels={"data": "Data", "xp_ganho": "XP"},
            color_discrete_sequence=["#C9A84C"],
        )
        
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#6B6B6B",
            margin=dict(t=40, b=10, l=0, r=0),
            height=250,
        )
        
        return fig
    
    def _calcular_total_xp(self, historico: List[Dict]) -> int:
        """Calcula total de XP de forma segura."""
        try:
            total = sum(r.get("xp_ganho", 0) for r in historico)
            return int(total)
        except (ValueError, TypeError) as e:
            logger.warning(f"Erro ao calcular total XP: {e}")
            return 0
    
    def _render_narrativa_xp(self, total_xp: int) -> None:
        """Renderiza narrativa contextualizada do XP."""
        try:
            score = min(100, total_xp / 10)
            narrativa = ctx.score(score)
            
            st.markdown(
                f"""
                <div style="font-size: 0.86rem; color: var(--text-muted); margin-top: 0.5rem;">
                    {narrativa}
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.debug(f"Erro ao renderizar narrativa XP: {e}")


# Função de compatibilidade
def _tab_conquistas(svc: EvolutionService, user: Dict[str, Any]) -> None:
    """Renderiza aba conquistas (compatibilidade)."""
    renderer = GamiRenderer(svc, user)
    renderer.render()
