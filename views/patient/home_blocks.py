"""
Melshape — Home: blocos de progresso, XP, desafio e peso.
Usa contextualizer para nunca exibir número cru sem narrativa.
"""
import streamlit as st
from typing import Dict, Any, Optional, List
import logging

from views.components.cards import (
    empty_state, challenge_card, alert, metric_card,
)
from services.contextualizer import ctx
import config

logger = logging.getLogger("Melshape.HomeBlocks")


# Constantes de limites
LIMITE_ALERTA_CALORIAS = 85
LIMITE_PERIGO_CALORIAS = 100
LIMITE_SUCESSO_PROTEINA = 80
MAX_DESAFIOS_EXIBIDOS = 2


class HomeBlocksRenderer:
    """Renderer para blocos da home."""
    
    def __init__(self, db, nutr, user: Dict[str, Any]):
        self.db = db
        self.nutr = nutr
        self.user = user or {}
    
    def render_progresso_dia(self, sm: Dict, hydration: int) -> None:
        """Renderiza bloco de progresso do dia."""
        self._render_header_bloco("Progresso de Hoje")
        
        # Obtém dados do usuário
        dados_user = self._extrair_dados_usuario()
        
        # Calcula metas nutricionais
        metas = self._calcular_metas_nutricionais(dados_user)
        
        # Obtém consumo de hoje
        cal_hoje = self._parse_float(sm.get("calories", 0))
        prot_hoje = self._parse_float(sm.get("protein", 0))
        hydration_val = self._parse_float(hydration)
        
        # Calcula percentuais
        pct_cal = self._calcular_percentual(cal_hoje, metas["goal_cal"])
        pct_prot = self._calcular_percentual(prot_hoje, metas["goal_prot"])
        pct_agua = self._calcular_percentual(hydration_val, metas["goal_agua"])
        
        # Gera narrativas
        narrativas = self._gerar_narrativas(
            cal_hoje, prot_hoje, hydration_val, metas
        )
        
        # Renderiza cards
        self._render_cards_progresso(
            cal_hoje, prot_hoje, hydration_val,
            pct_cal, pct_prot, pct_agua,
            narrativas
        )
        
        # Alertas nutricionais
        self._render_alertas_nutricionais(
            cal_hoje, prot_hoje,
            metas["goal_cal"], metas["goal_prot"]
        )
    
    def _render_header_bloco(self, titulo: str) -> None:
        """Renderiza cabeçalho de bloco."""
        st.markdown(
            f"""
            <p style="font-size: 0.74rem; font-weight: 700; letter-spacing: 0.08em;
                color: var(--text-faint); text-transform: uppercase;
                margin-bottom: 0.7rem;">
                {titulo}
            </p>
            """,
            unsafe_allow_html=True,
        )
    
    def _extrair_dados_usuario(self) -> Dict[str, Any]:
        """Extrai dados do usuário de forma segura."""
        return {
            "weight": self._parse_float(self.user.get("current_weight")),
            "height": self._parse_float(self.user.get("height")),
            "age": self._parse_int(self.user.get("age")),
            "gender": self.user.get("gender", "female"),
            "health_mode": self.user.get("health_mode", "general"),
            "goal": self.user.get("goal", "lose"),
            "activity": self.user.get("activity_level", "moderate"),
            "goal_weight": self._parse_float(self.user.get("goal_weight")),
        }
    
    def _calcular_metas_nutricionais(self, dados: Dict[str, Any]) -> Dict[str, float]:
        """Calcula metas nutricionais com tratamento de erros."""
        try:
            tmb = self.nutr.calc_tmb(
                dados["weight"],
                dados["height"],
                dados["age"],
                dados["gender"]
            )
            
            goal_cal = self.nutr.calc_goal_calories(
                tmb,
                dados["activity"],
                dados["goal"],
                dados["health_mode"]
            )
            
            goal_prot = self.nutr.calc_protein_goal(
                dados["weight"],
                dados["health_mode"]
            )
            
            goal_agua = self._get_hydration_goal()
            
            return {
                "tmb": tmb,
                "goal_cal": goal_cal,
                "goal_prot": goal_prot,
                "goal_agua": goal_agua,
            }
        except Exception as e:
            logger.error(f"Erro ao calcular metas nutricionais: {e}", exc_info=True)
            return {
                "tmb": 0,
                "goal_cal": 2000,
                "goal_prot": 100,
                "goal_agua": 2000,
            }
    
    @st.cache_data(ttl=60)
    def _get_hydration_goal(_self) -> float:
        """Obtém meta de hidratação (com cache)."""
        try:
            return float(config.HYDRATION_GOAL_ML)
        except Exception as e:
            logger.error(f"Erro ao obter meta de hidratação: {e}")
            return 2000.0
    
    def _parse_float(self, value: Any) -> float:
        """Converte valor para float de forma segura."""
        try:
            return float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def _parse_int(self, value: Any) -> int:
        """Converte valor para int de forma segura."""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def _calcular_percentual(self, atual: float, meta: float) -> int:
        """Calcula percentual de forma segura (evita divisão por zero)."""
        if meta <= 0:
            return 0
        
        try:
            pct = int(atual / meta * 100)
            return min(100, max(0, pct))  # Garante entre 0 e 100
        except Exception as e:
            logger.debug(f"Erro ao calcular percentual: {e}")
            return 0
    
    def _gerar_narrativas(
        self,
        cal_hoje: float,
        prot_hoje: float,
        hydration: float,
        metas: Dict[str, float],
    ) -> Dict[str, str]:
        """Gera narrativas contextualizadas."""
        try:
            return {
                "cal": ctx.calories(cal_hoje, metas["goal_cal"]),
                "prot": ctx.protein(prot_hoje, metas["goal_prot"]),
                "agua": ctx.hydration(hydration, metas["goal_agua"]),
            }
        except Exception as e:
            logger.error(f"Erro ao gerar narrativas: {e}", exc_info=True)
            return {
                "cal": "—",
                "prot": "—",
                "agua": "—",
            }
    
    def _render_cards_progresso(
        self,
        cal_hoje: float,
        prot_hoje: float,
        hydration: float,
        pct_cal: int,
        pct_prot: int,
        pct_agua: int,
        narrativas: Dict[str, str],
    ) -> None:
        """Renderiza cards de progresso nutricional."""
        cor_cal = self._get_cor_calorias(pct_cal)
        cor_prot = self._get_cor_proteina(pct_prot)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            self._render_card_nutricional(
                valor=f"{cal_hoje:.0f} kcal",
                narrativa=narrativas["cal"],
                pct=pct_cal,
                cor=cor_cal,
            )
        
        with col2:
            self._render_card_nutricional(
                valor=f"{prot_hoje:.0f}g",
                narrativa=narrativas["prot"],
                pct=pct_prot,
                cor=cor_prot,
            )
        
        with col3:
            self._render_card_nutricional(
                valor=f"{hydration:.0f}ml",
                narrativa=narrativas["agua"],
                pct=pct_agua,
                cor="",
                cor_barra="var(--info)",
            )
    
    def _get_cor_calorias(self, pct: int) -> str:
        """Retorna cor baseada no percentual de calorias."""
        if pct >= LIMITE_PERIGO_CALORIAS:
            return "danger"
        elif pct >= LIMITE_ALERTA_CALORIAS:
            return "warning"
        else:
            return ""
    
    def _get_cor_proteina(self, pct: int) -> str:
        """Retorna cor baseada no percentual de proteína."""
        return "success" if pct >= LIMITE_SUCESSO_PROTEINA else ""
    
    def _render_card_nutricional(
        self,
        valor: str,
        narrativa: str,
        pct: int,
        cor: str,
        cor_barra: Optional[str] = None,
    ) -> None:
        """Renderiza card nutricional individual."""
        style_barra = f"background: {cor_barra};" if cor_barra else ""
        
        st.markdown(
            f"""
            <div class="metric-card fade-in">
                <div class="metric-value" style="font-size: 1.5rem;">
                    {valor}
                </div>
                <div style="font-size: 0.78rem; color: var(--text-muted);
                    margin-bottom: 0.5rem;">{narrativa}</div>
                <div class="progress-track">
                    <div class="progress-fill {cor}" 
                        style="width: {pct}%; {style_barra}"></div>
                </div>
                <div style="font-size: 0.72rem; color: var(--text-faint);
                    margin-top: 0.25rem;">{pct}% da meta</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_alertas_nutricionais(
        self,
        cal_hoje: float,
        prot_hoje: float,
        goal_cal: float,
        goal_prot: float,
    ) -> None:
        """Renderiza alertas nutricionais."""
        try:
            alert_cal = self.nutr.calorie_alert(cal_hoje, goal_cal)
            alert_prot = self.nutr.protein_alert(prot_hoje, goal_prot)
            
            if alert_cal:
                alert(alert_cal, "warning")
            if alert_prot:
                alert(alert_prot, "warning")
        except Exception as e:
            logger.error(f"Erro ao renderizar alertas nutricionais: {e}", exc_info=True)
    
    def render_xp(self, stats: Dict, dash_pac: Dict) -> None:
        """Renderiza bloco de XP."""
        self._render_header_bloco("Sua Evolução")
        
        # Extrai dados de forma segura
        dados_xp = self._extrair_dados_xp(stats, dash_pac)
        
        # Renderiza card
        self._render_card_xp(dados_xp)
    
    def _extrair_dados_xp(self, stats: Dict, dash_pac: Dict) -> Dict[str, Any]:
        """Extrai dados de XP de forma segura."""
        try:
            return {
                "level_icon": stats.get("level_icon", "🌱"),
                "level_number": stats.get("level_number", 1),
                "level_name": stats.get("level_name", "Iniciante"),
                "xp": stats.get("xp", 0),
                "progress_pct": min(100, max(0, stats.get("progress_pct", 0))),
                "next_level": stats.get("next_level"),
                "xp_to_next": stats.get("xp_to_next", 0),
                "badges": dash_pac.get("total_badges", stats.get("total_badges", 0)),
                "desafios": dash_pac.get("desafios_concluidos", 0),
            }
        except Exception as e:
            logger.error(f"Erro ao extrair dados de XP: {e}", exc_info=True)
            return {
                "level_icon": "🌱",
                "level_number": 1,
                "level_name": "Iniciante",
                "xp": 0,
                "progress_pct": 0,
                "next_level": None,
                "xp_to_next": 0,
                "badges": 0,
                "desafios": 0,
            }
    
    def _render_card_xp(self, dados: Dict[str, Any]) -> None:
        """Renderiza card de XP."""
        pct = dados["progress_pct"]
        next_level = dados["next_level"] or "MAX"
        xp_next = dados["xp_to_next"]
        
        next_level_text = f"→ {next_level}" if dados["next_level"] else "MAX"
        xp_next_html = (
            f'<div style="font-size: 0.78rem; color: var(--text-faint); margin-top: 0.35rem;">'
            f'{xp_next} XP para o próximo nível</div>'
            if xp_next > 0 else ""
        )
        
        st.markdown(
            f"""
            <div class="metric-card fade-in">
                <div style="display: flex; align-items: center; gap: 0.7rem;
                    margin-bottom: 0.6rem;">
                    <span style="font-size: 2rem;">{dados["level_icon"]}</span>
                    <div>
                        <div style="font-weight: 800; font-size: 1.05rem; color: var(--text);">
                            Nível {dados["level_number"]} — {dados["level_name"]}
                        </div>
                        <div style="font-size: 0.80rem; color: var(--text-muted); margin-top: 0.15rem;">
                            {dados["xp"]} XP total
                        </div>
                    </div>
                </div>
                <div class="progress-track">
                    <div class="progress-fill" style="width: {pct}%"></div>
                </div>
                <div class="progress-meta">
                    <span>Progresso</span>
                    <span>{pct}%</span>
                    <span>{next_level_text}</span>
                </div>
                {xp_next_html}
                <div style="display: flex; gap: 1.2rem; margin-top: 0.6rem;">
                    <span style="font-size: 0.80rem; color: var(--text-muted);">
                        🏅 {dados["badges"]} conquistas
                    </span>
                    <span style="font-size: 0.80rem; color: var(--text-muted);">
                        🎯 {dados["desafios"]} desafios
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def render_desafio(self, gami) -> None:
        """Renderiza bloco de desafio."""
        self._render_header_bloco("Desafio da Semana")
        
        desafios = self._get_desafios_semanais(gami)
        
        if not desafios:
            empty_state("🎯", "Nenhum desafio ativo")
            return
        
        for desafio in desafios[:MAX_DESAFIOS_EXIBIDOS]:
            self._render_desafio_item(desafio)
        
        self._render_botao_ver_todos_desafios()
    
    def _get_desafios_semanais(self, gami) -> List[Dict]:
        """Obtém desafios semanais com tratamento de erros."""
        try:
            desafios = gami.weekly_challenges()
            return desafios if isinstance(desafios, list) else []
        except Exception as e:
            logger.error(f"Erro ao obter desafios semanais: {e}", exc_info=True)
            return []
    
    def _render_desafio_item(self, desafio: Dict) -> None:
        """Renderiza item de desafio."""
        try:
            emoji = desafio.get("emoji", "🎯")
            title = desafio.get("title", "Desafio")
            xp = desafio.get("xp", 0)
            challenge_card(emoji, title, xp)
        except Exception as e:
            logger.error(f"Erro ao renderizar desafio: {e}", exc_info=True)
    
    def _render_botao_ver_todos_desafios(self) -> None:
        """Renderiza botão para ver todos os desafios."""
        if st.button(
            "Ver todos os desafios →",
            use_container_width=True,
            key="home_ver_desafios",
        ):
            st.session_state.page = "analysis"
            st.rerun()
    
    def render_peso(self, last_weight: Optional[float]) -> None:
        """Renderiza bloco de peso."""
        self._render_header_bloco("Peso")
        
        if last_weight is None:
            empty_state(
                "⚖️",
                "Sem pesagens",
                "Registre seu peso para ver a evolução",
            )
            return
        
        peso_val = self._parse_float(last_weight)
        goal_w = self._extrair_goal_weight()
        msg_peso = self._gerar_narrativa_peso(peso_val, goal_w)
        
        self._render_card_peso(peso_val, msg_peso)
        self._render_botao_registrar_peso()
    
    def _extrair_goal_weight(self) -> Optional[float]:
        """Extrai peso meta de forma segura."""
        try:
            goal_w = self.user.get("goal_weight")
            return float(goal_w) if goal_w else None
        except (ValueError, TypeError):
            return None
    
    def _gerar_narrativa_peso(self, peso: float, goal: Optional[float]) -> str:
        """Gera narrativa do peso com tratamento de erros."""
        try:
            return ctx.weight(peso, goal=goal)
        except Exception as e:
            logger.error(f"Erro ao gerar narrativa de peso: {e}", exc_info=True)
            return "—"
    
    def _render_card_peso(self, peso: float, msg: str) -> None:
        """Renderiza card de peso."""
        st.markdown(
            f"""
            <div class="metric-card fade-in">
                <div class="metric-value" style="font-size: 2.2rem;">
                    {peso:.1f} kg
                </div>
                <div style="font-size: 0.82rem; color: var(--text-muted);
                    margin-top: 0.35rem;">{msg}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_botao_registrar_peso(self) -> None:
        """Renderiza botão para registrar peso."""
        if st.button(
            "Registrar peso →",
            use_container_width=True,
            key="home_reg_peso",
        ):
            st.session_state.page = "meals"
            st.session_state.hub_tipo = "weight"
            st.rerun()


# Funções de compatibilidade (mantendo a interface original)
def _bloco_progresso_dia(sm: Dict, hydration: int, user: Dict,
                          nutr, last_weight) -> None:
    """Bloco de progresso do dia (compatibilidade)."""
    renderer = HomeBlocksRenderer(None, nutr, user)
    renderer.render_progresso_dia(sm, hydration)


def _bloco_xp(stats: Dict, dash_pac: Dict) -> None:
    """Bloco de XP (compatibilidade)."""
    renderer = HomeBlocksRenderer(None, None, {})
    renderer.render_xp(stats, dash_pac)


def _bloco_desafio(gami) -> None:
    """Bloco de desafio (compatibilidade)."""
    renderer = HomeBlocksRenderer(None, None, {})
    renderer.render_desafio(gami)


def _bloco_peso(last_weight, user: Dict) -> None:
    """Bloco de peso (compatibilidade)."""
    renderer = HomeBlocksRenderer(None, None, user)
    renderer.render_peso(last_weight)
