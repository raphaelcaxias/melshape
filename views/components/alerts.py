"""Melshape — Alertas clínicos contextuais."""
import streamlit as st
from views.components.cards import alert


def show_clinical_alerts(services: dict, user: dict) -> None:
    """Centraliza todos os alertas clínicos da Home e Dashboard."""
    nutrition = services["nutrition"]
    db        = services["db"]
    mode      = user.get("health_mode", "general")

    # ── GLP-1: baixa caloria por 3 dias ───────────────────────────────────
    if mode == "glp1":
        glp1_alert = nutrition.glp1_low_calorie_alert()
        if glp1_alert:
            alert(glp1_alert, "clinical")

    # ── Proteína baixa por 2 dias ─────────────────────────────────────────
    import config
    w         = float(user.get("current_weight") or 70)
    prot_goal = nutrition.calc_protein_goal(w, mode)
    prot_2d   = nutrition.protein_two_day_alert(prot_goal)
    if prot_2d:
        alert(prot_2d, "warning")

    # ── Hidratação baixa ──────────────────────────────────────────────────
    if user.get("can_use_hydration", True):
        total_ml = db.get_hydration_today()
        if 0 < total_ml < config.HYDRATION_MIN_ML:
            alert(
                f"💧 Hidratação baixa: {total_ml} ml de {config.HYDRATION_MIN_ML} ml mínimos. "
                "Beba água agora!",
                "info",
            )

    # ── Sintomas severos por 2+ dias ──────────────────────────────────────
    if mode in ("glp1", "bariatric"):
        severe_days = db.consecutive_severe_symptom_days()
        if severe_days >= 2:
            alert(
                f"🩺 Sintomas severos registrados por {severe_days} dias consecutivos. "
                "Consulte seu médico ou nutricionista.",
                "clinical",
            )

    # ── Bariátrico: lembrete de fase ──────────────────────────────────────
    if mode == "bariatric":
        phase = user.get("bariatric_phase", "")
        if phase in ("liquid", "pasty"):
            import config as cfg
            phase_data = cfg.BARIATRIC_PHASES.get(phase, {})
            alert(
                f"🔪 Fase **{phase_data.get('name','')}**: máximo "
                f"{phase_data.get('max_ml','')}ml por refeição. Fracione bem!",
                "bariatric",
            )

    # ── Sono curto + ganho de peso ────────────────────────────────────────
    if user.get("gender") in ("female", "other"):
        cycle = db.get_cycle_today()
        sleep = db.get_sleep_today()
        if cycle and cycle.phase == "luteal" and sleep and sleep.is_short():
            alert(
                "🌙 Fase lútea + sono curto: ganho de peso pode ser retenção hídrica, "
                "não gordura. Sem ansiedade — monitore por mais 2-3 dias.",
                "info",
            )
