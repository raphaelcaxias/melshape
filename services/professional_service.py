"""Melshape — Serviço do painel profissional com triagem clínica."""
import logging
from typing import List, Dict, Any
from datetime import date, timedelta

from core.database import Database

logger = logging.getLogger("Melshape.Professional")

# Critérios de triagem
TRIAGE_GAP_DAYS_CRITICAL = 3   # sem registro há 3+ dias → crítico
TRIAGE_GAP_DAYS_WARNING  = 1   # sem registro ontem → atenção
TRIAGE_LOW_PROTEIN_PCT   = 0.5 # proteína < 50% da meta → atenção
TRIAGE_LOW_CALORIES      = 900 # calorias abaixo disso → atenção


class ProfessionalService:

    def __init__(self, db: Database):
        self.db = db

    def get_patients(self, professional_email: str) -> List[dict]:
        return self.db.get_patients_of_professional(professional_email)

    def get_patient_summary(self, patient_email: str) -> Dict[str, Any]:
        return self.db.get_patient_summary(patient_email)

    def get_triage_list(self, patients: List[dict]) -> Dict[str, List[dict]]:
        """
        Classifica pacientes em:
        - critical: sem registros há 3+ dias ou sintomas severos
        - warning:  sem registros ontem, proteína baixa, calorias muito baixas
        - ok:       dentro do esperado
        """
        critical, warning, ok = [], [], []

        for p in patients:
            email   = p.get("email", "")
            summary = self.get_patient_summary(email)
            reasons = []
            level   = "ok"

            gap = summary.get("gap_days", 0)
            if gap >= TRIAGE_GAP_DAYS_CRITICAL:
                reasons.append(f"📵 Sem registros há {gap} dias")
                level = "critical"
            elif gap >= TRIAGE_GAP_DAYS_WARNING:
                reasons.append("⚠️ Sem registro ontem")
                level = "warning" if level == "ok" else level

            cal = summary.get("cal_today", 0)
            if 0 < cal < TRIAGE_LOW_CALORIES:
                reasons.append(f"🔥 Calorias muito baixas hoje: {cal} kcal")
                level = "warning" if level == "ok" else level

            prot = summary.get("prot_today", 0)
            health_mode = p.get("health_mode", "general")
            w = p.get("current_weight", 70) or 70
            proto_per_kg = {"glp1": 1.6, "bariatric": 1.5, "fitness": 2.0}.get(health_mode, 1.4)
            prot_goal = w * proto_per_kg
            if prot > 0 and prot < prot_goal * TRIAGE_LOW_PROTEIN_PCT:
                reasons.append(f"🥩 Proteína baixa: {prot:.0f}g de {prot_goal:.0f}g")
                level = "warning" if level == "ok" else level

            enriched = {**p, "triage_level": level, "triage_reasons": reasons, "summary": summary}
            if level == "critical":
                critical.append(enriched)
            elif level == "warning":
                warning.append(enriched)
            else:
                ok.append(enriched)

        return {"critical": critical, "warning": warning, "ok": ok}

    def get_patient_insights(self, patient_email: str) -> Dict[str, Any]:
        """Insights clínicos para a página de detalhe do paciente."""
        summary = self.get_patient_summary(patient_email)
        return {
            "summary":      summary,
            "weight_trend": self._weight_trend(patient_email),
        }

    def _weight_trend(self, patient_email: str) -> str:
        weights = [
            w for w in self.db._mock().get("weights", [])
            if w.get("user_id") == patient_email
        ]
        if len(weights) < 2:
            return "Dados insuficientes"
        weights_sorted = sorted(weights, key=lambda x: x.get("log_date",""))
        first = weights_sorted[0].get("weight", 0)
        last  = weights_sorted[-1].get("weight", 0)
        diff  = round(last - first, 1)
        if diff < -0.5:
            return f"📉 Perdendo peso ({diff:+.1f} kg)"
        elif diff > 0.5:
            return f"📈 Ganhando peso ({diff:+.1f} kg)"
        return "↔️ Peso estável"
