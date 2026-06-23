"""
Melshape — Dashboard Profissional: tabs de alertas e inativos.
"""
import streamlit as st
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

from views.components.cards import empty_state, metric_card

logger = logging.getLogger("Melshape.ProDashTabs")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Prioridades
PRIORIDADE_EMOJI = {
    "URGENTE": "🚨",
    "ALTA": "⚠️",
    "MODERADA": "📋",
    "BAIXA": "✅",
}

PRIORIDADE_COR = {
    "URGENTE": "error",
    "ALTA": "warning",
    "MODERADA": "info",
    "BAIXA": "success",
}

# Limiares
RISCO_ABANDONO_ALERTA = 70
GRAVIDADE_ERRO = 3
GRAVIDADE_WARNING = 2

# Limites
MAX_RESULTADOS_QUERY = 100

# Fallbacks
DEFAULT_NOME = "—"
DEFAULT_DATA = "—"
DEFAULT_GRAVIDADE = 1


@dataclass
class AlertaItem:
    """Item de alerta clínico."""
    nome: str = DEFAULT_NOME
    titulo: str = ""
    descricao: str = ""
    gravidade: int = DEFAULT_GRAVIDADE
    data: str = DEFAULT_DATA


@dataclass
class InativoItem:
    """Item de paciente inativo."""
    nome: str = DEFAULT_NOME
    dias_sem_acesso: int = 0
    dias_sem_checkin: int = 0
    risco_abandono: float = 0.0


class DashboardTabsRenderer:
    """Renderer para as tabs do dashboard profissional."""
    
    def __init__(self, db):
        self.db = db
    
    def render_alertas(self) -> None:
        """Renderiza tab de alertas clínicos com tratamento de erros."""
        try:
            alertas = self._query(
                "vw_alertas_abertos",
                "nome_completo,titulo,descricao,gravidade,criado_em",
            )
            
            if not alertas:
                self._render_sem_alertas()
                return
            
            self._render_header_alertas(len(alertas))
            
            for alerta in alertas:
                self._render_alerta_item(alerta)
        except Exception as e:
            logger.error(f"Erro ao renderizar alertas: {e}", exc_info=True)
            st.error("❌ Erro ao carregar alertas clínicos.")
    
    def _render_sem_alertas(self) -> None:
        """Renderiza mensagem quando não há alertas."""
        st.markdown(
            """
            <div class="alert-success" style="margin: 0.5rem 0;">
                ✅ Nenhum alerta clínico aberto
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_header_alertas(self, total: int) -> None:
        """Renderiza cabeçalho de alertas."""
        st.markdown(
            f"""
            <div class="alert-warning" style="margin: 0.5rem 0;">
                ⚠️ <b>{total}</b> alerta(s) clínico(s) aberto(s)
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div style="margin-top: 0.7rem;"></div>', unsafe_allow_html=True)
    
    def _render_alerta_item(self, alerta: Dict) -> None:
        """Renderiza um item de alerta com tratamento de erros."""
        try:
            if not isinstance(alerta, dict):
                return
            
            gravidade = self._parse_int(alerta.get("gravidade", DEFAULT_GRAVIDADE))
            cor = self._get_cor_alerta(gravidade)
            data = self._formatar_data(alerta.get("criado_em"))
            
            nome = alerta.get("nome_completo", DEFAULT_NOME)
            titulo = alerta.get("titulo", "")
            descricao = alerta.get("descricao", "")
            
            self._render_card_alerta(nome, titulo, descricao, data, cor)
        except Exception as e:
            logger.error(f"Erro ao renderizar alerta item: {e}", exc_info=True)
    
    def _get_cor_alerta(self, gravidade: int) -> str:
        """Retorna cor baseada na gravidade."""
        if gravidade >= GRAVIDADE_ERRO:
            return "error"
        elif gravidade >= GRAVIDADE_WARNING:
            return "warning"
        return "info"
    
    def _formatar_data(self, data_raw: Any) -> str:
        """Formata data de forma segura."""
        try:
            if not data_raw:
                return DEFAULT_DATA
            return str(data_raw)[:10]
        except Exception as e:
            logger.debug(f"Erro ao formatar data: {e}")
            return DEFAULT_DATA
    
    def _render_card_alerta(
        self,
        nome: str,
        titulo: str,
        descricao: str,
        data: str,
        cor: str,
    ) -> None:
        """Renderiza card de alerta."""
        desc_html = (
            f'<div style="font-size: 0.82rem; color: var(--text-faint); margin-top: 0.2rem;">'
            f'{descricao}</div>'
            if descricao else ""
        )
        
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="margin-bottom: 0.6rem;">
                <div style="display: flex; justify-content: space-between;
                    align-items: flex-start;">
                    <div style="flex: 1;">
                        <div style="font-weight: 700; font-size: 0.94rem; color: var(--text);">
                            {nome}
                        </div>
                        <div style="font-size: 0.86rem; color: var(--text-muted); margin-top: 0.25rem;">
                            {titulo}
                        </div>
                        {desc_html}
                    </div>
                    <div style="text-align: right; font-size: 0.76rem;
                        color: var(--text-faint); margin-left: 1rem;">
                        {data}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def render_inativos(self) -> None:
        """Renderiza tab de pacientes inativos com tratamento de erros."""
        try:
            inativos = self._query(
                "vw_pacientes_inativos",
                "nome_completo,dias_sem_acesso,dias_sem_checkin,risco_abandono",
            )
            sem_checkin = self._query(
                "vw_sem_checkin_recente",
                "nome_completo,dias_sem_checkin,ultimo_checkin",
            )
            
            if not inativos and not sem_checkin:
                self._render_todos_ativos()
                return
            
            if inativos:
                self._render_inativos_list(inativos)
            
            if sem_checkin:
                self._render_sem_checkin_list(sem_checkin)
        except Exception as e:
            logger.error(f"Erro ao renderizar inativos: {e}", exc_info=True)
            st.error("❌ Erro ao carregar pacientes inativos.")
    
    def _render_todos_ativos(self) -> None:
        """Renderiza mensagem quando todos estão ativos."""
        st.markdown(
            """
            <div class="alert-success" style="margin: 0.5rem 0;">
                ✅ Todos os pacientes estão ativos
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_inativos_list(self, inativos: List[Dict]) -> None:
        """Renderiza lista de pacientes inativos."""
        st.markdown("##### 📵 Risco de Abandono")
        
        for paciente in inativos:
            self._render_inativo_item(paciente)
    
    def _render_inativo_item(self, paciente: Dict) -> None:
        """Renderiza item de paciente inativo com tratamento de erros."""
        try:
            if not isinstance(paciente, dict):
                return
            
            nome = paciente.get("nome_completo", DEFAULT_NOME)
            risco = self._parse_float(paciente.get("risco_abandono", 0))
            dias = self._parse_int(paciente.get("dias_sem_acesso", 0))
            
            cor = self._get_cor_risco(risco)
            
            self._render_card_inativo(nome, risco, dias, cor)
        except Exception as e:
            logger.error(f"Erro ao renderizar inativo item: {e}", exc_info=True)
    
    def _get_cor_risco(self, risco: float) -> str:
        """Retorna cor baseada no risco."""
        return "error" if risco >= RISCO_ABANDONO_ALERTA else "warning"
    
    def _render_card_inativo(
        self,
        nome: str,
        risco: float,
        dias: int,
        cor: str,
    ) -> None:
        """Renderiza card de paciente inativo."""
        st.markdown(
            f"""
            <div class="metric-card fade-in" style="margin-bottom: 0.5rem;">
                <div style="display: flex; justify-content: space-between;
                    align-items: center;">
                    <div style="flex: 1;">
                        <div style="font-weight: 600; color: var(--text); font-size: 0.92rem;">
                            {nome}
                        </div>
                        <div style="font-size: 0.80rem; color: var(--text-muted); margin-top: 0.2rem;">
                            Sem acesso há {dias} dias
                        </div>
                    </div>
                    <span class="xp-badge" style="
                        background: var(--{cor}-bg);
                        color: var(--{cor});
                        border-color: transparent;
                        font-size: 0.78rem;">
                        Risco: {risco:.0f}%
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_sem_checkin_list(self, sem_checkin: List[Dict]) -> None:
        """Renderiza lista de pacientes sem check-in."""
        st.markdown("##### 🔕 Sem Check-in Recente")
        
        for paciente in sem_checkin:
            self._render_sem_checkin_item(paciente)
    
    def _render_sem_checkin_item(self, paciente: Dict) -> None:
        """Renderiza item de paciente sem check-in."""
        try:
            if not isinstance(paciente, dict):
                return
            
            nome = paciente.get("nome_completo", DEFAULT_NOME)
            dias = self._parse_int(paciente.get("dias_sem_checkin", 0))
            
            st.markdown(
                f"""
                <div style="font-size: 0.90rem; padding: 0.6rem 0;
                    border-bottom: 1px solid var(--border);">
                    <b>{nome}</b> — {dias} dia(s) sem check-in
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar sem check-in item: {e}", exc_info=True)
    
    @st.cache_data(ttl=60)
    def _query(_self, tabela: str, colunas: str, filtro_pro: bool = False) -> List[Dict]:
        """Executa query no Supabase com cache e tratamento de erros."""
        if not _self._is_real_db():
            return []
        
        try:
            q = _self.db.client.table(tabela).select(colunas)
            
            if filtro_pro and tabela == "perfis":
                pro_email = _self._get_pro_email()
                if pro_email:
                    q = q.eq("profissional_id", pro_email)
            
            result = q.limit(MAX_RESULTADOS_QUERY).execute()
            data = result.data or []
            
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Erro ao executar query em '{tabela}': {e}", exc_info=True)
            return []
    
    def _is_real_db(self) -> bool:
        """Verifica se o banco é real (não mock)."""
        try:
            return (
                hasattr(self.db, "is_real") and
                self.db.is_real and
                hasattr(self.db, "client")
            )
        except Exception as e:
            logger.debug(f"Erro ao verificar banco real: {e}")
            return False
    
    def _get_pro_email(self) -> str:
        """Obtém email do profissional."""
        try:
            pro = st.session_state.get("professional")
            
            if not pro:
                return ""
            
            if hasattr(pro, "email"):
                return pro.email or ""
            
            if isinstance(pro, dict):
                return pro.get("email", "")
            
            return ""
        except Exception as e:
            logger.error(f"Erro ao obter email do profissional: {e}", exc_info=True)
            return ""
    
    def _parse_int(self, value: Any) -> int:
        """Converte valor para int de forma segura."""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    def _parse_float(self, value: Any) -> float:
        """Converte valor para float de forma segura."""
        try:
            return float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0


# Funções de compatibilidade
def _tab_alertas(db) -> None:
    """Renderiza tab de alertas (compatibilidade)."""
    try:
        renderer = DashboardTabsRenderer(db)
        renderer.render_alertas()
    except Exception as e:
        logger.error(f"Erro ao renderizar tab alertas: {e}", exc_info=True)
        st.error("❌ Erro ao carregar alertas.")


def _tab_inativos(db) -> None:
    """Renderiza tab de inativos (compatibilidade)."""
    try:
        renderer = DashboardTabsRenderer(db)
        renderer.render_inativos()
    except Exception as e:
        logger.error(f"Erro ao renderizar tab inativos: {e}", exc_info=True)
        st.error("❌ Erro ao carregar pacientes inativos.")


def _query(db, tabela: str, colunas: str, filtro_pro: bool = False) -> List[Dict]:
    """Executa query (compatibilidade)."""
    try:
        renderer = DashboardTabsRenderer(db)
        return renderer._query(tabela, colunas, filtro_pro)
    except Exception as e:
        logger.error(f"Erro ao executar query: {e}", exc_info=True)
        return []


def _pro_email() -> str:
    """Obtém email do profissional (compatibilidade)."""
    try:
        pro = st.session_state.get("professional")
        
        if not pro:
            return ""
        
        if hasattr(pro, "email"):
            return pro.email or ""
        
        if isinstance(pro, dict):
            return pro.get("email", "")
        
        return ""
    except Exception as e:
        logger.error(f"Erro ao obter email do profissional: {e}", exc_info=True)
        return ""
