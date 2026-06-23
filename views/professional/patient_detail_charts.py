"""
Melshape — Detalhe do Paciente: gráficos de peso e nutrição.
"""
import streamlit as st
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

from views.components.cards import empty_state, metric_card, divider

logger = logging.getLogger("Melshape.PatientDetailCharts")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Limites de query
LIMIT_PESOS = 100
LIMIT_CONSUMO = 100
MAX_DIAS_NUTRICAO = 14

# Cores dos gráficos
CORES_GRAFICO = {
    "calorias": "rgba(201,168,76,0.75)",
    "proteina": "#10B981",
    "carboidratos": "#6366F1",
    "gorduras": "#F59E0B",
    "linha_peso": "#C9A84C",
    "fill_peso": "rgba(201,168,76,0.08)",
}

# Configurações de layout
LAYOUT_CONFIG = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font_color": "#6B6B6B",
    "grid_color": "rgba(0,0,0,0.05)",
}

# Fallbacks
DEFAULT_METRIC_VALUE = "—"


@dataclass
class WeightData:
    """Dados de evolução de peso."""
    datas: List[str]
    valores: List[float]
    atual: Optional[float] = None
    inicial: Optional[float] = None
    variacao: Optional[float] = None


@dataclass
class NutritionData:
    """Dados de consumo nutricional."""
    datas: List[str]
    calorias: List[float]
    proteina: List[float]
    carboidratos: List[float]
    gorduras: List[float]
    media_calorias: float = 0.0
    media_proteina: float = 0.0
    dias_registro: int = 0


class PatientDetailChartsRenderer:
    """Renderer dedicado para gráficos do paciente."""
    
    def __init__(self, db):
        self.db = db
    
    def render_peso(self, perfil_id: str, nome: str) -> None:
        """Renderiza gráfico de evolução de peso com tratamento de erros."""
        try:
            pesos = self._query_pesos(perfil_id)
            
            if not pesos:
                empty_state(
                    "⚖️",
                    "Sem pesagens registradas",
                    "O paciente ainda não registrou o peso",
                )
                return
            
            data = self._process_weight_data(pesos)
            
            # Métricas rápidas
            self._render_weight_metrics(data)
            
            # Gráfico
            self._render_weight_chart(data, nome)
        except Exception as e:
            logger.error(f"Erro ao renderizar gráfico de peso: {e}", exc_info=True)
            st.error("❌ Erro ao carregar evolução de peso.")
    
    @st.cache_data(ttl=60)
    def _query_pesos(_self, perfil_id: str) -> List[Dict]:
        """Busca histórico de pesos com cache e tratamento de erros."""
        if not _self._is_real_db():
            return []
        
        try:
            response = (
                _self.db.client
                .table("vw_evolucao_peso")
                .select("peso,criado_em")
                .eq("perfil_id", perfil_id)
                .order("criado_em")
                .limit(LIMIT_PESOS)
                .execute()
            )
            
            data = response.data or []
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Erro ao buscar pesos do perfil {perfil_id}: {e}", exc_info=True)
            return []
    
    def _is_real_db(self) -> bool:
        """Verifica se o banco é real (não mock)."""
        try:
            return (
                hasattr(self.db, "is_real") and
                self.db.is_real and
                hasattr(self.db, "client")
            )
        except Exception as e:
            logger.debug(f"Erro ao verificar banco real: {e}")
            return False
    
    def _process_weight_data(self, pesos: List[Dict]) -> WeightData:
        """Processa dados de peso com validação robusta."""
        valores = []
        datas = []
        
        for p in pesos:
            try:
                if not isinstance(p, dict):
                    continue
                
                peso = self._parse_float_optional(p.get("peso"))
                
                if peso is not None and peso > 0:
                    valores.append(peso)
                    datas.append(self._formatar_data(p.get("criado_em", "")))
            except Exception as e:
                logger.debug(f"Erro ao processar peso: {e}")
                continue
        
        return self._build_weight_data(valores, datas)
    
    def _build_weight_data(self, valores: List[float], datas: List[str]) -> WeightData:
        """Constrói WeightData com cálculos seguros."""
        try:
            return WeightData(
                datas=datas,
                valores=valores,
                atual=valores[-1] if valores else None,
                inicial=valores[0] if valores else None,
                variacao=self._calcular_variacao(valores),
            )
        except Exception as e:
            logger.error(f"Erro ao construir WeightData: {e}", exc_info=True)
            return WeightData(datas=datas, valores=valores)
    
    def _calcular_variacao(self, valores: List[float]) -> Optional[float]:
        """Calcula variação de peso com proteção."""
        try:
            if len(valores) >= 2:
                return valores[-1] - valores[0]
            return None
        except Exception as e:
            logger.debug(f"Erro ao calcular variação: {e}")
            return None
    
    def _formatar_data(self, data_raw: Any) -> str:
        """Formata data de forma segura."""
        try:
            if not data_raw:
                return ""
            return str(data_raw)[:10]
        except Exception as e:
            logger.debug(f"Erro ao formatar data: {e}")
            return ""
    
    def _parse_float_optional(self, value: Any) -> Optional[float]:
        """Converte valor para float opcional de forma segura."""
        try:
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None
    
    def _render_weight_metrics(self, data: WeightData) -> None:
        """Renderiza métricas de peso com tratamento de erros."""
        try:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                self._render_metric_peso_atual(data.atual)
            
            with col2:
                self._render_metric_variacao(data.variacao)
            
            with col3:
                metric_card(str(len(data.valores)), "Pesagens", "📊")
        except Exception as e:
            logger.error(f"Erro ao renderizar métricas de peso: {e}", exc_info=True)
    
    def _render_metric_peso_atual(self, atual: Optional[float]) -> None:
        """Renderiza métrica de peso atual."""
        if atual is not None:
            metric_card(f"{atual:.1f} kg", "Peso Atual", "⚖️")
        else:
            metric_card(DEFAULT_METRIC_VALUE, "Peso Atual", "⚖️")
    
    def _render_metric_variacao(self, variacao: Optional[float]) -> None:
        """Renderiza métrica de variação."""
        if variacao is not None:
            cor = "success" if variacao < 0 else "warning"
            metric_card(f"{variacao:+.1f} kg", "Variação Total", "📉", cor)
        else:
            metric_card(DEFAULT_METRIC_VALUE, "Variação Total", "📉")
    
    def _render_weight_chart(self, data: WeightData, nome: str) -> None:
        """Renderiza gráfico de peso com proteção contra ImportError."""
        if len(data.valores) < 2:
            st.info("📊 São necessárias pelo menos 2 pesagens para exibir o gráfico.")
            return
        
        try:
            import plotly.graph_objects as go
            
            fig = self._build_weight_figure(go, data, nome)
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            logger.warning("Plotly não disponível para renderizar gráfico de peso")
            self._render_weight_fallback(data)
        except Exception as e:
            logger.error(f"Erro ao renderizar gráfico de peso: {e}", exc_info=True)
            self._render_weight_fallback(data)
    
    def _build_weight_figure(self, go, data: WeightData, nome: str):
        """Constrói figura Plotly de peso."""
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=data.datas,
            y=data.valores,
            mode="lines+markers",
            name=nome,
            line=dict(color=CORES_GRAFICO["linha_peso"], width=2),
            marker=dict(size=6, color=CORES_GRAFICO["linha_peso"]),
            fill="tozeroy",
            fillcolor=CORES_GRAFICO["fill_peso"],
        ))
        
        fig.update_layout(
            title="Evolução de Peso",
            xaxis_title="Data",
            yaxis_title="Peso (kg)",
            paper_bgcolor=LAYOUT_CONFIG["paper_bgcolor"],
            plot_bgcolor=LAYOUT_CONFIG["plot_bgcolor"],
            font_color=LAYOUT_CONFIG["font_color"],
            showlegend=False,
            margin=dict(t=40, b=30, l=30, r=10),
            height=350,
            hovermode="x unified",
        )
        
        fig.update_xaxes(gridcolor=LAYOUT_CONFIG["grid_color"])
        fig.update_yaxes(gridcolor=LAYOUT_CONFIG["grid_color"])
        
        return fig
    
    def _render_weight_fallback(self, data: WeightData) -> None:
        """Renderiza fallback quando Plotly não está disponível."""
        st.markdown(
            """
            <div style="font-size: 0.86rem; color: var(--text-muted); margin-bottom: 0.6rem;">
                📊 <b>Evolução de Peso:</b>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        for i, (data_str, valor) in enumerate(zip(data.datas, data.valores)):
            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between;
                    padding: 0.4rem 0; border-bottom: 1px solid var(--border-subtle);">
                    <span>{data_str}</span>
                    <span style="font-weight: 700;">{valor:.1f} kg</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    def render_nutricao(self, perfil_id: str) -> None:
        """Renderiza gráficos de nutrição com tratamento de erros."""
        try:
            consumo = self._query_consumo(perfil_id)
            
            if not consumo:
                empty_state(
                    "🍽️",
                    "Sem registros nutricionais",
                    "O paciente ainda não registrou refeições",
                )
                return
            
            data = self._process_nutrition_data(consumo)
            
            # Métricas
            self._render_nutrition_metrics(data)
            
            # Gráfico
            self._render_nutrition_chart(data)
        except Exception as e:
            logger.error(f"Erro ao renderizar gráfico de nutrição: {e}", exc_info=True)
            st.error("❌ Erro ao carregar dados de nutrição.")
    
    @st.cache_data(ttl=60)
    def _query_consumo(_self, perfil_id: str) -> List[Dict]:
        """Busca consumo nutricional com cache e tratamento de erros."""
        if not _self._is_real_db():
            return []
        
        try:
            response = (
                _self.db.client
                .table("vw_consumo_diario")
                .select("dia,calorias,proteina,carboidratos,gorduras")
                .eq("perfil_id", perfil_id)
                .order("dia")
                .limit(LIMIT_CONSUMO)
                .execute()
            )
            
            data = response.data or []
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Erro ao buscar consumo do perfil {perfil_id}: {e}", exc_info=True)
            return []
    
    def _process_nutrition_data(self, consumo: List[Dict]) -> NutritionData:
        """Processa dados nutricionais com validação robusta."""
        datas, calorias, proteina, carboidratos, gorduras = [], [], [], [], []
        
        for item in consumo:
            try:
                if not isinstance(item, dict):
                    continue
                
                cal = self._parse_float(item.get("calorias"))
                prot = self._parse_float(item.get("proteina"))
                carb = self._parse_float(item.get("carboidratos"))
                gor = self._parse_float(item.get("gorduras"))
                
                datas.append(self._formatar_data(item.get("dia", "")))
                calorias.append(cal)
                proteina.append(prot)
                carboidratos.append(carb)
                gorduras.append(gor)
            except Exception as e:
                logger.debug(f"Erro ao processar consumo: {e}")
                continue
        
        # Limita aos últimos N dias
        dados_limitados = self._limitar_dados_nutricao(
            datas, calorias, proteina, carboidratos, gorduras
        )
        
        return self._build_nutrition_data(*dados_limitados)
    
    def _limitar_dados_nutricao(
        self,
        datas: List[str],
        calorias: List[float],
        proteina: List[float],
        carboidratos: List[float],
        gorduras: List[float],
    ) -> tuple:
        """Limita dados nutricionais aos últimos N dias."""
        try:
            if len(datas) > MAX_DIAS_NUTRICAO:
                return (
                    datas[-MAX_DIAS_NUTRICAO:],
                    calorias[-MAX_DIAS_NUTRICAO:],
                    proteina[-MAX_DIAS_NUTRICAO:],
                    carboidratos[-MAX_DIAS_NUTRICAO:],
                    gorduras[-MAX_DIAS_NUTRICAO:],
                )
            return datas, calorias, proteina, carboidratos, gorduras
        except Exception as e:
            logger.error(f"Erro ao limitar dados nutrição: {e}", exc_info=True)
            return datas, calorias, proteina, carboidratos, gorduras
    
    def _build_nutrition_data(
        self,
        datas: List[str],
        calorias: List[float],
        proteina: List[float],
        carboidratos: List[float],
        gorduras: List[float],
    ) -> NutritionData:
        """Constrói NutritionData com cálculos seguros."""
        try:
            cal_validas = [c for c in calorias if c > 0]
            prot_validas = [p for p in proteina if p > 0]
            
            return NutritionData(
                datas=datas,
                calorias=calorias,
                proteina=proteina,
                carboidratos=carboidratos,
                gorduras=gorduras,
                media_calorias=self._calcular_media(cal_validas),
                media_proteina=self._calcular_media(prot_validas),
                dias_registro=len(cal_validas),
            )
        except Exception as e:
            logger.error(f"Erro ao construir NutritionData: {e}", exc_info=True)
            return NutritionData(datas=datas, calorias=calorias, proteina=proteina,
                                carboidratos=carboidratos, gorduras=gorduras)
    
    def _calcular_media(self, valores: List[float]) -> float:
        """Calcula média com proteção contra divisão por zero."""
        try:
            if not valores:
                return 0.0
            return sum(valores) / len(valores)
        except Exception as e:
            logger.debug(f"Erro ao calcular média: {e}")
            return 0.0
    
    def _parse_float(self, value: Any) -> float:
        """Converte valor para float de forma segura."""
        try:
            return float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def _render_nutrition_metrics(self, data: NutritionData) -> None:
        """Renderiza métricas de nutrição com tratamento de erros."""
        try:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                metric_card(
                    f"{data.media_calorias:.0f} kcal",
                    "Média Diária (14d)",
                    "🔥",
                )
            
            with col2:
                metric_card(
                    f"{data.media_proteina:.0f}g",
                    "Proteína Média (14d)",
                    "🥩",
                )
            
            with col3:
                total_dias = len(data.datas)
                metric_card(
                    f"{data.dias_registro}/{total_dias}",
                    "Dias com Registro",
                    "📅",
                )
        except Exception as e:
            logger.error(f"Erro ao renderizar métricas de nutrição: {e}", exc_info=True)
    
    def _render_nutrition_chart(self, data: NutritionData) -> None:
        """Renderiza gráfico de nutrição com proteção contra ImportError."""
        if not data.datas:
            return
        
        try:
            import plotly.graph_objects as go
            
            fig = self._build_nutrition_figure(go, data)
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            logger.warning("Plotly não disponível para renderizar gráfico de nutrição")
            self._render_nutrition_fallback(data)
        except Exception as e:
            logger.error(f"Erro ao renderizar gráfico de nutrição: {e}", exc_info=True)
            self._render_nutrition_fallback(data)
    
    def _build_nutrition_figure(self, go, data: NutritionData):
        """Constrói figura Plotly de nutrição."""
        fig = go.Figure()
        
        # Barras de calorias
        fig.add_trace(go.Bar(
            x=data.datas,
            y=data.calorias,
            name="Calorias",
            marker_color=CORES_GRAFICO["calorias"],
            yaxis="y1",
        ))
        
        # Linha de proteína
        fig.add_trace(go.Scatter(
            x=data.datas,
            y=data.proteina,
            name="Proteína (g)",
            yaxis="y2",
            mode="lines+markers",
            line=dict(color=CORES_GRAFICO["proteina"], width=2),
            marker=dict(size=5, color=CORES_GRAFICO["proteina"]),
        ))
        
        fig.update_layout(
            title="Consumo Nutricional (últimos 14 dias)",
            yaxis=dict(
                title="Calorias (kcal)",
                gridcolor=LAYOUT_CONFIG["grid_color"],
                side="left",
            ),
            yaxis2=dict(
                title="Proteína (g)",
                overlaying="y",
                side="right",
                gridcolor="rgba(0,0,0,0)",
            ),
            paper_bgcolor=LAYOUT_CONFIG["paper_bgcolor"],
            plot_bgcolor=LAYOUT_CONFIG["plot_bgcolor"],
            font_color=LAYOUT_CONFIG["font_color"],
            legend=dict(orientation="h", y=1.1),
            margin=dict(t=50, b=30, l=30, r=50),
            height=350,
            hovermode="x unified",
        )
        
        return fig
    
    def _render_nutrition_fallback(self, data: NutritionData) -> None:
        """Renderiza fallback quando Plotly não está disponível."""
        st.markdown(
            """
            <div style="font-size: 0.86rem; color: var(--text-muted); margin-bottom: 0.6rem;">
                📊 <b>Consumo Nutricional (últimos 14 dias):</b>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        for i, (data_str, cal, prot) in enumerate(
            zip(data.datas, data.calorias, data.proteina)
        ):
            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between;
                    padding: 0.4rem 0; border-bottom: 1px solid var(--border-subtle);">
                    <span>{data_str}</span>
                    <span style="font-weight: 700;">
                        {cal:.0f} kcal · {prot:.0f}g prot
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )


# Funções de compatibilidade
def _tab_peso(db, perfil_id: str, nome: str) -> None:
    """Renderiza tab de peso (compatibilidade)."""
    try:
        renderer = PatientDetailChartsRenderer(db)
        renderer.render_peso(perfil_id, nome)
    except Exception as e:
        logger.error(f"Erro ao renderizar tab peso: {e}", exc_info=True)
        st.error("❌ Erro ao carregar evolução de peso.")


def _tab_nutricao(db, perfil_id: str) -> None:
    """Renderiza tab de nutrição (compatibilidade)."""
    try:
        renderer = PatientDetailChartsRenderer(db)
        renderer.render_nutricao(perfil_id)
    except Exception as e:
        logger.error(f"Erro ao renderizar tab nutrição: {e}", exc_info=True)
        st.error("❌ Erro ao carregar dados de nutrição.")
