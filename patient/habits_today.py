"""
Melshape — Hábitos: tab de hoje e detalhe.
"""
import streamlit as st
from typing import Dict, Any, List, Set, Optional, Tuple
import logging

from services.habit_service import HabitService
from views.components.cards import empty_state, show_new_achievements
from views.patient.habits_detail import render_detalhe_habito

logger = logging.getLogger("Melshape.HabitsToday")


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

# Constantes de configuração
DIAS_CALENDARIO_COMPACTO = 7
DIAS_ADERENCIA = 7
MAX_NOME_BOTAO = 20


class HabitsTodayRenderer:
    """Renderer dedicado para tab de hoje."""
    
    def __init__(self, svc: HabitService, gami, user: Dict[str, Any]):
        self.svc = svc
        self.gami = gami
        self.user = user
    
    def render(self, habitos: List[Dict], feitos_hoje: Set[str]) -> None:
        """Renderiza tab de hoje."""
        if not habitos:
            empty_state(
                "📋",
                "Nenhum hábito criado",
                "Vá em 'Novo Hábito' para começar",
            )
            return
        
        for habito in habitos:
            self._render_habito_item(habito, feitos_hoje)
    
    def _render_habito_item(self, habito: Dict[str, Any],
                             feitos_hoje: Set[str]) -> None:
        """Renderiza um item de hábito."""
        habito_id = habito.get("id", "")
        nome = habito.get("nome", "")
        icone = habito.get("icone", "⭐")
        categoria_key = habito.get("categoria", "geral")
        
        if not habito_id:
            logger.warning("Hábito sem ID encontrado")
            return
        
        # Obtém dados do hábito
        categoria_label = self._get_categoria_label(categoria_key)
        feito = habito_id in feitos_hoje
        streak = self._get_streak(habito_id)
        aderencia = self._get_aderencia(habito_id)
        calendario = self._get_calendario(habito_id)
        
        # Renderiza card
        self._render_card_habito(
            habito_id, nome, icone, categoria_label,
            feito, streak, aderencia, calendario
        )
        
        # Renderiza botões de ação
        self._render_botoes_acao(habito_id, nome, icone, feito)
    
    def _get_categoria_label(self, categoria_key: str) -> str:
        """Obtém label da categoria de forma segura."""
        try:
            _, label = CATEGORIAS.get(categoria_key, ("⭐", "Geral"))
            return label
        except Exception as e:
            logger.debug(f"Erro ao obter label da categoria '{categoria_key}': {e}")
            return "Geral"
    
    @st.cache_data(ttl=30)
    def _get_streak(_self, habito_id: str) -> int:
        """Obtém streak do hábito (com cache)."""
        try:
            streak = _self.svc.streak_habito(habito_id)
            return int(streak) if streak is not None else 0
        except Exception as e:
            logger.error(f"Erro ao obter streak do hábito {habito_id}: {e}", exc_info=True)
            return 0
    
    @st.cache_data(ttl=30)
    def _get_aderencia(_self, habito_id: str) -> float:
        """Obtém aderência do hábito (com cache)."""
        try:
            aderencia = _self.svc.aderencia(habito_id, days=DIAS_ADERENCIA)
            return max(0.0, min(float(aderencia), 100.0))
        except Exception as e:
            logger.error(f"Erro ao obter aderência do hábito {habito_id}: {e}", exc_info=True)
            return 0.0
    
    @st.cache_data(ttl=30)
    def _get_calendario(_self, habito_id: str) -> List[Dict]:
        """Obtém calendário compacto do hábito (com cache)."""
        try:
            calendario = _self.svc.calendario(habito_id, days=DIAS_CALENDARIO_COMPACTO)
            return calendario if isinstance(calendario, list) else []
        except Exception as e:
            logger.error(f"Erro ao obter calendário do hábito {habito_id}: {e}", exc_info=True)
            return []
    
    def _render_card_habito(
        self,
        habito_id: str,
        nome: str,
        icone: str,
        categoria_label: str,
        feito: bool,
        streak: int,
        aderencia: float,
        calendario: List[Dict],
    ) -> None:
        """Renderiza card do hábito."""
        dots = self._render_calendario_dots(calendario)
        cor_card = "border-color: var(--success);" if feito else ""
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" 
                style="margin-bottom: 0.7rem; {cor_card}">
                <div style="display: flex; justify-content: space-between;
                    align-items: flex-start;">
                    <div style="display: flex; align-items: center; gap: 0.7rem;">
                        <span style="font-size: 1.6rem;">{icone}</span>
                        <div>
                            <div style="font-weight: 700; font-size: 0.96rem; color: var(--text);">
                                {nome}
                            </div>
                            <div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 0.15rem;">
                                {categoria_label} · {streak}d seguidos · {aderencia:.0f}% (7d)
                            </div>
                        </div>
                    </div>
                    <div style="font-size: 0.88rem; letter-spacing: 1px;">
                        {dots}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_calendario_dots(self, calendario: List[Dict]) -> str:
        """Renderiza dots do calendário compacto."""
        try:
            return "".join(
                "🟢" if dia.get("concluido") else "⚫"
                for dia in calendario
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar dots do calendário: {e}")
            return ""
    
    def _render_botoes_acao(
        self,
        habito_id: str,
        nome: str,
        icone: str,
        feito: bool,
    ) -> None:
        """Renderiza botões de ação do hábito."""
        col_btn, col_arch = st.columns([4, 1])
        
        with col_btn:
            self._render_botao_marcar(habito_id, nome, icone, feito)
        
        with col_arch:
            self._render_botao_arquivar(habito_id)
    
    def _render_botao_marcar(
        self,
        habito_id: str,
        nome: str,
        icone: str,
        feito: bool,
    ) -> None:
        """Renderiza botão de marcar hábito."""
        if feito:
            st.button(
                "✅ Concluído",
                key=f"h_done_{habito_id}",
                disabled=True,
                use_container_width=True,
            )
        else:
            # Trunca nome se muito longo
            nome_display = nome[:MAX_NOME_BOTAO] if len(nome) > MAX_NOME_BOTAO else nome
            
            if st.button(
                f"Marcar {nome_display}",
                key=f"h_reg_{habito_id}",
                type="primary",
                use_container_width=True,
            ):
                self._marcar_habito(habito_id, nome, icone)
    
    def _render_botao_arquivar(self, habito_id: str) -> None:
        """Renderiza botão de arquivar hábito."""
        if st.button(
            "🗄️",
            key=f"h_arch_{habito_id}",
            help="Arquivar hábito",
        ):
            self._arquivar_habito(habito_id)
    
    def _marcar_habito(self, habito_id: str, nome: str, icone: str) -> None:
        """Marca um hábito como concluído com tratamento de erros."""
        try:
            resultado = self.svc.registrar(habito_id)
            
            if not isinstance(resultado, dict):
                logger.error(f"Resultado inválido ao registrar hábito {habito_id}")
                st.error("❌ Erro ao registrar hábito.")
                return
            
            if resultado.get("ok"):
                self._processar_sucesso_registro(resultado, nome, icone)
            else:
                st.error("❌ Erro ao registrar hábito.")
        except Exception as e:
            logger.error(f"Erro ao marcar hábito {habito_id}: {e}", exc_info=True)
            st.error(f"❌ Erro ao registrar hábito: {str(e)}")
    
    def _processar_sucesso_registro(
        self,
        resultado: Dict[str, Any],
        nome: str,
        icone: str,
    ) -> None:
        """Processa sucesso do registro de hábito."""
        xp_ganho = resultado.get("xp_ganho", 0)
        bonus_msg = resultado.get("bonus_msg")
        
        st.toast(f"{icone} {nome} concluído! +{xp_ganho} XP", icon="✅")
        
        if bonus_msg:
            st.toast(bonus_msg, icon="🎉")
        
        # Verifica conquistas
        self._verificar_conquistas()
        
        # Limpa cache e rerun
        st.cache_data.clear()
        st.rerun()
    
    def _verificar_conquistas(self) -> None:
        """Verifica e exibe novas conquistas."""
        try:
            novos = self.gami.check_achievements(self.user)
            show_new_achievements(novos)
        except Exception as e:
            logger.error(f"Erro ao verificar conquistas: {e}", exc_info=True)
    
    def _arquivar_habito(self, habito_id: str) -> None:
        """Arquiva um hábito com tratamento de erros."""
        try:
            self.svc.db.arquivar_habito(habito_id)
            st.toast("🗄️ Hábito arquivado.", icon="✅")
            
            # Limpa cache e rerun
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao arquivar hábito {habito_id}: {e}", exc_info=True)
            st.error(f"❌ Erro ao arquivar hábito: {str(e)}")


class HabitsDetailRenderer:
    """Renderer dedicado para tab de detalhe."""
    
    def __init__(self, svc: HabitService):
        self.svc = svc
    
    def render(self, habitos: List[Dict]) -> None:
        """Renderiza tab de detalhe."""
        if not habitos:
            empty_state("📈", "Sem hábitos para analisar")
            return
        
        nomes = self._extrair_nomes_habitos(habitos)
        
        idx = st.selectbox(
            "Selecione o hábito",
            range(len(nomes)),
            format_func=lambda i: nomes[i],
            key="habit_detail_sel",
            label_visibility="collapsed",
        )
        
        habito_selecionado = self._get_habito_por_indice(habitos, idx)
        
        if habito_selecionado:
            render_detalhe_habito(habito_selecionado, self.svc)
    
    def _extrair_nomes_habitos(self, habitos: List[Dict]) -> List[str]:
        """Extrai nomes dos hábitos para o selectbox."""
        try:
            return [
                f"{h.get('icone', '')} {h.get('nome', '')}"
                for h in habitos
            ]
        except Exception as e:
            logger.error(f"Erro ao extrair nomes de hábitos: {e}", exc_info=True)
            return ["Hábito inválido"]
    
    def _get_habito_por_indice(
        self,
        habitos: List[Dict],
        idx: int,
    ) -> Optional[Dict]:
        """Obtém hábito por índice de forma segura."""
        try:
            if 0 <= idx < len(habitos):
                return habitos[idx]
            return None
        except Exception as e:
            logger.error(f"Erro ao obter hábito por índice {idx}: {e}")
            return None


# Funções de compatibilidade
def _tab_hoje(
    habitos: List[Dict],
    feitos_hoje: Set[str],
    svc: HabitService,
    gami,
    user: Dict[str, Any],
) -> None:
    """Renderiza tab de hoje (compatibilidade)."""
    renderer = HabitsTodayRenderer(svc, gami, user)
    renderer.render(habitos, feitos_hoje)


def _tab_detalhe(habitos: List[Dict], svc: HabitService) -> None:
    """Renderiza tab de detalhe (compatibilidade)."""
    renderer = HabitsDetailRenderer(svc)
    renderer.render(habitos)


def _melhor_streak_geral(svc: HabitService, habitos: List[Dict]) -> int:
    """Calcula o melhor streak geral entre todos os hábitos."""
    if not habitos:
        return 0
    
    try:
        streaks = []
        for h in habitos:
            habito_id = h.get("id")
            if habito_id:
                streak = svc.streak_habito(habito_id)
                streaks.append(streak)
        
        return max(streaks, default=0)
    except Exception as e:
        logger.error(f"Erro ao calcular melhor streak geral: {e}", exc_info=True)
        return 0
