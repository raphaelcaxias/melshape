"""
Melshape — Onboarding do Paciente.
Fluxo guiado para configurar perfil, objetivos e preferências.
"""
import streamlit as st
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class OnboardingData:
    """Dados coletados durante o onboarding."""
    # Dados pessoais
    birth_date: Optional[datetime] = None
    gender: str = ""
    height_cm: float = 0.0
    weight_kg: float = 0.0
    
    # Objetivos
    primary_goal: str = ""
    target_weight_kg: float = 0.0
    weekly_goal: str = "moderate"  # light, moderate, intense
    
    # Preferências
    dietary_restrictions: List[str] = field(default_factory=list)
    exercise_frequency: str = ""
    sleep_hours: int = 0
    
    # Condições médicas
    medical_conditions: List[str] = field(default_factory=list)
    medications: List[str] = field(default_factory=list)
    
    # Experiência
    fitness_level: str = "beginner"
    previous_diets: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "gender": self.gender,
            "height_cm": self.height_cm,
            "weight_kg": self.weight_kg,
            "primary_goal": self.primary_goal,
            "target_weight_kg": self.target_weight_kg,
            "weekly_goal": self.weekly_goal,
            "dietary_restrictions": self.dietary_restrictions,
            "exercise_frequency": self.exercise_frequency,
            "sleep_hours": self.sleep_hours,
            "medical_conditions": self.medical_conditions,
            "medications": self.medications,
            "fitness_level": self.fitness_level,
            "previous_diets": self.previous_diets,
            "onboarding_completed_at": datetime.now().isoformat()
        }


class OnboardingRenderer:
    """Renderer dedicado para o fluxo de onboarding."""
    
    # Opções para os selects
    GENEROS = ["Feminino", "Masculino", "Prefiro não informar", "Outro"]
    
    OBJETIVOS_PRINCIPAIS = {
        "weight_loss": "🏋️ Perda de peso",
        "muscle_gain": "💪 Ganho muscular",
        "maintenance": "⚖️ Manutenção",
        "post_bariatric": "🔪 Pós-bariátrica",
        "health_improvement": "❤️ Melhora da saúde",
        "glp1_support": "💉 Suporte GLP-1"
    }
    
    METAS_SEMANAIS = {
        "light": "🐢 Leve (0-2kg/mês)",
        "moderate": "🐇 Moderada (2-4kg/mês)",
        "intense": "🐆 Intensa (4-6kg/mês)"
    }
    
    NIVEL_FITNESS = {
        "beginner": "🌱 Iniciante",
        "intermediate": "🌿 Intermediário",
        "advanced": "🌳 Avançado"
    }
    
    FREQUENCIA_EXERCICIO = [
        "Nenhum", "1-2 vezes/semana", "3-4 vezes/semana",
        "5-6 vezes/semana", "Todos os dias"
    ]
    
    RESTRICOES_ALIMENTARES = [
        "🥩 Carnívoro", "🐟 Pescetariano", "🥬 Vegetariano",
        "🌱 Vegano", "🌾 Glúten", "🥛 Lactose",
        "🥜 Nozes", "🍷 Álcool", "☕ Cafeína"
    ]
    
    CONDICOES_MEDICAS = [
        "Diabetes tipo 2", "Hipertensão", "Colesterol alto",
        "Hipotireoidismo", "Síndrome do ovário policístico",
        "Apneia do sono", "Refluxo", "Gastrite",
        "Ansiedade", "Depressão", "Lesão muscular",
        "Outro"
    ]
    
    DIETAS_ANTERIORES = [
        "Low carb", "Cetogênica", "Mediterrânea",
        "DASH", "Vegan", "Vegetariana",
        "Jejum intermitente", "Low fat", "Não fiz dieta"
    ]
    
    def __init__(self, services: Dict[str, Any]):
        self.services = services
        self.db = services.get("db")
        self._init_session_state()
    
    def _init_session_state(self) -> None:
        """Inicializa estado do onboarding."""
        if "onboarding_step" not in st.session_state:
            st.session_state.onboarding_step = 1
        if "onboarding_data" not in st.session_state:
            st.session_state.onboarding_data = OnboardingData()
        if "onboarding_completed" not in st.session_state:
            st.session_state.onboarding_completed = False
    
    def render(self) -> None:
        """Renderiza fluxo de onboarding."""
        # Verifica se já completou
        if st.session_state.onboarding_completed:
            self._render_completed()
            return
        
        # Progresso
        self._render_progress()
        
        # Passo atual
        step = st.session_state.onboarding_step
        
        if step == 1:
            self._render_step_1()
        elif step == 2:
            self._render_step_2()
        elif step == 3:
            self._render_step_3()
        elif step == 4:
            self._render_step_4()
        elif step == 5:
            self._render_step_5()
        elif step == 6:
            self._render_step_6()
        else:
            self._render_step_1()
    
    def _render_progress(self) -> None:
        """Renderiza barra de progresso."""
        total_steps = 6
        current_step = st.session_state.onboarding_step
        
        progress = (current_step - 1) / total_steps
        
        st.markdown(
            f"""
            <div style="max-width:600px;margin:0 auto 2rem;">
                <div style="display:flex;justify-content:space-between;
                    font-size:0.8rem;color:var(--text-muted);margin-bottom:0.3rem;">
                    <span>Passo {current_step} de {total_steps}</span>
                    <span>{int(progress * 100)}% completo</span>
                </div>
                <div style="background:var(--surface-2);border-radius:8px;
                    height:6px;overflow:hidden;">
                    <div style="width:{progress * 100}%;
                        background:linear-gradient(90deg,var(--primary),var(--secondary));
                        height:100%;transition:width 0.3s ease;">
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_step_1(self) -> None:
        """Passo 1: Dados pessoais."""
        data = st.session_state.onboarding_data
        
        st.markdown(
            """
            <div style="max-width:600px;margin:0 auto;">
                <h3 style="text-align:center;font-weight:700;color:var(--text);">
                    📋 Vamos começar com seus dados
                </h3>
                <p style="text-align:center;color:var(--text-muted);margin-bottom:1.5rem;">
                    Essas informações nos ajudam a personalizar seu plano
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        with st.form("onboarding_step_1", clear_on_submit=False):
            col1, col2 = st.columns(2)
            with col1:
                data.birth_date = st.date_input(
                    "Data de nascimento",
                    value=data.birth_date or datetime(1990, 1, 1),
                    min_value=datetime(1900, 1, 1),
                    max_value=datetime.now(),
                    key="onb_birth"
                )
                data.gender = st.selectbox(
                    "Gênero",
                    self.GENEROS,
                    index=self.GENEROS.index(data.gender) if data.gender in self.GENEROS else 0,
                    key="onb_gender"
                )
            
            with col2:
                data.height_cm = st.number_input(
                    "Altura (cm)",
                    min_value=100.0,
                    max_value=250.0,
                    value=data.height_cm or 165.0,
                    step=1.0,
                    key="onb_height"
                )
                data.weight_kg = st.number_input(
                    "Peso atual (kg)",
                    min_value=30.0,
                    max_value=350.0,
                    value=data.weight_kg or 70.0,
                    step=0.5,
                    key="onb_weight"
                )
            
            col1, col2 = st.columns(2)
            with col1:
                st.caption("💡 Exemplo: 16/05/1990")
            
            submitted = st.form_submit_button(
                "Próximo →",
                type="primary",
                use_container_width=True
            )
        
        if submitted:
            if self._validate_step_1(data):
                st.session_state.onboarding_step = 2
                st.rerun()
    
    def _render_step_2(self) -> None:
        """Passo 2: Objetivos e metas."""
        data = st.session_state.onboarding_data
        
        st.markdown(
            """
            <div style="max-width:600px;margin:0 auto;">
                <h3 style="text-align:center;font-weight:700;color:var(--text);">
                    🎯 Qual é o seu objetivo?
                </h3>
                <p style="text-align:center;color:var(--text-muted);margin-bottom:1.5rem;">
                    Defina metas realistas para sua jornada
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        with st.form("onboarding_step_2", clear_on_submit=False):
            data.primary_goal = st.selectbox(
                "Objetivo principal",
                list(self.OBJETIVOS_PRINCIPAIS.keys()),
                format_func=lambda x: self.OBJETIVOS_PRINCIPAIS[x],
                index=0,
                key="onb_goal"
            )
            
            data.target_weight_kg = st.number_input(
                "Peso desejado (kg)",
                min_value=30.0,
                max_value=300.0,
                value=data.target_weight_kg or 65.0,
                step=0.5,
                key="onb_target_weight",
                help="Defina um peso realista e saudável"
            )
            
            data.weekly_goal = st.select_slider(
                "Ritmo de progresso semanal",
                options=["light", "moderate", "intense"],
                format_func=lambda x: self.METAS_SEMANAIS[x],
                value=data.weekly_goal or "moderate",
                key="onb_weekly_goal"
            )
            
            # Mostra estimativa
            self._show_goal_estimate(data)
            
            submitted = st.form_submit_button(
                "Próximo →",
                type="primary",
                use_container_width=True
            )
        
        if submitted:
            if self._validate_step_2(data):
                st.session_state.onboarding_step = 3
                st.rerun()
    
    def _render_step_3(self) -> None:
        """Passo 3: Hábitos e estilo de vida."""
        data = st.session_state.onboarding_data
        
        st.markdown(
            """
            <div style="max-width:600px;margin:0 auto;">
                <h3 style="text-align:center;font-weight:700;color:var(--text);">
                    🏃‍♂️ Conte sobre sua rotina
                </h3>
                <p style="text-align:center;color:var(--text-muted);margin-bottom:1.5rem;">
                    Entendendo seus hábitos para recomendações melhores
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        with st.form("onboarding_step_3", clear_on_submit=False):
            data.exercise_frequency = st.selectbox(
                "Frequência de exercícios físicos",
                self.FREQUENCIA_EXERCICIO,
                index=self.FREQUENCIA_EXERCICIO.index(data.exercise_frequency) 
                    if data.exercise_frequency in self.FREQUENCIA_EXERCICIO else 0,
                key="onb_exercise"
            )
            
            data.fitness_level = st.select_slider(
                "Nível de condicionamento físico atual",
                options=["beginner", "intermediate", "advanced"],
                format_func=lambda x: self.NIVEL_FITNESS[x],
                value=data.fitness_level or "beginner",
                key="onb_fitness"
            )
            
            data.sleep_hours = st.slider(
                "Horas de sono por noite",
                min_value=3,
                max_value=12,
                value=data.sleep_hours or 7,
                step=1,
                key="onb_sleep",
                help="O sono adequado é fundamental para os resultados"
            )
            
            submitted = st.form_submit_button(
                "Próximo →",
                type="primary",
                use_container_width=True
            )
        
        if submitted:
            if self._validate_step_3(data):
                st.session_state.onboarding_step = 4
                st.rerun()
    
    def _render_step_4(self) -> None:
        """Passo 4: Restrições alimentares."""
        data = st.session_state.onboarding_data
        
        st.markdown(
            """
            <div style="max-width:600px;margin:0 auto;">
                <h3 style="text-align:center;font-weight:700;color:var(--text);">
                    🍽️ Preferências alimentares
                </h3>
                <p style="text-align:center;color:var(--text-muted);margin-bottom:1.5rem;">
                    Selecione suas restrições e preferências
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        with st.form("onboarding_step_4", clear_on_submit=False):
            data.dietary_restrictions = st.multiselect(
                "Restrições alimentares (opcional)",
                self.RESTRICOES_ALIMENTARES,
                default=data.dietary_restrictions,
                key="onb_restrictions",
                help="Selecione todas que se aplicam a você"
            )
            
            data.previous_diets = st.multiselect(
                "Dietas que já tentou",
                self.DIETAS_ANTERIORES,
                default=data.previous_diets,
                key="onb_previous_diets",
                help="Isso nos ajuda a entender sua experiência"
            )
            
            submitted = st.form_submit_button(
                "Próximo →",
                type="primary",
                use_container_width=True
            )
        
        if submitted:
            st.session_state.onboarding_step = 5
            st.rerun()
    
    def _render_step_5(self) -> None:
        """Passo 5: Condições médicas."""
        data = st.session_state.onboarding_data
        
        st.markdown(
            """
            <div style="max-width:600px;margin:0 auto;">
                <h3 style="text-align:center;font-weight:700;color:var(--text);">
                    🏥 Saúde e condições médicas
                </h3>
                <p style="text-align:center;color:var(--text-muted);margin-bottom:1.5rem;">
                    Essas informações são confidenciais e nos ajudam a personalizar seu plano com segurança
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        with st.form("onboarding_step_5", clear_on_submit=False):
            data.medical_conditions = st.multiselect(
                "Condições médicas existentes",
                self.CONDICOES_MEDICAS,
                default=data.medical_conditions,
                key="onb_conditions",
                help="Selecione todas que se aplicam"
            )
            
            if "Outro" in data.medical_conditions:
                other_condition = st.text_input(
                    "Especifique outras condições",
                    key="onb_condition_other",
                    placeholder="Ex: Asma, Artrite..."
                )
            
            data.medications = st.text_area(
                "Medicamentos em uso (opcional)",
                value=", ".join(data.medications) if data.medications else "",
                placeholder="Ex: Metformina, Losartana, Vitamina D...",
                key="onb_medications",
                help="Liste todos os medicamentos que você toma regularmente"
            )
            
            st.info(
                "⚠️ **Importante**: Consulte sempre seu médico antes de iniciar "
                "qualquer programa de mudança alimentar ou exercícios."
            )
            
            submitted = st.form_submit_button(
                "Próximo →",
                type="primary",
                use_container_width=True
            )
        
        if submitted:
            # Atualiza medicações
            if data.medications:
                data.medications = [m.strip() for m in data.medications.split(",") if m.strip()]
            
            st.session_state.onboarding_step = 6
            st.rerun()
    
    def _render_step_6(self) -> None:
        """Passo 6: Revisão e finalização."""
        data = st.session_state.onboarding_data
        
        st.markdown(
            """
            <div style="max-width:600px;margin:0 auto;">
                <h3 style="text-align:center;font-weight:700;color:var(--text);">
                    ✅ Revisão do seu perfil
                </h3>
                <p style="text-align:center;color:var(--text-muted);margin-bottom:1.5rem;">
                    Confirme se todas as informações estão corretas
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Exibe resumo
        self._render_summary(data)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Voltar", use_container_width=True):
                st.session_state.onboarding_step = 5
                st.rerun()
        
        with col2:
            if st.button(
                "✅ Finalizar cadastro",
                type="primary",
                use_container_width=True
            ):
                self._complete_onboarding(data)
    
    def _render_summary(self, data: OnboardingData) -> None:
        """Renderiza resumo dos dados."""
        
        # Dados pessoais
        with st.expander("📋 Dados pessoais", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Idade", self._calculate_age(data.birth_date) if data.birth_date else "—")
            with col2:
                st.metric("Gênero", data.gender or "—")
            with col3:
                st.metric("Altura", f"{data.height_cm:.1f} cm" if data.height_cm else "—")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Peso atual", f"{data.weight_kg:.1f} kg" if data.weight_kg else "—")
            with col2:
                st.metric("Peso desejado", f"{data.target_weight_kg:.1f} kg" if data.target_weight_kg else "—")
        
        # Objetivos
        with st.expander("🎯 Objetivos", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Objetivo", self.OBJETIVOS_PRINCIPAIS.get(data.primary_goal, "—"))
            with col2:
                st.metric("Ritmo", self.METAS_SEMANAIS.get(data.weekly_goal, "—"))
        
        # Hábitos
        with st.expander("🏃‍♂️ Hábitos", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Exercícios", data.exercise_frequency or "—")
            with col2:
                st.metric("Nível", self.NIVEL_FITNESS.get(data.fitness_level, "—"))
            with col3:
                st.metric("Sono", f"{data.sleep_hours}h" if data.sleep_hours else "—")
        
        # Restrições e saúde
        with st.expander("🍽️ Preferências e saúde", expanded=False):
            if data.dietary_restrictions:
                st.write("**Restrições alimentares:**", ", ".join(data.dietary_restrictions))
            else:
                st.write("**Restrições alimentares:** Nenhuma")
            
            if data.previous_diets:
                st.write("**Dietas anteriores:**", ", ".join(data.previous_diets))
            
            if data.medical_conditions:
                st.write("**Condições médicas:**", ", ".join(data.medical_conditions))
            
            if data.medications:
                st.write("**Medicamentos:**", ", ".join(data.medications))
    
    def _complete_onboarding(self, data: OnboardingData) -> None:
        """Completa o onboarding e salva os dados."""
        try:
            # Salva dados no banco
            user_data = st.session_state.get("user", {})
            if user_data:
                # Atualiza usuário com dados do onboarding
                onboarding_dict = data.to_dict()
                
                # No sistema real, salvaria no banco
                # Aqui simulamos no session_state
                if "mock_db" in st.session_state:
                    users = st.session_state.mock_db.get("users", {})
                    email = user_data.get("email", "").lower()
                    if email in users:
                        users[email]["onboarding_data"] = onboarding_dict
                        users[email]["onboarding_done"] = True
                        users[email]["onboarding_completed_at"] = datetime.now().isoformat()
                
                # Atualiza sessão
                st.session_state.user["onboarding_done"] = True
                st.session_state.user["onboarding_data"] = onboarding_dict
            
            # Marca como completo
            st.session_state.onboarding_completed = True
            
            # Mensagem de sucesso
            st.success("🎉 Perfil configurado com sucesso!")
            st.balloons()
            
            # Aguarda um momento e redireciona
            st.info("Redirecionando para sua página inicial...")
            import time
            time.sleep(1.5)
            
            st.session_state.page = "home"
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Erro ao salvar dados: {str(e)}")
            st.session_state.onboarding_completed = False
    
    def _render_completed(self) -> None:
        """Renderiza estado de onboarding já completo."""
        st.success("✅ Você já completou seu onboarding!")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("Ir para página inicial →", type="primary", use_container_width=True):
                st.session_state.page = "home"
                st.rerun()
    
    def _show_goal_estimate(self, data: OnboardingData) -> None:
        """Mostra estimativa de tempo para atingir meta."""
        if data.weight_kg > 0 and data.target_weight_kg > 0 and data.weight_kg > data.target_weight_kg:
            diff = data.weight_kg - data.target_weight_kg
            
            # Taxas por nível
            rates = {
                "light": 0.5,    # kg por semana
                "moderate": 1.0,
                "intense": 1.5
            }
            
            rate = rates.get(data.weekly_goal, 1.0)
            weeks = diff / rate if rate > 0 else 0
            
            if weeks > 0:
                st.info(
                    f"💡 Com seu ritmo atual, você pode atingir seu peso desejado "
                    f"em aproximadamente **{weeks:.1f} semanas** "
                    f"({int(weeks / 4.3)} meses)."
                )
            else:
                st.success("✅ Você já está em seu peso desejado!")
        elif data.weight_kg > 0 and data.target_weight_kg > 0 and data.weight_kg < data.target_weight_kg:
            st.info("🎯 Você está buscando ganho de peso/massa muscular. Vamos trabalhar nisso!")
    
    def _validate_step_1(self, data: OnboardingData) -> bool:
        """Valida dados do passo 1."""
        if not data.birth_date:
            st.error("Por favor, informe sua data de nascimento.")
            return False
        
        age = self._calculate_age(data.birth_date)
        if age < 18:
            st.error("Você deve ter pelo menos 18 anos para usar o Melshape.")
            return False
        if age > 100:
            st.error("Por favor, verifique sua data de nascimento.")
            return False
        
        if not data.gender:
            st.error("Por favor, selecione seu gênero.")
            return False
        
        if data.height_cm < 100 or data.height_cm > 250:
            st.error("Altura inválida. Por favor, verifique o valor.")
            return False
        
        if data.weight_kg < 20 or data.weight_kg > 350:
            st.error("Peso inválido. Por favor, verifique o valor.")
            return False
        
        return True
    
    def _validate_step_2(self, data: OnboardingData) -> bool:
        """Valida dados do passo 2."""
        if not data.primary_goal:
            st.error("Por favor, selecione um objetivo principal.")
            return False
        
        if data.target_weight_kg <= 0:
            st.error("Por favor, informe um peso desejado válido.")
            return False
        
        if data.target_weight_kg < 20 or data.target_weight_kg > 300:
            st.error("Peso desejado inválido.")
            return False
        
        if data.weight_kg > 0 and abs(data.target_weight_kg - data.weight_kg) > 100:
            st.warning("⚠️ A diferença entre seu peso atual e desejado é muito grande. Considere metas intermediárias.")
        
        return True
    
    def _validate_step_3(self, data: OnboardingData) -> bool:
        """Valida dados do passo 3."""
        if not data.exercise_frequency:
            st.error("Por favor, informe sua frequência de exercícios.")
            return False
        
        if data.sleep_hours < 3 or data.sleep_hours > 12:
            st.error("Por favor, informe uma quantidade válida de horas de sono (3-12).")
            return False
        
        return True
    
    def _calculate_age(self, birth_date: datetime) -> int:
        """Calcula idade a partir da data de nascimento."""
        today = datetime.now()
        return today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )


# Interface compatível com o sistema existente
def render(services: Dict[str, Any]) -> None:
    """Função principal de renderização."""
    renderer = OnboardingRenderer(services)
    renderer.render()
