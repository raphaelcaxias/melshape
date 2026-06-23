"""
Melshape — Página Inicial do Paciente.
Dashboard principal com métricas, check-in diário e progresso.
"""
import streamlit as st
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


class HomeRenderer:
    """Renderer dedicado para página inicial do paciente."""
    
    def __init__(self, services: Dict[str, Any]):
        self.services = services
        self.db = services.get("db")
        self.user = st.session_state.get("user", {})
    
    def render(self) -> None:
        """Renderiza página inicial."""
        # Verifica autenticação
        if not self.user:
            st.error("Por favor, faça login para acessar esta página.")
            if st.button("Ir para login"):
                st.session_state.page = "login"
                st.rerun()
            return
        
        # Cabeçalho com saudação
        self._render_header()
        
        # Métricas principais
        self._render_metrics()
        
        # Check-in diário
        self._render_daily_checkin()
        
        # Progresso e gráficos
        col1, col2 = st.columns(2)
        with col1:
            self._render_progress_chart()
        with col2:
            self._render_streak_info()
        
        # Ações rápidas
        self._render_quick_actions()
        
        # Próximos passos
        self._render_next_steps()
    
    def _render_header(self) -> None:
        """Renderiza cabeçalho com saudação."""
        name = self.user.get("name", "Usuário")
        today = datetime.now().strftime("%A, %d de %B de %Y")
        days_in_program = self._calculate_days_in_program()
        
        st.markdown(
            f"""
            <div style="max-width:800px;margin:0 auto 1.5rem;">
                <div style="display:flex;justify-content:space-between;
                    align-items:center;flex-wrap:wrap;">
                    <div>
                        <h2 style="font-family:var(--font-display);font-weight:800;
                            color:var(--text);margin:0;">
                            👋 Olá, {name.split()[0]}!
                        </h2>
                        <p style="color:var(--text-muted);margin:0.2rem 0 0;">
                            {today} • {days_in_program} dias no programa
                        </p>
                    </div>
                    <div>
                        <span style="background:var(--success-light);
                            color:var(--success);padding:0.3rem 0.8rem;
                            border-radius:20px;font-size:0.8rem;
                            font-weight:600;">
                            ⭐ Nível 3
                        </span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_metrics(self) -> None:
        """Renderiza métricas principais."""
        # Dados de exemplo - no sistema real viriam do banco
        metrics = self._get_user_metrics()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "⚖️ Peso atual",
                f"{metrics.get('weight', 72.5):.1f} kg",
                delta=f"{metrics.get('weight_change', -0.8):.1f} kg",
                delta_color="normal"
            )
        
        with col2:
            st.metric(
                "📐 IMC",
                f"{metrics.get('bmi', 26.8):.1f}",
                delta=f"{metrics.get('bmi_change', -0.3):.1f}",
                delta_color="inverse"
            )
        
        with col3:
            st.metric(
                "🔥 Calorias hoje",
                f"{metrics.get('calories_today', 1650)} kcal",
                delta=f"{metrics.get('calories_goal', 1800) - metrics.get('calories_today', 1650)} kcal restantes"
            )
        
        with col4:
            st.metric(
                "💪 Sequência",
                f"{metrics.get('streak', 7)} dias",
                delta="🔥 em alta!" if metrics.get('streak', 0) > 5 else "continue assim"
            )
    
    def _render_daily_checkin(self) -> None:
        """Renderiza widget de check-in diário."""
        st.divider()
        
        st.markdown(
            """
            <div style="text-align:center;margin-bottom:1rem;">
                <h3 style="font-weight:600;color:var(--text);">
                    📝 Check-in Diário
                </h3>
                <p style="color:var(--text-muted);">
                    Como foi seu dia hoje? Leva apenas 30 segundos.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Verifica se já fez check-in hoje
        checked_in_today = self._check_in_today()
        
        if checked_in_today:
            st.success("✅ Você já fez seu check-in hoje! Continue assim! 🌟")
        else:
            with st.form("daily_checkin", clear_on_submit=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    mood = st.select_slider(
                        "Humor",
                        options=["😞", "😐", "🙂", "😊", "🤩"],
                        value="🙂",
                        key="mood"
                    )
                with col2:
                    energy = st.select_slider(
                        "Energia",
                        options=["🔋 Baixa", "🔋 Média", "🔋 Alta"],
                        value="🔋 Média",
                        key="energy"
                    )
                with col3:
                    sleep = st.select_slider(
                        "Sono",
                        options=["😴 Ruim", "😴 Regular", "😴 Bom"],
                        value="😴 Bom",
                        key="sleep"
                    )
                
                # Motivação
                motivation = st.text_area(
                    "Como você está se sentindo hoje? (opcional)",
                    placeholder="Ex: Me sinto motivado, tive um dia produtivo...",
                    key="motivation"
                )
                
                if st.form_submit_button(
                    "✅ Registrar check-in",
                    type="primary",
                    use_container_width=True
                ):
                    self._save_checkin(mood, energy, sleep, motivation)
                    st.success("🌟 Check-in registrado com sucesso!")
                    st.balloons()
                    st.rerun()
    
    def _render_progress_chart(self) -> None:
        """Renderiza gráfico de progresso."""
        st.markdown(
            """
            <div style="margin-top:1.5rem;">
                <h4 style="font-weight:600;color:var(--text);">
                    📊 Progresso do peso
                </h4>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Dados de exemplo
        data = self._get_weight_history()
        
        if data and len(data) > 1:
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=data["dates"],
                y=data["weights"],
                mode="lines+markers",
                name="Peso atual",
                line=dict(color="#FF6B6B", width=3),
                marker=dict(size=8, color="#FF6B6B")
            ))
            
            # Meta
            target_weight = self.user.get("onboarding_data", {}).get("target_weight_kg", 65)
            fig.add_hline(
                y=target_weight,
                line_dash="dash",
                line_color="#51CF66",
                annotation_text=f"🎯 Meta: {target_weight}kg",
                annotation_position="bottom right"
            )
            
            fig.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=20, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#666"),
               
