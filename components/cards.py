"""
Melshape — Componentes visuais reutilizáveis.
REGRA: zero cores hardcoded. Tudo via var(--css).
REGRA: usar st.toast() para feedback rápido, não st.success().
"""
import streamlit as st
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
import logging

logger = logging.getLogger("Melshape.Cards")


# ── CONSTANTES ─────────────────────────────────────────────────────────────────
# Cores válidas para componentes
ALERT_KINDS = {"warning", "error", "success", "info"}
PILL_COLORS = {"primary", "success", "warning", "error", "info"}
CARD_COLORS = {"success", "warning", "error", "info", ""}

# Valores padrão
DEFAULT_ICON = "📊"
DEFAULT_ALERT_KIND = "warning"
DEFAULT_PILL_COLOR = "primary"
DEFAULT_DIVIDER_THICKNESS = "1px"
DEFAULT_DIVIDER_MARGIN = "1rem 0"

# Limites
MAX_DROPS = 8
MIN_DROPS = 1
DROPS_DIVISOR = 13

# Estilos padrão
DEFAULT_CARD_STYLES = {
    "background": "var(--surface)",
    "border": "var(--border)",
    "radius": "var(--radius-md)",
    "padding": "0.75rem 1rem",
    "margin": "0.4rem 0",
}


@dataclass
class CardStyles:
    """Estilos configuráveis para cards."""
    background: str = DEFAULT_CARD_STYLES["background"]
    border: str = DEFAULT_CARD_STYLES["border"]
    radius: str = DEFAULT_CARD_STYLES["radius"]
    padding: str = DEFAULT_CARD_STYLES["padding"]
    margin: str = DEFAULT_CARD_STYLES["margin"]


class CardRenderer:
    """Renderer dedicado para componentes visuais."""
    
    @staticmethod
    def metric_card(value: str, label: str, icon: str = DEFAULT_ICON,
                    color: str = "", use_container_width: bool = True) -> None:
        """
        Renderiza um card de métrica.
        
        Args:
            value: Valor a ser exibido
            label: Rótulo da métrica
            icon: Ícone (emoji)
            color: Cor CSS opcional (success, warning, error, info)
            use_container_width: Se deve ocupar toda largura
        """
        try:
            # Valida cor
            color_valido = color if color in CARD_COLORS else ""
            css = f"metric-value {color_valido}".strip()
            
            st.markdown(
                f"""
                <div class="metric-card fade-in">
                    <div class="{css}">{value}</div>
                    <div class="metric-label">{icon} {label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar metric_card: {e}", exc_info=True)
    
    @staticmethod
    def progress_bar(current: float, maximum: float,
                     label_left: str = "", label_right: str = "",
                     color: str = "", show_percentage: bool = True) -> None:
        """
        Renderiza uma barra de progresso.
        
        Args:
            current: Valor atual
            maximum: Valor máximo
            label_left: Texto à esquerda
            label_right: Texto à direita
            color: Cor CSS (danger, warning, success)
            show_percentage: Se deve mostrar porcentagem
        """
        try:
            # Proteção contra divisão por zero
            pct = CardRenderer._calcular_percentual(current, maximum)
            
            # Cor automática se não especificada
            if not color:
                color = "danger" if pct >= 100 else "warning" if pct >= 85 else ""
            
            st.markdown(
                f"""
                <div class="progress-wrap">
                    <div class="progress-track">
                        <div class="progress-fill {color}" style="width:{pct}%"></div>
                    </div>
                    <div class="progress-meta">
                        <span>{label_left}</span>
                        <span>{pct}%</span>
                        <span>{label_right}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar progress_bar: {e}", exc_info=True)
    
    @staticmethod
    def _calcular_percentual(current: float, maximum: float) -> int:
        """Calcula percentual com proteção contra divisão por zero."""
        try:
            if maximum <= 0:
                return 0
            
            pct = int(current / maximum * 100)
            return max(0, min(100, pct))  # Garante entre 0 e 100
        except (ValueError, TypeError) as e:
            logger.debug(f"Erro ao calcular percentual: {e}")
            return 0
    
    @staticmethod
    def empty_state(icon: str, message: str, hint: str = "") -> None:
        """Renderiza estado vazio."""
        try:
            hint_html = f'<p class="empty-hint">{hint}</p>' if hint else ""
            
            st.markdown(
                f"""
                <div class="empty-state fade-in">
                    <div class="empty-icon">{icon}</div>
                    <p class="empty-msg">{message}</p>
                    {hint_html}
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar empty_state: {e}", exc_info=True)
    
    @staticmethod
    def achievement_card(title: str, date_str: str = "", xp: Optional[int] = None) -> None:
        """Renderiza card de conquista."""
        try:
            date_html = (
                f'<div style="font-size:0.72rem;color:var(--text-muted);'
                f'margin-top:0.2rem;">{date_str}</div>'
                if date_str else ""
            )
            
            xp_html = ""
            if xp is not None and xp > 0:
                xp_html = f'<span class="xp-badge" style="font-size:0.72rem;">+{xp} XP</span>'
            
            st.markdown(
                f"""
                <div class="achievement-card">
                    <div style="display:flex;align-items:center;gap:0.6rem;">
                        <div class="medal">🏅</div>
                        <div>
                            <div class="title">{title}</div>
                            {date_html}
                        </div>
                    </div>
                    {xp_html}
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar achievement_card: {e}", exc_info=True)
    
    @staticmethod
    def challenge_card(emoji: str, title: str, xp: int, 
                        progress: Optional[int] = None) -> None:
        """Renderiza card de desafio."""
        try:
            progress_html = ""
            if progress is not None and 0 <= progress <= 100:
                progress_html = (
                    f'<div class="progress-track" style="width:60px;height:4px;">'
                    f'<div class="progress-fill" style="width:{progress}%;"></div>'
                    f'</div>'
                )
            
            st.markdown(
                f"""
                <div class="challenge-card">
                    <span class="challenge-title">{emoji} {title}</span>
                    <div style="display:flex;align-items:center;gap:0.5rem;">
                        {progress_html}
                        <span class="xp-badge">+{xp} XP</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar challenge_card: {e}", exc_info=True)
    
    @staticmethod
    def meal_item(time: str, food: str, calories: int, 
                  score: int = 0, protein: Optional[float] = None) -> None:
        """Renderiza item de refeição."""
        try:
            score_html = ""
            if score and score > 0:
                score_html = f'<div class="meal-score">Score: {score}/100</div>'
            
            protein_html = ""
            if protein is not None and protein > 0:
                protein_html = (
                    f'<span style="font-size:0.70rem;color:var(--text-muted);'
                    f'margin-left:0.5rem;">🥩 {protein:.0f}g</span>'
                )
            
            st.markdown(
                f"""
                <div class="meal-item">
                    <div>
                        <div class="meal-name">{food}</div>
                        <div class="meal-time">⏰ {time}{protein_html}</div>
                        {score_html}
                    </div>
                    <div class="meal-cal">{calories} kcal</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar meal_item: {e}", exc_info=True)
    
    @staticmethod
    def alert(message: str, kind: str = DEFAULT_ALERT_KIND) -> None:
        """
        Renderiza um alerta.
        
        Args:
            message: Mensagem do alerta
            kind: Tipo (warning, error, success, info)
        """
        try:
            # Valida kind
            kind_valido = kind if kind in ALERT_KINDS else DEFAULT_ALERT_KIND
            
            st.markdown(
                f'<div class="alert-{kind_valido}">{message}</div>',
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar alert: {e}", exc_info=True)
    
    @staticmethod
    def section_header(title: str, subtitle: str = "", 
                        icon: Optional[str] = None) -> None:
        """Renderiza cabeçalho de seção."""
        try:
            icon_html = f'{icon} ' if icon else ""
            sub_html = (
                f'<p style="color:var(--text-muted);font-size:0.86rem;'
                f'margin:0.18rem 0 0;">{subtitle}</p>'
                if subtitle else ""
            )
            
            st.markdown(
                f"""
                <div style="margin-bottom:1.1rem;">
                    <h2 style="font-family:var(--font-display);font-weight:700;
                        color:var(--text);margin:0;">{icon_html}{title}</h2>
                    {sub_html}
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar section_header: {e}", exc_info=True)
    
    @staticmethod
    def feature_card(icon: str, title: str, description: str) -> None:
        """Renderiza card de feature."""
        try:
            st.markdown(
                f"""
                <div class="feature-card">
                    <span class="icon">{icon}</span>
                    <h3>{title}</h3>
                    <p>{description}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar feature_card: {e}", exc_info=True)
    
    @staticmethod
    def mode_badge(health_mode: str, label: str) -> None:
        """Renderiza badge do modo de saúde."""
        try:
            st.markdown(
                f'<span class="mode-badge mode-{health_mode}">{label}</span>',
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar mode_badge: {e}", exc_info=True)
    
    @staticmethod
    def motivational_quote(text: str, author: Optional[str] = None) -> None:
        """Renderiza citação motivacional."""
        try:
            author_html = ""
            if author:
                author_html = (
                    f'<span style="font-size:0.72rem;color:var(--text-muted);'
                    f'margin-top:0.2rem;display:block;">— {author}</span>'
                )
            
            st.markdown(
                f"""
                <div class="quote-card fade-in-fast">
                    <div style="font-size:1.2rem;margin-bottom:0.2rem;">💬</div>
                    <div>{text}</div>
                    {author_html}
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar motivational_quote: {e}", exc_info=True)
    
    @staticmethod
    def medical_disclaimer() -> None:
        """Renderiza aviso médico."""
        try:
            import config
            st.markdown(
                f'<div class="medical-disclaimer">{config.MEDICAL_DISCLAIMER}</div>',
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar medical_disclaimer: {e}", exc_info=True)
    
    @staticmethod
    def hydration_bar(current_ml: int, goal_ml: int) -> None:
        """Renderiza barra de hidratação."""
        try:
            # Proteção contra divisão por zero
            pct = CardRenderer._calcular_percentual(current_ml, goal_ml)
            
            # Calcula número de gotas
            drops_count = min(MAX_DROPS, max(MIN_DROPS, pct // DROPS_DIVISOR))
            drops = "💧" * drops_count
            
            st.markdown(
                f"""
                <div class="hydration-bar">
                    <span class="hydration-drops">{drops}</span>
                    <span class="hydration-text">
                        {current_ml} ml / {goal_ml} ml ({pct}%)
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar hydration_bar: {e}", exc_info=True)
    
    @staticmethod
    def show_new_achievements(unlocked: List[str]) -> None:
        """
        Exibe conquistas novas via st.toast().
        Não usar st.success() conforme regra.
        """
        try:
            if not unlocked or not isinstance(unlocked, list):
                return
            
            for title in unlocked:
                if title and isinstance(title, str):
                    st.toast(f"🏆 {title}", icon="🎉")
        except Exception as e:
            logger.error(f"Erro ao exibir conquistas: {e}", exc_info=True)
    
    @staticmethod
    def fab_button(label: str = "+", action: Optional[Callable] = None) -> None:
        """Renderiza botão flutuante para ação rápida."""
        try:
            # Nota: O FAB é renderizado via CSS, mas o clique é tratado separadamente
            st.markdown(
                f'<div class="fab">{label}</div>',
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar fab_button: {e}", exc_info=True)
    
    @staticmethod
    def xp_toast(amount: int, motivo: str = "") -> None:
        """Toast de XP ganho."""
        try:
            if amount <= 0:
                return
            
            msg = f"⭐ +{amount} XP"
            if motivo:
                msg += f" — {motivo}"
            
            st.toast(msg, icon="⭐")
        except Exception as e:
            logger.error(f"Erro ao exibir xp_toast: {e}", exc_info=True)
    
    @staticmethod
    def divider(thickness: str = DEFAULT_DIVIDER_THICKNESS, 
                margin: str = DEFAULT_DIVIDER_MARGIN) -> None:
        """Renderiza divisor visual."""
        try:
            st.markdown(
                f"""
                <div style="border-top:{thickness} solid var(--border);
                    margin:{margin};">
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar divider: {e}", exc_info=True)
    
    @staticmethod
    def pill_badge(text: str, color: str = DEFAULT_PILL_COLOR) -> None:
        """Renderiza badge em formato de pílula."""
        try:
            # Valida cor
            color_valido = color if color in PILL_COLORS else DEFAULT_PILL_COLOR
            
            st.markdown(
                f"""
                <span style="background:var(--{color_valido}-light);
                    color:var(--{color_valido});
                    padding:0.15rem 0.6rem;
                    border-radius:9999px;
                    font-size:0.72rem;
                    font-weight:600;
                    border:1px solid var(--{color_valido}-border);
                    display:inline-block;">
                    {text}
                </span>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar pill_badge: {e}", exc_info=True)
    
    @staticmethod
    def info_box(message: str, icon: str = "💡") -> None:
        """Renderiza caixa de informação."""
        try:
            st.markdown(
                f"""
                <div style="background:var(--surface-2);
                    border-radius:var(--radius-md);
                    padding:0.75rem 1rem;
                    border:1px solid var(--border);
                    display:flex;
                    align-items:flex-start;
                    gap:0.6rem;
                    margin:0.4rem 0;">
                    <span style="font-size:1.2rem;flex-shrink:0;">{icon}</span>
                    <span style="font-size:0.85rem;color:var(--text-muted);">
                        {message}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar info_box: {e}", exc_info=True)


# Funções de compatibilidade (mantendo a interface original)
def metric_card(value: str, label: str, icon: str = DEFAULT_ICON,
                color: str = "") -> None:
    CardRenderer.metric_card(value, label, icon, color)


def progress_bar(current: float, maximum: float,
                 label_left: str = "", label_right: str = "",
                 color: str = "") -> None:
    CardRenderer.progress_bar(current, maximum, label_left, label_right, color)


def empty_state(icon: str, message: str, hint: str = "") -> None:
    CardRenderer.empty_state(icon, message, hint)


def achievement_card(title: str, date_str: str = "", xp: Optional[int] = None) -> None:
    CardRenderer.achievement_card(title, date_str, xp)


def challenge_card(emoji: str, title: str, xp: int, 
                   progress: Optional[int] = None) -> None:
    CardRenderer.challenge_card(emoji, title, xp, progress)


def meal_item(time: str, food: str, calories: int, score: int = 0,
              protein: Optional[float] = None) -> None:
    CardRenderer.meal_item(time, food, calories, score, protein)


def alert(message: str, kind: str = DEFAULT_ALERT_KIND) -> None:
    CardRenderer.alert(message, kind)


def section_header(title: str, subtitle: str = "", 
                   icon: Optional[str] = None) -> None:
    CardRenderer.section_header(title, subtitle, icon)


def feature_card(icon: str, title: str, description: str) -> None:
    CardRenderer.feature_card(icon, title, description)


def mode_badge(health_mode: str, label: str) -> None:
    CardRenderer.mode_badge(health_mode, label)


def motivational_quote(text: str, author: Optional[str] = None) -> None:
    CardRenderer.motivational_quote(text, author)


def medical_disclaimer() -> None:
    CardRenderer.medical_disclaimer()


def hydration_bar(current_ml: int, goal_ml: int) -> None:
    CardRenderer.hydration_bar(current_ml, goal_ml)


def show_new_achievements(unlocked: List[str]) -> None:
    CardRenderer.show_new_achievements(unlocked)


def fab_button(label: str = "+", action: Optional[Callable] = None) -> None:
    CardRenderer.fab_button(label, action)


def xp_toast(amount: int, motivo: str = "") -> None:
    CardRenderer.xp_toast(amount, motivo)


def divider(thickness: str = DEFAULT_DIVIDER_THICKNESS, 
            margin: str = DEFAULT_DIVIDER_MARGIN) -> None:
    CardRenderer.divider(thickness, margin)


def pill_badge(text: str, color: str = DEFAULT_PILL_COLOR) -> None:
    CardRenderer.pill_badge(text, color)


def info_box(message: str, icon: str = "💡") -> None:
    CardRenderer.info_box(message, icon)
