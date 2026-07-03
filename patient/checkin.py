"""
Melshape — Check-in Diário Unificado.

O ritual central do MelShape. Uma ação alimenta:
humor → energia → hábito do dia → pequena vitória →
→ Orchestrator → metas → jornada → XP → badge → notificação

Substitui a aba de check-in do register_hub.
"""
import streamlit as st
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import date
import logging

from services.orchestrator import Orchestrator, OrchestratorResult
from views.components.cards import (
    section_header, metric_card, alert,
    show_new_achievements, xp_toast,
)
from views.patient.checkin_result import render_resultado
from views.patient.checkin_done import _tela_ja_feito

logger = logging.getLogger("Melshape.Checkin")


@dataclass
class CheckinData:
    """Dados do check-in."""
    humor: int = 3
    energia: int = 3
    sono: int = 3
    habito_id: Optional[str] = None
    vitoria: str = ""
    dificuldade: str = ""


class CheckinRenderer:
    """Renderer dedicado para check-in diário."""
    
    SLIDER_OPTIONS = [1, 2, 3, 4, 5]
    SONO_LABELS = {
        1: "😖 Péssimo",
        2: "😕 Ruim",
        3: "😐 Regular",
        4: "🙂 Bom",
        5: "😄 Ótimo",
    }
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user
        self.db = services.get("db")
        self.orch = services.get("orchestrator") or Orchestrator(self.db)
        
        # Cache de dados para evitar múltiplas consultas
        self._habitos_cache: Optional[List[Dict]] = None
        self._registros_cache: Optional[set] = None
    
    def render(self) -> None:
        """Renderiza tela de check-in."""
        section_header("✅ Check-in Diário", "Seu ritual de 30 segundos")
        
        # Verifica se já fez hoje
        if self._ja_feito_hoje():
            return
        
        self._render_form()
    
    def _ja_feito_hoje(self) -> bool:
        """Verifica se o check-in já foi feito hoje."""
        try:
            checkin_hoje = self.db.get_checkin_today()
            if checkin_hoje:
                _tela_ja_feito(checkin_hoje, self.db, self.user)
                return True
        except Exception as e:
            logger.error(f"Erro ao verificar check-in de hoje: {e}", exc_info=True)
            st.error("❌ Erro ao verificar status do check-in.")
        
        return False
    
    def _render_form(self) -> None:
        """Renderiza formulário de check-in."""
        health_mode = self.user.get("health_mode", "general")
        data = CheckinData()
        
        self._render_intro_text()
        
        with st.form("checkin_form", clear_on_submit=False):
            # Bloco 1: Como está
            data = self._render_estado_bloco(data)
            
            # Bloco 2: Hábito do dia
            data = self._render_habito_bloco(data)
            
            # Bloco 3: Pequena vitória
            data = self._render_vitoria_bloco(data)
            
            # Bloco 4: Contexto do pilar
            data = self._render_contexto_bloco(data, health_mode)
            
            # Espaçamento antes do botão
            st.markdown('<div style="margin-top: 1.2rem;"></div>', unsafe_allow_html=True)
            
            # Botão de envio
            if st.form_submit_button(
                "✅ Fazer check-in",
                type="primary",
                use_container_width=True,
                key="ci_salvar",
            ):
                self._processar_checkin(data)
    
    def _render_intro_text(self) -> None:
        """Renderiza texto introdutório."""
        st.markdown(
            """
            <div style="font-size: 0.86rem; color: var(--text-muted); margin-bottom: 1.2rem;">
                Como você está agora? Leva menos de 30 segundos.
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_estado_bloco(self, data: CheckinData) -> CheckinData:
        """Renderiza bloco de estado (humor, energia, sono)."""
        col1, col2 = st.columns(2)
        
        with col1:
            data.humor = st.select_slider(
                "😊 Humor",
                options=self.SLIDER_OPTIONS,
                value=data.humor,
                key="ci_humor",
            )
        
        with col2:
            data.energia = st.select_slider(
                "⚡ Energia",
                options=self.SLIDER_OPTIONS,
                value=data.energia,
                key="ci_energia",
            )
        
        data.sono = st.select_slider(
            "😴 Qualidade do sono",
            options=self.SLIDER_OPTIONS,
            value=data.sono,
            format_func=lambda x: self.SONO_LABELS.get(x, "😐"),
            key="ci_sono",
        )
        
        return data
    
    def _render_habito_bloco(self, data: CheckinData) -> CheckinData:
        """Renderiza bloco de hábito do dia."""
        habitos = self._get_habitos()
        feitos = self._get_registros_hoje()
        
        if not habitos:
            return data
        
        pendentes = [h for h in habitos if h.get("id") not in feitos]
        
        if not pendentes:
            st.markdown(
                """
                <div style="margin-top: 0.8rem; padding: 0.6rem 0.8rem; 
                    background: var(--success-light); border-radius: 8px;
                    font-size: 0.82rem; color: var(--success);">
                    ✅ Todos os hábitos de hoje já foram concluídos!
                </div>
                """,
                unsafe_allow_html=True,
            )
            return data
        
        st.markdown(
            """
            <div style="margin-top: 1rem; font-size: 0.82rem;
                font-weight: 600; color: var(--text-muted);">
                📋 Principal hábito de hoje
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        nomes = [
            f'{h.get("icone", "")} {h.get("nome", "")}'
            for h in pendentes
        ]
        
        idx = st.selectbox(
            "Hábito",
            range(len(nomes)),
            format_func=lambda i: nomes[i],
            key="ci_habito_idx",
            label_visibility="collapsed",
        )
        
        data.habito_id = pendentes[idx].get("id")
        
        return data
    
    @st.cache_data(ttl=60)
    def _get_habitos(_self) -> List[Dict]:
        """Obtém lista de hábitos (com cache)."""
        try:
            return _self.db.get_habitos() or []
        except Exception as e:
            logger.error(f"Erro ao buscar hábitos: {e}", exc_info=True)
            return []
    
    @st.cache_data(ttl=30)
    def _get_registros_hoje(_self) -> set:
        """Obtém IDs de hábitos já registrados hoje (com cache)."""
        try:
            registros = _self.db.get_registros_hoje()
            return set(registros) if registros else set()
        except Exception as e:
            logger.error(f"Erro ao buscar registros de hoje: {e}", exc_info=True)
            return set()
    
    def _render_vitoria_bloco(self, data: CheckinData) -> CheckinData:
        """Renderiza bloco de pequena vitória."""
        st.markdown(
            """
            <div style="margin-top: 1rem; font-size: 0.82rem;
                font-weight: 600; color: var(--text-muted);">
                🌟 Pequena vitória de hoje (opcional)
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        data.vitoria = st.text_input(
            "Vitória",
            placeholder="Ex: Tomei água antes do café, dormi antes das 23h...",
            key="ci_vitoria",
            label_visibility="collapsed",
        )
        
        return data
    
    def _render_contexto_bloco(self, data: CheckinData, health_mode: str) -> CheckinData:
        """Renderiza bloco de contexto adaptativo baseado no pilar e histórico recente."""
        # Pergunta contextual adaptativa
        pergunta = self._get_pergunta_adaptativa(health_mode)
        
        data.dificuldade = st.text_input(
            pergunta["label"],
            placeholder=pergunta["placeholder"],
            key=pergunta["key"],
        )
        
        # Pergunta extra contextual (aparece só quando relevante)
        extra = self._get_pergunta_extra(health_mode)
        if extra:
            st.markdown(
                f'<div style="font-size:.80rem;color:var(--text-muted);'
                f'margin-top:.6rem;font-weight:600;">{extra["label"]}</div>',
                unsafe_allow_html=True,
            )
            # Usa select_slider para perguntas numéricas, checkbox para sim/não
            if extra.get("tipo") == "slider":
                setattr(data, extra["campo"], st.select_slider(
                    extra["label"],
                    options=extra["opcoes"],
                    value=extra["opcoes"][len(extra["opcoes"])//2],
                    key=extra["key"],
                    label_visibility="collapsed",
                ))
            elif extra.get("tipo") == "bool":
                setattr(data, extra["campo"], st.checkbox(
                    extra["label_check"],
                    key=extra["key"],
                ))
        
        return data
    
    def _get_pergunta_adaptativa(self, health_mode: str) -> dict:
        """Retorna pergunta principal baseada no pilar."""
        streak = 0
        try:
            streak = self.db.get_checkin_streak()
        except Exception:
            pass
        
        if health_mode == "glp1":
            return {
                "label": "💉 Como foi o apetite hoje?",
                "placeholder": "Sem fome, náusea, normal, muita fome...",
                "key": "ci_glp1_apetite",
            }
        elif health_mode == "bariatric":
            return {
                "label": "🔪 Como foi a alimentação hoje?",
                "placeholder": "Volume, tolerâncias, dificuldades...",
                "key": "ci_bar_ali",
            }
        elif health_mode == "fitness":
            return {
                "label": "💪 Como foi a recuperação muscular?",
                "placeholder": "Dor muscular, cansaço, disposição para treinar...",
                "key": "ci_fit_recup",
            }
        elif streak == 0:
            # Recomeço — pergunta empática
            return {
                "label": "🌱 O que te trouxe de volta hoje?",
                "placeholder": "Sem julgamentos — cada recomeço conta",
                "key": "ci_recomeco",
            }
        elif streak >= 7 and streak % 7 == 0:
            # Marco de streak — celebrar e perguntar sobre aprendizado
            return {
                "label": f"🔥 {streak} dias! O que mudou na sua rotina?",
                "placeholder": "Hábito novo, percepção diferente, algo que facilitou...",
                "key": "ci_marco_streak",
            }
        else:
            return {
                "label": "💬 Algo que quer registrar hoje?",
                "placeholder": "Dificuldade, vitória pequena, observação...",
                "key": "ci_geral",
            }
    
    def _get_pergunta_extra(self, health_mode: str) -> dict | None:
        """Retorna pergunta extra contextual (só quando relevante)."""
        try:
            if health_mode == "glp1":
                # Verifica se é dia provável de dose (semanal)
                from services.glp1_service import GLP1Service
                svc = GLP1Service(self.db)
                proxima = svc.proxima_dose(self.user.get("glp1_medication", ""))
                if proxima and proxima.lower() in ("hoje", "amanhã"):
                    return {
                        "label": "💉 Tomou a dose hoje?",
                        "label_check": "💉 Sim, tomei a dose GLP-1 hoje",
                        "campo": "dificuldade",  # reusa campo para não precisar migrar DB
                        "tipo": "bool",
                        "key": "ci_glp1_dose_check",
                    }
            
            elif health_mode == "fitness":
                # Verifica se treinou hoje
                treino = self.db.get_workout_today()
                if not treino:
                    return {
                        "label": "🏋️ Treinou hoje?",
                        "label_check": "🏋️ Sim, treinei hoje",
                        "campo": "dificuldade",
                        "tipo": "bool",
                        "key": "ci_fit_treino_check",
                    }
            
            elif health_mode == "bariatric":
                # Sempre pergunta proteína — crítico no pós-bariátrico
                return {
                    "label": "🥩 Atingiu a meta de proteína?",
                    "opcoes": ["Não", "Parcialmente", "Sim"],
                    "campo": "dificuldade",
                    "tipo": "slider",
                    "key": "ci_bar_prot",
                }
        except Exception:
            pass
        
        return None
    
    def _processar_checkin(self, data: CheckinData) -> None:
        """Processa e salva o check-in."""
        # Validação básica
        if not self._validar_dados(data):
            return
        
        with st.spinner("Salvando seu check-in..."):
            # 1. Salvar check-in na tabela checkins
            if not self._salvar_checkin(data):
                return
            
            # 2. Disparar Orchestrator
            result = self._processar_orchestrator(data)
            
            # 3. Feedback imediato
            self._render_feedback(result)
            
            # 4. Persiste resultado na sessão
            st.session_state["ci_result"] = result
            
            # 5. Limpa cache para atualizar dados
            st.cache_data.clear()
            
            st.rerun()
    
    def _validar_dados(self, data: CheckinData) -> bool:
        """Valida dados do check-in."""
        if not (1 <= data.humor <= 5):
            st.error("❌ Humor inválido.")
            return False
        
        if not (1 <= data.energia <= 5):
            st.error("❌ Energia inválida.")
            return False
        
        if not (1 <= data.sono <= 5):
            st.error("❌ Qualidade do sono inválida.")
            return False
        
        return True
    
    def _salvar_checkin(self, data: CheckinData) -> bool:
        """Salva check-in no banco de dados."""
        observacao = " | ".join(
            filter(None, [data.vitoria, data.dificuldade])
        )
        
        try:
            success = self.db.save_checkin(
                data.humor,
                data.energia,
                float(data.sono),
                observacao
            )
            
            if not success:
                st.error("❌ Erro ao salvar check-in.")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar check-in: {e}", exc_info=True)
            st.error(f"❌ Erro ao salvar check-in: {str(e)}")
            return False
    
    def _processar_orchestrator(self, data: CheckinData) -> OrchestratorResult:
        """Processa check-in no orchestrator."""
        payload = {
            "humor": data.humor,
            "energia": data.energia,
            "sono": data.sono,
            "habito_id": data.habito_id,
            "vitoria": data.vitoria,
        }
        
        try:
            return self.orch.processar("checkin", self.user, payload)
        except Exception as e:
            logger.error(f"Erro no orchestrator: {e}", exc_info=True)
            # Retorna resultado vazio em caso de erro
            return OrchestratorResult(
                xp_ganho=0,
                badges_novos=[],
                alertas=[],
            )
    
    def _render_feedback(self, result: OrchestratorResult) -> None:
        """Renderiza feedback pós-check-in."""
        # Toast principal
        if result.xp_ganho > 0:
            st.toast(
                f"✅ Check-in feito! +{result.xp_ganho} XP",
                icon="🔥",
            )
        else:
            st.toast("✅ Check-in feito!", icon="✅")
        
        # Badges novos
        show_new_achievements(result.badges_novos)
        
        # Alertas
        for kind, msg in result.alertas:
            icon = "⚠️" if kind == "warning" else "ℹ️"
            st.toast(msg, icon=icon)


# Função principal de compatibilidade
def render(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = CheckinRenderer(services, user)
    renderer.render()
