"""
Melshape — Serviço de notificações agendadas.
Usa APScheduler para enviar lembretes diários.
Inicia junto com o app e roda em background.
"""
import logging
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger("Melshape.Notifications")


def _should_send_reminder(user: dict, db) -> bool:
    """Verifica se usuário merece lembrete: sem registro hoje."""
    email = user.get("email", "")
    if not email or email == "demo@melshape.com.br":
        return False
    # Notificações opt-out
    if user.get("disable_reminders"):
        return False
    # Verifica se tem registro hoje
    today = date.today().isoformat()
    meals = [m for m in db._mock().get("meals", [])
             if m.get("user_id") == email and m.get("meal_date") == today]
    return len(meals) == 0


def schedule_daily_reminders(db) -> None:
    """
    Agenda verificação diária às 20h para enviar lembretes.
    Chamado uma vez na inicialização do app.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BackgroundScheduler()

        def daily_check():
            logger.info("Executando verificação de lembretes diários...")
            _run_daily_notifications(db)

        # Roda às 20h todos os dias
        scheduler.add_job(
            daily_check,
            CronTrigger(hour=20, minute=0),
            id="daily_reminders",
            replace_existing=True,
        )

        # Trial expirando — verifica às 9h
        scheduler.add_job(
            lambda: _run_trial_notifications(db),
            CronTrigger(hour=9, minute=0),
            id="trial_check",
            replace_existing=True,
        )

        scheduler.start()
        logger.info("✅ Agendador de notificações iniciado (20h lembretes, 9h trial)")
        return scheduler

    except ImportError:
        logger.warning(
            "APScheduler não instalado. Notificações agendadas desativadas. "
            "Execute: pip install apscheduler"
        )
        return None
    except Exception as e:
        logger.error(f"Erro ao iniciar agendador: {e}")
        return None


def _run_daily_notifications(db) -> None:
    """Verifica todos os usuários e envia lembretes se necessário."""
    from services.email_service import send_meal_reminder, send_streak_at_risk
    from services.gamification_service import GamificationService

    users = db._mock().get("users", {})
    sent  = 0

    for email, user in users.items():
        try:
            if not _should_send_reminder(user, db):
                continue

            # Calcula streak
            gamification = GamificationService(db)
            streak = gamification.streak()

            # Se tem streak em risco (registrou ontem mas não hoje)
            if streak >= 3:
                send_streak_at_risk(email, user.get("name", ""), streak)
            else:
                send_meal_reminder(email, user.get("name", ""), streak)

            sent += 1
        except Exception as e:
            logger.error(f"Erro ao notificar {email}: {e}")

    logger.info(f"Lembretes enviados: {sent} usuários")


def _run_trial_notifications(db) -> None:
    """Verifica trials prestes a expirar e envia aviso."""
    from services.email_service import send_trial_expiring
    from core.models import User

    users = db._mock().get("users", {})

    for email, user_dict in users.items():
        try:
            u = User.from_dict(user_dict)
            if u.plan != "trial":
                continue
            days = u.trial_days_remaining()
            if days in (3, 1):  # Avisa com 3 dias e 1 dia de antecedência
                send_trial_expiring(email, u.name, days)
                logger.info(f"Aviso de trial enviado para {email} ({days}d restantes)")
        except Exception as e:
            logger.error(f"Erro ao verificar trial de {email}: {e}")


def send_manual_reminder(email: str, name: str, db) -> bool:
    """Envia lembrete manual para um usuário específico."""
    from services.email_service import send_meal_reminder
    from services.gamification_service import GamificationService

    try:
        gamification = GamificationService(db)
        streak = gamification.streak()
        return send_meal_reminder(email, name, streak)
    except Exception as e:
        logger.error(f"Erro ao enviar lembrete manual para {email}: {e}")
        return False
