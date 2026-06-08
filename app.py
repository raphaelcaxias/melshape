# app.py
import streamlit as st
from datetime import date
import random

from config import FEATURES, DESAFIOS, CONQUISTAS
from styles import aplicar_css, get_tema
from utils import *
from database import conectar_supabase, criar_usuario, get_usuario, get_ranking
from avatar_maker import tela_avatar

# -----------------------------------------------------------------------------
# PÁGINAS
# -----------------------------------------------------------------------------

def pagina_login():
    st.markdown("<h1 style='text-align:center;'>?? EmagreSim</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            email = st.text_input("E-mail", placeholder="seu@email.com")
            senha = st.text_input("Senha", type="password", placeholder="••••••••")
            if st.form_submit_button("Entrar", use_container_width=True):
                st.success("Login simulado! Use o modo demonstração.")
        
        st.markdown("---")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("?? Criar conta", use_container_width=True):
                st.query_params["pagina"] = "avatar"
                st.rerun()
        with col_b:
            if st.button("?? Modo demonstração", use_container_width=True):
                st.session_state["usuario"] = {
                    "nome": "Adriano", "email": "demo@emagresim.com",
                    "idade": 39, "altura": 1.75, "peso_atual": 144.0, "peso_meta": 90.0,
                    "sexo": "M", "avatar": "??"
                }
                st.query_params["pagina"] = "dashboard"
                st.rerun()

def pagina_criar_conta():
    st.markdown("<h1 style='text-align:center;'>?? Criar Conta</h1>", unsafe_allow_html=True)
    
    if "avatar_svg" in st.session_state:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(f'<div style="display: flex; justify-content: center;">{st.session_state["avatar_svg"]}</div>', unsafe_allow_html=True)
            if st.button("?? Editar Avatar"):
                st.query_params["pagina"] = "avatar"
                st.rerun()
        with col2:
            with st.form("form_criar_conta"):
                nome = st.text_input("Nome completo")
                email = st.text_input("E-mail")
                senha = st.text_input("Senha", type="password")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    idade = st.number_input("Idade", 18, 100, 30)
                    altura = st.number_input("Altura (m)", 1.40, 2.50, 1.75, 0.01)
                with col_b:
                    peso = st.number_input("Peso atual (kg)", 30.0, 300.0, 80.0, 0.1)
                    meta_peso = st.number_input("Meta de peso (kg)", 40.0, 200.0, 70.0, 0.5)
                
                sexo = st.selectbox("Sexo", ["Masculino", "Feminino"])
                
                if st.form_submit_button("?? Criar minha conta", use_container_width=True):
                    if nome and email and senha:
                        st.session_state["usuario"] = {
                            "nome": nome, "email": email, "idade": idade,
                            "altura": altura, "peso_atual": peso, "peso_meta": meta_peso,
                            "sexo": "M" if sexo == "Masculino" else "F",
                            "avatar": st.session_state.get("avatar_svg", "??")
                        }
                        st.success(f"? Conta criada com sucesso, {nome}!")
                        st.balloons()
                        st.query_params["pagina"] = "dashboard"
                        st.rerun()
    else:
        st.info("?? Primeiro, crie seu avatar!")
        if st.button("Criar Avatar"):
            st.query_params["pagina"] = "avatar"
            st.rerun()

def pagina_dashboard():
    usuario = get_usuario()
    if not usuario:
        st.warning("Nenhum usuário logado")
        if st.button("Voltar"):
            st.query_params.clear()
            st.rerun()
        return
    
    C = get_tema()
    
    # Cabeçalho com avatar
    col_avatar, col_titulo = st.columns([1, 4])
    with col_avatar:
        if usuario.get("avatar") and usuario["avatar"].startswith("<svg"):
            st.markdown(f'<div style="display: flex; justify-content: center;">{usuario["avatar"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="font-size: 3rem; text-align: center;">{usuario.get("avatar", "??")}</div>', unsafe_allow_html=True)
    with col_titulo:
        st.markdown(f"<h1>Olá, {usuario['nome']}!</h1>", unsafe_allow_html=True)
        st.markdown(f"<p>{mensagem_bom_dia()}</p>", unsafe_allow_html=True)
    
    # Mensagem de suporte emocional
    if FEATURES["enable_mood_support"] and st.button("?? Estou me sentindo para baixo", use_container_width=True):
        st.info("?? Um dia difícil não define sua jornada. Que tal uma meta mais leve hoje?")
        st.session_state["meta_leve"] = True
    
    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        imc = calcular_imc(usuario["peso_atual"], usuario["altura"])
        st.metric("Peso Atual", f"{usuario['peso_atual']:.1f} kg", f"Meta: {usuario['peso_meta']:.0f} kg")
    with col2:
        st.metric("IMC", f"{imc:.1f}", classificar_imc(imc))
    with col3:
        tmb = calcular_tmb(usuario["peso_atual"], usuario["altura"], usuario["idade"], usuario["sexo"])
        st.metric("TMB", f"{int(tmb)} kcal", "Basal")
    with col4:
        st.metric("Plano", "Grátis")
    
    # Gráfico de evolução
    st.markdown("### ?? Evolução do Peso")
    fig = gerar_grafico_peso([], usuario["peso_meta"])
    st.plotly_chart(fig, use_container_width=True)
    
    # Previsão
    data_meta = previsao_meta(usuario["peso_atual"], usuario["peso_meta"])
    if data_meta:
        st.info(f"?? **Previsão:** Mantendo o ritmo, você atinge sua meta em **{data_meta.strftime('%d/%m/%Y')}**")
    
    # Desafio da semana
    if FEATURES["enable_challenges"]:
        with st.expander("?? Desafio da Semana", expanded=True):
            desafio = random.choice(DESAFIOS)
            st.markdown(f"**{desafio['nome']}** – {desafio['descricao']} ? +{desafio['xp']} XP")
            st.progress(0.3, text=f"Progresso: {desafio['meta'] * 0.3:.0f}/{desafio['meta']} dias")
    
    # Receita do dia
    if FEATURES["enable_recipe_suggestion"]:
        with st.expander("?? Receita do dia", expanded=False):
            receita = receita_do_dia()
            st.markdown(f"**{receita['nome']}** - {receita['calorias']} kcal")
    
    # Ranking
    ranking = get_ranking()
    if ranking:
        st.markdown("### ?? Ranking Semanal")
        for i, r in enumerate(ranking[:5]):
            medalha = ["??", "??", "??"][i] if i < 3 else f"{i+1}º"
            st.write(f"{medalha} **{r['nome']}** – {r['pontos']} pontos")
    
    # Botão sair
    if st.button("?? Sair", use_container_width=True):
        st.session_state.clear()
        st.query_params.clear()
        st.rerun()

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

def main():
    aplicar_css()
    
    pagina = st.query_params.get("pagina", "login")
    
    if pagina == "avatar":
        tela_avatar()
    elif pagina == "criar_conta":
        pagina_criar_conta()
    elif pagina == "dashboard":
        pagina_dashboard()
    else:
        pagina_login()

if __name__ == "__main__":
    main()