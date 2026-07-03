"""
Melshape — Home: bloco de consistência (streak + calendário).
Usa contextualizer — streak zero nunca é punição, sempre recomeço.
"""
import streamlit as st
from typing import Dict, Any, Optional, List, Set
from datetime import date, timedelta
import logging

from views.components.cards import alert
from services.contextualizer import ctx

logger = logging.getLogger("Melshape.HomeConsistency")


# Constantes de limiares de streak
STREAK_LENDA = 30
STREAK_DESTAQUE = 7
STREAK_INICIO = 3
DIAS_HISTORICO_PADRAO = 7

# Constantes de XP
XP_RECOMECO_PADRAO = 25


class HomeConsistencyRenderer:
    """Renderer dedicado para bloco de consistência."""
    
    def __init__(self, db, gami, user: Dict[str, Any]):
        self.db = db
        self.gami = gami
        self.user = user
    
    def render(self, streak: int, checkin: Optional[Dict]) -> None:
        """Renderiza bloco de consistência."""
        self._render_header()
        
        # Parse seguro dos dados
        streak_val = self._parse_streak(streak)
        checkin_hoje = checkin is not None
        
        # Obtém informações formatadas
        checkin_emoji, checkin_label = self._get_checkin_info(checkin_hoje)
        cor_streak = self._get_cor_streak(streak_val)
        msg_streak = self._get_mensagem_streak(streak_val)
        
        # Histórico de checkins
        historico = self._get_historico_checkins(DIAS_HISTORICO_PADRAO)
        dots = self._render_dots_historico(historico)
        
        # Renderiza cards
        self._render_cards(streak_val, cor_streak, msg_streak,
                           checkin_emoji, checkin_label, dots)
        
        # Mensagens motivacionais
        self._render_mensagens(streak_val, checkin_hoje)
    
    def _render_header(self) -> None:
        """Renderiza cabeçalho do bloco."""
        st.markdown(
            """
            <p style="font-size: 0.74rem; font-weight: 700; letter-spacing: 0.08em;
                color: var(--text-faint); text-transform: uppercase;
                margin-bottom: 0.7rem;">
                Consistência
            </p>
            """,
            unsafe_allow_html=True,
        )
    
    def _parse_streak(self, streak: Any) -> int:
        """Parse streak de forma segura."""
        try:
            val = int(streak) if streak is not None else 0
            return max(0, val)  # Garante não negativo
        except (ValueError, TypeError) as e:
            logger.warning(f"Erro ao parsear streak '{streak}': {e}")
            return 0
    
    def _get_checkin_info(self, checkin_hoje: bool) -> tuple:
        """Retorna emoji e label do check-in."""
        if checkin_hoje:
            return "✅", "Check-in feito!"
        return "⬜", "Sem check-in hoje"
    
    def _get_cor_streak(self, streak: int) -> str:
        """Retorna cor baseada no streak."""
        if streak >= STREAK_DESTAQUE:
            return "success"
        elif streak >= STREAK_INICIO:
            return "warning"
        return ""
    
    def _get_mensagem_streak(self, streak: int) -> str:
        """Gera mensagem contextualizada do streak."""
        try:
            return ctx.streak(streak)
        except Exception as e:
            logger.error(f"Erro ao gerar mensagem de streak: {e}", exc_info=True)
            return "Continue sua jornada!"
    
    def _render_dots_historico(self, historico: List[bool]) -> str:
        """Renderiza dots do histórico."""
        try:
            return "".join("🟢" if d else "⬜" for d in historico)
        except Exception as e:
            logger.error(f"Erro ao renderizar dots: {e}")
            return "⬜" * DIAS_HISTORICO_PADRAO
    
    def _render_cards(
        self,
        streak: int,
        cor_streak: str,
        msg_streak: str,
        checkin_emoji: str,
        checkin_label: str,
        dots: str,
    ) -> None:
        """Renderiza os 3 cards do bloco."""
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            self._render_card_streak(streak, cor_streak, msg_streak)
        
        with col2:
            self._render_card_checkin(checkin_emoji, checkin_label)
        
        with col3:
            self._render_card_historico(dots)
    
    def _render_card_streak(self, streak: int, cor: str, msg: str) -> None:
        """Renderiza card de streak."""
        st.markdown(
            f"""
            <div class="metric-card fade-in">
                <div class="metric-value {cor}" style="font-size: 3rem;">
                    {streak}
                </div>
                <div style="font-size: 0.80rem; color: var(--text-muted);
                    margin-top: 0.25rem;">{msg}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_card_checkin(self, emoji: str, label: str) -> None:
        """Renderiza card de check-in de hoje."""
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="text-align: center;">
                <div style="font-size: 2.2rem;">{emoji}</div>
                <div class="metric-label">{label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_card_historico(self, dots: str) -> None:
        """Renderiza card de histórico."""
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="text-align: center;">
                <div style="font-size: 1.15rem; letter-spacing: 2px;">{dots}</div>
                <div class="metric-label">Últimos 7 dias</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_mensagens(self, streak: int, checkin_hoje: bool) -> None:
        """Renderiza mensagens motivacionais."""
        if streak >= STREAK_LENDA:
            alert("🏆 30 dias seguidos! Você é lendário.", "success")
        elif streak >= STREAK_DESTAQUE:
            alert(f"🔥 {streak} dias seguidos! Continue assim.", "success")
        elif streak == 0 and not checkin_hoje:
            # Protocolo de recaída
            self._render_recomeco()
    
    def _render_recomeco(self) -> None:
        """Renderiza bloco de recomeço com tratamento de erros."""
        try:
            from services.relapse_service import RelapseService
            svc_relapse = RelapseService(self.db)
            dados_recaida = svc_relapse.detectar(self.user)
            
            if dados_recaida:
                self._render_bloco_recomeco(svc_relapse, dados_recaida)
            else:
                alert(
                    "Comece sua sequência hoje. Um check-in muda tudo.",
                    "info",
                )
        except Exception as e:
            logger.error(f"Erro no protocolo de recomeço: {e}", exc_info=True)
            alert(
                "Comece sua sequência hoje. Um check-in muda tudo.",
                "info",
            )
    
    def _render_bloco_recomeco(self, svc_relapse, dados: Dict) -> None:
        """Renderiza bloco de recomeço ativo."""
        melhor = self._parse_int(dados.get("melhor_streak", 0))
        xp = self._parse_int(dados.get("xp_recomeço", XP_RECOMECO_PADRAO))
        
        # Card principal
        self._render_card_recomeco(melhor, xp)
        
        # Motivo da jornada
        motivo = self._get_motivo_jornada(svc_relapse)
        if motivo:
            self._render_motivo_jornada(motivo)
        
        # Botão CTA
        self._render_botao_recomeco(svc_relapse, dados, xp)
    
    def _parse_int(self, value: Any) -> int:
        """Converte valor para int de forma segura."""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def _render_card_recomeco(self, melhor: int, xp: int) -> None:
        """Renderiza card principal de recomeço."""
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="
                border-left: 4px solid var(--primary);">
                <div style="font-size: 1.6rem; margin-bottom: 0.4rem;">🌱</div>
                <div style="font-weight: 700; font-size: 0.98rem; color: var(--text);">
                    Sua sequência anterior de {melhor} dias prova que você consegue.
                </div>
                <div style="font-size: 0.84rem; color: var(--text-muted);
                    margin-top: 0.35rem;">
                    Hoje é dia 1 de algo ainda maior. 
                    Recomeçar também vale +{xp} XP.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _get_motivo_jornada(self, svc_relapse) -> Optional[str]:
        """Obtém motivo da jornada com tratamento de erros."""
        try:
            return svc_relapse.get_motivo_para_lembrar(self.user)
        except Exception as e:
            logger.error(f"Erro ao obter motivo da jornada: {e}", exc_info=True)
            return None
    
    def _render_motivo_jornada(self, motivo: str) -> None:
        """Renderiza bloco do motivo da jornada."""
        st.markdown(
            f"""
            <div style="background: var(--primary-light);
                border: 1px solid var(--primary-border);
                border-radius: 12px; padding: 0.85rem 1.1rem;
                margin: 0.6rem 0; font-size: 0.88rem; color: var(--text);">
                💛 Lembre-se: "{motivo}"
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_botao_recomeco(self, svc_relapse, dados: Dict, xp: int) -> None:
        """Renderiza botão de recomeço."""
        if st.button(
            f"🌱 Recomeçar minha jornada — +{xp} XP",
            type="primary",
            use_container_width=True,
            key="recomeco_cta",
        ):
            self._registrar_recomeco(svc_relapse, dados, xp)
    
    def _registrar_recomeco(self, svc_relapse, dados: Dict, xp: int) -> None:
        """Registra recomeço com tratamento de erros."""
        try:
            svc_relapse.registrar_recomeco(self.user, dados)
            st.toast(
                f"🌱 Bem-vindo de volta! +{xp} XP pelo recomeço.",
                icon="🔥",
            )
            st.session_state.page = "checkin"
            st.rerun()
        except Exception as e:
            logger.error(f"Erro ao registrar recomeço: {e}", exc_info=True)
            st.error("❌ Erro ao registrar recomeço. Tente novamente.")
    
    @st.cache_data(ttl=30)
    def _get_historico_checkins(_self, days: int = 7) -> List[bool]:
        """Retorna lista de checkins dos últimos N dias (com cache)."""
        datas = _self._gerar_datas_ultimos_dias(days)
        feitos = _self._buscar_checkins_feitos(datas)
        return [d in feitos for d in datas]
    
    def _gerar_datas_ultimos_dias(self, days: int) -> List[str]:
        """Gera lista de datas dos últimos N dias."""
        try:
            today = date.today()
            return [
                (today - timedelta(days=i)).isoformat()
                for i in range(days - 1, -1, -1)
            ]
        except Exception as e:
            logger.error(f"Erro ao gerar datas: {e}", exc_info=True)
            return []
    
    def _buscar_checkins_feitos(self, datas: List[str]) -> Set[str]:
        """Busca check-ins feitos nas datas especificadas."""
        if not datas:
            return set()
        
        if self._is_real_db():
            return self._buscar_checkins_real(datas)
        else:
            return self._buscar_checkins_mock(datas)
    
    def _is_real_db(self) -> bool:
        """Verifica se o banco é real (não mock)."""
        return (
            hasattr(self.db, "is_real") and
            self.db.is_real and
            hasattr(self.db, "client")
        )
    
    def _buscar_checkins_real(self, datas: List[str]) -> Set[str]:
        """Busca check-ins no banco real."""
        try:
            uid = self.db.uid()
            response = (
                self.db.client
                .table("checkins")
                .select("data_checkin")
                .eq("perfil_id", uid)
                .in_("data_checkin", datas)
                .execute()
            )
            return {x["data_checkin"] for x in (response.data or [])}
        except Exception as e:
            logger.error(f"Erro ao buscar check-ins reais: {e}", exc_info=True)
            return set()
    
    def _buscar_checkins_mock(self, datas: List[str]) -> Set[str]:
        """Busca check-ins no mock."""
        try:
            uid = self.db.uid()
            return {
                c.get("log_date", "")
                for c in self.db._mock().get("checkins", [])
                if c.get("user_id") == uid
                and c.get("log_date") in datas
            }
        except Exception as e:
            logger.error(f"Erro ao buscar check-ins mock: {e}", exc_info=True)
            return set()


# Funções de compatibilidade
def _bloco_consistencia(streak: int, checkin: Optional[Dict],
                         db, gami, user: Dict[str, Any]) -> None:
    """Renderiza bloco de consistência (compatibilidade)."""
    renderer = HomeConsistencyRenderer(db, gami, user)
    renderer.render(streak, checkin)


def _historico_checkins(db, days: int = 7) -> List[bool]:
    """Retorna histórico de checkins (compatibilidade)."""
    renderer = HomeConsistencyRenderer(db, None, {})
    return renderer._get_historico_checkins(days)
