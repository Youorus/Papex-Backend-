# api/utils/email/jurist_appointment/tasks.py
# ✅ Migré Celery → Django-Q2

import logging

from django_q.tasks import async_task

logger = logging.getLogger(__name__)


# ================================================================
# WORKERS
# ================================================================

def _run_send_jurist_appointment_created(appointment_id: int):
    from api.jurist_appointment.models import JuristAppointment
    from api.utils.email.jurist_appointment.notifications import send_jurist_appointment_email

    appointment = (
        JuristAppointment.objects
        .select_related("lead")
        .filter(id=appointment_id)
        .first()
    )

    if not appointment:
        logger.warning("❌ JuristAppointment #%s introuvable", appointment_id)
        return

    send_jurist_appointment_email(appointment)
    logger.info("⚖️ Email RDV juriste envoyé (appointment #%s)", appointment.id)


def _run_send_jurist_appointment_deleted(lead_id: int, jurist_id: int, date_str: str):
    from datetime import datetime
    from api.leads.models import Lead
    from api.users.models import User
    from api.utils.email.jurist_appointment.notifications import send_jurist_appointment_deleted_email

    try:
        lead = Lead.objects.get(id=lead_id)
        jurist = User.objects.get(id=jurist_id)
        date = datetime.fromisoformat(date_str)

        send_jurist_appointment_deleted_email(lead, jurist, date)

        logger.info(
            "⚖️ Email annulation RDV juriste envoyé (lead #%s, juriste #%s)",
            lead_id, jurist_id
        )

    except (Lead.DoesNotExist, User.DoesNotExist, ValueError) as e:
        logger.error("❌ Erreur email annulation RDV juriste", exc_info=e)


# ================================================================
# API PUBLIQUE — dispatchers
# ================================================================

def send_jurist_appointment_created_task(appointment_id: int):
    """Anciennement send_jurist_appointment_created_task.delay(appointment_id)"""
    async_task(
        "api.utils.email.jurist_appointment.tasks._run_send_jurist_appointment_created",
        appointment_id,
        group="emails",
    )


def send_jurist_appointment_deleted_task(lead_id: int, jurist_id: int, date_str: str):
    """Anciennement send_jurist_appointment_deleted_task.delay(lead_id, jurist_id, date_str)"""
    async_task(
        "api.utils.email.jurist_appointment.tasks._run_send_jurist_appointment_deleted",
        lead_id,
        jurist_id,
        date_str,
        group="emails",
    )