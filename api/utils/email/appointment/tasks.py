# api/appointment/tasks.py
# ✅ Migré Celery → Django-Q2

import logging

from django_q.tasks import async_task

logger = logging.getLogger(__name__)


# ================================================================
# WORKERS
# ================================================================

def _run_send_appointment_created(appointment_id: int):
    from api.appointment.models import Appointment
    from api.utils.email.appointment.notifications import send_appointment_created_email

    appointment = Appointment.objects.select_related("lead").filter(id=appointment_id).first()

    if appointment and appointment.lead and appointment.lead.email:
        send_appointment_created_email(appointment.lead, appointment)
        logger.info(
            "📅 Email création RDV envoyé à %s (lead #%s)",
            appointment.lead.email, appointment.lead.id
        )
    else:
        logger.warning("❌ RDV non envoyé : lead ou email manquant pour appointment #%s", appointment_id)


def _run_send_appointment_updated(appointment_id: int):
    from api.appointment.models import Appointment
    from api.utils.email.appointment.notifications import send_appointment_updated_email

    appointment = Appointment.objects.select_related("lead").filter(id=appointment_id).first()

    if appointment and appointment.lead and appointment.lead.email:
        send_appointment_updated_email(appointment.lead, appointment)
        logger.info(
            "✏️ Email modification RDV envoyé à %s (lead #%s)",
            appointment.lead.email, appointment.lead.id
        )
    else:
        logger.warning("❌ RDV modifié non envoyé : lead ou email manquant pour appointment #%s", appointment_id)


def _run_send_appointment_deleted(lead_id: int, appointment_data: dict):
    from django.utils.dateparse import parse_datetime
    from api.leads.models import Lead
    from api.utils.email.appointment.notifications import send_appointment_deleted_email

    try:
        lead = Lead.objects.get(pk=lead_id)
        appointment_date = parse_datetime(appointment_data["date"])
        send_appointment_deleted_email(lead, appointment_date, appointment_data)
        logger.info("🗑️ Email annulation RDV envoyé à %s (lead #%s)", lead.email, lead.id)
    except Exception:
        logger.error("❌ Erreur email annulation RDV pour lead #%s", lead_id, exc_info=True)


# ================================================================
# API PUBLIQUE — dispatchers
# ================================================================

def send_appointment_created_task(appointment_id: int):
    """Anciennement send_appointment_created_task.delay(appointment_id)"""
    async_task(
        "api.appointment.tasks._run_send_appointment_created",
        appointment_id,
        group="emails",
    )


def send_appointment_updated_task(appointment_id: int):
    """Anciennement send_appointment_updated_task.delay(appointment_id)"""
    async_task(
        "api.appointment.tasks._run_send_appointment_updated",
        appointment_id,
        group="emails",
    )


def send_appointment_deleted_task(lead_id: int, appointment_data: dict):
    """Anciennement send_appointment_deleted_task.delay(lead_id, appointment_data)"""
    async_task(
        "api.appointment.tasks._run_send_appointment_deleted",
        lead_id,
        appointment_data,
        group="emails",
    )