"""
Melshape — Onboarding: steps 1-4 e finalização.
"""
import streamlit as st
from typing import Dict, Any, List, Optional, Tuple
import logging

import config
from views.components.cards import alert

logger = logging.getLogger("Melshape.OnboardingSteps")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Limites de validação
MIN_PESO = 30.0
MAX_PESO = 300.0
MIN_ALTURA = 100
MAX_ALTURA = 250
MIN_IDADE = 16
MAX_IDADE = 99
MIN_MOTIVO_LENGTH = 10

# Valores padrão
DEFAULT_PESO = 80.0
DEFAULT_ALTURA = 170
DEFAULT_IDADE = 30
DEFAULT_GENERO = "female"
DEFAULT_OBJETIVO = "lose"
DEFAULT_PESO_META = 70.0

# Chaves de session state
SESSION_KEY_STEP = "onboarding_step"
SESSION_KEY_MODE = "onboarding_mode"
SESSION_KEY_DADOS = "ob_dados"
SESSION_KEY_PORQUE = "ob_porque_salvo"

# Mapeamentos
GENEROS_MAP = {
    "female": "Feminino",
    "male": "Masculino",
    "other": "Outro",
}

OBJETIVOS_MAP = {
    "lose": "⬇️ Perder peso",
    "maintain": "⚖️ Manter peso",
    "gain": "⬆️ Ganhar massa",
}


# ── PILARES ──────────────────────────────────────────────────────────────────
PILARES = {
    "general": {
        "icon": "⚖️",
        "nome": "Emagrecimento",
        "desc": "Perda de peso com hábitos reais, sem restrições extremas.",
        "habitos": [
            ("🍽️", "Registrar refeições", "registro"),
            ("💧", "Beber 2L de água", "hidratacao"),
            ("✅", "Check-in diário", "registro"),
        ],
    },
    "fitness": {
        "icon": "💪",
        "nome": "Fitness",
        "desc": "Composição corporal, proteína e performance.",
        "habitos": [
            ("🏋️", "Registrar treino", "treino"),
            ("🥩", "Meta proteica diária", "nutricao"),
            ("✅", "Check-in diário", "registro"),
        ],
    },
    "bariatric": {
        "icon": "🔪",
        "nome": "Pós-Bariátrica",
        "desc": "Acompanhamento de fases, suplementação e exames.",
        "habitos": [
            ("💊", "Tomar suplementos", "suplementos"),
            ("🥄", "Controle de volume", "nutricao"),
            ("✅", "Check-in diário", "registro"),
        ],
    },
    "glp1": {
        "icon": "💉",
        "nome": "GLP-1",
        "desc": "Adesão ao tratamento, doses e sintomas.",
        "habitos": [
            ("💉", "Registrar dose", "medicamento"),
            ("🥩", "Proteína na refeição", "nutricao"),
            ("✅", "Check-in diário", "registro"),
        ],
    },
}

DEFAULT_PILAR = PILARES["general"]


class OnboardingStepsRenderer:
    """Renderer para os passos do onboarding."""
    
    def __init__(self, db=None, user=None):
        self.db = db
        self.user = user or {}
    
    # ── PASSO 1: PILAR ─────────────────────────────────────────────────────────
    def step_pilar(self) -> None:
        """Passo 1: Escolha do pilar."""
        self._render_header_pilar()
        self._render_pilares_grid()
        self._render_botao_continuar_pilar()
    
    def _render_header_pilar(self) -> None:
        """Renderiza cabeçalho do passo 1."""
        st.markdown(
            """
            <h2 style="font-family: var(--font-display); font-weight: 800;
                color: var(--text); margin-bottom: 0.3rem;">
                Qual é sua jornada?
            </h2>
            <p style="color: var(--text-muted); margin-bottom: 1.3rem;">
                O Melshape personaliza tudo com base na sua resposta.
            </p>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_pilares_grid(self) -> None:
        """Renderiza grid de pilares."""
        cols = st.columns(2)
        
        for i, (key, pilar) in enumerate(PILARES.items()):
            with cols[i % 2]:
                self._render_pilar_card(key, pilar)
    
    def _render_pilar_card(self, key: str, pilar: Dict) -> None:
        """Renderiza card de um pilar."""
        selecionado = self._is_pilar_selecionado(key)
        borda = self._get_cor_borda_pilar(selecionado)
        
        self._render_card_html(pilar, borda)
        self._render_botao_escolher_pilar(key, pilar, selecionado)
    
    def _is_pilar_selecionado(self, key: str) -> bool:
        """Verifica se pilar está selecionado."""
        try:
            return st.session_state.get(SESSION_KEY_MODE) == key
        except Exception as e:
            logger.debug(f"Erro ao verificar pilar selecionado: {e}")
            return False
    
    def _get_cor_borda_pilar(self, selecionado: bool) -> str:
        """Retorna cor da borda do pilar."""
        return "var(--primary)" if selecionado else "var(--border)"
    
    def _render_card_html(self, pilar: Dict, borda: str) -> None:
        """Renderiza HTML do card do pilar."""
        st.markdown(
            f"""
            <div style="border: 2px solid {borda}; border-radius: 16px;
                padding: 1.1rem; margin-bottom: 0.7rem; cursor: pointer;">
                <div style="font-size: 1.7rem;">{pilar['icon']}</div>
                <div style="font-weight: 700; color: var(--text); font-size: 1rem; margin-top: 0.2rem;">
                    {pilar['nome']}
                </div>
                <div style="font-size: 0.80rem; color: var(--text-muted); margin-top: 0.3rem;">
                    {pilar['desc']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_botao_escolher_pilar(self, key: str, pilar: Dict, selecionado: bool) -> None:
        """Renderiza botão de escolher pilar."""
        prefixo = "✅ " if selecionado else ""
        tipo_botao = "primary" if selecionado else "secondary"
        
        if st.button(
            f"{prefixo}Escolher {pilar['nome']}",
            key=f"ob_pilar_{key}",
            use_container_width=True,
            type=tipo_botao,
        ):
            self._selecionar_pilar(key)
    
    def _selecionar_pilar(self, key: str) -> None:
        """Seleciona pilar e atualiza session state."""
        try:
            st.session_state[SESSION_KEY_MODE] = key
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao selecionar pilar: {e}", exc_info=True)
            st.error("❌ Erro ao selecionar pilar. Tente novamente.")
    
    def _render_botao_continuar_pilar(self) -> None:
        """Renderiza botão de continuar para próximo passo."""
        if not st.session_state.get(SESSION_KEY_MODE):
            return
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button(
            "Continuar →",
            type="primary",
            use_container_width=True,
            key="ob_p1_next",
        ):
            self._ir_para_proximo_step(2)
    
    # ── PASSO 2: DADOS ─────────────────────────────────────────────────────────
    def step_dados(self, user: Dict) -> None:
        """Passo 2: Dados pessoais."""
        self._render_header_dados()
        self._render_form_dados(user)
        self._render_botao_voltar(1, "ob_p2_back")
    
    def _render_header_dados(self) -> None:
        """Renderiza cabeçalho do passo 2."""
        st.markdown(
            """
            <h2 style="font-family: var(--font-display); font-weight: 800;
                color: var(--text); margin-bottom: 0.3rem;">
                Seus dados
            </h2>
            <p style="color: var(--text-muted); margin-bottom: 1.3rem;">
                Usados para calcular suas metas nutricionais.
            </p>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_form_dados(self, user: Dict) -> None:
        """Renderiza formulário de dados pessoais."""
        with st.form("ob_dados", clear_on_submit=False):
            self._render_campos_dados(user)
            
            if st.form_submit_button(
                "Continuar →",
                type="primary",
                use_container_width=True,
            ):
                self._salvar_dados_e_continuar()
    
    def _render_campos_dados(self, user: Dict) -> None:
        """Renderiza campos do formulário de dados."""
        col1, col2 = st.columns(2)
        
        with col1:
            peso = self._render_campo_peso(user)
            altura = self._render_campo_altura(user)
        
        with col2:
            idade = self._render_campo_idade(user)
            genero = self._render_campo_genero(user)
        
        objetivo = self._render_campo_objetivo(user)
        peso_meta = self._render_campo_peso_meta(user, peso)
        
        # Salva no session_state
        self._salvar_dados_session(peso, altura, idade, genero, objetivo, peso_meta)
    
    def _render_campo_peso(self, user: Dict) -> float:
        """Renderiza campo de peso."""
        peso_default = self._extrair_peso_default(user)
        return st.number_input(
            "Peso atual (kg)",
            MIN_PESO, MAX_PESO,
            peso_default,
            0.1,
            key="ob_peso",
        )
    
    def _extrair_peso_default(self, user: Dict) -> float:
        """Extrai peso padrão do usuário."""
        try:
            peso = user.get("current_weight")
            return float(peso) if peso is not None else DEFAULT_PESO
        except (ValueError, TypeError):
            return DEFAULT_PESO
    
    def _render_campo_altura(self, user: Dict) -> int:
        """Renderiza campo de altura."""
        altura_default = self._extrair_altura_default(user)
        return st.number_input(
            "Altura (cm)",
            MIN_ALTURA, MAX_ALTURA,
            altura_default,
            key="ob_altura",
        )
    
    def _extrair_altura_default(self, user: Dict) -> int:
        """Extrai altura padrão do usuário."""
        try:
            altura = user.get("height")
            return int(altura) if altura is not None else DEFAULT_ALTURA
        except (ValueError, TypeError):
            return DEFAULT_ALTURA
    
    def _render_campo_idade(self, user: Dict) -> int:
        """Renderiza campo de idade."""
        idade_default = self._extrair_idade_default(user)
        return st.number_input(
            "Idade",
            MIN_IDADE, MAX_IDADE,
            idade_default,
            key="ob_idade",
        )
    
    def _extrair_idade_default(self, user: Dict) -> int:
        """Extrai idade padrão do usuário."""
        try:
            idade = user.get("age")
            return int(idade) if idade is not None else DEFAULT_IDADE
        except (ValueError, TypeError):
            return DEFAULT_IDADE
    
    def _render_campo_genero(self, user: Dict) -> str:
        """Renderiza campo de gênero."""
        genero_default = self._extrair_genero_default(user)
        return st.selectbox(
            "Gênero",
            list(GENEROS_MAP.keys()),
            format_func=lambda x: GENEROS_MAP[x],
            index=list(GENEROS_MAP.keys()).index(genero_default),
            key="ob_genero",
        )
    
    def _extrair_genero_default(self, user: Dict) -> str:
        """Extrai gênero padrão do usuário."""
        try:
            genero = user.get("gender", DEFAULT_GENERO)
            return genero if genero in GENEROS_MAP else DEFAULT_GENERO
        except Exception:
            return DEFAULT_GENERO
    
    def _render_campo_objetivo(self, user: Dict) -> str:
        """Renderiza campo de objetivo."""
        objetivo_default = self._extrair_objetivo_default(user)
        return st.selectbox(
            "Objetivo principal",
            list(OBJETIVOS_MAP.keys()),
            format_func=lambda x: OBJETIVOS_MAP[x],
            index=list(OBJETIVOS_MAP.keys()).index(objetivo_default),
            key="ob_objetivo",
        )
    
    def _extrair_objetivo_default(self, user: Dict) -> str:
        """Extrai objetivo padrão do usuário."""
        try:
            objetivo = user.get("goal", DEFAULT_OBJETIVO)
            return objetivo if objetivo in OBJETIVOS_MAP else DEFAULT_OBJETIVO
        except Exception:
            return DEFAULT_OBJETIVO
    
    def _render_campo_peso_meta(self, user: Dict, peso_atual: float) -> float:
        """Renderiza campo de peso meta."""
        peso_meta_default = self._calcular_peso_meta_default(user, peso_atual)
        return st.number_input(
            "Peso desejado (kg)",
            MIN_PESO, MAX_PESO,
            peso_meta_default,
            0.1,
            key="ob_peso_meta",
        )
    
    def _calcular_peso_meta_default(self, user: Dict, peso_atual: float) -> float:
        """Calcula peso meta padrão."""
        try:
            peso_meta = user.get("goal_weight")
            if peso_meta is not None:
                return float(peso_meta)
            
            # Calcula baseado no peso atual
            return max(MIN_PESO, peso_atual - 5)
        except (ValueError, TypeError):
            return DEFAULT_PESO_META
    
    def _salvar_dados_session(
        self,
        peso: float,
        altura: int,
        idade: int,
        genero: str,
        objetivo: str,
        peso_meta: float,
    ) -> None:
        """Salva dados no session state."""
        try:
            st.session_state[SESSION_KEY_DADOS] = {
                "peso": peso,
                "altura": altura,
                "idade": idade,
                "genero": genero,
                "objetivo": objetivo,
                "peso_meta": peso_meta,
            }
        except Exception as e:
            logger.error(f"Erro ao salvar dados no session state: {e}", exc_info=True)
    
    def _salvar_dados_e_continuar(self) -> None:
        """Salva dados e vai para próximo passo."""
        if self._validar_dados():
            self._ir_para_proximo_step(3)
    
    def _validar_dados(self) -> bool:
        """Valida dados do formulário."""
        dados = st.session_state.get(SESSION_KEY_DADOS, {})
        
        if not dados:
            st.warning("⚠️ Preencha todos os campos.")
            return False
        
        # Valida peso
        peso = dados.get("peso", 0)
        if peso < MIN_PESO or peso > MAX_PESO:
            st.warning(f"⚠️ Peso deve estar entre {MIN_PESO} e {MAX_PESO} kg.")
            return False
        
        # Valida peso meta
        peso_meta = dados.get("peso_meta", 0)
        if peso_meta < MIN_PESO or peso_meta > MAX_PESO:
            st.warning(f"⚠️ Peso meta deve estar entre {MIN_PESO} e {MAX_PESO} kg.")
            return False
        
        return True
    
    def _render_botao_voltar(self, step_destino: int, key: str) -> None:
        """Renderiza botão de voltar."""
        if st.button("← Voltar", key=key):
            self._ir_para_proximo_step(step_destino)
    
    # ── PASSO 3: PORQUÊ ────────────────────────────────────────────────────────
    def step_porque(self, db, user: Dict) -> None:
        """Passo 3: Por que você começou."""
        self._render_header_porque()
        motivo = self._render_campo_motivo()
        self._render_botoes_porque(motivo)
    
    def _render_header_porque(self) -> None:
        """Renderiza cabeçalho do passo 3."""
        st.markdown(
            """
            <h2 style="font-family: var(--font-display); font-weight: 800;
                color: var(--text); margin-bottom: 0.3rem;">
                💛 Por que você começou?
            </h2>
            <p style="color: var(--text-muted); margin-bottom: 1.3rem;">
                Seu motivo é o que vai te trazer de volta nos dias difíceis.
            </p>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_campo_motivo(self) -> str:
        """Renderiza campo de motivo."""
        return st.text_area(
            "Seu motivo",
            height=120,
            placeholder=(
                "Ex: Quero ter energia para brincar com meus filhos. "
                "Quero me sentir bem ao me olhar no espelho. "
                "Quero controlar minha saúde antes que seja tarde."
            ),
            key="ob_motivo",
            label_visibility="collapsed",
        )
    
    def _render_botoes_porque(self, motivo: str) -> None:
        """Renderiza botões do passo 3."""
        col1, col2 = st.columns(2)
        
        with col1:
            self._render_botao_voltar(2, "ob_p3_back")
        
        with col2:
            if st.button(
                "Continuar →",
                type="primary",
                use_container_width=True,
                key="ob_p3_next",
            ):
                self._salvar_motivo_e_continuar(motivo)
    
    def _salvar_motivo_e_continuar(self, motivo: str) -> None:
        """Salva motivo e vai para próximo passo."""
        if not self._validar_motivo(motivo):
            return
        
        try:
            st.session_state[SESSION_KEY_PORQUE] = motivo.strip()
            self._ir_para_proximo_step(4)
        except Exception as e:
            logger.error(f"Erro ao salvar motivo: {e}", exc_info=True)
            st.error("❌ Erro ao salvar motivo. Tente novamente.")
    
    def _validar_motivo(self, motivo: str) -> bool:
        """Valida motivo."""
        if not motivo or not motivo.strip():
            st.warning("⚠️ Escreva seu motivo para continuar.")
            return False
        
        if len(motivo.strip()) < MIN_MOTIVO_LENGTH:
            st.warning(f"⚠️ O motivo deve ter pelo menos {MIN_MOTIVO_LENGTH} caracteres.")
            return False
        
        return True
    
    # ── PASSO 4: HÁBITOS ───────────────────────────────────────────────────────
    def step_habitos(self, db, user: Dict) -> None:
        """Passo 4: Hábitos iniciais."""
        health_mode = self._get_health_mode()
        pilar = self._get_pilar(health_mode)
        
        self._render_header_habitos(pilar)
        self._render_lista_habitos(pilar)
        self._render_dica_habitos()
        self._render_botoes_habitos(db, user)
    
    def _get_health_mode(self) -> str:
        """Obtém health mode do session state."""
        try:
            return st.session_state.get(SESSION_KEY_MODE, "general")
        except Exception as e:
            logger.debug(f"Erro ao obter health mode: {e}")
            return "general"
    
    def _get_pilar(self, health_mode: str) -> Dict:
        """Obtém pilar baseado no health mode."""
        try:
            return PILARES.get(health_mode, DEFAULT_PILAR)
        except Exception as e:
            logger.error(f"Erro ao obter pilar: {e}", exc_info=True)
            return DEFAULT_PILAR
    
    def _render_header_habitos(self, pilar: Dict) -> None:
        """Renderiza cabeçalho do passo 4."""
        st.markdown(
            f"""
            <h2 style="font-family: var(--font-display); font-weight: 800;
                color: var(--text); margin-bottom: 0.3rem;">
                📋 Hábitos iniciais
            </h2>
            <p style="color: var(--text-muted); margin-bottom: 1.3rem;">
                Baseado no seu pilar {pilar['icon']} {pilar['nome']}, 
                vamos começar com estes hábitos:
            </p>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_lista_habitos(self, pilar: Dict) -> None:
        """Renderiza lista de hábitos sugeridos."""
        habitos = pilar.get("habitos", [])
        
        for icone, nome, categoria in habitos:
            self._render_habito_item(icone, nome)
    
    def _render_habito_item(self, icone: str, nome: str) -> None:
        """Renderiza item de hábito."""
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 0.9rem;
                padding: 0.7rem 0.9rem; background: var(--surface-2);
                border-radius: 12px; margin-bottom: 0.5rem;
                border: 1px solid var(--border);">
                <span style="font-size: 1.4rem;">{icone}</span>
                <span style="font-weight: 500; color: var(--text); font-size: 0.92rem;">
                    {nome}
                </span>
                <span style="font-size: 0.74rem; color: var(--text-muted); margin-left: auto;">
                    ✅ será criado automaticamente
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_dica_habitos(self) -> None:
        """Renderiza dica sobre hábitos."""
        st.markdown(
            """
            <div style="font-size: 0.82rem; color: var(--text-muted); margin: 0.9rem 0;">
                💡 Você poderá criar, editar ou arquivar hábitos depois.
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_botoes_habitos(self, db, user: Dict) -> None:
        """Renderiza botões do passo 4."""
        col1, col2 = st.columns(2)
        
        with col1:
            self._render_botao_voltar(3, "ob_p4_back")
        
        with col2:
            if st.button(
                "🚀 Começar jornada!",
                type="primary",
                use_container_width=True,
                key="ob_finalizar",
            ):
                self._finalizar_onboarding(db, user)
    
    def _finalizar_onboarding(self, db, user: Dict) -> None:
        """Finaliza o onboarding com tratamento de erros."""
        health_mode = self._get_health_mode()
        dados = self._get_dados_session()
        motivo = self._get_motivo_session()
        
        try:
            # 1. Atualizar perfil
            self._atualizar_perfil(db, health_mode, dados)
            
            # 2. Criar hábitos iniciais
            self._criar_habitos_iniciais(db, health_mode)
            
            # 3. Salvar motivo da jornada
            self._salvar_motivo_jornada(db, motivo)
            
            # 4. Ir para home
            self._ir_para_home()
            
        except Exception as e:
            logger.error(f"Erro ao finalizar onboarding: {e}", exc_info=True)
            # Mesmo com erro, tenta ir para home
            self._ir_para_home_com_erro()
    
    def _get_dados_session(self) -> Dict:
        """Obtém dados do session state."""
        try:
            return st.session_state.get(SESSION_KEY_DADOS, {})
        except Exception as e:
            logger.error(f"Erro ao obter dados do session state: {e}", exc_info=True)
            return {}
    
    def _get_motivo_session(self) -> str:
        """Obtém motivo do session state."""
        try:
            return st.session_state.get(SESSION_KEY_PORQUE, "")
        except Exception as e:
            logger.error(f"Erro ao obter motivo do session state: {e}", exc_info=True)
            return ""
    
    def _atualizar_perfil(self, db, health_mode: str, dados: Dict) -> None:
        """Atualiza perfil do usuário."""
        upd = self._montar_dados_atualizacao(health_mode, dados)
        
        if hasattr(db, "update_user"):
            try:
                db.update_user(upd)
            except Exception as e:
                logger.error(f"Erro ao atualizar perfil: {e}", exc_info=True)
                raise
        
        try:
            st.session_state.user.update(upd)
        except Exception as e:
            logger.error(f"Erro ao atualizar session state user: {e}", exc_info=True)
    
    def _montar_dados_atualizacao(self, health_mode: str, dados: Dict) -> Dict:
        """Monta dados para atualização do perfil."""
        return {
            "health_mode": health_mode,
            "onboarding_done": True,
            "current_weight": dados.get("peso", DEFAULT_PESO),
            "height": dados.get("altura", DEFAULT_ALTURA),
            "age": dados.get("idade", DEFAULT_IDADE),
            "gender": dados.get("genero", DEFAULT_GENERO),
            "goal": dados.get("objetivo", DEFAULT_OBJETIVO),
            "goal_weight": dados.get("peso_meta", DEFAULT_PESO_META),
        }
    
    def _criar_habitos_iniciais(self, db, health_mode: str) -> None:
        """Cria hábitos iniciais."""
        try:
            from services.habit_service import HabitService
            svc = HabitService(db)
            svc.inicializar_habitos_padrao(health_mode)
        except Exception as e:
            logger.error(f"Erro ao criar hábitos iniciais: {e}", exc_info=True)
            # Não raise, pois não é crítico
    
    def _salvar_motivo_jornada(self, db, motivo: str) -> None:
        """Salva motivo da jornada."""
        if not motivo:
            return
        
        try:
            jornada = self._garantir_jornada(db)
            
            if jornada:
                db.salvar_motivo(jornada["id"], motivo)
        except Exception as e:
            logger.error(f"Erro ao salvar motivo da jornada: {e}", exc_info=True)
            # Não raise, pois não é crítico
    
    def _garantir_jornada(self, db) -> Optional[Dict]:
        """Garante que jornada existe."""
        try:
            jornada = db.get_jornada_ativa()
            
            if not jornada:
                from services.journey_service import JourneyService
                jornada = JourneyService(db).garantir_jornada(st.session_state.user)
            
            return jornada
        except Exception as e:
            logger.error(f"Erro ao garantir jornada: {e}", exc_info=True)
            return None
    
    def _ir_para_home(self) -> None:
        """Vai para home após onboarding."""
        try:
            st.session_state[SESSION_KEY_STEP] = 1
            st.session_state.page = "home"
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao ir para home: {e}", exc_info=True)
            st.error("❌ Erro ao finalizar onboarding. Tente recarregar a página.")
    
    def _ir_para_home_com_erro(self) -> None:
        """Vai para home mesmo com erro."""
        try:
            st.session_state.user["onboarding_done"] = True
            st.session_state.page = "home"
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao ir para home com erro: {e}", exc_info=True)
    
    def _ir_para_proximo_step(self, step: int) -> None:
        """Vai para próximo step."""
        try:
            st.session_state[SESSION_KEY_STEP] = step
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao ir para step {step}: {e}", exc_info=True)
            st.error("❌ Erro ao navegar. Tente novamente.")


# Funções de compatibilidade (mantendo a interface original)
def _step_pilar() -> None:
    """Passo 1: Escolha do pilar (compatibilidade)."""
    renderer = OnboardingStepsRenderer()
    renderer.step_pilar()


def _step_dados(user: Dict) -> None:
    """Passo 2: Dados pessoais (compatibilidade)."""
    renderer = OnboardingStepsRenderer(user=user)
    renderer.step_dados(user)


def _step_porque(db, user: Dict) -> None:
    """Passo 3: Por que você começou (compatibilidade)."""
    renderer = OnboardingStepsRenderer(db, user)
    renderer.step_porque(db, user)


def _step_habitos(db, user: Dict) -> None:
    """Passo 4: Hábitos iniciais (compatibilidade)."""
    renderer = OnboardingStepsRenderer(db, user)
    renderer.step_habitos(db, user)
