"""
Melshape — Hub de Registro.
Regra dos 3 cliques: toda ação de registro em no máximo 3 interações.

Fluxo:
  1. Usuário clica em "Registrar" na sidebar → esta tela
  2. Escolhe o tipo (refeição / peso / água / check-in)
  3. Preenche e confirma → toast de feedback + XP

Botão flutuante "+" também navega para cá.
"""
import streamlit as st
from typing import Dict, Any, Optional, List, Tuple
from datetime import date
from dataclasses import dataclass, field
import logging

from views.patient.register_hub_quick import _form_agua, _form_checkin
from views.components.cards import (
    section_header, empty_state, metric_card,
    show_new_achievements, xp_toast, alert,
)
import config

logger = logging.getLogger("Melshape.RegisterHub")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Tipos de registro
TIPOS_REGISTRO = {
    "🍽️ Refeição": "meal",
    "⚖️ Peso": "weight",
    "💧 Água": "hydration",
    "✅ Check-in": "checkin",
}

# Tipos de refeição
TIPOS_REFEICAO = {
    "cafe_manha": "☀️ Café",
    "almoco": "🍽️ Almoço",
    "jantar": "🌙 Jantar",
    "lanche": "🍎 Lanche",
    "pre_pos_treino": "💪 Pré/Pós Treino",
    "outro": "📋 Outro",
}

# Limites
MIN_PESO = 20.0
MAX_PESO = 300.0
MIN_QUANTIDADE = 1.0
MAX_QUANTIDADE = 2000.0
MIN_GORDURA = 0.0
MAX_GORDURA = 80.0
MIN_MASSA = 0.0
MAX_MASSA = 150.0
MIN_VOLUME_ML = 0.0
MAX_VOLUME_ML = 800.0

# Valores padrão
DEFAULT_PESO_ATUAL = 70.0
DEFAULT_PORCAO = 100.0
DEFAULT_QUANTIDADE = 100.0

# Limites de busca
MAX_SUGESTOES_FREQUENTES = 5
MAX_RESULTADOS_BUSCA = 8
MAX_NOME_SUGESTAO = 18

# Chaves de session state
SESSION_KEY_HUB_TIPO = "hub_tipo"
SESSION_KEY_HUB_FOOD_SELECTED = "hub_food_selected_obj"
SESSION_KEY_HUB_FOOD_SEARCH = "hub_food_search"


@dataclass
class FoodSelection:
    """Estado da seleção de alimento."""
    search_term: str = ""
    selected: Optional[Dict] = None


class RegisterHubRenderer:
    """Renderer dedicado para hub de registro."""
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user or {}
        self.db = services.get("db")
        self.nutr = services.get("nutrition")
        self.gami = services.get("gamification")
        self.foods = services.get("foods")
        self.health_mode = user.get("health_mode", "general")
        self.is_bariatric = self._is_bariatric_mode()
        self._init_session_state()
    
    def _is_bariatric_mode(self) -> bool:
        """Verifica se usuário está em modo bariátrico."""
        try:
            return (
                self.user.get("is_bariatric", False) or
                self.health_mode == "bariatric"
            )
        except Exception as e:
            logger.debug(f"Erro ao verificar modo bariátrico: {e}")
            return False
    
    def _init_session_state(self) -> None:
        """Inicializa estado da sessão com tratamento de erros."""
        try:
            if SESSION_KEY_HUB_TIPO not in st.session_state:
                st.session_state[SESSION_KEY_HUB_TIPO] = "meal"
            if SESSION_KEY_HUB_FOOD_SELECTED not in st.session_state:
                st.session_state[SESSION_KEY_HUB_FOOD_SELECTED] = None
            if SESSION_KEY_HUB_FOOD_SEARCH not in st.session_state:
                st.session_state[SESSION_KEY_HUB_FOOD_SEARCH] = ""
        except Exception as e:
            logger.error(f"Erro ao inicializar session state: {e}", exc_info=True)
    
    def render(self) -> None:
        """Renderiza hub de registro."""
        section_header("➕ Registrar", "Escolha o que quer registrar hoje")
        
        # Seleção do tipo
        self._render_tipo_selecao()
        
        st.divider()
        
        # Formulário correspondente
        tipo = self._get_tipo_atual()
        self._render_formulario(tipo)
    
    def _get_tipo_atual(self) -> str:
        """Obtém tipo atual do session state."""
        try:
            return st.session_state.get(SESSION_KEY_HUB_TIPO, "meal")
        except Exception as e:
            logger.error(f"Erro ao obter tipo atual: {e}")
            return "meal"
    
    def _render_tipo_selecao(self) -> None:
        """Renderiza seleção do tipo de registro."""
        cols = st.columns(4)
        tipos_labels = list(TIPOS_REGISTRO.keys())
        
        for i, label in enumerate(tipos_labels):
            with cols[i]:
                tipo_valor = TIPOS_REGISTRO[label]
                if st.button(
                    label,
                    use_container_width=True,
                    key=f"hub_{i}",
                ):
                    self._selecionar_tipo(tipo_valor)
    
    def _selecionar_tipo(self, tipo_valor: str) -> None:
        """Seleciona tipo e atualiza session state."""
        try:
            st.session_state[SESSION_KEY_HUB_TIPO] = tipo_valor
            
            # Limpa seleção de alimento ao mudar de tipo
            if tipo_valor != "meal":
                st.session_state[SESSION_KEY_HUB_FOOD_SELECTED] = None
            
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao selecionar tipo: {e}", exc_info=True)
            st.error("❌ Erro ao selecionar tipo. Tente novamente.")
    
    def _render_formulario(self, tipo: str) -> None:
        """Renderiza formulário baseado no tipo selecionado."""
        try:
            if tipo == "meal":
                self._render_meal_form()
            elif tipo == "weight":
                self._render_weight_form()
            elif tipo == "hydration":
                _form_agua(self.db, self.gami)
            elif tipo == "checkin":
                _form_checkin(self.db, self.gami)
        except Exception as e:
            logger.error(f"Erro ao renderizar formulário tipo '{tipo}': {e}", exc_info=True)
            alert(f"❌ Erro ao carregar formulário de {tipo}.", "error")
    
    # ── FORMULÁRIO DE REFEIÇÃO ─────────────────────────────────────────────────
    def _render_meal_form(self) -> None:
        """Renderiza formulário de refeição."""
        st.markdown("#### 🍽️ Registrar Refeição")
        
        # Busca de alimento
        termo, resultados = self._render_busca_alimento()
        
        # Seleção do alimento
        alimento_selecionado = self._render_selecao_alimento(resultados)
        
        if not alimento_selecionado:
            return
        
        # Formulário final
        self._render_meal_detail_form(alimento_selecionado)
    
    def _render_busca_alimento(self) -> Tuple[str, List[Dict]]:
        """Renderiza campo de busca de alimentos."""
        frequentes = self._get_sugestoes_frequentes()
        termo_atual = self._get_termo_busca()
        
        col1, col2 = st.columns([3, 1])
        with col1:
            termo = st.text_input(
                "Buscar alimento",
                placeholder="Ex: frango, arroz, ovo...",
                key=SESSION_KEY_HUB_FOOD_SEARCH,
                label_visibility="collapsed",
            )
        
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
        
        # Sugestões rápidas
        if frequentes and not termo:
            self._render_sugestoes_frequentes(frequentes)
        
        # Busca
        resultados = self._buscar_alimentos(termo, frequentes)
        
        return termo, resultados
    
    def _get_sugestoes_frequentes(self) -> List[str]:
        """Obtém sugestões de alimentos frequentes."""
        if not self.nutr:
            return []
        
        try:
            frequentes = self.nutr.suggest_foods()
            return frequentes if isinstance(frequentes, list) else []
        except Exception as e:
            logger.error(f"Erro ao obter sugestões frequentes: {e}", exc_info=True)
            return []
    
    def _get_termo_busca(self) -> str:
        """Obtém termo de busca atual."""
        try:
            return st.session_state.get(SESSION_KEY_HUB_FOOD_SEARCH, "")
        except Exception as e:
            logger.debug(f"Erro ao obter termo de busca: {e}")
            return ""
    
    def _render_sugestoes_frequentes(self, frequentes: List[str]) -> None:
        """Renderiza sugestões de alimentos frequentes."""
        st.markdown(
            """
            <div style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.4rem;">
                ⚡ Recentes:
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        num_cols = min(MAX_SUGESTOES_FREQUENTES, len(frequentes))
        cols_freq = st.columns(num_cols)
        
        for i, nome in enumerate(frequentes[:MAX_SUGESTOES_FREQUENTES]):
            with cols_freq[i]:
                nome_display = nome[:MAX_NOME_SUGESTAO]
                if st.button(
                    nome_display,
                    key=f"freq_{i}",
                    use_container_width=True,
                ):
                    self._selecionar_sugestao(nome)
    
    def _selecionar_sugestao(self, nome: str) -> None:
        """Seleciona sugestão e atualiza busca."""
        try:
            st.session_state[SESSION_KEY_HUB_FOOD_SEARCH] = nome
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao selecionar sugestão: {e}", exc_info=True)
    
    def _buscar_alimentos(self, termo: str, frequentes: List[str]) -> List[Dict]:
        """Busca alimentos com tratamento de erros."""
        if not self.foods:
            logger.warning("Serviço de alimentos não disponível")
            return []
        
        try:
            resultados = self.foods.search_foods(
                termo,
                limit=MAX_RESULTADOS_BUSCA,
                frequent_foods=frequentes,
            )
            return resultados if isinstance(resultados, list) else []
        except Exception as e:
            logger.error(f"Erro ao buscar alimentos: {e}", exc_info=True)
            return []
    
    def _render_selecao_alimento(self, resultados: List[Dict]) -> Optional[Dict]:
        """Renderiza seleção de alimento e retorna o selecionado."""
        alimento_selecionado = self._get_alimento_selecionado()
        
        if not resultados and not alimento_selecionado:
            empty_state(
                "🔍",
                "Busque um alimento acima",
                "Digite pelo menos 2 letras para buscar nos 695 alimentos",
            )
            return None
        
        if resultados and not alimento_selecionado:
            return self._render_lista_selecao(resultados)
        
        return alimento_selecionado
    
    def _get_alimento_selecionado(self) -> Optional[Dict]:
        """Obtém alimento selecionado do session state."""
        try:
            return st.session_state.get(SESSION_KEY_HUB_FOOD_SELECTED)
        except Exception as e:
            logger.debug(f"Erro ao obter alimento selecionado: {e}")
            return None
    
    def _render_lista_selecao(self, resultados: List[Dict]) -> Optional[Dict]:
        """Renderiza lista de seleção de alimentos."""
        nomes = self._formatar_nomes_resultados(resultados)
        
        idx = st.selectbox(
            "Selecione o alimento",
            range(len(nomes)),
            format_func=lambda i: nomes[i],
            key="hub_food_idx",
            label_visibility="collapsed",
        )
        
        if st.button("Selecionar →", key="hub_food_confirm"):
            self._selecionar_alimento(resultados[idx])
        
        return None
    
    def _formatar_nomes_resultados(self, resultados: List[Dict]) -> List[str]:
        """Formata nomes dos resultados de busca."""
        try:
            return [
                f"{self._extrair_nome_alimento(r)} "
                f"({self._extrair_calorias(r):.0f} kcal/100g)"
                for r in resultados
            ]
        except Exception as e:
            logger.error(f"Erro ao formatar nomes: {e}", exc_info=True)
            return ["Alimento"]
    
    def _extrair_nome_alimento(self, resultado: Dict) -> str:
        """Extrai nome do alimento de forma segura."""
        try:
            return resultado.get("nome", resultado.get("name", "Alimento"))
        except Exception:
            return "Alimento"
    
    def _extrair_calorias(self, resultado: Dict) -> float:
        """Extrai calorias do alimento de forma segura."""
        try:
            cal = resultado.get("calorias", resultado.get("calories", 0))
            return float(cal)
        except (ValueError, TypeError):
            return 0.0
    
    def _selecionar_alimento(self, alimento: Dict) -> None:
        """Seleciona alimento e atualiza session state."""
        try:
            st.session_state[SESSION_KEY_HUB_FOOD_SELECTED] = alimento
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao selecionar alimento: {e}", exc_info=True)
            st.error("❌ Erro ao selecionar alimento. Tente novamente.")
    
    def _render_meal_detail_form(self, alimento: Dict) -> None:
        """Renderiza formulário detalhado da refeição."""
        dados_alimento = self._extrair_dados_alimento(alimento)
        
        # Card do alimento
        self._render_card_alimento(dados_alimento)
        
        # Quantidade e tipo
        quantidade, horario, tipo_refeicao, volume_ml = self._render_campos_refeicao(
            dados_alimento["porcao_padrao"]
        )
        
        # Preview de macros
        macros = self._calcular_macros(dados_alimento, quantidade)
        self._render_macros_preview(macros)
        
        # Botões
        self._render_botoes_refeicao(
            alimento, quantidade, horario, tipo_refeicao, volume_ml
        )
    
    def _extrair_dados_alimento(self, alimento: Dict) -> Dict[str, Any]:
        """Extrai dados do alimento de forma segura."""
        try:
            return {
                "nome": self._extrair_nome_alimento(alimento),
                "cal100": float(alimento.get("calorias", alimento.get("calories", 0))),
                "prot100": float(alimento.get("proteina", alimento.get("protein", 0))),
                "carb100": float(alimento.get("carboidratos", alimento.get("carbs", 0))),
                "fat100": float(alimento.get("gorduras", alimento.get("fat", 0))),
                "porcao_padrao": float(alimento.get("porcao_padrao", DEFAULT_PORCAO)),
            }
        except (ValueError, TypeError) as e:
            logger.error(f"Erro ao extrair dados do alimento: {e}", exc_info=True)
            return {
                "nome": "Alimento",
                "cal100": 0.0,
                "prot100": 0.0,
                "carb100": 0.0,
                "fat100": 0.0,
                "porcao_padrao": DEFAULT_PORCAO,
            }
    
    def _render_card_alimento(self, dados: Dict[str, Any]) -> None:
        """Renderiza card do alimento selecionado."""
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="margin-bottom: 0.9rem;">
                <div style="font-weight: 700; color: var(--text); font-size: 1rem;">
                    {dados['nome']}
                </div>
                <div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.35rem;">
                    Por 100g: {dados['cal100']:.0f} kcal · {dados['prot100']:.1f}g prot · 
                    {dados['carb100']:.1f}g carb · {dados['fat100']:.1f}g gord
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_campos_refeicao(self, porcao_padrao: float) -> Tuple[float, str, str, float]:
        """Renderiza campos do formulário de refeição."""
        col_q, col_t, col_tipo = st.columns([2, 1, 2])
        
        with col_q:
            quantidade = st.number_input(
                "Quantidade (g)",
                min_value=MIN_QUANTIDADE,
                max_value=MAX_QUANTIDADE,
                value=porcao_padrao,
                step=10.0,
                key="hub_qtd",
            )
        
        with col_t:
            horario = st.text_input(
                "Horário",
                value="",
                placeholder="12:30",
                key="hub_horario",
            )
        
        with col_tipo:
            tipo_refeicao = self._render_selectbox_tipo_refeicao()
        
        # Volume para bariátrico
        volume_ml = 0.0
        if self.is_bariatric:
            volume_ml = self._render_campo_volume()
        
        return quantidade, horario, tipo_refeicao, volume_ml
    
    def _render_selectbox_tipo_refeicao(self) -> str:
        """Renderiza selectbox de tipo de refeição."""
        tipos = list(TIPOS_REFEICAO.keys())
        return st.selectbox(
            "Tipo",
            tipos,
            format_func=lambda x: TIPOS_REFEICAO.get(x, x),
            key="hub_tipo_ref",
        )
    
    def _render_campo_volume(self) -> float:
        """Renderiza campo de volume para bariátrico."""
        return st.number_input(
            "Volume (ml) — controle bariátrico",
            min_value=MIN_VOLUME_ML,
            max_value=MAX_VOLUME_ML,
            value=0.0,
            step=10.0,
            key="hub_vol",
        )
    
    def _calcular_macros(self, dados: Dict, quantidade: float) -> Dict[str, float]:
        """Calcula macros baseado na quantidade."""
        try:
            fator = quantidade / 100
            return {
                "cal": dados["cal100"] * fator,
                "prot": dados["prot100"] * fator,
                "carb": dados["carb100"] * fator,
                "fat": dados["fat100"] * fator,
            }
        except Exception as e:
            logger.error(f"Erro ao calcular macros: {e}", exc_info=True)
            return {"cal": 0.0, "prot": 0.0, "carb": 0.0, "fat": 0.0}
    
    def _render_macros_preview(self, macros: Dict[str, float]) -> None:
        """Renderiza preview de macros."""
        alerta = self._validar_macros(macros)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            metric_card(f"{macros['cal']:.0f}", "kcal", "🔥")
        with col2:
            metric_card(f"{macros['prot']:.1f}g", "proteína", "🥩")
        with col3:
            metric_card(f"{macros['carb']:.1f}g", "carbos", "🌾")
        with col4:
            metric_card(f"{macros['fat']:.1f}g", "gordura", "🫙")
        
        if alerta:
            alert(alerta, "warning")
    
    def _validar_macros(self, macros: Dict[str, float]) -> Optional[str]:
        """Valida macros com cross-validation."""
        if not self.nutr:
            return None
        
        try:
            return self.nutr.cross_validate(
                macros["cal"],
                macros["prot"],
                macros["carb"],
                macros["fat"],
            )
        except Exception as e:
            logger.error(f"Erro ao validar macros: {e}", exc_info=True)
            return None
    
    def _render_botoes_refeicao(
        self,
        alimento: Dict,
        quantidade: float,
        horario: str,
        tipo_refeicao: str,
        volume_ml: float,
    ) -> None:
        """Renderiza botões de ação da refeição."""
        col_reg, col_trocar = st.columns([2, 1])
        
        with col_reg:
            if st.button(
                "✅ Registrar refeição",
                type="primary",
                use_container_width=True,
                key="hub_save_meal",
            ):
                self._registrar_refeicao(
                    alimento, quantidade, horario, tipo_refeicao, volume_ml
                )
        
        with col_trocar:
            if st.button(
                "🔄 Trocar alimento",
                use_container_width=True,
                key="hub_change_food",
            ):
                self._limpar_selecao_alimento()
    
    def _limpar_selecao_alimento(self) -> None:
        """Limpa seleção de alimento."""
        try:
            st.session_state[SESSION_KEY_HUB_FOOD_SELECTED] = None
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao limpar seleção: {e}", exc_info=True)
    
    def _registrar_refeicao(
        self,
        alimento: Dict,
        quantidade: float,
        horario: str,
        tipo_refeicao: str,
        volume_ml: float,
    ) -> None:
        """Registra uma refeição com validações."""
        # Validações
        if not self._validar_refeicao(quantidade):
            return
        
        fator = quantidade / 100
        
        try:
            ok, alerta = self.nutr.register_meal(
                food=alimento,
                quantity=fator,
                meal_time=horario,
                meal_type=tipo_refeicao,
                volume_ml=volume_ml,
            )
            
            if ok:
                self._processar_sucesso_refeicao(alerta)
            else:
                st.toast("❌ Erro ao registrar. Tente novamente.", icon="❌")
        except Exception as e:
            logger.error(f"Erro ao registrar refeição: {e}", exc_info=True)
            st.toast("❌ Erro ao registrar refeição.", icon="❌")
    
    def _validar_refeicao(self, quantidade: float) -> bool:
        """Valida dados da refeição."""
        if quantidade < MIN_QUANTIDADE or quantidade > MAX_QUANTIDADE:
            st.warning(f"⚠️ Quantidade deve estar entre {MIN_QUANTIDADE} e {MAX_QUANTIDADE}g.")
            return False
        
        return True
    
    def _processar_sucesso_refeicao(self, alerta: Optional[str]) -> None:
        """Processa sucesso do registro de refeição."""
        st.toast("🍽️ Refeição registrada!", icon="✅")
        
        if alerta:
            st.toast(alerta, icon="⚠️")
        
        # Orchestrator ou gamification
        self._processar_recompensa_refeicao()
        
        # Limpa estado
        self._limpar_estado_refeicao()
        st.rerun()
    
    def _processar_recompensa_refeicao(self) -> None:
        """Processa recompensa via Orchestrator ou gamification."""
        orch = self.services.get("orchestrator")
        
        if orch:
            try:
                resultado = orch.processar("refeicao", self.user, {})
                
                if resultado and resultado.xp_ganho:
                    xp_toast(resultado.xp_ganho, "refeição")
                
                if resultado and hasattr(resultado, "badges_novos"):
                    show_new_achievements(resultado.badges_novos)
            except Exception as e:
                logger.error(f"Erro no Orchestrator: {e}", exc_info=True)
                self._fallback_gamification()
        else:
            self._fallback_gamification()
    
    def _fallback_gamification(self) -> None:
        """Fallback para gamification quando Orchestrator não está disponível."""
        try:
            if self.gami:
                novos = self.gami.check_achievements(self.user)
                show_new_achievements(novos)
        except Exception as e:
            logger.error(f"Erro no fallback gamification: {e}", exc_info=True)
    
    def _limpar_estado_refeicao(self) -> None:
        """Limpa estado da refeição."""
        try:
            st.session_state[SESSION_KEY_HUB_FOOD_SELECTED] = None
            st.session_state[SESSION_KEY_HUB_FOOD_SEARCH] = ""
        except Exception as e:
            logger.error(f"Erro ao limpar estado: {e}", exc_info=True)
    
    # ── FORMULÁRIO DE PESO ─────────────────────────────────────────────────────
    def _render_weight_form(self) -> None:
        """Renderiza formulário de peso."""
        st.markdown("#### ⚖️ Registrar Peso")
        
        peso_atual = self._get_peso_atual()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            peso = st.number_input(
                "Peso (kg)",
                min_value=MIN_PESO,
                max_value=MAX_PESO,
                value=peso_atual,
                step=0.1,
                key="hub_peso",
            )
        
        with col2:
            gordura = st.number_input(
                "% Gordura (opcional)",
                min_value=MIN_GORDURA,
                max_value=MAX_GORDURA,
                value=0.0,
                step=0.1,
                key="hub_gordura",
            )
        
        massa = st.number_input(
            "Massa muscular kg (opcional)",
            min_value=MIN_MASSA,
            max_value=MAX_MASSA,
            value=0.0,
            step=0.1,
            key="hub_massa",
        )
        
        observacao = st.text_input(
            "Observação",
            placeholder="Ex: Após treino",
            key="hub_peso_obs",
        )
        
        # Diferença vs peso anterior
        self._render_diferenca_peso(peso, peso_atual)
        
        if st.button(
            "✅ Registrar peso",
            type="primary",
            use_container_width=True,
            key="hub_save_peso",
        ):
            self._registrar_peso(peso, gordura, massa, observacao)
    
    def _get_peso_atual(self) -> float:
        """Obtém peso atual do usuário."""
        try:
            peso = self.user.get("current_weight")
            return float(peso) if peso is not None else DEFAULT_PESO_ATUAL
        except (ValueError, TypeError):
            return DEFAULT_PESO_ATUAL
    
    def _render_diferenca_peso(self, peso: float, peso_atual: float) -> None:
        """Renderiza alerta de diferença de peso."""
        if peso == peso_atual or peso_atual <= 0:
            return
        
        try:
            diff = peso - peso_atual
            emoji = "📉" if diff < 0 else "📈"
            cor = "success" if diff < 0 else "warning"
            alert(
                f"{emoji} Diferença: {diff:+.1f} kg em relação ao último registro",
                cor,
            )
        except Exception as e:
            logger.debug(f"Erro ao calcular diferença de peso: {e}")
    
    def _registrar_peso(
        self,
        peso: float,
        gordura: float,
        massa: float,
        observacao: str,
    ) -> None:
        """Registra peso com validações."""
        # Validações
        if not self._validar_peso(peso):
            return
        
        try:
            from core.models import WeightLog
            
            log = WeightLog(
                weight=peso,
                body_fat=gordura,
                muscle_mass=massa,
                log_date=date.today().isoformat(),
                notes=observacao,
            )
            
            success = self.db.save_weight(log)
            
            if success:
                self._processar_sucesso_peso(peso)
            else:
                st.toast("❌ Erro ao registrar peso.", icon="❌")
        except Exception as e:
            logger.error(f"Erro ao registrar peso: {e}", exc_info=True)
            st.toast("❌ Erro ao registrar peso.", icon="❌")
    
    def _validar_peso(self, peso: float) -> bool:
        """Valida peso antes de registrar."""
        if peso < MIN_PESO or peso > MAX_PESO:
            st.warning(f"⚠️ Peso deve estar entre {MIN_PESO} e {MAX_PESO} kg.")
            return False
        
        return True
    
    def _processar_sucesso_peso(self, peso: float) -> None:
        """Processa sucesso do registro de peso."""
        # Atualiza peso atual
        try:
            st.session_state.user["current_weight"] = peso
        except Exception as e:
            logger.error(f"Erro ao atualizar peso no session state: {e}", exc_info=True)
        
        st.toast(f"⚖️ {peso:.1f} kg registrado!", icon="✅")
        
        # Orchestrator ou gamification
        self._processar_recompensa_peso(peso)
        
        # Verifica conquistas
        self._verificar_conquistas()
        
        st.rerun()
    
    def _processar_recompensa_peso(self, peso: float) -> None:
        """Processa recompensa via Orchestrator ou gamification."""
        orch = self.services.get("orchestrator")
        
        if orch:
            try:
                resultado = orch.processar("peso", self.user, {"peso": peso})
                
                if resultado and resultado.xp_ganho:
                    xp_toast(resultado.xp_ganho, "pesagem")
                
                if resultado and hasattr(resultado, "badges_novos"):
                    show_new_achievements(resultado.badges_novos)
                
                return
            except Exception as e:
                logger.error(f"Erro no Orchestrator: {e}", exc_info=True)
        
        # Fallback
        try:
            if hasattr(self.db, "xp_pesagem"):
                self.db.xp_pesagem()
            xp_toast(30, "pesagem")
        except Exception as e:
            logger.error(f"Erro no fallback XP pesagem: {e}", exc_info=True)
    
    def _verificar_conquistas(self) -> None:
        """Verifica e exibe novas conquistas."""
        try:
            if self.gami:
                novos = self.gami.check_achievements(self.user)
                show_new_achievements(novos)
        except Exception as e:
            logger.error(f"Erro ao verificar conquistas: {e}", exc_info=True)


# Função principal de compatibilidade
def render(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = RegisterHubRenderer(services, user)
    renderer.render()
