"""
Melshape — Perfil do Paciente.

Abas:
  👤 Meus Dados     → peso, altura, objetivo, modo de saúde
  💳 Meu Plano      → trial, upgrade, histórico
  🔔 Preferências   → notificações, dark mode, lembretes
  🚪 Conta          → logout, exclusão
"""
import streamlit as st
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging

import config
from views.components.cards import section_header, alert, metric_card
from views.patient.profile_tabs import (
    _tab_plano, _tab_preferencias, _tab_conta
)

logger = logging.getLogger("Melshape.Profile")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Mapeamentos
MODE_LABELS = {
    "general": "⚖️ Emagrecimento",
    "fitness": "💪 Fitness",
    "bariatric": "🔪 Pós-Bariátrica",
    "glp1": "💉 GLP-1",
}

GENEROS = ["female", "male", "other"]
GENEROS_LABELS = {
    "female": "Feminino",
    "male": "Masculino",
    "other": "Outro",
}

OBJETIVOS = ["lose", "maintain", "gain"]
OBJETIVOS_LABELS = {
    "lose": "⬇️ Perder peso",
    "maintain": "⚖️ Manter peso",
    "gain": "⬆️ Ganhar massa",
}

# Limites
MIN_PESO = 20.0
MAX_PESO = 300.0
MIN_ALTURA = 100
MAX_ALTURA = 250
MIN_IDADE = 16
MAX_IDADE = 99

# Valores padrão
DEFAULT_NOME = ""
DEFAULT_PESO = 70.0
DEFAULT_ALTURA = 170.0
DEFAULT_IDADE = 30
DEFAULT_GENERO = "female"
DEFAULT_OBJETIVO = "lose"
DEFAULT_PESO_META = 65.0
DEFAULT_HEALTH_MODE = "general"

# Chaves de session state
SESSION_KEY_PF_DATA = "pf_data"


@dataclass
class ProfileData:
    """Dados do perfil."""
    name: str = DEFAULT_NOME
    current_weight: float = DEFAULT_PESO
    height: float = DEFAULT_ALTURA
    age: int = DEFAULT_IDADE
    gender: str = DEFAULT_GENERO
    goal: str = DEFAULT_OBJETIVO
    goal_weight: float = DEFAULT_PESO_META
    health_mode: str = DEFAULT_HEALTH_MODE


class ProfileRenderer:
    """Renderer dedicado para tela de perfil."""
    
    def __init__(self, services: Dict[str, Any], user: Dict[str, Any]):
        self.services = services
        self.user = user or {}
        self.db = services.get("db")
        self.plan_svc = services.get("plan") or services.get("plan_service")
        self.nome = self._extrair_primeiro_nome()
    
    def _extrair_primeiro_nome(self) -> str:
        """Extrai primeiro nome do usuário de forma segura."""
        try:
            nome_completo = self.user.get("name", "")
            if not nome_completo:
                return "Usuário"
            partes = nome_completo.split()
            return partes[0] if partes else "Usuário"
        except Exception as e:
            logger.debug(f"Erro ao extrair primeiro nome: {e}")
            return "Usuário"
    
    def render(self) -> None:
        """Renderiza tela de perfil."""
        section_header(
            f"👤 Perfil — {self.nome}",
            "Seus dados e configurações"
        )
        
        tab_dados, tab_plano, tab_pref, tab_conta = st.tabs([
            "👤 Meus Dados",
            "💳 Meu Plano",
            "🔔 Preferências",
            "🚪 Conta",
        ])
        
        with tab_dados:
            self._render_tab_dados()
        
        with tab_plano:
            self._render_tab_plano()
        
        with tab_pref:
            self._render_tab_preferencias()
        
        with tab_conta:
            self._render_tab_conta()
    
    def _render_tab_dados(self) -> None:
        """Renderiza aba de dados com tratamento de erros."""
        try:
            self._render_dados()
        except Exception as e:
            logger.error(f"Erro ao renderizar tab dados: {e}", exc_info=True)
            alert("❌ Erro ao carregar dados do perfil.", "error")
    
    def _render_tab_plano(self) -> None:
        """Renderiza aba de plano com tratamento de erros."""
        try:
            _tab_plano(self.plan_svc, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab plano: {e}", exc_info=True)
            alert("❌ Erro ao carregar informações do plano.", "error")
    
    def _render_tab_preferencias(self) -> None:
        """Renderiza aba de preferências com tratamento de erros."""
        try:
            _tab_preferencias(self.db, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab preferências: {e}", exc_info=True)
            alert("❌ Erro ao carregar preferências.", "error")
    
    def _render_tab_conta(self) -> None:
        """Renderiza aba de conta com tratamento de erros."""
        try:
            _tab_conta(self.db, self.user)
        except Exception as e:
            logger.error(f"Erro ao renderizar tab conta: {e}", exc_info=True)
            alert("❌ Erro ao carregar opções de conta.", "error")
    
    def _render_dados(self) -> None:
        """Renderiza aba de dados pessoais."""
        st.markdown("##### 👤 Dados Pessoais")
        
        data = self._get_profile_data()
        
        with st.form("profile_dados", clear_on_submit=False):
            self._render_dados_form(data)
            
            if st.form_submit_button(
                "💾 Salvar dados",
                type="primary",
                use_container_width=True,
            ):
                self._salvar_dados(data)
    
    def _get_profile_data(self) -> ProfileData:
        """Obtém dados do perfil com parse seguro."""
        return ProfileData(
            name=self._parse_string(self.user.get("name"), DEFAULT_NOME),
            current_weight=self._parse_float(
                self.user.get("current_weight"), DEFAULT_PESO
            ),
            height=self._parse_float(
                self.user.get("height"), DEFAULT_ALTURA
            ),
            age=self._parse_int(self.user.get("age"), DEFAULT_IDADE),
            gender=self._parse_genero(self.user.get("gender")),
            goal=self._parse_objetivo(self.user.get("goal")),
            goal_weight=self._parse_float(
                self.user.get("goal_weight"), DEFAULT_PESO_META
            ),
            health_mode=self._parse_health_mode(self.user.get("health_mode")),
        )
    
    def _parse_string(self, value: Any, default: str) -> str:
        """Converte valor para string de forma segura."""
        try:
            return str(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    def _parse_float(self, value: Any, default: float) -> float:
        """Converte valor para float de forma segura."""
        try:
            return float(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    def _parse_int(self, value: Any, default: int) -> int:
        """Converte valor para int de forma segura."""
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    def _parse_genero(self, value: Any) -> str:
        """Parse gênero com validação."""
        try:
            if value in GENEROS:
                return value
            return DEFAULT_GENERO
        except Exception:
            return DEFAULT_GENERO
    
    def _parse_objetivo(self, value: Any) -> str:
        """Parse objetivo com validação."""
        try:
            if value in OBJETIVOS:
                return value
            return DEFAULT_OBJETIVO
        except Exception:
            return DEFAULT_OBJETIVO
    
    def _parse_health_mode(self, value: Any) -> str:
        """Parse health_mode com validação."""
        try:
            if value in MODE_LABELS:
                return value
            return DEFAULT_HEALTH_MODE
        except Exception:
            return DEFAULT_HEALTH_MODE
    
    def _render_dados_form(self, data: ProfileData) -> None:
        """Renderiza campos do formulário."""
        col1, col2 = st.columns(2)
        
        with col1:
            data.name = self._render_campo_nome(data.name)
            data.current_weight = self._render_campo_peso(data.current_weight)
            data.height = self._render_campo_altura(data.height)
        
        with col2:
            data.age = self._render_campo_idade(data.age)
            data.gender = self._render_campo_genero(data.gender)
            data.goal = self._render_campo_objetivo(data.goal)
        
        data.goal_weight = self._render_campo_peso_meta(data.goal_weight)
        data.health_mode = self._render_campo_health_mode(data.health_mode)
        
        # Armazena dados para salvar
        try:
            st.session_state[SESSION_KEY_PF_DATA] = data
        except Exception as e:
            logger.error(f"Erro ao salvar dados no session state: {e}", exc_info=True)
    
    def _render_campo_nome(self, valor: str) -> str:
        """Renderiza campo nome."""
        return st.text_input(
            "Nome completo",
            value=valor,
            key="pf_nome",
        )
    
    def _render_campo_peso(self, valor: float) -> float:
        """Renderiza campo peso."""
        return st.number_input(
            "Peso atual (kg)",
            min_value=MIN_PESO,
            max_value=MAX_PESO,
            value=valor,
            step=0.1,
            key="pf_peso",
        )
    
    def _render_campo_altura(self, valor: float) -> float:
        """Renderiza campo altura."""
        return st.number_input(
            "Altura (cm)",
            min_value=MIN_ALTURA,
            max_value=MAX_ALTURA,
            value=int(valor),
            key="pf_altura",
        )
    
    def _render_campo_idade(self, valor: int) -> int:
        """Renderiza campo idade."""
        return st.number_input(
            "Idade",
            min_value=MIN_IDADE,
            max_value=MAX_IDADE,
            value=valor,
            key="pf_idade",
        )
    
    def _render_campo_genero(self, valor: str) -> str:
        """Renderiza campo gênero com proteção contra ValueError."""
        try:
            idx = GENEROS.index(valor) if valor in GENEROS else GENEROS.index(DEFAULT_GENERO)
        except (ValueError, Exception):
            idx = GENEROS.index(DEFAULT_GENERO)
        
        return st.selectbox(
            "Gênero",
            GENEROS,
            index=idx,
            format_func=lambda x: GENEROS_LABELS[x],
            key="pf_genero",
        )
    
    def _render_campo_objetivo(self, valor: str) -> str:
        """Renderiza campo objetivo com proteção contra ValueError."""
        try:
            idx = OBJETIVOS.index(valor) if valor in OBJETIVOS else OBJETIVOS.index(DEFAULT_OBJETIVO)
        except (ValueError, Exception):
            idx = OBJETIVOS.index(DEFAULT_OBJETIVO)
        
        return st.selectbox(
            "Objetivo",
            OBJETIVOS,
            index=idx,
            format_func=lambda x: OBJETIVOS_LABELS[x],
            key="pf_objetivo",
        )
    
    def _render_campo_peso_meta(self, valor: float) -> float:
        """Renderiza campo peso meta."""
        return st.number_input(
            "Peso desejado (kg)",
            min_value=MIN_PESO,
            max_value=MAX_PESO,
            value=valor,
            step=0.1,
            key="pf_peso_meta",
        )
    
    def _render_campo_health_mode(self, valor: str) -> str:
        """Renderiza campo modo de saúde com proteção contra ValueError."""
        modos = list(MODE_LABELS.keys())
        
        try:
            idx = modos.index(valor) if valor in modos else modos.index(DEFAULT_HEALTH_MODE)
        except (ValueError, Exception):
            idx = modos.index(DEFAULT_HEALTH_MODE)
        
        return st.selectbox(
            "Modo de saúde",
            modos,
            index=idx,
            format_func=lambda k: MODE_LABELS[k],
            key="pf_hm",
        )
    
    def _salvar_dados(self, data: ProfileData) -> None:
        """Salva dados do perfil com validações."""
        # Validações
        if not self._validar_dados(data):
            return
        
        upd = self._montar_dados_atualizacao(data)
        
        try:
            # Atualiza no banco
            if self.db and hasattr(self.db, "update_user"):
                self.db.update_user(upd)
            
            # Atualiza no session state
            if "user" in st.session_state:
                st.session_state.user.update(upd)
            
            # Limpa cache para refletir mudanças
            st.cache_data.clear()
            
            st.toast("💾 Dados salvos!", icon="✅")
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao salvar dados do perfil: {e}", exc_info=True)
            st.toast(f"❌ Erro ao salvar: {str(e)}", icon="❌")
    
    def _validar_dados(self, data: ProfileData) -> bool:
        """Valida dados antes de salvar."""
        # Valida nome
        if not data.name or not data.name.strip():
            st.warning("⚠️ Nome não pode estar vazio.")
            return False
        
        # Valida peso
        if data.current_weight < MIN_PESO or data.current_weight > MAX_PESO:
            st.warning(f"⚠️ Peso deve estar entre {MIN_PESO} e {MAX_PESO} kg.")
            return False
        
        # Valida peso meta
        if data.goal_weight < MIN_PESO or data.goal_weight > MAX_PESO:
            st.warning(f"⚠️ Peso meta deve estar entre {MIN_PESO} e {MAX_PESO} kg.")
            return False
        
        # Valida altura
        if data.height < MIN_ALTURA or data.height > MAX_ALTURA:
            st.warning(f"⚠️ Altura deve estar entre {MIN_ALTURA} e {MAX_ALTURA} cm.")
            return False
        
        # Valida idade
        if data.age < MIN_IDADE or data.age > MAX_IDADE:
            st.warning(f"⚠️ Idade deve estar entre {MIN_IDADE} e {MAX_IDADE} anos.")
            return False
        
        return True
    
    def _montar_dados_atualizacao(self, data: ProfileData) -> Dict[str, Any]:
        """Monta dicionário de dados para atualização."""
        return {
            "name": data.name.strip(),
            "current_weight": data.current_weight,
            "height": data.height,
            "age": data.age,
            "gender": data.gender,
            "goal": data.goal,
            "goal_weight": data.goal_weight,
            "health_mode": data.health_mode,
        }


# Função principal de compatibilidade
def render(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = ProfileRenderer(services, user)
    renderer.render()
