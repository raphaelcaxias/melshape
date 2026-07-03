"""
Melshape — Home: blocos diários de hábitos, comportamento, 
consequências e score.
"""
import streamlit as st
from typing import Dict, Any, List, Optional, Set
from datetime import date, datetime
import logging

from views.components.cards import empty_state
import config

logger = logging.getLogger("Melshape.HomeDaily")


# Constantes de configuração
MAX_HABITOS_EXIBIR = 4
DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# Mapas de emoji
HUMOR_MAP = {1: "😖", 2: "😕", 3: "😐", 4: "🙂", 5: "😄"}
ENERGIA_MAP = {1: "😴", 2: "🥱", 3: "⚡", 4: "💪", 5: "🚀"}
SONO_MAP = {1: "😫", 2: "😕", 3: "😐", 4: "🙂", 5: "😴✨"}

# Limiares
PROTEINA_SUCESSO = 80


class HomeDailyRenderer:
    """Renderer para blocos diários."""
    
    def __init__(self, db, nutr, user: Dict[str, Any]):
        self.db = db
        self.nutr = nutr
        self.user = user or {}
    
    def render_habitos_hoje(self) -> None:
        """Renderiza bloco de hábitos de hoje."""
        self._render_header_bloco("📋 Hábitos de Hoje")
        
        habitos = self._get_habitos()
        
        if not habitos:
            empty_state(
                "📋",
                "Nenhum hábito criado ainda",
                "Crie hábitos na tela de Hábitos",
            )
            self._render_cta_habitos()
            return
        
        feitos_hoje = self._get_registros_hoje()
        stats = self._calcular_stats_habitos(habitos, feitos_hoje)
        
        self._render_progresso_habitos(stats)
        self._render_lista_habitos(habitos, feitos_hoje)
        self._render_botao_ver_todos()
    
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
    
    @st.cache_data(ttl=60)
    def _get_habitos(_self) -> List[Dict]:
        """Obtém lista de hábitos (com cache)."""
        if not _self.db:
            return []
        
        try:
            habitos = _self.db.get_habitos()
            return habitos if isinstance(habitos, list) else []
        except Exception as e:
            logger.error(f"Erro ao buscar hábitos: {e}", exc_info=True)
            return []
    
    @st.cache_data(ttl=30)
    def _get_registros_hoje(_self) -> Set[str]:
        """Obtém IDs de hábitos registrados hoje (com cache)."""
        if not _self.db:
            return set()
        
        try:
            registros = _self.db.get_registros_hoje()
            return set(registros) if registros else set()
        except Exception as e:
            logger.error(f"Erro ao buscar registros de hoje: {e}", exc_info=True)
            return set()
    
    def _calcular_stats_habitos(self, habitos: List[Dict], feitos: Set[str]) -> Dict[str, int]:
        """Calcula estatísticas de hábitos."""
        try:
            total = len(habitos)
            concluidos = sum(1 for h in habitos if h.get("id") in feitos)
            pct = int(concluidos / total * 100) if total > 0 else 0
            
            return {
                "total": total,
                "concluidos": concluidos,
                "pct": pct,
            }
        except Exception as e:
            logger.error(f"Erro ao calcular stats de hábitos: {e}", exc_info=True)
            return {"total": 0, "concluidos": 0, "pct": 0}
    
    def _render_progresso_habitos(self, stats: Dict[str, int]) -> None:
        """Renderiza progresso de hábitos."""
        st.markdown(
            f"""
            <div style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.5rem;">
                {stats['concluidos']} de {stats['total']} hábitos ({stats['pct']}%)
            </div>
            <div class="progress-track" style="margin-bottom: 0.7rem;">
                <div class="progress-fill" style="width: {stats['pct']}%;"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_lista_habitos(self, habitos: List[Dict], feitos: Set[str]) -> None:
        """Renderiza lista de hábitos."""
        for habito in habitos[:MAX_HABITOS_EXIBIR]:
            self._render_habito_item(habito, feitos)
    
    def _render_habito_item(self, habito: Dict, feitos: Set[str]) -> None:
        """Renderiza um item de hábito."""
        habito_id = habito.get("id", "")
        nome = habito.get("nome", "")
        icone = habito.get("icone", "⭐")
        feito = habito_id in feitos
        
        if not habito_id:
            logger.warning("Hábito sem ID encontrado")
            return
        
        cor = self._get_cor_habito(feito)
        sinal = "✅" if feito else "⬜"
        peso_fonte = "400" if feito else "600"
        
        col1, col2 = st.columns([5, 1])
        
        with col1:
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; gap: 0.6rem;
                    padding: 0.4rem 0; border-bottom: 1px solid var(--border-subtle);">
                    <span style="font-size: 1.1rem;">{icone}</span>
                    <span style="color: {cor}; font-weight: {peso_fonte}; font-size: 0.9rem;">
                        {nome}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        
        with col2:
            if not feito:
                self._render_botao_marcar_habito(habito_id, icone, nome)
    
    def _get_cor_habito(self, feito: bool) -> str:
        """Retorna cor baseada no status do hábito."""
        return "var(--success)" if feito else "var(--border)"
    
    def _render_botao_marcar_habito(self, habito_id: str, icone: str, nome: str) -> None:
        """Renderiza botão para marcar hábito."""
        if st.button(
            "✓",
            key=f"home_hab_{habito_id}",
            help="Marcar como concluído",
        ):
            self._marcar_habito(habito_id, icone, nome)
    
    def _render_cta_habitos(self) -> None:
        """Renderiza CTA para ir para hábitos."""
        if st.button(
            "Ir para Hábitos →",
            use_container_width=True,
            key="home_hab_cta",
        ):
            st.session_state.page = "habits"
            st.rerun()
    
    def _render_botao_ver_todos(self) -> None:
        """Renderiza botão para ver todos os hábitos."""
        if st.button(
            "Ver todos os hábitos →",
            use_container_width=True,
            key="home_ver_habitos",
        ):
            st.session_state.page = "habits"
            st.rerun()
    
    def _marcar_habito(self, habito_id: str, icone: str, nome: str) -> None:
        """Marca um hábito como concluído com tratamento de erros."""
        try:
            from services.habit_service import HabitService
            resultado = HabitService(self.db).registrar(habito_id)
            
            if not isinstance(resultado, dict):
                logger.error(f"Resultado inválido ao registrar hábito {habito_id}")
                st.error("❌ Erro ao registrar hábito.")
                return
            
            if resultado.get("ok"):
                self._processar_sucesso_registro(resultado, icone, nome)
            else:
                st.error("❌ Erro ao registrar hábito.")
        except Exception as e:
            logger.error(f"Erro ao marcar hábito {habito_id}: {e}", exc_info=True)
            st.error(f"❌ Erro ao registrar hábito: {str(e)}")
    
    def _processar_sucesso_registro(self, resultado: Dict, icone: str, nome: str) -> None:
        """Processa sucesso do registro de hábito."""
        xp_ganho = resultado.get("xp_ganho", 0)
        bonus_msg = resultado.get("bonus_msg")
        
        st.toast(f"{icone} {nome} — +{xp_ganho} XP", icon="✅")
        
        if bonus_msg:
            st.toast(bonus_msg, icon="🎉")
        
        # Limpa cache e rerun
        st.cache_data.clear()
        st.rerun()
    
    def render_comportamento(self, checkin: Optional[Dict]) -> None:
        """Renderiza bloco de comportamento."""
        self._render_header_bloco("💭 Como Você Está")
        
        if not checkin:
            self._render_mensagem_sem_checkin()
            return
        
        self._render_cards_comportamento(checkin)
    
    def _render_mensagem_sem_checkin(self) -> None:
        """Renderiza mensagem quando não há check-in."""
        st.markdown(
            """
            <div style="font-size: 0.86rem; color: var(--text-muted); margin-top: 0.3rem;">
                Faça o check-in para registrar como você está hoje.
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_cards_comportamento(self, checkin: Dict) -> None:
        """Renderiza cards de comportamento."""
        humor = self._parse_int(checkin.get("humor", 0))
        energia = self._parse_int(checkin.get("energia", 0))
        sono = self._parse_int(checkin.get("qualidade_sono", 0))
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            self._render_card_comportamento(humor, HUMOR_MAP, "Humor")
        
        with col2:
            self._render_card_comportamento(energia, ENERGIA_MAP, "Energia")
        
        with col3:
            self._render_card_comportamento(sono, SONO_MAP, "Sono")
    
    def _render_card_comportamento(self, valor: int, mapa: Dict[int, str], label: str) -> None:
        """Renderiza card de comportamento individual."""
        emoji = self._get_emoji(valor, mapa)
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="text-align: center;">
                <div style="font-size: 2rem;">{emoji}</div>
                <div class="metric-label">{label}: {valor}/5</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _get_emoji(self, valor: int, mapa: Dict[int, str]) -> str:
        """Obtém emoji baseado no valor."""
        try:
            return mapa.get(valor, "—") if valor else "—"
        except Exception as e:
            logger.debug(f"Erro ao obter emoji para valor {valor}: {e}")
            return "—"
    
    def _parse_int(self, value: Any) -> int:
        """Converte valor para int de forma segura."""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def render_consequencias(self, sm: Dict, hydration: int, last_weight: Optional[float]) -> None:
        """Renderiza bloco de consequências."""
        self._render_header_bloco("📊 Consequências de Hoje")
        
        # Calcula metas nutricionais
        metas = self._calcular_metas_nutricionais()
        
        # Obtém consumo de hoje
        cal_hoje = self._parse_float(sm.get("calories", 0))
        prot_hoje = self._parse_float(sm.get("protein", 0))
        hydration_val = self._parse_float(hydration)
        
        # Calcula percentuais
        pct_cal = self._calcular_percentual(cal_hoje, metas["goal_cal"])
        pct_prot = self._calcular_percentual(prot_hoje, metas["goal_prot"])
        pct_agua = self._calcular_percentual(hydration_val, metas["goal_agua"])
        
        # Renderiza cards
        self._render_cards_consequencias(
            cal_hoje, prot_hoje, hydration_val, last_weight,
            pct_cal, pct_prot, pct_agua
        )
    
    def _calcular_metas_nutricionais(self) -> Dict[str, float]:
        """Calcula metas nutricionais com tratamento de erros."""
        try:
            weight = self._parse_float(self.user.get("current_weight"))
            height = self._parse_float(self.user.get("height"))
            age = self._parse_int(self.user.get("age"))
            gender = self.user.get("gender", "female")
            health_mode = self.user.get("health_mode", "general")
            goal = self.user.get("goal", "lose")
            activity = self.user.get("activity_level", "moderate")
            
            tmb = self.nutr.calc_tmb(weight, height, age, gender)
            goal_cal = self.nutr.calc_goal_calories(tmb, activity, goal, health_mode)
            goal_prot = self.nutr.calc_protein_goal(weight, health_mode)
            goal_agua = self._get_hydration_goal()
            
            return {
                "goal_cal": goal_cal,
                "goal_prot": goal_prot,
                "goal_agua": goal_agua,
            }
        except Exception as e:
            logger.error(f"Erro ao calcular metas nutricionais: {e}", exc_info=True)
            return {
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
    
    def _calcular_percentual(self, atual: float, meta: float) -> int:
        """Calcula percentual de forma segura."""
        if meta <= 0:
            return 0
        
        try:
            pct = int(atual / meta * 100)
            return min(100, max(0, pct))
        except Exception as e:
            logger.debug(f"Erro ao calcular percentual: {e}")
            return 0
    
    def _render_cards_consequencias(
        self,
        cal_hoje: float,
        prot_hoje: float,
        hydration: float,
        last_weight: Optional[float],
        pct_cal: int,
        pct_prot: int,
        pct_agua: int,
    ) -> None:
        """Renderiza cards de consequências."""
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            self._render_card_consequencia(
                f"{cal_hoje:.0f}", "🔥 kcal", pct_cal, ""
            )
        
        with col2:
            cor_prot = "success" if pct_prot >= PROTEINA_SUCESSO else ""
            self._render_card_consequencia(
                f"{prot_hoje:.0f}g", "🥩 proteína", pct_prot, cor_prot
            )
        
        with col3:
            self._render_card_consequencia(
                f"{hydration:.0f}ml", "💧 água", pct_agua, "info"
            )
        
        with col4:
            peso_texto = f"{last_weight:.1f}kg" if last_weight else "—"
            self._render_card_consequencia(peso_texto, "⚖️ peso", 0, "")
    
    def _render_card_consequencia(
        self,
        valor: str,
        label: str,
        pct: int,
        cor: str,
    ) -> None:
        """Renderiza card de consequência individual."""
        fill_css = f"background: var(--{cor});" if cor in ("success", "info") else ""
        progress_html = (
            f'<div class="progress-track" style="margin-top: 0.35rem;">'
            f'<div class="progress-fill" style="width: {pct}%; {fill_css}"></div>'
            f'</div>'
            if pct > 0 else ""
        )
        
        st.markdown(
            f"""
            <div class="metric-card fade-in">
                <div style="font-weight: 700; font-size: 1.15rem; color: var(--text);">
                    {valor}
                </div>
                <div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 0.15rem;">
                    {label}
                </div>
                {progress_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def render_score(self, services: Dict) -> None:
        """Renderiza score narrativo com tratamento de erros."""
        try:
            from services.score_service import ScoreService
            narrativa = ScoreService(self.db).narrativa_paciente(self.user)
            
            if not narrativa or narrativa.get("icone") == "🗺️":
                return
            
            self._render_card_score(narrativa)
        except Exception as e:
            logger.error(f"Erro ao renderizar score: {e}", exc_info=True)
    
    def _render_card_score(self, narrativa: Dict) -> None:
        """Renderiza card de score narrativo."""
        icone = narrativa.get("icone", "📊")
        cor = narrativa.get("cor", "var(--primary)")
        titulo = narrativa.get("titulo", "")
        mensagem = narrativa.get("mensagem", "")
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="border-left: 4px solid {cor};">
                <div style="display: flex; gap: 0.8rem; align-items: center;">
                    <span style="font-size: 2rem;">{icone}</span>
                    <div>
                        <div style="font-weight: 700; font-size: 0.95rem; color: var(--text);">
                            {titulo}
                        </div>
                        <div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.2rem;">
                            {mensagem}
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# Funções de compatibilidade
def _bloco_habitos_hoje(db, user: Dict) -> None:
    """Renderiza bloco de hábitos de hoje (compatibilidade)."""
    renderer = HomeDailyRenderer(db, None, user)
    renderer.render_habitos_hoje()


def _bloco_comportamento(checkin: Optional[Dict]) -> None:
    """Renderiza bloco de comportamento (compatibilidade)."""
    renderer = HomeDailyRenderer(None, None, {})
    renderer.render_comportamento(checkin)


def _bloco_consequencias(sm: Dict, hydration: int, user: Dict,
                          nutr, last_weight: Optional[float]) -> None:
    """Renderiza bloco de consequências (compatibilidade)."""
    renderer = HomeDailyRenderer(None, nutr, user)
    renderer.render_consequencias(sm, hydration, last_weight)


def _bloco_score(services: Dict, user: Dict) -> None:
    """Renderiza bloco de score (compatibilidade)."""
    renderer = HomeDailyRenderer(services.get("db"), None, user)
    renderer.render_score(services)


def _div() -> None:
    """Renderiza divisor."""
    st.markdown(
        '<div style="border-top: 1px solid var(--border); margin: 1rem 0;"></div>',
        unsafe_allow_html=True,
    )


def _turno() -> str:
    """Retorna saudação baseada no horário."""
    try:
        hora = datetime.now().hour
        if hora < 12:
            return "Bom dia"
        elif hora < 18:
            return "Boa tarde"
        else:
            return "Boa noite"
    except Exception as e:
        logger.error(f"Erro ao obter turno: {e}")
        return "Olá"


def _data_br() -> str:
    """Retorna data no formato brasileiro."""
    try:
        hoje = date.today()
        dia_semana = DIAS_SEMANA[hoje.weekday()]
        mes = MESES[hoje.month - 1]
        return f"{dia_semana}, {hoje.day} de {mes}"
    except Exception as e:
        logger.error(f"Erro ao formatar data BR: {e}")
        return ""
