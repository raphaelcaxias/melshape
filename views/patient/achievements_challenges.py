"""
Melshape — Desafios com progresso real.

Tabelas: desafios, desafios_usuario
Fallback: lista semanal do GamificationService quando banco vazio.
"""
import streamlit as st
from typing import Dict, Any, List, Optional, Set
from datetime import date, timedelta
import logging

from services.gamification_service import GamificationService
from views.components.cards import empty_state, xp_toast, show_new_achievements

logger = logging.getLogger("Melshape.Challenges")


class ChallengesRenderer:
    """Renderer dedicado para desafios."""
    
    def __init__(self, db, gami: GamificationService):
        self.db = db
        self.gami = gami
        self.user_id = db.uid() if hasattr(db, "uid") else None
    
    def render(self) -> None:
        """Renderiza lista de desafios."""
        desafios_db = self._buscar_desafios()
        
        if desafios_db:
            self._render_desafios_banco(desafios_db)
        else:
            self._render_desafios_fallback()
    
    # ── DESAFIOS DO BANCO ──────────────────────────────────────────────────────
    def _buscar_desafios(self) -> List[Dict]:
        """Busca desafios ativos no banco."""
        if hasattr(self.db, "is_real") and self.db.is_real and hasattr(self.db, "client"):
            try:
                response = (
                    self.db.client
                    .table("desafios")
                    .select("id,titulo,descricao,xp_recompensa,data_fim,encerrado")
                    .eq("encerrado", False)
                    .limit(20)
                    .execute()
                )
                return response.data or []
            except Exception as e:
                logger.warning(f"Erro ao buscar desafios: {e}")
        
        return []
    
    def _render_desafios_banco(self, desafios: List[Dict]) -> None:
        """Renderiza desafios do banco de dados."""
        if not self.user_id:
            st.warning("Usuário não identificado.")
            return
        
        progresso = self._buscar_progresso_usuario()
        concluidos_ids = {
            d.get("desafio_id") 
            for d in progresso 
            if d.get("concluido")
        }
        ativos = [d for d in desafios if not d.get("encerrado")]
        
        # Cabeçalho
        st.markdown(
            f"""
            <div style="font-size:0.82rem;color:var(--text-muted);
                margin-bottom:0.8rem;">
                <b>{len(ativos)}</b> desafio(s) ativo(s) · 
                <b>{len(concluidos_ids)}</b> concluído(s)
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        if not ativos:
            empty_state("🎯", "Nenhum desafio ativo", "Novos desafios em breve!")
            return
        
        # Renderiza cada desafio
        for desafio in ativos:
            self._render_desafio_item(desafio, concluidos_ids)
    
    def _buscar_progresso_usuario(self) -> List[Dict]:
        """Busca progresso do usuário nos desafios."""
        if not self.user_id:
            return []
        
        if hasattr(self.db, "is_real") and self.db.is_real and hasattr(self.db, "client"):
            try:
                response = (
                    self.db.client
                    .table("desafios_usuario")
                    .select("desafio_id,concluido")
                    .eq("perfil_id", self.user_id)
                    .execute()
                )
                return response.data or []
            except Exception as e:
                logger.warning(f"Erro ao buscar progresso: {e}")
        
        return []
    
    def _render_desafio_item(self, desafio: Dict, concluidos_ids: Set[str]) -> None:
        """Renderiza um item de desafio individual."""
        desafio_id = desafio.get("id", "")
        titulo = desafio.get("titulo", "Desafio")
        descricao = desafio.get("descricao", "")
        xp_val = int(desafio.get("xp_recompensa") or 0)
        concluido = desafio_id in concluidos_ids
        
        dias_rest = self._dias_restantes(desafio.get("data_fim", ""))
        cor = "var(--success)" if concluido else "var(--border)"
        icon = "✅" if concluido else "🎯"
        
        # Monta HTML do desafio
        xp_html = f'<span class="xp-badge">+{xp_val} XP</span>' if xp_val else ""
        prazo_html = (
            f'<div style="font-size:0.72rem;color:var(--text-faint);">'
            f'{dias_rest}d restantes</div>'
            if dias_rest is not None else ""
        )
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="margin-bottom:0.6rem;
                border-color:{cor};">
                <div style="display:flex;justify-content:space-between;
                    align-items:flex-start;">
                    <div style="display:flex;gap:0.6rem;">
                        <span style="font-size:1.3rem;">{icon}</span>
                        <div>
                            <div style="font-weight:700;font-size:0.92rem;
                                color:var(--text);">{titulo}</div>
                            {f'<div style="font-size:0.78rem;color:var(--text-muted);">{descricao}</div>' if descricao else ""}
                        </div>
                    </div>
                    <div style="text-align:right;">
                        {xp_html}
                        {prazo_html}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Botão de concluir
        if not concluido:
            if st.button(
                "✅ Marcar concluído",
                key=f"ch_{desafio_id}",
                use_container_width=True
            ):
                self._concluir_desafio(desafio_id, xp_val)
    
    def _concluir_desafio(self, desafio_id: str, xp_val: int) -> None:
        """Marca desafio como concluído e adiciona XP."""
        if not self.user_id:
            st.error("Usuário não identificado.")
            return
        
        success = False
        
        # Tenta salvar no banco
        if hasattr(self.db, "is_real") and self.db.is_real and hasattr(self.db, "client"):
            try:
                self.db.client.table("desafios_usuario").upsert({
                    "desafio_id": desafio_id,
                    "perfil_id": self.user_id,
                    "concluido": True,
                    "concluido_em": date.today().isoformat(),
                }, on_conflict="desafio_id,perfil_id").execute()
                success = True
            except Exception as e:
                logger.warning(f"Erro ao concluir desafio: {e}")
        else:
            # Fallback para mock
            success = True
        
        if success:
            self.db.add_xp(xp_val, motivo=f"desafio_{desafio_id[:8]}")
            st.toast(f"🎯 +{xp_val} XP!", icon="🎉")
            xp_toast(xp_val, "desafio concluído")
            st.rerun()
    
    def _dias_restantes(self, prazo: str) -> Optional[int]:
        """Calcula dias restantes até o prazo."""
        if not prazo:
            return None
        try:
            return max(0, (date.fromisoformat(prazo[:10]) - date.today()).days)
        except Exception:
            return None
    
    # ── FALLBACK SEMANAL ──────────────────────────────────────────────────────
    def _render_desafios_fallback(self) -> None:
        """Renderiza desafios da semana (fallback)."""
        st.markdown(
            """
            <div style="font-size:0.80rem;color:var(--text-muted);
                margin-bottom:0.8rem;">
                🎯 Desafios desta semana
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        desafios = self.gami.weekly_challenges()
        concluidos = st.session_state.get("desafios_concluidos_local", set())
        
        if not desafios:
            empty_state("🎯", "Sem desafios esta semana")
            return
        
        for idx, desafio in enumerate(desafios):
            self._render_desafio_fallback_item(idx, desafio, concluidos)
        
        # Reset semanal
        hoje = date.today()
        prox_seg = hoje + timedelta(days=(7 - hoje.weekday()))
        st.markdown(
            f"""
            <div style="font-size:0.74rem;color:var(--text-faint);
                margin-top:0.5rem;text-align:center;">
                🔄 Reset em {(prox_seg - hoje).days} dia(s)
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_desafio_fallback_item(self, idx: int, desafio: Dict, 
                                       concluidos: Set[str]) -> None:
        """Renderiza item de desafio fallback."""
        emoji = desafio.get("emoji", "🎯")
        titulo = desafio.get("title", "")
        xp_val = desafio.get("xp", 0)
        key = f"ch_local_{idx}"
        concluido = key in concluidos
        
        cor = "var(--success)" if concluido else "var(--border)"
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="margin-bottom:0.5rem;
                border-color:{cor};">
                <div style="display:flex;justify-content:space-between;
                    align-items:center;">
                    <span style="font-size:0.90rem;font-weight:600;
                        color:var(--text);">{emoji} {titulo}</span>
                    <span class="xp-badge">+{xp_val} XP</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        if not concluido:
            if st.button(
                "✅ Concluído",
                key=f"ch_fb_{idx}",
                use_container_width=True
            ):
                self._concluir_desafio_fallback(key, xp_val)
        else:
            st.markdown(
                '<div style="font-size:0.76rem;color:var(--success);">✅ Concluído</div>',
                unsafe_allow_html=True,
            )
    
    def _concluir_desafio_fallback(self, key: str, xp_val: int) -> None:
        """Conclui desafio no fallback local."""
        concluidos = st.session_state.get("desafios_concluidos_local", set())
        concluidos.add(key)
        st.session_state["desafios_concluidos_local"] = concluidos
        
        self.db.add_xp(xp_val, motivo="desafio_semanal")
        st.toast(f"🎯 +{xp_val} XP!", icon="🎉")
        xp_toast(xp_val, "desafio")
        
        novos = self.gami.check_achievements()
        show_new_achievements(novos)
        st.rerun()


# Interface compatível com o sistema existente
def render_desafios(db, gami: GamificationService) -> None:
    """Função principal para renderização de desafios."""
    renderer = ChallengesRenderer(db, gami)
    renderer.render()
