# api/utils/email/leads/tasks.py

import logging

from django_q.tasks import async_task

from api.leads.models import Lead

from api.utils.email import send_appointment_confirmation_email
from api.utils.email.leads.notifications import (
    send_appointment_planned_email,
    send_dossier_status_email,
    send_formulaire_email,
    send_jurist_assigned_email,
    send_appointment_absent_email,
    send_appointment_reminder_email,
)

logger = logging.getLogger(__name__)


# ================================================================
# WORKERS (EXECUTION)
# ================================================================

def _get_lead(lead_id: int, task_name: str):
    lead = (
        Lead.objects
        .select_related("status", "statut_dossier")
        .filter(id=lead_id)
        .first()
    )

    if not lead:
        logger.warning(
            "[%s] Lead #%s introuvable — task ignorée",
            task_name,
            lead_id,
        )

    return lead


def _run_send_appointment_confirmation(lead_id: int):
    lead = _get_lead(lead_id, "email_confirmation")
    if lead and lead.email:
        send_appointment_confirmation_email(lead)
        logger.info("📧 Confirmation envoyée → %s (lead #%s)", lead.email, lead.id)


def _run_send_appointment_planned(lead_id: int):
    lead = _get_lead(lead_id, "email_planned")
    if lead and lead.email:
        send_appointment_planned_email(lead)
        logger.info("📅 RDV planifié → %s (lead #%s)", lead.email, lead.id)


def _run_send_dossier_status_notification(lead_id: int):
    lead = _get_lead(lead_id, "email_dossier_status")
    if lead and lead.statut_dossier:
        send_dossier_status_email(lead)
        logger.info(
            "📨 Statut dossier '%s' envoyé (lead #%s)",
            lead.statut_dossier.label, lead.id,
        )


def _run_send_formulaire(lead_id: int):
    lead = _get_lead(lead_id, "email_formulaire")
    if lead and lead.email:
        send_formulaire_email(lead)
        logger.info("📤 Formulaire envoyé (lead #%s)", lead.id)


def _run_send_jurist_assigned_notification(lead_id: int, jurist_id: int):
    from api.users.models import User

    lead = _get_lead(lead_id, "email_jurist")
    jurist = User.objects.filter(id=jurist_id).first()

    if lead and jurist and lead.email:
        send_jurist_assigned_email(lead, jurist)
        logger.info("📩 Juriste assigné → %s (lead #%s)", lead.email, lead.id)


# ================================================================
# 🔥 NOUVEAUX WORKERS
# ================================================================

def _run_send_appointment_absent(lead_id: int):
    lead = _get_lead(lead_id, "email_absent")
    if lead and lead.email:
        send_appointment_absent_email(lead)
        logger.info("❌ ABSENT email → %s (lead #%s)", lead.email, lead.id)


def _run_send_appointment_reminder(lead_id: int):
    lead = _get_lead(lead_id, "email_reminder")
    if lead and lead.email:
        send_appointment_reminder_email(lead)
        logger.info("⏰ Reminder email → %s (lead #%s)", lead.email, lead.id)


# ================================================================
# DISPATCHERS
# ================================================================

def send_appointment_confirmation_task(lead_id: int):
    async_task(
        "api.utils.email.leads.tasks._run_send_appointment_confirmation",
        lead_id,
        group="emails",
    )


def send_appointment_planned_task(lead_id: int):
    async_task(
        "api.utils.email.leads.tasks._run_send_appointment_planned",
        lead_id,
        group="emails",
    )


def send_dossier_status_notification_task(lead_id: int):
    async_task(
        "api.utils.email.leads.tasks._run_send_dossier_status_notification",
        lead_id,
        group="emails",
    )


def send_formulaire_task(lead_id: int):
    async_task(
        "api.utils.email.leads.tasks._run_send_formulaire",
        lead_id,
        group="emails",
    )


def send_jurist_assigned_notification_task(lead_id: int, jurist_id: int):
    async_task(
        "api.utils.email.leads.tasks._run_send_jurist_assigned_notification",
        lead_id,
        jurist_id,
        group="emails",
    )


# 🔥 NOUVELLES API PUBLIQUES

def send_appointment_absent_email_task(lead_id: int):
    async_task(
        "api.utils.email.leads.tasks._run_send_appointment_absent",
        lead_id,
        group="emails",
    )


def send_appointment_reminder_email_task(lead_id: int):
    async_task(
        "api.utils.email.leads.tasks._run_send_appointment_reminder",
        lead_id,
        group="emails",
    )