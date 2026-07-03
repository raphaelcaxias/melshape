"""
Melshape — Hábitos: Aba de Treinos.
Fundido de workout.py — treino é um hábito de movimento.
Dispara Orchestrator via services["orchestrator"].processar("treino").
"""
import streamlit as st
from typing import Dict, Any, Optional
from datetime import date
import logging

from views.components.cards import empty_state, metric_card, xp_toast

logger = logging.getLogger("Melshape.Treinos")


# Constantes de intensidade
INTENSIDADE_LABELS = {
    1: "Leve", 2: "Leve", 3: "Moderado",
    4: "Moderado", 5: "Moderado", 6: "Intenso",
    7: "Intenso", 8: "Muito Intenso",
    9: "Máximo", 10: "Máximo",
}

# Constantes de XP
XP_TREINO_PADRAO = 20

# Constantes de limites
DURACAO_MIN = 1
DURACAO_MAX = 300
DURACAO_PADRAO = 30
INTENSIDADE_PADRAO = 5


class TreinosRenderer:
    """Renderer dedicado para aba de treinos."""
    
    def __init__(self, db, user: Dict[str, Any], services: Optional[Dict] = None):
        self.db = db
        self.user = user
        self.services = services or {}
    
    def render(self) -> None:
        """Renderiza aba de treinos."""
        st.markdown("##### 🏋️ Treino de Hoje")
        
        treino = self._get_treino_hoje()
        
        if treino:
            self._render_treino_hoje(treino)
        else:
            empty_state(
                "🏋️",
                "Nenhum treino registrado hoje",
                "Registre para manter seu histórico",
            )
        
        st.markdown("---")
        
        # Formulário para registrar
        self._render_form_registro()
    
    @st.cache_data(ttl=30)
    def _get_treino_hoje(_self) -> Optional[Any]:
        """Obtém treino de hoje (com cache)."""
        try:
            treino = _self.db.get_workout_today()
            return treino
        except Exception as e:
            logger.error(f"Erro ao buscar treino de hoje: {e}", exc_info=True)
            return None
    
    def _render_treino_hoje(self, treino: Any) -> None:
        """Renderiza treino de hoje."""
        tipo = self._extrair_campo(treino, "workout_type", "")
        tipo_label = self._get_tipo_label(tipo)
        duracao = self._extrair_campo_int(treino, "duration", 0)
        intensidade = self._extrair_campo_int(treino, "intensity", 0)
        observacao = self._extrair_campo(treino, "notes", "")
        
        obs_html = (
            f'<div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.3rem;">'
            f'{observacao}</div>'
            if observacao else ""
        )
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" 
                style="border-color: var(--success);">
                <div style="font-weight: 700; font-size: 1.05rem; color: var(--text);">
                    🏋️ {tipo_label}
                </div>
                <div style="font-size: 0.86rem; color: var(--text-muted); margin-top: 0.3rem;">
                    Duração: <b>{duracao} min</b> · Intensidade: <b>{intensidade}/10</b>
                </div>
                {obs_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _extrair_campo(self, treino: Any, campo: str, default: str = "") -> str:
        """Extrai campo de treino de forma segura (suporta dict e objeto)."""
        try:
            # Tenta como atributo de objeto
            valor = getattr(treino, campo, None)
            
            # Se não encontrou, tenta como dict
            if valor is None and isinstance(treino, dict):
                valor = treino.get(campo, default)
            
            return str(valor) if valor is not None else default
        except Exception as e:
            logger.debug(f"Erro ao extrair campo '{campo}': {e}")
            return default
    
    def _extrair_campo_int(self, treino: Any, campo: str, default: int = 0) -> int:
        """Extrai campo inteiro de treino de forma segura."""
        try:
            valor_str = self._extrair_campo(treino, campo, str(default))
            return int(valor_str)
        except (ValueError, TypeError):
            return default
    
    def _get_tipo_label(self, tipo: str) -> str:
        """Obtém label do tipo de treino."""
        try:
            from config import WORKOUT_TYPES
            return WORKOUT_TYPES.get(tipo, "Treino")
        except Exception as e:
            logger.error(f"Erro ao obter label do tipo '{tipo}': {e}")
            return "Treino"
    
    def _render_form_registro(self) -> None:
        """Renderiza formulário para registrar treino."""
        st.markdown("##### ➕ Registrar Treino")
        
        tipos_treino = self._get_tipos_treino()
        
        col1, col2 = st.columns(2)
        
        with col1:
            tipo = st.selectbox(
                "Tipo",
                list(tipos_treino.keys()),
                format_func=lambda k: tipos_treino[k],
                key="workout_tipo",
            )
        
        with col2:
            duracao = st.number_input(
                "Duração (min)",
                min_value=DURACAO_MIN,
                max_value=DURACAO_MAX,
                value=DURACAO_PADRAO,
                step=5,
                key="workout_dur",
            )
        
        intensidade = st.select_slider(
            "Intensidade",
            options=list(range(1, 11)),
            value=INTENSIDADE_PADRAO,
            format_func=lambda x: f"{x}/10 — {INTENSIDADE_LABELS.get(x, '')}",
            key="workout_int",
        )
        
        observacao = st.text_input(
            "Observação (opcional)",
            placeholder="Ex: Foco em peito e ombros",
            key="workout_obs",
        )
        
        if st.button(
            "🏋️ Registrar treino",
            type="primary",
            use_container_width=True,
            key="workout_save",
        ):
            self._registrar_treino(tipo, duracao, intensidade, observacao)
    
    def _get_tipos_treino(self) -> Dict[str, str]:
        """Obtém tipos de treino com fallback."""
        try:
            from config import WORKOUT_TYPES
            return WORKOUT_TYPES
        except Exception as e:
            logger.error(f"Erro ao obter tipos de treino: {e}")
            return {"general": "Treino Geral"}
    
    def _registrar_treino(
        self,
        tipo: str,
        duracao: int,
        intensidade: int,
        observacao: str,
    ) -> None:
        """Registra um treino com tratamento de erros."""
        # Validações
        if not self._validar_dados(duracao, intensidade):
            return
        
        try:
            # Cria objeto WorkoutLog
            treino = self._criar_objeto_treino(tipo, duracao, intensidade, observacao)
            
            if not treino:
                st.error("❌ Erro ao criar objeto de treino.")
                return
            
            # Salva no banco
            success = self.db.save_workout(treino)
            
            if success:
                self._processar_sucesso_registro(tipo, duracao)
            else:
                st.error("❌ Erro ao registrar treino.")
        except Exception as e:
            logger.error(f"Erro ao registrar treino: {e}", exc_info=True)
            st.error(f"❌ Erro ao registrar treino: {str(e)}")
    
    def _validar_dados(self, duracao: int, intensidade: int) -> bool:
        """Valida dados do treino."""
        if duracao < DURACAO_MIN or duracao > DURACAO_MAX:
            st.warning(f"⚠️ Duração deve estar entre {DURACAO_MIN} e {DURACAO_MAX} minutos.")
            return False
        
        if intensidade < 1 or intensidade > 10:
            st.warning("⚠️ Intensidade deve estar entre 1 e 10.")
            return False
        
        return True
    
    def _criar_objeto_treino(
        self,
        tipo: str,
        duracao: int,
        intensidade: int,
        observacao: str,
    ) -> Optional[Any]:
        """Cria objeto WorkoutLog de forma segura."""
        try:
            from core.models import WorkoutLog
            
            return WorkoutLog(
                workout_type=tipo,
                duration=duracao,
                intensity=intensidade,
                notes=observacao,
                log_date=date.today().isoformat(),
            )
        except Exception as e:
            logger.error(f"Erro ao criar objeto WorkoutLog: {e}", exc_info=True)
            return None
    
    def _processar_sucesso_registro(self, tipo: str, duracao: int) -> None:
        """Processa sucesso do registro de treino."""
        st.toast("🏋️ Treino registrado!", icon="✅")
        
        # Dispara Orchestrator ou adiciona XP direto
        xp_ganho = self._processar_recompensa(tipo, duracao)
        
        # Limpa cache e rerun
        st.cache_data.clear()
        st.rerun()
    
    def _processar_recompensa(self, tipo: str, duracao: int) -> int:
        """Processa recompensa de XP via Orchestrator ou direto."""
        # Tenta via Orchestrator
        orch = self.services.get("orchestrator")
        
        if orch:
            try:
                user_data = st.session_state.get("user", self.user)
                resultado = orch.processar(
                    "refeicao",
                    user_data,
                    {"tipo": "treino", "duracao": duracao},
                )
                
                if resultado and resultado.xp_ganho:
                    xp_toast(resultado.xp_ganho, "treino")
                    return resultado.xp_ganho
            except Exception as e:
                logger.error(f"Erro no Orchestrator: {e}", exc_info=True)
        
        # Fallback: adiciona XP direto
        try:
            self.db.add_xp(XP_TREINO_PADRAO, motivo="treino")
            return XP_TREINO_PADRAO
        except Exception as e:
            logger.error(f"Erro ao adicionar XP: {e}")
            return 0


# Função de compatibilidade
def render_tab_treinos(db, user: Dict[str, Any],
                        services: Optional[Dict] = None) -> None:
    """Renderiza tab de treinos (compatibilidade)."""
    renderer = TreinosRenderer(db, user, services)
    renderer.render()
