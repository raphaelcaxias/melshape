"""
Melshape — EventTracker: métricas de uso internas.

Constituição Cap. VII: "Evidência antes de opinião. Toda mudança importante
deve ser sustentada por evidência concreta (métrica, feedback real)."

Sprint 6 — MVP para Validação Real.

O que rastreamos (tudo anônimo por padrão):
  - page_view: qual tela o usuário visitou
  - feature_use: qual funcionalidade foi acionada
  - checkin_done: check-in completado com streak
  - habit_logged: hábito marcado
  - plan_upgrade_click: clique em assinar
  - paywall_shown: paywall exibido para qual feature

Tabela Supabase necessária:
  CREATE TABLE IF NOT EXISTS eventos_uso (
    id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    evento      text NOT NULL,
    propriedades jsonb DEFAULT '{}',
    perfil_id   text,             -- NULL = anônimo
    criado_em   timestamptz DEFAULT now()
  );

Política: nenhum dado pessoal sensível. Apenas IDs e eventos.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("Melshape.Analytics")

_TABELA = "eventos_uso"
_ENABLED = os.getenv("ANALYTICS_ENABLED", "true").lower() == "true"
_MAX_BATCH = 20  # máximo de eventos em memória antes de descartar


class EventTracker:
    """
    Rastreador de eventos de uso interno.

    Uso:
        tracker = EventTracker(db)
        tracker.track("page_view", {"page": "home"})
        tracker.track("checkin_done", {"streak": 7, "pilar": "fitness"})
    """

    def __init__(self, db: Any, perfil_id: str = "") -> None:
        self.db = db
        self.perfil_id = perfil_id
        self._batch: list[dict] = []

    def track(self, evento: str, props: dict | None = None) -> None:
        """
        Registra um evento de uso.

        Falha silenciosamente — nunca deve quebrar o fluxo principal.

        Args:
            evento: Nome do evento (ex: "page_view", "checkin_done").
            props:  Propriedades adicionais (dict simples, sem PII).
        """
        if not _ENABLED:
            return

        try:
            row = {
                "evento": evento,
                "propriedades": props or {},
                "perfil_id": self.perfil_id or None,
                "criado_em": datetime.now(timezone.utc).isoformat(),
            }
            self._persist(row)
        except Exception as e:
            logger.debug(f"EventTracker.track silencioso: {e}")

    def page_view(self, page: str, extra: dict | None = None) -> None:
        """Atalho para rastrear visitas de página."""
        self.track("page_view", {"page": page, **(extra or {})})

    def feature_use(self, feature: str, extra: dict | None = None) -> None:
        """Atalho para rastrear uso de funcionalidade."""
        self.track("feature_use", {"feature": feature, **(extra or {})})

    def checkin_done(self, streak: int, pilar: str) -> None:
        """Rastreia check-in completado."""
        self.track("checkin_done", {"streak": streak, "pilar": pilar})

    def habit_logged(self, habit_id: str, pilar: str) -> None:
        """Rastreia hábito marcado."""
        self.track("habit_logged", {"habit_id": habit_id, "pilar": pilar})

    def paywall_shown(self, feature: str) -> None:
        """Rastreia quando o paywall é exibido."""
        self.track("paywall_shown", {"feature": feature})

    def plan_upgrade_click(self, plan: str) -> None:
        """Rastreia clique em assinar."""
        self.track("plan_upgrade_click", {"plan": plan})

    def abandonment_risk(self, dias_sem_checkin: int, streak_perdido: int) -> None:
        """Rastreia risco de abandono detectado."""
        self.track("abandonment_risk", {
            "dias_sem_checkin": dias_sem_checkin,
            "streak_perdido": streak_perdido,
        })

    # ── Persistência ──────────────────────────────────────────────────────────

    def _persist(self, row: dict) -> None:
        """Persiste evento no Supabase. Silencioso em caso de erro."""
        if self.db and self.db.is_real and self.db.client:
            try:
                self.db.client.table(_TABELA).insert(row).execute()
            except Exception as e:
                logger.debug(f"_persist: {e}")
        # Em mock/demo: apenas loga no debug
        else:
            logger.debug(f"[Analytics] {row['evento']} {row.get('propriedades', {})}")


# ─────────────────────────────────────────────────────────────────────────────
# REPORTS — para o executive dashboard
# ─────────────────────────────────────────────────────────────────────────────

class AnalyticsReport:
    """Gera relatórios de uso a partir dos eventos armazenados."""

    def __init__(self, db: Any) -> None:
        self.db = db

    def top_pages(self, days: int = 30, limit: int = 10) -> list[dict]:
        """Páginas mais visitadas nos últimos N dias."""
        return self._aggregate("page_view", "page", days, limit)

    def top_features(self, days: int = 30, limit: int = 10) -> list[dict]:
        """Funcionalidades mais usadas nos últimos N dias."""
        return self._aggregate("feature_use", "feature", days, limit)

    def daily_checkins(self, days: int = 30) -> list[dict]:
        """Check-ins por dia nos últimos N dias."""
        if not (self.db and self.db.is_real and self.db.client):
            return []
        try:
            from datetime import date, timedelta
            inicio = (date.today() - timedelta(days=days)).isoformat()
            r = (
                self.db.client.table(_TABELA)
                .select("criado_em")
                .eq("evento", "checkin_done")
                .gte("criado_em", inicio)
                .execute()
            )
            # Agrupa por data
            from collections import Counter
            counts = Counter(
                row["criado_em"][:10] for row in (r.data or [])
            )
            return [{"data": d, "total": c} for d, c in sorted(counts.items())]
        except Exception as e:
            logger.debug(f"daily_checkins: {e}")
            return []

    def paywall_conversion(self, days: int = 30) -> dict:
        """Taxa de conversão: paywall_shown → plan_upgrade_click."""
        if not (self.db and self.db.is_real and self.db.client):
            return {"shown": 0, "clicked": 0, "rate": 0.0}
        try:
            from datetime import date, timedelta
            inicio = (date.today() - timedelta(days=days)).isoformat()

            r_shown = (
                self.db.client.table(_TABELA)
                .select("id", count="exact")
                .eq("evento", "paywall_shown")
                .gte("criado_em", inicio)
                .execute()
            )
            r_click = (
                self.db.client.table(_TABELA)
                .select("id", count="exact")
                .eq("evento", "plan_upgrade_click")
                .gte("criado_em", inicio)
                .execute()
            )
            shown = r_shown.count or 0
            clicked = r_click.count or 0
            rate = (clicked / shown * 100) if shown > 0 else 0.0
            return {"shown": shown, "clicked": clicked, "rate": round(rate, 1)}
        except Exception as e:
            logger.debug(f"paywall_conversion: {e}")
            return {"shown": 0, "clicked": 0, "rate": 0.0}

    def abandonment_events(self, days: int = 30) -> list[dict]:
        """Eventos de risco de abandono detectados."""
        if not (self.db and self.db.is_real and self.db.client):
            return []
        try:
            from datetime import date, timedelta
            inicio = (date.today() - timedelta(days=days)).isoformat()
            r = (
                self.db.client.table(_TABELA)
                .select("propriedades,criado_em")
                .eq("evento", "abandonment_risk")
                .gte("criado_em", inicio)
                .order("criado_em", desc=True)
                .limit(50)
                .execute()
            )
            return r.data or []
        except Exception as e:
            logger.debug(f"abandonment_events: {e}")
            return []

    def _aggregate(self, evento: str, prop_key: str, days: int, limit: int) -> list[dict]:
        """Agrega contagens de um evento por propriedade."""
        if not (self.db and self.db.is_real and self.db.client):
            return []
        try:
            from datetime import date, timedelta
            from collections import Counter
            inicio = (date.today() - timedelta(days=days)).isoformat()
            r = (
                self.db.client.table(_TABELA)
                .select("propriedades")
                .eq("evento", evento)
                .gte("criado_em", inicio)
                .execute()
            )
            counts = Counter(
                row.get("propriedades", {}).get(prop_key, "?")
                for row in (r.data or [])
            )
            return [
                {"nome": nome, "total": total}
                for nome, total in counts.most_common(limit)
            ]
        except Exception as e:
            logger.debug(f"_aggregate {evento}: {e}")
            return []
