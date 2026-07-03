"""
Melshape — Serviço de Pagamento (Mercado Pago).

Integração via Checkout Pro (hosted page) — o mais simples e seguro:
  1. Backend cria preferência de pagamento via API do MP
  2. Paciente/profissional é redirecionado para a página do MP
  3. MP chama o webhook de volta quando o pagamento é confirmado
  4. Webhook atualiza o plano do usuário no Supabase

Configuração necessária (.env):
  MP_ACCESS_TOKEN=APP_USR-xxxx   (Produção)
  MP_ACCESS_TOKEN=TEST-xxxx      (Sandbox)
  MP_WEBHOOK_SECRET=xxxx         (validação HMAC do webhook)
  APP_URL=https://seuapp.com     (URL base para retorno)

Sprint 6 — MVP para Validação Real.
Constituição Cap. VIII: pagamento é o bloqueador comercial identificado
na Auditoria Mestra. Sem pagamento, sem negócio.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import config

logger = logging.getLogger("Melshape.PaymentService")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────────────────────────────────────
_MP_API_BASE = "https://api.mercadopago.com"
_MP_CHECKOUT_URL = "https://www.mercadopago.com.br/checkout/v1/redirect"

_PLAN_ITEMS = {
    "pro": {
        "title": "Melshape Pro — Mensal",
        "description": "Acesso completo ao Melshape Pro com acompanhamento profissional",
        "quantity": 1,
        "currency_id": "BRL",
    },
    "clinic": {
        "title": "Melshape Clínica — Mensal",
        "description": "Plano para clínicas com múltiplos profissionais",
        "quantity": 1,
        "currency_id": "BRL",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class CheckoutResult:
    """Resultado da criação de preferência de checkout."""
    ok: bool
    checkout_url: str = ""
    preference_id: str = ""
    error: str = ""


@dataclass
class WebhookEvent:
    """Evento de webhook do Mercado Pago."""
    event_type: str        # payment, subscription, etc.
    resource_id: str       # ID do pagamento ou assinatura
    action: str            # payment.created, payment.updated, etc.
    raw: dict = field(default_factory=dict)


@dataclass
class PaymentInfo:
    """Dados de um pagamento processado."""
    payment_id: str
    status: str            # approved, pending, rejected, cancelled
    email: str
    plan: str
    amount: float
    approved_at: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# SERVIÇO PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────
class PaymentService:
    """
    Integração com Mercado Pago.

    Fluxo:
      1. create_checkout_url() → URL para redirecionar o usuário
      2. Usuário paga no MP
      3. MP chama POST /webhook → process_webhook()
      4. process_webhook() → validate_webhook() + update_user_plan()
    """

    def __init__(self, db: Any) -> None:
        self.db = db
        self._access_token = os.getenv("MP_ACCESS_TOKEN", "")
        self._webhook_secret = os.getenv("MP_WEBHOOK_SECRET", "")
        self._app_url = getattr(config, "APP_URL", "").rstrip("/")

    @property
    def is_configured(self) -> bool:
        """Verifica se o Mercado Pago está configurado."""
        return bool(self._access_token and not self._access_token.startswith("sua_"))

    # ── Checkout ──────────────────────────────────────────────────────────────

    def create_checkout_url(
        self,
        user_email: str,
        user_name: str,
        plan: str = "pro",
    ) -> CheckoutResult:
        """
        Cria uma preferência de pagamento no Mercado Pago e retorna a URL
        de checkout para redirecionar o usuário.

        Args:
            user_email: Email do usuário (identificação pós-pagamento).
            user_name: Nome do usuário (exibido na página do MP).
            plan: "pro" ou "clinic".

        Returns:
            CheckoutResult com ok=True e checkout_url, ou ok=False e error.
        """
        if not self.is_configured:
            return CheckoutResult(
                ok=False,
                error="MP_ACCESS_TOKEN não configurado. Adicione ao .env e reinicie.",
            )

        plan_item = _PLAN_ITEMS.get(plan)
        if not plan_item:
            return CheckoutResult(ok=False, error=f"Plano '{plan}' inválido.")

        price = config.PRO_PRICE if plan == "pro" else config.CLINIC_PRICE

        payload = {
            "items": [{
                **plan_item,
                "unit_price": float(price),
            }],
            "payer": {
                "email": user_email,
                "name": user_name,
            },
            "external_reference": f"{plan}|{user_email}",
            "back_urls": {
                "success": f"{self._app_url}/?payment=success&plan={plan}",
                "failure": f"{self._app_url}/?payment=failure",
                "pending": f"{self._app_url}/?payment=pending",
            },
            "auto_return": "approved",
            "notification_url": f"{self._app_url}/webhook/mercadopago",
            "statement_descriptor": "MELSHAPE",
            "expires": False,
        }

        try:
            import urllib.request, json
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{_MP_API_BASE}/checkout/preferences",
                data=data,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                    "X-Idempotency-Key": f"melshape-{user_email}-{plan}-{datetime.now().strftime('%Y%m%d%H%M')}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())

            pref_id = result.get("id", "")
            init_point = result.get("init_point", "")  # URL de produção
            sandbox_point = result.get("sandbox_init_point", "")

            # Usa sandbox se token for de teste
            url = sandbox_point if self._access_token.startswith("TEST-") else init_point

            if not url:
                return CheckoutResult(ok=False, error="MP não retornou URL de checkout.")

            logger.info(f"✅ Checkout criado para {user_email} plano={plan} pref={pref_id}")
            return CheckoutResult(ok=True, checkout_url=url, preference_id=pref_id)

        except Exception as e:
            logger.error(f"create_checkout_url: {e}")
            return CheckoutResult(ok=False, error=str(e))

    # ── Webhook ───────────────────────────────────────────────────────────────

    def validate_webhook(self, payload: str, signature: str) -> bool:
        """
        Valida a assinatura HMAC-SHA256 do webhook do Mercado Pago.

        Args:
            payload: Corpo da requisição (string JSON raw).
            signature: Header 'x-signature' enviado pelo MP.

        Returns:
            True se a assinatura for válida, False caso contrário.
        """
        if not self._webhook_secret:
            logger.warning("MP_WEBHOOK_SECRET não configurado — aceitando sem validação (não use em produção).")
            return True

        try:
            expected = hmac.new(
                self._webhook_secret.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception as e:
            logger.error(f"validate_webhook: {e}")
            return False

    def process_webhook(self, body: dict) -> bool:
        """
        Processa um evento de webhook do Mercado Pago.

        Fluxo:
          1. Verifica tipo do evento (só processa 'payment')
          2. Busca dados do pagamento na API do MP
          3. Se aprovado, atualiza plano do usuário no Supabase

        Args:
            body: Corpo do webhook (já parseado como dict).

        Returns:
            True se processado com sucesso, False caso contrário.
        """
        try:
            action = body.get("action", "")
            topic = body.get("type", body.get("topic", ""))

            if topic not in ("payment", "merchant_order"):
                logger.debug(f"Webhook ignorado: tipo={topic}")
                return True  # OK — só não processamos

            payment_id = (
                body.get("data", {}).get("id")
                or body.get("resource", "").split("/")[-1]
            )

            if not payment_id:
                logger.warning("Webhook sem payment_id")
                return False

            payment = self._get_payment_info(str(payment_id))
            if payment is None:
                return False

            if payment.status == "approved":
                return self._activate_plan(payment)
            elif payment.status in ("cancelled", "rejected"):
                logger.info(f"Pagamento {payment_id} {payment.status} — sem ação")
                return True

            return True

        except Exception as e:
            logger.error(f"process_webhook: {e}")
            return False

    def _get_payment_info(self, payment_id: str) -> PaymentInfo | None:
        """Busca dados de um pagamento na API do Mercado Pago."""
        try:
            import urllib.request, json
            req = urllib.request.Request(
                f"{_MP_API_BASE}/v1/payments/{payment_id}",
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            ext_ref = data.get("external_reference", "")
            plan, email = (ext_ref.split("|", 1) + ["pro", ""])[:2] if ext_ref else ("pro", "")
            if not email:
                email = data.get("payer", {}).get("email", "")

            return PaymentInfo(
                payment_id=payment_id,
                status=data.get("status", ""),
                email=email,
                plan=plan or "pro",
                amount=float(data.get("transaction_amount", 0)),
                approved_at=data.get("date_approved", ""),
            )
        except Exception as e:
            logger.error(f"_get_payment_info {payment_id}: {e}")
            return None

    def _activate_plan(self, payment: PaymentInfo) -> bool:
        """Ativa o plano do usuário no Supabase após pagamento aprovado."""
        if not payment.email:
            logger.error("_activate_plan: email vazio")
            return False

        try:
            if self.db.is_real and self.db.client:
                # Atualiza profissional se existir
                self.db.client.table("profissionais").update({
                    "plano": payment.plan,
                    "plano_ativo_desde": payment.approved_at or datetime.now(timezone.utc).isoformat(),
                    "ultimo_pagamento_id": payment.payment_id,
                    "ultimo_pagamento_valor": payment.amount,
                }).eq("email", payment.email).execute()

                # Atualiza perfil do paciente se existir
                self.db.client.table("perfis").update({
                    "plano": payment.plan,
                }).eq("email", payment.email).execute()

                logger.info(f"✅ Plano '{payment.plan}' ativado para {payment.email}")
                return True

            logger.warning("_activate_plan: DB não real — sem persistência")
            return True

        except Exception as e:
            logger.error(f"_activate_plan: {e}")
            return False

    # ── Helpers para a UI ─────────────────────────────────────────────────────

    def get_checkout_button_html(
        self,
        user_email: str,
        user_name: str,
        plan: str = "pro",
        label: str = "🚀 Assinar agora",
    ) -> str:
        """
        Gera HTML de botão de checkout ou mensagem de erro de configuração.
        Chamado pela plan_service.show_paywall() e profile_tabs.

        Returns:
            HTML para ser passado para st.markdown(..., unsafe_allow_html=True).
        """
        result = self.create_checkout_url(user_email, user_name, plan)

        if not result.ok:
            return (
                f'<div style="background:var(--warning-bg);border:1px solid var(--warning-border);'
                f'border-radius:var(--radius-md);padding:.8rem 1rem;font-size:.84rem;'
                f'color:var(--warning);">⚠️ Pagamento temporariamente indisponível. '
                f'Entre em contato pelo suporte.</div>'
            )

        price = config.PRO_PRICE if plan == "pro" else config.CLINIC_PRICE

        return (
            f'<div style="text-align:center;">'
            f'<a href="{result.checkout_url}" target="_blank" rel="noopener">'
            f'<button style="background:var(--gradient-primary);color:#fff;border:none;'
            f'padding:.75rem 2rem;border-radius:var(--radius-md);font-weight:700;'
            f'font-size:1rem;cursor:pointer;box-shadow:0 2px 8px rgba(184,146,42,.35);">'
            f'{label} — R$ {price:.2f}/mês'
            f'</button></a>'
            f'<div style="font-size:.76rem;color:var(--text-faint);margin-top:.4rem;">'
            f'Pagamento seguro via Mercado Pago 🔒'
            f'</div></div>'
        )
