"""
Melshape — Versão de Teste Simplificada.

Este é um app Streamlit mínimo e autossuficiente para testar a estrutura
do projeto e verificar se o ambiente Streamlit Cloud está funcionando.

Não depende de módulos externos problemáticos.
"""
import streamlit as st
from datetime import datetime
import random

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="🔥 Melshape — Teste",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "Melshape v3.0 — Teste de Deploy",
        "Report a bug": "mailto:suporte@melshape.com.br",
        "Get help": "mailto:suporte@melshape.com.br",
    },
)

# ─────────────────────────────────────────────────────────────────────────────
# ESTILO CSS (resumido)
# ─────────────────────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
        /* Reset e base */
        .main {
            background: #F7F5F2;
        }
        h1, h2, h3 {
            font-family: 'Segoe UI', system-ui, sans-serif;
            color: #1A1814;
        }
        .metric-card {
            background: white;
            border: 1px solid #DDD9D1;
            border-radius: 10px;
            padding: 1rem 1.1rem;
            box-shadow: 0 1px 3px rgba(26,24,20,.06);
            margin-bottom: 0.5rem;
        }
        .metric-value {
            font-weight: 800;
            font-size: 1.6rem;
            color: #1A1814;
        }
        .metric-label {
            font-size: 0.76rem;
            color: #6B6560;
            margin-top: 0.2rem;
        }
        .badge {
            display: inline-block;
            border-radius: 9999px;
            padding: 0.2rem 0.65rem;
            font-size: 0.72rem;
            font-weight: 700;
            background: #FBF4E0;
            color: #B8922A;
            border: 1px solid #E8D08A;
        }
        .alert-info {
            background: #EFF6FF;
            border-left: 3px solid #1D4ED8;
            border-radius: 6px;
            padding: 0.7rem 1rem;
            margin: 0.5rem 0;
        }
        .btn-primary {
            background: linear-gradient(135deg, #C9A84C, #a8862e);
            color: white;
            border: none;
            padding: 0.55rem 1.25rem;
            border-radius: 8px;
            font-weight: 700;
            cursor: pointer;
        }
        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 14px rgba(184,146,42,.45);
        }
        .status-ok { color: #15803D; }
        .status-error { color: #B91C1C; }
        .status-warning { color: #B45309; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# DADOS MOCK
# ─────────────────────────────────────────────────────────────────────────────

MOCK_USER = {
    "name": "Usuário Teste",
    "email": "teste@melshape.com.br",
    "health_mode": "general",
    "current_weight": 78.5,
    "goal_weight": 70.0,
    "plan": "trial",
    "dark_mode": False,
}

MOCK_STATS = {
    "xp": 450,
    "level": 3,
    "level_name": "Determinado",
    "streak": 7,
    "badges": 4,
}

MOCK_DAILY = {
    "calories": 1650,
    "protein": 82.5,
    "hydration": 1800,
    "water_goal": 2000,
    "meals_count": 3,
}

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR SIMPLIFICADA
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        """
        <div style="padding: 1rem 0.5rem;">
            <div style="font-size: 2rem;">🔥</div>
            <div style="font-weight: 800; font-size: 1.25rem; color: #1A1814;">
                Melshape
            </div>
            <div style="font-size: 0.72rem; color: #A09890; font-style: italic;">
                Para quem está mudando de verdade.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Informações do usuário
    st.markdown(
        f"""
        <div style="padding: 0.2rem 0;">
            <div style="font-weight: 700; font-size: 0.9rem; color: #1A1814;">
                👤 {MOCK_USER['name']}
            </div>
            <span class="badge">⚖️ Emagrecimento</span>
            <span class="badge" style="background:#E8F5E9;color:#15803D;border-color:#86EFAC;">
                ⏳ TRIAL (7d)
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Stats rápidos
    col1, col2 = st.columns(2)
    with col1:
        st.metric("🔥 Calorias", f"{MOCK_DAILY['calories']} kcal")
    with col2:
        st.metric("🥩 Proteína", f"{MOCK_DAILY['protein']:.0f}g")

    st.markdown("---")

    # Menu
    pages = [
        "🏠 Home",
        "✅ Check-in",
        "📊 Score",
        "📋 Hábitos",
        "➕ Registrar",
        "🎯 Metas",
        "🗺️ Jornada",
        "🏆 Conquistas",
        "👤 Perfil",
    ]

    for page in pages:
        if st.button(page, use_container_width=True, key=f"menu_{page}"):
            st.session_state.page = page
            st.rerun()

    st.markdown("---")

    if st.button("🌙 Modo escuro", use_container_width=True):
        st.session_state.dark_mode = not st.session_state.get("dark_mode", False)
        st.rerun()

    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# CONTEÚDO PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def render_home():
    """Renderiza a página inicial."""
    st.markdown(
        f"""
        <div style="margin-bottom: 1rem;">
            <h1 style="font-size: 1.7rem; margin: 0;">
                Olá, {MOCK_USER['name']} 👋
            </h1>
            <p style="color: #6B6560; margin: 0.2rem 0 0;">
                {datetime.now().strftime('%A, %d de %B de %Y')}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Card de streak
    st.markdown(
        f"""
        <div class="metric-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div class="metric-value" style="font-size: 2.5rem;">
                        {MOCK_STATS['streak']}
                    </div>
                    <div class="metric-label">🔥 Dias consecutivos</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 1.2rem;">✅ Check-in feito!</div>
                    <div style="font-size: 0.76rem; color: #6B6560;">
                        Últimos 7 dias: 🟢🟢🟢🟢🟢🟢🟢
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Próximo passo
    st.markdown(
        """
        <div class="alert-info">
            <b>💡 Próximo passo:</b> Registre suas refeições de hoje
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{MOCK_DAILY['calories']}</div>
                <div class="metric-label">🔥 kcal</div>
                <div style="font-size:0.72rem;color:#6B6560;">Meta: 1800 kcal</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{MOCK_DAILY['protein']:.0f}g</div>
                <div class="metric-label">🥩 Proteína</div>
                <div style="font-size:0.72rem;color:#6B6560;">Meta: 100g</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{MOCK_DAILY['hydration']}ml</div>
                <div class="metric-label">💧 Água</div>
                <div style="font-size:0.72rem;color:#6B6560;">Meta: {MOCK_DAILY['water_goal']}ml</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-value">{MOCK_STATS['xp']}</div>
                <div class="metric-label">⭐ XP Total</div>
                <div style="font-size:0.72rem;color:#6B6560;">Nível {MOCK_STATS['level']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Hábitos do dia
    st.markdown("---")
    st.markdown("### 📋 Hábitos de Hoje")

    habits = [
        ("💧", "Beber 2L de água", True),
        ("🥩", "Atingir meta proteica", False),
        ("🚶", "Caminhar 30 minutos", True),
        ("😴", "Dormir 7-8 horas", False),
    ]

    for icon, name, done in habits:
        status = "✅" if done else "⬜"
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between; align-items: center;
                 padding: 0.5rem 0; border-bottom: 1px solid #EAE7E1;">
                <span style="font-size: 0.9rem;">
                    {icon} {name}
                </span>
                <span style="font-weight: 700; color: {'#15803D' if done else '#6B6560'};">
                    {status}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_checkin():
    """Renderiza a página de check-in."""
    st.markdown(
        """
        <h1>✅ Check-in Diário</h1>
        <p style="color: #6B6560;">Como você está hoje? Leva menos de 30 segundos.</p>
        """,
        unsafe_allow_html=True,
    )

    with st.form("checkin_form"):
        st.select_slider(
            "😊 Humor",
            options=[1, 2, 3, 4, 5],
            value=3,
            key="checkin_humor",
        )

        st.select_slider(
            "⚡ Energia",
            options=[1, 2, 3, 4, 5],
            value=3,
            key="checkin_energia",
        )

        st.select_slider(
            "😴 Qualidade do sono",
            options=[1, 2, 3, 4, 5],
            value=3,
            key="checkin_sono",
        )

        st.text_input(
            "💬 Algo que quer registrar?",
            placeholder="Ex: Dormi bem, estou motivado...",
            key="checkin_obs",
        )

        if st.form_submit_button(
            "✅ Fazer check-in",
            type="primary",
            use_container_width=True,
        ):
            st.toast("✅ Check-in realizado com sucesso! +20 XP", icon="🔥")
            st.balloons()


def render_habits():
    """Renderiza a página de hábitos."""
    st.markdown(
        """
        <h1>📋 Hábitos</h1>
        <p style="color: #6B6560;">Pequenas ações diárias que geram transformação.</p>
        """,
        unsafe_allow_html=True,
    )

    # Estatísticas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📋 Hábitos hoje", "3/5")
    with col2:
        st.metric("📊 Aderência (7d)", "78%")
    with col3:
        st.metric("🔥 Melhor streak", "12 dias")

    st.markdown("---")

    # Lista de hábitos
    habits = [
        {"icon": "💧", "name": "Beber 2L de água", "streak": 7, "done": True},
        {"icon": "🥩", "name": "Atingir meta proteica", "streak": 3, "done": False},
        {"icon": "🚶", "name": "Caminhar 30 minutos", "streak": 5, "done": True},
        {"icon": "😴", "name": "Dormir 7-8 horas", "streak": 2, "done": False},
        {"icon": "✅", "name": "Registrar refeições", "streak": 4, "done": True},
    ]

    for habit in habits:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.markdown(
                f"""
                <div style="font-weight: 600; color: #1A1814; font-size: 0.95rem;">
                    {habit['icon']} {habit['name']}
                </div>
                <div style="font-size: 0.76rem; color: #6B6560;">
                    🔥 {habit['streak']} dias
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            if habit['done']:
                st.markdown(
                    """
                    <div style="color: #15803D; font-weight: 700; text-align: center;">
                        ✅ Concluído
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                if st.button("✓", key=f"hab_{habit['name']}"):
                    st.toast(f"{habit['icon']} {habit['name']} — +15 XP", icon="✅")
                    st.rerun()
        with col3:
            if not habit['done']:
                st.markdown(
                    """
                    <div style="font-size: 0.76rem; color: #6B6560; text-align: center;">
                        Pendente
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    if st.button("➕ Criar novo hábito", type="primary", use_container_width=True):
        st.info("📝 Funcionalidade em desenvolvimento")


def render_register():
    """Renderiza a página de registro."""
    st.markdown(
        """
        <h1>➕ Registrar</h1>
        <p style="color: #6B6560;">Escolha o que quer registrar hoje.</p>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🍽️ Refeição", use_container_width=True):
            st.session_state.registro = "refeicao"
            st.rerun()

    with col2:
        if st.button("⚖️ Peso", use_container_width=True):
            st.session_state.registro = "peso"
            st.rerun()

    with col3:
        if st.button("💧 Água", use_container_width=True):
            st.session_state.registro = "agua"
            st.rerun()

    with col4:
        if st.button("✅ Check-in", use_container_width=True):
            st.session_state.registro = "checkin"
            st.rerun()

    st.markdown("---")

    tipo = st.session_state.get("registro", "refeicao")

    if tipo == "refeicao":
        st.subheader("🍽️ Registrar Refeição")

        col1, col2 = st.columns(2)
        with col1:
            alimento = st.text_input("Alimento", placeholder="Ex: Frango Grelhado")
            quantidade = st.number_input("Quantidade (g)", min_value=10, value=150, step=10)
        with col2:
            tipo_refeicao = st.selectbox(
                "Tipo",
                ["Café da Manhã", "Almoço", "Lanche", "Jantar", "Ceia"]
            )
            horario = st.time_input("Horário", value=datetime.now().time())

        if st.button("✅ Registrar refeição", type="primary", use_container_width=True):
            st.toast("🍽️ Refeição registrada! +5 XP", icon="✅")

    elif tipo == "peso":
        st.subheader("⚖️ Registrar Peso")

        peso = st.number_input(
            "Peso (kg)",
            min_value=30.0,
            max_value=300.0,
            value=MOCK_USER['current_weight'],
            step=0.1,
        )

        if st.button("✅ Registrar peso", type="primary", use_container_width=True):
            st.toast(f"⚖️ {peso:.1f} kg registrado! +30 XP", icon="✅")

    elif tipo == "agua":
        st.subheader("💧 Registrar Água")

        ml = st.number_input("Quantidade (ml)", min_value=50, max_value=1000, value=200, step=50)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💧 Adicionar", type="primary", use_container_width=True):
                st.toast(f"💧 {ml}ml de água registrado! +10 XP", icon="✅")

        with col2:
            total_hj = st.session_state.get("agua_total", 0) + ml
            st.metric("Total hoje", f"{total_hj}ml", delta=f"{total_hj - 2000:.0f}ml da meta")

    else:
        st.subheader("✅ Check-in Rápido")

        humor = st.select_slider("😊 Humor", options=[1, 2, 3, 4, 5], value=3)

        if st.button("✅ Salvar check-in", type="primary", use_container_width=True):
            st.toast("✅ Check-in salvo! +20 XP", icon="✅")


def render_score():
    """Renderiza a página de score."""
    st.markdown(
        """
        <h1>📊 Seu Score de Transformação</h1>
        <p style="color: #6B6560;">Uma visão completa de como você está evoluindo.</p>
        """,
        unsafe_allow_html=True,
    )

    score = 68
    level = "📈 Progresso Consistente"

    st.markdown(
        f"""
        <div class="metric-card" style="text-align: center; padding: 1.5rem;">
            <div style="font-size: 2.5rem;">{level.split()[0]}</div>
            <div style="font-family: 'Segoe UI', sans-serif; font-weight: 800;
                 font-size: 2.2rem; color: #B8922A;">
                {score}
            </div>
            <div style="font-size: 0.76rem; color: #6B6560;">de 100 pontos</div>
            <div style="font-size: 0.88rem; color: #B8922A; font-weight: 700; margin-top: 0.4rem;">
                {level}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Dimensões
    st.markdown("### As 5 dimensões da sua transformação")

    dimensions = [
        ("📅 Consistência", 72),
        ("⚡ Engajamento", 65),
        ("🍽️ Alimentação", 58),
        ("😊 Bem-estar", 75),
        ("📊 Indicadores", 45),
    ]

    for label, value in dimensions:
        st.markdown(
            f"""
            <div style="margin-bottom: 0.5rem;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.2rem;">
                    <span style="font-size: 0.85rem;">{label}</span>
                    <span style="font-weight: 700; color: {'#15803D' if value >= 60 else '#B45309' if value >= 40 else '#B91C1C'};">
                        {value}%
                    </span>
                </div>
                <div style="background: #F0EDE8; border-radius: 4px; height: 8px; overflow: hidden;">
                    <div style="background: {'#15803D' if value >= 60 else '#B8922A' if value >= 40 else '#B91C1C'}; 
                         height: 100%; width: {value}%; border-radius: 4px;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_profile():
    """Renderiza a página de perfil."""
    st.markdown(
        """
        <h1>👤 Perfil</h1>
        <p style="color: #6B6560;">Seus dados e configurações.</p>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs(["👤 Dados", "💳 Plano", "⚙️ Preferências"])

    with tab1:
        st.markdown("##### 👤 Dados Pessoais")

        col1, col2 = st.columns(2)

        with col1:
            st.text_input("Nome", value=MOCK_USER['name'])
            st.number_input("Peso atual (kg)", value=MOCK_USER['current_weight'])
            st.number_input("Altura (cm)", value=170)

        with col2:
            st.text_input("Email", value=MOCK_USER['email'], disabled=True)
            st.number_input("Peso desejado (kg)", value=MOCK_USER['goal_weight'])
            st.selectbox("Gênero", ["Feminino", "Masculino", "Outro"])

        st.selectbox(
            "Modo de saúde",
            ["⚖️ Emagrecimento", "💪 Fitness", "🔪 Pós-Bariátrica", "💉 GLP-1"],
        )

        if st.button("💾 Salvar dados", type="primary", use_container_width=True):
            st.toast("💾 Dados salvos!", icon="✅")

    with tab2:
        st.markdown("##### 💳 Meu Plano")

        st.markdown(
            """
            <div class="metric-card">
                <div style="display: flex; align-items: center; gap: 0.8rem;">
                    <span style="font-size: 2rem;">✨</span>
                    <div>
                        <div style="font-weight: 800; font-size: 1.1rem; color: #1A1814;">
                            Trial
                        </div>
                        <div style="font-size: 0.80rem; color: #6B6560;">
                            10 dias de acesso completo
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.progress(0.3, text="⏳ 7 dias restantes")

        if st.button("🚀 Assinar Pro", type="primary", use_container_width=True):
            st.info("🔜 Pagamento em breve")

    with tab3:
        st.markdown("##### ⚙️ Preferências")

        dark_mode = st.toggle("🌙 Modo escuro", value=False)

        st.markdown("##### 📧 Notificações")
        st.checkbox("📬 Lembretes por email", value=True)
        st.checkbox("🔥 Alertas de streak", value=True)


# ─────────────────────────────────────────────────────────────────────────────
# ROTEAMENTO
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Função principal."""
    # Inicializa estado da sessão
    if "page" not in st.session_state:
        st.session_state.page = "🏠 Home"

    # Renderiza página selecionada
    page = st.session_state.page

    if page == "🏠 Home" or page == "home":
        render_home()
    elif page == "✅ Check-in" or page == "checkin":
        render_checkin()
    elif page == "📋 Hábitos" or page == "habits":
        render_habits()
    elif page == "➕ Registrar" or page == "meals":
        render_register()
    elif page == "📊 Score" or page == "score":
        render_score()
    elif page == "👤 Perfil" or page == "profile":
        render_profile()
    else:
        render_home()


if __name__ == "__main__":
    main()