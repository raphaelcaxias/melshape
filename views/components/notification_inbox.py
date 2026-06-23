"""
Melshape — Inbox de Notificações In-App.

Exibido no topo da home após login.
Também usado no dashboard profissional para ver pacientes em risco.
"""
import streamlit as st
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

from services.notification_service import NotificationService

logger = logging.getLogger("Melshape.NotificationInbox")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Limites
MAX_NOTIFICACOES_EXIBIR = 8
DIAS_HISTORICO_NOTIFICACOES = 7
MAX_NOTIFICACOES_PENDENTES = 5

# Fallbacks
DEFAULT_ICON = "💬"
DEFAULT_KIND = "info"
DEFAULT_LABEL = "Notificação"
DEFAULT_MOTIVO_LABEL = "Acompanhamento"


@dataclass
class NotificationType:
    """Configuração de um tipo de notificação."""
    icon: str = DEFAULT_ICON
    kind: str = DEFAULT_KIND
    label: str = DEFAULT_LABEL


# Mapeamento de tipos de notificação
TIPO_CONFIG = {
    "streak_risco": NotificationType("🔥", "warning", "Streak em risco"),
    "meta_proxima": NotificationType("🎯", "info", "Meta próxima"),
    "habito_pendente": NotificationType("📋", "info", "Hábito pendente"),
    "jornada_avanco": NotificationType("🗺️", "success", "Jornada avançou"),
    "risco_abandono": NotificationType("😔", "error", "Risco de abandono"),
    "sem_checkin": NotificationType("⚡", "warning", "Sem check-in"),
    "engajamento": NotificationType("✅", "success", "Engajamento"),
}

# Mapeamento de motivo para pacientes em risco
MOTIVO_CONFIG = {
    "RISCO_ABANDONO": NotificationType("🚨", "error", "Risco de abandono"),
    "SEM_CHECKIN": NotificationType("⚡", "warning", "Sem check-in"),
    "ACOMPANHAMENTO": NotificationType("📋", "info", "Acompanhamento"),
}

# Mapeamento de kind para CSS
KIND_CSS = {
    "warning": "color: var(--warning);",
    "error": "color: var(--error);",
    "success": "color: var(--success);",
    "info": "color: var(--info);",
}

# Mapeamento de kind para cor
KIND_COR = {
    "error": "var(--error)",
    "warning": "var(--warning)",
    "info": "var(--info)",
    "success": "var(--success)",
}

DEFAULT_COR = "var(--text-muted)"


class NotificationInboxRenderer:
    """Renderer dedicado para inbox de notificações."""
    
    def __init__(self, services: Dict[str, Any]):
        self.services = services or {}
        self.db = services.get("db")
        self.svc = self._init_notification_service()
    
    def _init_notification_service(self) -> Optional[NotificationService]:
        """Inicializa NotificationService com tratamento de erros."""
        if not self.db:
            logger.error("Database não disponível para NotificationInboxRenderer")
            return None
        
        try:
            return NotificationService(self.db)
        except Exception as e:
            logger.error(f"Erro ao inicializar NotificationService: {e}", exc_info=True)
            return None
    
    def exibir_notificacoes(self, user: Dict[str, Any]) -> None:
        """
        Lê fila_notificacoes, exibe via st.toast() e marca como entregues.
        Também verifica risco de abandono em tempo real.
        Chamado na home a cada acesso.
        """
        if not self.svc:
            logger.warning("NotificationService não disponível")
            return
        
        # Verifica risco de abandono
        self._verificar_risco_abandono(user)
        
        # Verifica condições para novas notificações contextuais
        self._notificar_contextos(user)
        
        # Entrega pendentes via toast
        self._entregar_pendentes(user)
    
    def _verificar_risco_abandono(self, user: Dict[str, Any]) -> None:
        """Verifica risco de abandono com tratamento de erros."""
        try:
            self.svc.verificar_risco_abandono(user)
        except Exception as e:
            logger.error(f"Erro ao verificar risco de abandono: {e}", exc_info=True)
    
    def _notificar_contextos(self, user: Dict[str, Any]) -> None:
        """Verifica e notifica contextos com tratamento de erros."""
        metodos = [
            ("streak em risco", self.svc.notificar_streak_em_risco),
            ("meta próxima", self.svc.notificar_meta_proxima),
            ("hábito pendente", self.svc.notificar_habito_pendente),
        ]
        
        for nome, metodo in metodos:
            try:
                metodo(user)
            except Exception as e:
                logger.error(f"Erro ao notificar {nome}: {e}", exc_info=True)
    
    def _entregar_pendentes(self, user: Dict[str, Any]) -> None:
        """Entrega notificações pendentes com tratamento de erros."""
        try:
            pendentes = self.svc.entregar_pendentes(user)
            
            if not isinstance(pendentes, list):
                logger.warning("entregar_pendentes não retornou lista")
                return
            
            for notificacao in pendentes:
                self._exibir_toast(notificacao)
        except Exception as e:
            logger.error(f"Erro ao entregar pendentes: {e}", exc_info=True)
    
    def _exibir_toast(self, notificacao: Dict[str, Any]) -> None:
        """Exibe uma notificação via toast."""
        try:
            if not isinstance(notificacao, dict):
                return
            
            tipo = notificacao.get("tipo", "engajamento")
            config = self._get_tipo_config(tipo)
            mensagem = notificacao.get("mensagem", "")
            
            if mensagem:
                st.toast(mensagem, icon=config.icon)
        except Exception as e:
            logger.error(f"Erro ao exibir toast: {e}", exc_info=True)
    
    def _get_tipo_config(self, tipo: str) -> NotificationType:
        """Obtém configuração do tipo com fallback."""
        try:
            return TIPO_CONFIG.get(tipo, NotificationType())
        except Exception as e:
            logger.debug(f"Erro ao obter config do tipo '{tipo}': {e}")
            return NotificationType()
    
    def render_inbox_panel(self, user: Dict[str, Any]) -> None:
        """
        Painel visual de notificações recentes.
        Para a tela de perfil ou notificações.
        """
        todas = self._get_todas_notificacoes()
        
        if not todas:
            self._render_empty_state()
            return
        
        self._render_header_notificacoes(len(todas))
        
        for notificacao in todas[:MAX_NOTIFICACOES_EXIBIR]:
            self._render_notificacao_item(notificacao)
    
    def _get_todas_notificacoes(self) -> List[Dict]:
        """Obtém todas as notificações (pendentes + histórico)."""
        if not self.db:
            return []
        
        try:
            historico = self._get_historico()
            pendentes = self._get_pendentes()
            return pendentes + historico
        except Exception as e:
            logger.error(f"Erro ao obter notificações: {e}", exc_info=True)
            return []
    
    @st.cache_data(ttl=60)
    def _get_historico(_self) -> List[Dict]:
        """Obtém histórico de notificações (com cache)."""
        if not _self.db:
            return []
        
        try:
            historico = _self.db.get_historico_notificacoes(days=DIAS_HISTORICO_NOTIFICACOES)
            return historico if isinstance(historico, list) else []
        except Exception as e:
            logger.error(f"Erro ao obter histórico: {e}", exc_info=True)
            return []
    
    @st.cache_data(ttl=30)
    def _get_pendentes(_self) -> List[Dict]:
        """Obtém notificações pendentes (com cache)."""
        if not _self.db:
            return []
        
        try:
            pendentes = _self.db.get_notificacoes_pendentes(limit=MAX_NOTIFICACOES_PENDENTES)
            return pendentes if isinstance(pendentes, list) else []
        except Exception as e:
            logger.error(f"Erro ao obter pendentes: {e}", exc_info=True)
            return []
    
    def _render_empty_state(self) -> None:
        """Renderiza estado vazio de notificações."""
        st.markdown(
            """
            <div style="font-size: 0.86rem; color: var(--text-muted); margin: 0.5rem 0;">
                📭 Nenhuma notificação recente.
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_header_notificacoes(self, total: int) -> None:
        """Renderiza cabeçalho de notificações."""
        st.markdown(
            f"""
            <div style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.7rem;">
                <b>{total}</b> notificação(ões) recentes
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_notificacao_item(self, notificacao: Dict[str, Any]) -> None:
        """Renderiza um item de notificação com tratamento de erros."""
        try:
            if not isinstance(notificacao, dict):
                return
            
            tipo = notificacao.get("tipo", "engajamento")
            config = self._get_tipo_config(tipo)
            
            kind_css = self._get_kind_css(config.kind)
            mensagem = notificacao.get("mensagem", "")
            data = self._formatar_data(notificacao.get("criado_em"))
            
            st.markdown(
                f"""
                <div style="display: flex; gap: 0.7rem; align-items: flex-start;
                    padding: 0.6rem 0; border-bottom: 1px solid var(--border-subtle);">
                    <span style="font-size: 1.2rem; flex-shrink: 0;">{config.icon}</span>
                    <div style="flex: 1;">
                        <div style="font-size: 0.86rem; color: var(--text); {kind_css}">
                            {mensagem}
                        </div>
                        <div style="font-size: 0.74rem; color: var(--text-faint); margin-top: 0.15rem;">
                            {data}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar notificação: {e}", exc_info=True)
    
    def _get_kind_css(self, kind: str) -> str:
        """Obtém CSS do kind com fallback."""
        try:
            return KIND_CSS.get(kind, "")
        except Exception as e:
            logger.debug(f"Erro ao obter CSS do kind '{kind}': {e}")
            return ""
    
    def _formatar_data(self, data_raw: Any) -> str:
        """Formata data de forma segura."""
        try:
            if not data_raw:
                return ""
            return str(data_raw)[:10]
        except Exception as e:
            logger.debug(f"Erro ao formatar data: {e}")
            return ""
    
    def render_pacientes_risco_pro(self) -> None:
        """
        Painel de pacientes em risco para o profissional.
        Usa vw_pacientes_para_notificar.
        """
        pacientes = self._get_pacientes_risco()
        
        if not pacientes:
            self._render_sem_pacientes_risco()
            return
        
        self._render_header_pacientes_risco(len(pacientes))
        
        for paciente in pacientes:
            self._render_paciente_risco_item(paciente)
    
    def _get_pacientes_risco(self) -> List[Dict]:
        """Obtém pacientes em risco com tratamento de erros."""
        if not self.svc:
            return []
        
        try:
            pacientes = self.svc.pacientes_para_notificar()
            return pacientes if isinstance(pacientes, list) else []
        except Exception as e:
            logger.error(f"Erro ao obter pacientes em risco: {e}", exc_info=True)
            return []
    
    def _render_sem_pacientes_risco(self) -> None:
        """Renderiza mensagem quando não há pacientes em risco."""
        st.markdown(
            """
            <div style="font-size: 0.86rem; color: var(--success); margin: 0.5rem 0;">
                ✅ Nenhum paciente em risco de abandono no momento.
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_header_pacientes_risco(self, total: int) -> None:
        """Renderiza cabeçalho de pacientes em risco."""
        st.markdown(
            f"""
            <div style="font-size: 0.84rem; color: var(--text-muted); margin-bottom: 0.7rem;">
                ⚠️ <b>{total}</b> paciente(s) precisam de atenção
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    def _render_paciente_risco_item(self, paciente: Dict[str, Any]) -> None:
        """Renderiza um item de paciente em risco com tratamento de erros."""
        try:
            if not isinstance(paciente, dict):
                return
            
            nome = paciente.get("nome_completo", "—")
            motivo = paciente.get("motivo", "ACOMPANHAMENTO")
            dias_sem_checkin = self._parse_int(paciente.get("dias_sem_checkin", 0))
            dias_sem_acesso = self._parse_int(paciente.get("dias_sem_acesso", 0))
            
            config = self._get_motivo_config(motivo)
            cor = self._get_cor_kind(config.kind)
            
            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between;
                    align-items: center; padding: 0.65rem 0.9rem;
                    border: 1px solid var(--border); border-radius: 12px;
                    margin-bottom: 0.5rem; background: var(--surface);">
                    <div>
                        <div style="font-weight: 600; font-size: 0.92rem;
                            color: var(--text);">
                            {config.icon} {nome}
                        </div>
                        <div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 0.15rem;">
                            {dias_sem_checkin}d sem check-in · {dias_sem_acesso}d sem acesso
                        </div>
                    </div>
                    <span style="font-size: 0.78rem; font-weight: 700;
                        color: {cor};">{config.label}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar paciente em risco: {e}", exc_info=True)
    
    def _get_motivo_config(self, motivo: str) -> NotificationType:
        """Obtém configuração do motivo com fallback."""
        try:
            config = MOTIVO_CONFIG.get(motivo)
            if config:
                return config
            
            # Fallback: cria config genérico
            return NotificationType("📋", "info", motivo or DEFAULT_MOTIVO_LABEL)
        except Exception as e:
            logger.debug(f"Erro ao obter config do motivo '{motivo}': {e}")
            return NotificationType()
    
    def _get_cor_kind(self, kind: str) -> str:
        """Obtém cor baseada no kind."""
        try:
            return KIND_COR.get(kind, DEFAULT_COR)
        except Exception as e:
            logger.debug(f"Erro ao obter cor do kind '{kind}': {e}")
            return DEFAULT_COR
    
    def _parse_int(self, value: Any) -> int:
        """Converte valor para int de forma segura."""
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0


# Funções de compatibilidade (mantendo a interface original)
def exibir_notificacoes(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Exibe notificações (compatibilidade)."""
    try:
        renderer = NotificationInboxRenderer(services)
        renderer.exibir_notificacoes(user)
    except Exception as e:
        logger.error(f"Erro ao exibir notificações: {e}", exc_info=True)


def render_inbox_panel(services: Dict[str, Any], user: Dict[str, Any]) -> None:
    """Renderiza painel de notificações (compatibilidade)."""
    try:
        renderer = NotificationInboxRenderer(services)
        renderer.render_inbox_panel(user)
    except Exception as e:
        logger.error(f"Erro ao renderizar inbox panel: {e}", exc_info=True)


def render_pacientes_risco_pro(services: Dict[str, Any]) -> None:
    """Renderiza pacientes em risco (compatibilidade)."""
    try:
        renderer = NotificationInboxRenderer(services)
        renderer.render_pacientes_risco_pro()
    except Exception as e:
        logger.error(f"Erro ao renderizar pacientes em risco: {e}", exc_info=True)


# Mantido para compatibilidade com código existente
_KIND_CSS = KIND_CSS
_TIPO_ICON = {k: v.icon for k, v in TIPO_CONFIG.items()}
_TIPO_KIND = {k: v.kind for k, v in TIPO_CONFIG.items()}
