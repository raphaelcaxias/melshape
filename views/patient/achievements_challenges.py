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
        self.user_id = self._get_user_id()
        
        # Cache de dados para evitar múltiplas consultas
        self._desafios_cache: Optional[List[Dict]] = None
        self._progresso_cache: Optional[List[Dict]] = None
    
    def _get_user_id(self) -> Optional[str]:
        """Obtém ID do usuário de forma segura."""
        if hasattr(self.db, "uid"):
            try:
                return self.db.uid()
            except Exception as e:
                logger.warning(f"Erro ao obter user_id: {e}")
        return None
    
    def render(self) -> None:
        """Renderiza lista de desafios."""
        desafios_db = self._buscar_desafios()
        
        if desafios_db:
            self._render_desafios_banco(desafios_db)
        else:
            self._render_desafios_fallback()
    
    # ── DESAFIOS DO BANCO ──────────────────────────────────────────────────────
    
    @st.cache_data(ttl=60)
    def _buscar_desafios(_self) -> List[Dict]:
        """Busca desafios ativos no banco (com cache)."""
        if not (_self._is_real_db() and hasattr(_self.db, "client")):
            return []
        
        try:
            response = (
                _self.db.client
                .table("desafios")
                .select("id,titulo,descricao,xp_recompensa,data_fim,encerrado")
                .eq("encerrado", False)
                .limit(20)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Erro ao buscar desafios: {e}", exc_info=True)
            return []
    
    def _is_real_db(self) -> bool:
        """Verifica se o banco é real (não mock)."""
        return hasattr(self.db, "is_real") and self.db.is_real
    
    def _render_desafios_banco(self, desafios: List[Dict]) -> None:
        """Renderiza desafios do banco de dados."""
        if not self.user_id:
            st.warning("⚠️ Usuário não identificado. Faça login para participar dos desafios.")
            return
        
        progresso = self._buscar_progresso_usuario()
        concluidos_ids = self._extrair_concluidos(progresso)
        ativos = [d for d in desafios if not d.get("encerrado")]
        
        self._render_cabecalho_desafios(len(ativos), len(concluidos_ids))
        
        if not ativos:
            empty_state("🎯", "Nenhum desafio ativo", "Novos desafios em breve!")
            return
        
        for desafio in ativos:
            self._render_desafio_item(desafio, concluidos_ids)
    
    def _extrair_concluidos(self, progresso: List[Dict]) -> Set[str]:
        """Extrai IDs de desafios concluídos."""
        return {
            d.get("desafio_id") 
            for d in progresso 
            if d.get("concluido") and d.get("desafio_id")
        }
    
    def _render_cabecalho_desafios(self, total_ativos: int, total_concluidos: int) -> None:
        """Renderiza cabeçalho com contadores."""
        st.markdown(
            f"""
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
                <b>{total_ativos}</b> desafio(s) ativo(s) · 
                <b>{total_concluidos}</b> concluído(s)
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    @st.cache_data(ttl=30)
    def _buscar_progresso_usuario(_self) -> List[Dict]:
        """Busca progresso do usuário nos desafios (com cache)."""
        if not _self.user_id or not (_self._is_real_db() and hasattr(_self.db, "client")):
            return []
        
        try:
            response = (
                _self.db.client
                .table("desafios_usuario")
                .select("desafio_id,concluido")
                .eq("perfil_id", _self.user_id)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Erro ao buscar progresso: {e}", exc_info=True)
            return []
    
    def _render_desafio_item(self, desafio: Dict, concluidos_ids: Set[str]) -> None:
        """Renderiza um item de desafio individual."""
        desafio_id = desafio.get("id", "")
        titulo = desafio.get("titulo", "Desafio")
        descricao = desafio.get("descricao", "")
        xp_val = self._parse_xp(desafio.get("xp_recompensa"))
        concluido = desafio_id in concluidos_ids
        
        dias_rest = self._calcular_dias_restantes(desafio.get("data_fim"))
        
        self._render_card_desafio(
            titulo=titulo,
            descricao=descricao,
            xp_val=xp_val,
            dias_rest=dias_rest,
            concluido=concluido,
            desafio_id=desafio_id,
        )
    
    def _parse_xp(self, xp_raw: Any) -> int:
        """Converte XP para int de forma segura."""
        try:
            return int(xp_raw or 0)
        except (ValueError, TypeError):
            return 0
    
    def _calcular_dias_restantes(self, prazo: Optional[str]) -> Optional[int]:
        """Calcula dias restantes até o prazo."""
        if not prazo:
            return None
        try:
            data_prazo = date.fromisoformat(prazo[:10])
            dias = (data_prazo - date.today()).days
            return max(0, dias)
        except (ValueError, TypeError) as e:
            logger.debug(f"Erro ao parsear prazo '{prazo}': {e}")
            return None
    
    def _render_card_desafio(
        self,
        titulo: str,
        descricao: str,
        xp_val: int,
        dias_rest: Optional[int],
        concluido: bool,
        desafio_id: str,
    ) -> None:
        """Renderiza card HTML de um desafio."""
        cor = "var(--success)" if concluido else "var(--border)"
        icon = "✅" if concluido else "🎯"
        
        xp_html = f'<span class="xp-badge">+{xp_val} XP</span>' if xp_val > 0 else ""
        prazo_html = (
            f'<div style="font-size: 0.72rem; color: var(--text-faint);">'
            f'{dias_rest}d restantes</div>'
            if dias_rest is not None else ""
        )
        desc_html = (
            f'<div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.2rem;">'
            f'{descricao}</div>'
            if descricao else ""
        )
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="margin-bottom: 0.6rem; border-color: {cor};">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div style="display: flex; gap: 0.6rem; flex: 1;">
                        <span style="font-size: 1.3rem;">{icon}</span>
                        <div style="flex: 1;">
                            <div style="font-weight: 700; font-size: 0.92rem; color: var(--text);">
                                {titulo}
                            </div>
                            {desc_html}
                        </div>
                    </div>
                    <div style="text-align: right; margin-left: 1rem;">
                        {xp_html}
                        {prazo_html}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        if not concluido:
            self._render_botao_concluir(desafio_id, xp_val)
    
    def _render_botao_concluir(self, desafio_id: str, xp_val: int) -> None:
        """Renderiza botão de concluir com confirmação."""
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if st.button(
                "✅ Marcar concluído",
                key=f"ch_{desafio_id}",
                use_container_width=True,
            ):
                st.session_state[f"confirm_{desafio_id}"] = True
        
        with col2:
            if st.session_state.get(f"confirm_{desafio_id}"):
                if st.button(
                    "Confirmar?",
                    key=f"ch_confirm_{desafio_id}",
                    type="primary",
                    use_container_width=True,
                ):
                    self._concluir_desafio(desafio_id, xp_val)
                    st.session_state[f"confirm_{desafio_id}"] = False
    
    def _concluir_desafio(self, desafio_id: str, xp_val: int) -> None:
        """Marca desafio como concluído e adiciona XP."""
        if not self.user_id:
            st.error("❌ Usuário não identificado.")
            return
        
        success = self._salvar_conclusao_banco(desafio_id)
        
        if success:
            self._processar_recompensa(xp_val, f"desafio_{desafio_id[:8]}")
            st.cache_data.clear()  # Limpa cache para atualizar dados
            st.rerun()
    
    def _salvar_conclusao_banco(self, desafio_id: str) -> bool:
        """Salva conclusão no banco de dados."""
        if not (self._is_real_db() and hasattr(self.db, "client")):
            return True  # Mock sempre succeeds
        
        try:
            self.db.client.table("desafios_usuario").upsert(
                {
                    "desafio_id": desafio_id,
                    "perfil_id": self.user_id,
                    "concluido": True,
                    "concluido_em": date.today().isoformat(),
                },
                on_conflict="desafio_id,perfil_id",
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Erro ao concluir desafio {desafio_id}: {e}", exc_info=True)
            st.error(f"❌ Erro ao salvar conclusão: {str(e)}")
            return False
    
    def _processar_recompensa(self, xp_val: int, motivo: str) -> None:
        """Processa recompensa de XP e conquistas."""
        try:
            self.db.add_xp(xp_val, motivo=motivo)
            st.toast(f"🎯 +{xp_val} XP!", icon="🎉")
            xp_toast(xp_val, "desafio concluído")
            
            novos = self.gami.check_achievements(self.user_id)
            show_new_achievements(novos)
        except Exception as e:
            logger.error(f"Erro ao processar recompensa: {e}", exc_info=True)
    
    # ── FALLBACK SEMANAL ──────────────────────────────────────────────────────
    
    def _render_desafios_fallback(self) -> None:
        """Renderiza desafios da semana (fallback)."""
        st.markdown(
            """
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
                🎯 Desafios desta semana
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        desafios = self.gami.weekly_challenges()
        concluidos = self._get_concluidos_fallback()
        
        if not desafios:
            empty_state("🎯", "Sem desafios esta semana", "Volte na próxima semana!")
            return
        
        for idx, desafio in enumerate(desafios):
            self._render_desafio_fallback_item(idx, desafio, concluidos)
        
        self._render_reset_semanal()
    
    def _get_concluidos_fallback(self) -> List[str]:
        """Obtém lista de desafios concluídos no fallback."""
        return st.session_state.get("desafios_concluidos_local", [])
    
    def _render_desafio_fallback_item(
        self,
        idx: int,
        desafio: Dict,
        concluidos: List[str],
    ) -> None:
        """Renderiza item de desafio fallback."""
        emoji = desafio.get("emoji", "🎯")
        titulo = desafio.get("title", "Desafio")
        xp_val = self._parse_xp(desafio.get("xp"))
        key = f"ch_local_{idx}"
        concluido = key in concluidos
        
        cor = "var(--success)" if concluido else "var(--border)"
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="margin-bottom: 0.5rem; border-color: {cor};">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 0.9rem; font-weight: 600; color: var(--text);">
                        {emoji} {titulo}
                    </span>
                    <span class="xp-badge">+{xp_val} XP</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        if not concluido:
            self._render_botao_concluir_fallback(idx, key, xp_val)
        else:
            st.markdown(
                '<div style="font-size: 0.76rem; color: var(--success); margin-top: 0.3rem;">'
                '✅ Concluído</div>',
                unsafe_allow_html=True,
            )
    
    def _render_botao_concluir_fallback(self, idx: int, key: str, xp_val: int) -> None:
        """Renderiza botão de concluir fallback com confirmação."""
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if st.button(
                "✅ Concluído",
                key=f"ch_fb_{idx}",
                use_container_width=True,
            ):
                st.session_state[f"confirm_fb_{idx}"] = True
        
        with col2:
            if st.session_state.get(f"confirm_fb_{idx}"):
                if st.button(
                    "Confirmar?",
                    key=f"ch_fb_confirm_{idx}",
                    type="primary",
                    use_container_width=True,
                ):
                    self._concluir_desafio_fallback(key, xp_val)
                    st.session_state[f"confirm_fb_{idx}"] = False
    
    def _concluir_desafio_fallback(self, key: str, xp_val: int) -> None:
        """Conclui desafio no fallback local."""
        concluidos = self._get_concluidos_fallback()
        if key not in concluidos:
            concluidos.append(key)
            st.session_state["desafios_concluidos_local"] = concluidos
        
        self._processar_recompensa(xp_val, "desafio_semanal")
        st.rerun()
    
    def _render_reset_semanal(self) -> None:
        """Renderiza informação de reset semanal."""
        hoje = date.today()
        dias_para_segunda = (7 - hoje.weekday()) % 7
        if dias_para_segunda == 0:
            dias_para_segunda = 7
        
        st.markdown(
            f"""
            <div style="font-size: 0.74rem; color: var(--text-faint); 
                margin-top: 0.8rem; text-align: center;">
                🔄 Reset em <b>{dias_para_segunda}</b> dia(s)
            </div>
            """,
            unsafe_allow_html=True,
        )


# Interface compatível com o sistema existente
def render_desafios(db, gami: GamificationService) -> None:
    """Função principal para renderização de desafios."""
    renderer = ChallengesRenderer(db, gami)
    renderer.render()
