"""
Melshape — Convite de Paciente pelo Profissional.

O profissional gera um link único com token de 7 dias.
O paciente abre o link, cria a conta (ou faz login) e é
vinculado automaticamente ao profissional.

Fluxo:
  1. Pro clica "Gerar link de convite"
  2. Sistema cria token na tabela convites_profissionais
  3. Pro copia link e envia via WhatsApp/email
  4. Paciente abre link → ?convite=<token>
  5. auth/register.py detecta o token e chama link_patient()
     após criar a conta
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import string
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import streamlit as st

import config
from views.components.cards import alert, empty_state, section_header

logger = logging.getLogger("Melshape.PatientInvite")

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────
TOKEN_BYTES = 32
TOKEN_TTL_DAYS = 7
MAX_PENDING_INVITES = 20
TABELA = "convites_profissionais"


# ─────────────────────────────────────────────────────────────────────────────
# MODELO
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Convite:
    id: str
    pro_email: str
    token: str
    criado_em: str
    expira_em: str
    usado: bool = False
    paciente_email: str | None = None

    @property
    def link(self) -> str:
        base = config.APP_URL.rstrip("/")
        return f"{base}/?convite={self.token}"

    @property
    def expirado(self) -> bool:
        try:
            exp = datetime.fromisoformat(self.expira_em.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > exp
        except Exception:
            return False

    @property
    def status_label(self) -> str:
        if self.usado:
            return "✅ Aceito"
        if self.expirado:
            return "⏰ Expirado"
        return "⏳ Pendente"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Convite":
        return cls(
            id=d.get("id", ""),
            pro_email=d.get("pro_email", ""),
            token=d.get("token", ""),
            criado_em=d.get("criado_em", ""),
            expira_em=d.get("expira_em", ""),
            usado=bool(d.get("usado", False)),
            paciente_email=d.get("paciente_email"),
        )


# ─────────────────────────────────────────────────────────────────────────────
# SERVIÇO DE CONVITES
# ─────────────────────────────────────────────────────────────────────────────
class InviteService:
    """Gera, lista e consome tokens de convite."""

    def __init__(self, db: Any) -> None:
        self.db = db

    def gerar(self, pro_email: str) -> Convite | None:
        """Cria um novo token de convite para o profissional."""
        if not pro_email:
            return None

        token = secrets.token_urlsafe(TOKEN_BYTES)
        agora = datetime.now(timezone.utc)
        expira = agora + timedelta(days=TOKEN_TTL_DAYS)

        row = {
            "pro_email": pro_email,
            "token": token,
            "criado_em": agora.isoformat(),
            "expira_em": expira.isoformat(),
            "usado": False,
        }

        if self.db.is_real and self.db.client:
            try:
                r = self.db.client.table(TABELA).insert(row).execute()
                if r.data:
                    return Convite.from_dict(r.data[0])
            except Exception as e:
                logger.error(f"gerar convite Supabase: {e}")
                # Tabela pode não existir ainda — retorna convite local
        
        # Fallback: retorna convite sem persistir (funcional para demo)
        row["id"] = hashlib.md5(token.encode()).hexdigest()
        return Convite.from_dict(row)

    def listar(self, pro_email: str) -> list[Convite]:
        """Lista convites do profissional."""
        if not (self.db.is_real and self.db.client):
            return []
        try:
            r = (
                self.db.client.table(TABELA)
                .select("*")
                .eq("pro_email", pro_email)
                .order("criado_em", desc=True)
                .limit(MAX_PENDING_INVITES)
                .execute()
            )
            return [Convite.from_dict(d) for d in (r.data or [])]
        except Exception as e:
            logger.error(f"listar convites: {e}")
            return []

    def consumir(self, token: str, paciente_email: str) -> str | None:
        """
        Valida e consome o token. Retorna o pro_email se ok, None se inválido.
        Chamado por auth/register.py após criar a conta do paciente.
        """
        if not token or not paciente_email:
            return None

        if self.db.is_real and self.db.client:
            try:
                r = (
                    self.db.client.table(TABELA)
                    .select("*")
                    .eq("token", token)
                    .eq("usado", False)
                    .execute()
                )
                if not r.data:
                    return None

                convite = Convite.from_dict(r.data[0])
                if convite.expirado:
                    return None

                # Marca como usado
                self.db.client.table(TABELA).update(
                    {"usado": True, "paciente_email": paciente_email}
                ).eq("token", token).execute()

                return convite.pro_email
            except Exception as e:
                logger.error(f"consumir convite: {e}")

        return None

    @staticmethod
    def token_da_url() -> str | None:
        """Lê ?convite=<token> da URL do Streamlit."""
        try:
            params = st.query_params
            return params.get("convite") or params.get("invite")
        except Exception:
            return None


# ─────────────────────────────────────────────────────────────────────────────
# RENDERER — painel do profissional
# ─────────────────────────────────────────────────────────────────────────────
class PatientInviteRenderer:
    def __init__(self, services: dict[str, Any], professional: Any) -> None:
        self.services = services
        self.db = services.get("db")
        self.pro_svc = services.get("professional")
        self.inv_svc = InviteService(self.db)
        self.pro = professional
        self.pro_email = (
            professional.email
            if hasattr(professional, "email")
            else professional.get("email", "")
        )
        self.pro_name = (
            professional.name
            if hasattr(professional, "name")
            else professional.get("name", "Profissional")
        )

    def render(self) -> None:
        section_header(
            "🔗 Convidar Pacientes",
            "Gere um link e envie via WhatsApp ou e-mail",
        )

        self._render_gerador()
        st.divider()
        self._render_historico()

    def _render_gerador(self) -> None:
        st.markdown("##### ➕ Gerar novo link de convite")
        st.markdown(
            """
            <div style="font-size:0.86rem;color:var(--text-muted);margin-bottom:1rem;">
                O link expira em <b>7 dias</b> e só pode ser usado por
                <b>um paciente</b>. Gere um link por paciente.
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            "🔗 Gerar link de convite",
            type="primary",
            use_container_width=True,
            key="inv_gerar",
        ):
            convite = self.inv_svc.gerar(self.pro_email)
            if convite:
                st.session_state["inv_ultimo"] = convite
                st.cache_data.clear()
            else:
                st.error("❌ Erro ao gerar convite.")

        # Exibe link gerado
        convite: Convite | None = st.session_state.get("inv_ultimo")
        if convite:
            link = convite.link
            expira = convite.expira_em[:10] if convite.expira_em else "—"

            st.markdown(
                f"""
                <div style="background:var(--success-bg);border:1px solid var(--success-border);
                    border-radius:var(--radius-md);padding:1rem 1.1rem;margin-top:0.8rem;">
                    <div style="font-size:0.78rem;color:var(--success);font-weight:700;
                        text-transform:uppercase;letter-spacing:.04em;margin-bottom:.4rem;">
                        ✅ Link gerado — expira em {expira}
                    </div>
                    <div style="font-family:monospace;font-size:0.82rem;
                        color:var(--text);word-break:break-all;line-height:1.5;">
                        {link}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Texto pronto para WhatsApp
            msg_whats = (
                f"Olá! Sou {self.pro_name} e uso o Melshape para acompanhar "
                f"meus pacientes. Clique no link abaixo para criar sua conta "
                f"e começar seu acompanhamento:\n\n{link}\n\n"
                f"_(Link válido por 7 dias)_"
            )

            st.text_area(
                "📱 Mensagem pronta para WhatsApp / e-mail",
                value=msg_whats,
                height=120,
                key="inv_msg",
                help="Selecione tudo e copie (Ctrl+A → Ctrl+C)",
            )

            col1, col2 = st.columns(2)
            with col1:
                # Link direto WhatsApp
                wa_text = msg_whats.replace("\n", "%0A").replace(" ", "%20")
                st.markdown(
                    f'<a href="https://wa.me/?text={wa_text}" target="_blank">'
                    f'<button style="width:100%;padding:.55rem;background:var(--gradient-primary);'
                    f'color:#fff;border:none;border-radius:var(--radius-md);font-weight:700;'
                    f'cursor:pointer;font-size:.9rem;">📱 Abrir no WhatsApp</button></a>',
                    unsafe_allow_html=True,
                )
            with col2:
                if st.button(
                    "🔄 Gerar outro link",
                    use_container_width=True,
                    key="inv_novo",
                ):
                    st.session_state.pop("inv_ultimo", None)
                    st.rerun()

    def _render_historico(self) -> None:
        st.markdown("##### 📋 Convites enviados")

        convites = self.inv_svc.listar(self.pro_email)
        if not convites:
            empty_state(
                "🔗",
                "Nenhum convite enviado ainda",
                "Gere o primeiro link acima.",
            )
            return

        pendentes = [c for c in convites if not c.usado and not c.expirado]
        aceitos = [c for c in convites if c.usado]
        expirados = [c for c in convites if c.expirado and not c.usado]

        st.markdown(
            f"""
            <div style="display:flex;gap:1.5rem;margin-bottom:1rem;font-size:.84rem;color:var(--text-muted);">
                <span>⏳ <b>{len(pendentes)}</b> pendentes</span>
                <span>✅ <b>{len(aceitos)}</b> aceitos</span>
                <span>⏰ <b>{len(expirados)}</b> expirados</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for c in convites[:15]:
            criado = c.criado_em[:10] if c.criado_em else "—"
            paciente = c.paciente_email or "—"
            cor = (
                "var(--success)"
                if c.usado
                else "var(--warning)"
                if c.expirado
                else "var(--text-muted)"
            )

            st.markdown(
                f"""
                <div style="display:flex;justify-content:space-between;align-items:center;
                    padding:.6rem 0;border-bottom:1px solid var(--border-subtle);">
                    <div>
                        <div style="font-size:.86rem;color:var(--text);font-weight:600;">
                            {c.status_label}
                        </div>
                        <div style="font-size:.76rem;color:var(--text-faint);margin-top:.15rem;">
                            Criado: {criado}
                            {"  ·  Paciente: " + paciente if c.usado else ""}
                        </div>
                    </div>
                    <div style="font-size:.76rem;color:{cor};font-weight:600;">
                        {c.status_label}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render(services: dict[str, Any], professional: Any) -> None:
    renderer = PatientInviteRenderer(services, professional)
    renderer.render()
