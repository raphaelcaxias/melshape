"""
Melshape — Home Contextual por Pilar (UNIFICADO).

Elimina home_context_b.py — sem import circular.
Cada health_mode gera um bloco diferente na home.

GLP-1     → próxima dose, adesão, sintomas de ontem
Bariátrica → fase, volume do dia, suplementos pendentes
Fitness   → meta proteica, treino de hoje, variação de peso
Geral     → etapa da jornada, progresso, próximo passo
"""
import streamlit as st
from typing import Dict, Any, Optional, List
import logging

from views.components.cards import metric_card, alert, empty_state

logger = logging.getLogger("Melshape.HomeContext")


# Constantes de limiares
ADESAO_EXCELENTE = 80
ADESAO_BOM = 50
PROTEINA_SUCESSO = 80
PROTEINA_ALERTA = 50
DIAS_VARIAÇÃO_PESO = 90
MAX_SUPLEMENTOS_EXIBIR = 3


class HomeContextRenderer:
    """Renderer dedicado para contexto do pilar."""
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user
        self.db = services.get("db")
        self.health_mode = user.get("health_mode", "general")
    
    def render(self) -> None:
        """Renderiza contexto do pilar."""
        self._render_header()
        
        # Roteia para o contexto correto
        if self.health_mode == "glp1":
            self._render_glp1()
        elif self.health_mode == "bariatric":
            self._render_bariatric()
        elif self.health_mode == "fitness":
            self._render_fitness()
        else:
            self._render_geral()
    
    def _render_header(self) -> None:
        """Renderiza cabeçalho do bloco."""
        st.markdown(
            """
            <p style="font-size: 0.74rem; font-weight: 700; letter-spacing: 0.08em;
                color: var(--text-faint); text-transform: uppercase;
                margin-bottom: 0.7rem;">
                Seu Contexto de Hoje
            </p>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_glp1(self) -> None:
        """Renderiza contexto GLP-1 com tratamento de erros."""
        try:
            resumo = self._get_resumo_glp1()
            
            if not resumo:
                alert("❌ Não foi possível carregar dados GLP-1.", "error")
                return
            
            self._render_cards_glp1(resumo)
            self._render_sintomas_glp1()
        except Exception as e:
            logger.error(f"Erro ao renderizar contexto GLP-1: {e}", exc_info=True)
            alert("❌ Erro ao carregar contexto GLP-1.", "error")
    
    @st.cache_data(ttl=60)
    def _get_resumo_glp1(_self) -> Optional[Dict]:
        """Obtém resumo GLP-1 (com cache)."""
        try:
            from services.glp1_service import GLP1Service
            svc = GLP1Service(_self.db)
            return svc.resumo(_self.user)
        except Exception as e:
            logger.error(f"Erro ao obter resumo GLP-1: {e}", exc_info=True)
            return None
    
    def _render_cards_glp1(self, resumo: Dict) -> None:
        """Renderiza cards do contexto GLP-1."""
        fase = resumo.get("fase", {})
        adesao = resumo.get("adesao", {})
        proxima = resumo.get("proxima_dose") or "—"
        dias = resumo.get("dias")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            self._render_card_fase_glp1(fase, dias)
        
        with col2:
            self._render_card_adesao_glp1(adesao)
        
        with col3:
            self._render_card_proxima_dose(proxima)
    
    def _render_card_fase_glp1(self, fase: Dict, dias: Optional[int]) -> None:
        """Renderiza card de fase GLP-1."""
        icon = fase.get("icon", "💉")
        label = fase.get("label", "—")
        dias_texto = f"{dias} dias" if dias is not None else "?"
        
        st.markdown(
            f"""
            <div class="metric-card fade-in">
                <div style="font-size: 1.3rem;">{icon}</div>
                <div style="font-weight: 700; font-size: 0.90rem; color: var(--text);">
                    {label}
                </div>
                <div style="font-size: 0.74rem; color: var(--text-muted); margin-top: 0.15rem;">
                    {dias_texto} de tratamento
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_card_adesao_glp1(self, adesao: Dict) -> None:
        """Renderiza card de adesão GLP-1."""
        pct = self._parse_int(adesao.get("pct", 0))
        cor = self._get_cor_adesao(pct)
        metric_card(f"{pct}%", "Adesão (4 sem.)", "✅", cor)
    
    def _get_cor_adesao(self, pct: int) -> str:
        """Retorna cor baseada na adesão."""
        return "success" if pct >= ADESAO_EXCELENTE else "warning"
    
    def _render_card_proxima_dose(self, proxima: str) -> None:
        """Renderiza card de próxima dose."""
        st.markdown(
            f"""
            <div class="metric-card fade-in">
                <div style="font-size: 0.80rem; color: var(--text-muted);">Próxima dose</div>
                <div style="font-weight: 700; font-size: 0.94rem; color: var(--primary); margin-top: 0.15rem;">
                    {proxima}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_sintomas_glp1(self) -> None:
        """Renderiza alerta de sintomas GLP-1."""
        sintomas = self._get_sintomas_glp1()
        
        if sintomas:
            self._render_alerta_sintomas(sintomas)
        else:
            self._render_cta_sintomas()
    
    @st.cache_data(ttl=30)
    def _get_sintomas_glp1(_self) -> List[Dict]:
        """Obtém sintomas GLP-1 (com cache)."""
        try:
            sintomas = _self.db.get_sintomas_glp1(days=1)
            return sintomas if isinstance(sintomas, list) else []
        except Exception as e:
            logger.error(f"Erro ao buscar sintomas GLP-1: {e}", exc_info=True)
            return []
    
    def _render_alerta_sintomas(self, sintomas: List[Dict]) -> None:
        """Renderiza alerta de sintomas."""
        try:
            severidade = self._parse_int(sintomas[0].get("severidade", 1))
            
            if severidade >= 2:
                alert(
                    f"⚠️ Sintomas de ontem com severidade {severidade}/3. Monitore hoje.",
                    "warning",
                )
        except Exception as e:
            logger.error(f"Erro ao renderizar alerta de sintomas: {e}", exc_info=True)
    
    def _render_cta_sintomas(self) -> None:
        """Renderiza CTA para registrar sintomas."""
        if st.button(
            "📋 Registrar sintomas de hoje →",
            use_container_width=True,
            key="ctx_glp1_sint",
        ):
            st.session_state.page = "glp1"
            st.rerun()
    
    def _render_bariatric(self) -> None:
        """Renderiza contexto bariátrico com tratamento de erros."""
        try:
            resumo = self._get_resumo_bariatric()
            
            if not resumo:
                alert("❌ Não foi possível carregar dados bariátricos.", "error")
                return
            
            sm = self._get_daily_summary()
            self._render_cards_bariatric(resumo, sm)
            self._render_suplementos_bariatric(resumo)
        except Exception as e:
            logger.error(f"Erro ao renderizar contexto bariátrico: {e}", exc_info=True)
            alert("❌ Erro ao carregar contexto bariátrico.", "error")
    
    @st.cache_data(ttl=60)
    def _get_resumo_bariatric(_self) -> Optional[Dict]:
        """Obtém resumo bariátrico (com cache)."""
        try:
            from services.bariatric_service import BariatricService
            svc = BariatricService(_self.db)
            return svc.resumo(_self.user)
        except Exception as e:
            logger.error(f"Erro ao obter resumo bariátrico: {e}", exc_info=True)
            return None
    
    @st.cache_data(ttl=60)
    def _get_daily_summary(_self) -> Dict:
        """Obtém resumo diário de nutrição (com cache)."""
        try:
            from services.nutrition_service import NutritionService
            nutr = NutritionService(_self.db)
            return nutr.daily_summary() or {}
        except Exception as e:
            logger.error(f"Erro ao obter daily summary: {e}", exc_info=True)
            return {}
    
    def _render_cards_bariatric(self, resumo: Dict, sm: Dict) -> None:
        """Renderiza cards do contexto bariátrico."""
        fase = resumo.get("fase", {})
        volume = self._parse_float(sm.get("volume_ml", 0))
        calorias = self._parse_float(sm.get("calories", 0))
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            self._render_card_fase_bariatric(fase)
        
        with col2:
            self._render_card_volume_bariatric(volume, fase)
        
        with col3:
            self._render_card_calorias_bariatric(calorias, fase)
    
    def _render_card_fase_bariatric(self, fase: Dict) -> None:
        """Renderiza card de fase bariátrica."""
        nome = fase.get("nome", "—")
        dias = fase.get("dias", "—")
        
        st.markdown(
            f"""
            <div class="metric-card fade-in">
                <div style="font-weight: 700; color: var(--primary); font-size: 0.95rem;">
                    {nome}
                </div>
                <div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 0.15rem;">
                    Dias {dias}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_card_volume_bariatric(self, volume: float, fase: Dict) -> None:
        """Renderiza card de volume bariátrico."""
        max_ml = self._parse_float(fase.get("max_ml", 500))
        cor_vol = self._get_cor_volume(volume, max_ml)
        metric_card(f"{volume:.0f}ml", f"Volume (máx {max_ml:.0f}ml)", "🥄", cor_vol)
    
    def _get_cor_volume(self, volume: float, max_ml: float) -> str:
        """Retorna cor baseada no volume."""
        if volume > max_ml:
            return "error"
        elif volume > 0:
            return "success"
        return ""
    
    def _render_card_calorias_bariatric(self, calorias: float, fase: Dict) -> None:
        """Renderiza card de calorias bariátrico."""
        max_cal = self._parse_float(fase.get("max_cal", 800))
        cor_cal = "error" if calorias > max_cal else ""
        metric_card(f"{calorias:.0f}", f"kcal (máx {max_cal:.0f})", "🔥", cor_cal)
    
    def _render_suplementos_bariatric(self, resumo: Dict) -> None:
        """Renderiza alerta de suplementos bariátricos."""
        try:
            suplementos = resumo.get("suplementos", [])[:MAX_SUPLEMENTOS_EXIBIR]
            
            if not suplementos:
                return
            
            nomes = " · ".join(s.get("name", "") for s in suplementos if s.get("name"))
            
            if nomes:
                alert(f"💊 Suplementos de hoje: {nomes}", "info")
        except Exception as e:
            logger.error(f"Erro ao renderizar suplementos bariátricos: {e}", exc_info=True)
    
    def _render_fitness(self) -> None:
        """Renderiza contexto fitness com tratamento de erros."""
        try:
            sm = self._get_daily_summary()
            treino = self._get_treino_hoje()
            
            self._render_cards_fitness(sm, treino)
            
            if not treino:
                self._render_cta_treino()
        except Exception as e:
            logger.error(f"Erro ao renderizar contexto fitness: {e}", exc_info=True)
            alert("❌ Erro ao carregar contexto fitness.", "error")
    
    @st.cache_data(ttl=30)
    def _get_treino_hoje(_self) -> Optional[Any]:
        """Obtém treino de hoje (com cache)."""
        try:
            return _self.db.get_workout_today()
        except Exception as e:
            logger.error(f"Erro ao buscar treino de hoje: {e}", exc_info=True)
            return None
    
    def _render_cards_fitness(self, sm: Dict, treino: Optional[Any]) -> None:
        """Renderiza cards do contexto fitness."""
        peso = self._parse_float(self.user.get("current_weight", 70))
        meta_prot = self._calcular_meta_proteina(peso)
        prot_hoje = self._parse_float(sm.get("protein", 0))
        pct_prot = self._calcular_percentual(prot_hoje, meta_prot)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            self._render_card_proteina_fitness(prot_hoje, meta_prot, pct_prot)
        
        with col2:
            self._render_card_treino_fitness(treino)
        
        with col3:
            self._render_card_variacao_peso()
    
    def _calcular_meta_proteina(self, peso: float) -> float:
        """Calcula meta de proteína com tratamento de erros."""
        try:
            from services.nutrition_service import NutritionService
            nutr = NutritionService(self.db)
            return nutr.calc_protein_goal(peso, "fitness")
        except Exception as e:
            logger.error(f"Erro ao calcular meta de proteína: {e}", exc_info=True)
            return 100.0
    
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
    
    def _render_card_proteina_fitness(self, prot_hoje: float, meta_prot: float, pct: int) -> None:
        """Renderiza card de proteína fitness."""
        cor = self._get_cor_proteina(pct)
        metric_card(
            f"{prot_hoje:.0f}g",
            f"Proteína (meta {meta_prot:.0f}g)",
            "🥩",
            cor,
        )
    
    def _get_cor_proteina(self, pct: int) -> str:
        """Retorna cor baseada no percentual de proteína."""
        if pct >= PROTEINA_SUCESSO:
            return "success"
        elif pct >= PROTEINA_ALERTA:
            return "warning"
        return "error"
    
    def _render_card_treino_fitness(self, treino: Optional[Any]) -> None:
        """Renderiza card de treino fitness."""
        if treino:
            label = self._get_tipo_treino_label(treino)
            metric_card(label, "Treino de hoje", "🏋️", "success")
        else:
            metric_card("—", "Treino não registrado", "🏋️")
    
    def _get_tipo_treino_label(self, treino: Any) -> str:
        """Obtém label do tipo de treino."""
        try:
            from config import WORKOUT_TYPES
            tipo = getattr(treino, "workout_type", "")
            return WORKOUT_TYPES.get(tipo, "Treino")
        except Exception as e:
            logger.error(f"Erro ao obter tipo de treino: {e}")
            return "Treino"
    
    def _render_card_variacao_peso(self) -> None:
        """Renderiza card de variação de peso."""
        try:
            df_peso = self.db.get_weights(DIAS_VARIAÇÃO_PESO)
            
            if df_peso is not None and not df_peso.empty and len(df_peso) >= 2:
                diff = float(df_peso.iloc[-1]["weight"]) - float(df_peso.iloc[0]["weight"])
                cor = "success" if diff < 0 else "warning"
                metric_card(f"{diff:+.1f}kg", "Variação 90d", "📊", cor)
            else:
                metric_card("—", "Variação de peso", "📊")
        except Exception as e:
            logger.error(f"Erro ao calcular variação de peso: {e}", exc_info=True)
            metric_card("—", "Variação de peso", "📊")
    
    def _render_cta_treino(self) -> None:
        """Renderiza CTA para registrar treino."""
        if st.button(
            "🏋️ Registrar treino →",
            use_container_width=True,
            key="ctx_fit_treino",
        ):
            st.session_state.page = "habits"
            st.rerun()
    
    def _render_geral(self) -> None:
        """Renderiza contexto geral/emagrecimento com tratamento de erros."""
        try:
            jornada = self._get_jornada_ativa()
            
            if not jornada:
                empty_state("🗺️", "Jornada não iniciada", "Acesse 'Jornada' para começar")
                return
            
            progresso = self._get_progresso_jornada(jornada["id"])
            
            if not progresso:
                alert("❌ Não foi possível carregar progresso da jornada.", "error")
                return
            
            self._render_card_jornada(progresso)
            self._render_cta_jornada(progresso)
        except Exception as e:
            logger.error(f"Erro ao renderizar contexto geral: {e}", exc_info=True)
            alert("❌ Erro ao carregar contexto da jornada.", "error")
    
    @st.cache_data(ttl=60)
    def _get_jornada_ativa(_self) -> Optional[Dict]:
        """Obtém jornada ativa (com cache)."""
        try:
            return _self.db.get_jornada_ativa()
        except Exception as e:
            logger.error(f"Erro ao buscar jornada ativa: {e}", exc_info=True)
            return None
    
    @st.cache_data(ttl=60)
    def _get_progresso_jornada(_self, jornada_id: str) -> Optional[Dict]:
        """Obtém progresso da jornada (com cache)."""
        try:
            from services.journey_service import JourneyService
            svc = JourneyService(_self.db)
            return svc.progresso_jornada(jornada_id, _self.health_mode)
        except Exception as e:
            logger.error(f"Erro ao obter progresso da jornada: {e}", exc_info=True)
            return None
    
    def _render_card_jornada(self, progresso: Dict) -> None:
        """Renderiza card da jornada."""
        etapa = progresso.get("etapa_atual", {})
        passo = self._get_proximo_passo(etapa)
        pct = self._parse_int(progresso.get("pct_geral", 0))
        
        icone_etapa = etapa.get("icone", "📍")
        nome_etapa = etapa.get("nome", "")
        acao_passo = passo.get("acao", "Continue sua jornada")
        
        st.markdown(
            f"""
            <div class="metric-card fade-in">
                <div style="display: flex; justify-content: space-between;
                    align-items: center; margin-bottom: 0.6rem;">
                    <div style="font-weight: 700; color: var(--text); font-size: 0.95rem;">
                        {icone_etapa} {nome_etapa}
                    </div>
                    <div style="font-size: 1.3rem; font-weight: 800; color: var(--primary);">
                        {pct}%
                    </div>
                </div>
                <div class="progress-track">
                    <div class="progress-fill" style="width: {pct}%;"></div>
                </div>
                <div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.5rem;">
                    ➡️ {acao_passo}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _get_proximo_passo(self, etapa: Dict) -> Dict:
        """Obtém próximo passo com tratamento de erros."""
        try:
            from services.journey_service import JourneyService
            svc = JourneyService(self.db)
            return svc.proximo_passo(etapa, self.user)
        except Exception as e:
            logger.error(f"Erro ao obter próximo passo: {e}", exc_info=True)
            return {"acao": "Continue sua jornada", "pagina": None}
    
    def _render_cta_jornada(self, progresso: Dict) -> None:
        """Renderiza CTA da jornada."""
        try:
            etapa = progresso.get("etapa_atual", {})
            passo = self._get_proximo_passo(etapa)
            pagina = passo.get("pagina")
            
            if not pagina:
                return
            
            icone = passo.get("icone", "➡️")
            acao = passo.get("acao", "Continuar")
            
            if st.button(
                f"{icone} {acao}",
                type="primary",
                use_container_width=True,
                key="ctx_geral_cta",
            ):
                st.session_state.page = pagina
                st.session_state.hub_tipo = passo.get("hub_tipo", "")
                st.rerun()
        except Exception as e:
            logger.error(f"Erro ao renderizar CTA da jornada: {e}", exc_info=True)
    
    def _parse_int(self, value: Any) -> int:
        """Converte valor para int de forma segura."""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def _parse_float(self, value: Any) -> float:
        """Converte valor para float de forma segura."""
        try:
            return float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0


# Função de compatibilidade
def render_contexto_pilar(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Renderiza contexto do pilar (compatibilidade)."""
    renderer = HomeContextRenderer(services, user)
    renderer.render()
