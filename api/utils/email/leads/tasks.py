# api/utils/email/leads/tasks.py
# ✅ Migré de Celery (@shared_task / .delay()) vers Django-Q2 (async_task)

import logging

from django_q.tasks import async_task

from api.leads.models import Lead

from api.utils.email import send_appointment_confirmation_email
from api.utils.email.leads.notifications import (
    send_appointment_planned_email,
    send_dossier_status_email,
    send_formulaire_email,
    send_jurist_assigned_email,
)

logger = logging.getLogger(__name__)


# ================================================================
# Fonctions exécutées par les workers Django-Q2
# ================================================================

def _run_send_appointment_confirmation(lead_id: int):
    lead = Lead.objects.select_related("status").filter(id=lead_id).first()
    if lead and lead.email:
        send_appointment_confirmation_email(lead)
        logger.info("📧 Confirmation envoyée à %s (lead #%s)", lead.email, lead.id)
    else:
        logger.warning(
            "❌ Aucune confirmation envoyée (lead #%s inexistant ou sans email)",
            lead_id,
        )


def _run_send_appointment_planned(lead_id: int):
    lead = Lead.objects.select_related("status").filter(id=lead_id).first()
    if lead and lead.email:
        send_appointment_planned_email(lead)
        logger.info("📅 RDV planifié envoyé à %s (lead #%s)", lead.email, lead.id)
    else:
        logger.warning(
            "❌ RDV planifié non envoyé (lead #%s inexistant ou sans email)",
            lead_id,
        )


def _run_send_dossier_status_notification(lead_id: int):
    lead = Lead.objects.select_related("statut_dossier").filter(id=lead_id).first()
    if lead and lead.statut_dossier:
        send_dossier_status_email(lead)
        logger.info(
            "📨 Statut dossier '%s' envoyé pour lead #%s",
            lead.statut_dossier.label, lead.id,
        )
    else:
        logger.warning(
            "❌ Notification statut dossier non envoyée (lead #%s ou statut manquant)",
            lead_id,
        )


def _run_send_formulaire(lead_id: int):
    lead = Lead.objects.filter(id=lead_id).first()
    if lead and lead.email:
        send_formulaire_email(lead)
        logger.info("📤 Formulaire envoyé pour lead #%s", lead.id)
    else:
        logger.warning(
            "❌ Formulaire non envoyé (lead #%s introuvable ou sans email)",
            lead_id,
        )


def _run_send_jurist_assigned_notification(lead_id: int, jurist_id: int):
    from api.users.models import User

    lead = Lead.objects.filter(id=lead_id).first()
    jurist = User.objects.filter(id=jurist_id).first()

    if lead and jurist and lead.email:
        send_jurist_assigned_email(lead, jurist)
        logger.info(
            "📩 Juriste assigné notifié (lead #%s — %s)",
            lead.id, lead.email,
        )
    else:
        logger.warning(
            "❌ Notification juriste non envoyée (lead #%s, juriste #%s)",
            lead_id, jurist_id,
        )


# ================================================================
# API publique — fonctions de dispatch
# ================================================================

def send_appointment_confirmation_task(lead_id: int):
    """Envoie immédiatement l'email de confirmation RDV."""
    async_task(
        "api.utils.email.leads.tasks._run_send_appointment_confirmation",
        lead_id,
        group="emails",
    )


def send_appointment_planned_task(lead_id: int):
    """Envoie immédiatement l'email RDV planifié."""
    async_task(
        "api.utils.email.leads.tasks._run_send_appointment_planned",
        lead_id,
        group="emails",
    )


def send_dossier_status_notification_task(lead_id: int):
    """Envoie immédiatement l'email de changement de statut dossier."""
    async_task(
        "api.utils.email.leads.tasks._run_send_dossier_status_notification",
        lead_id,
        group="emails",
    )


def send_formulaire_task(lead_id: int):
    """Envoie immédiatement l'email avec le lien du formulaire."""
    async_task(
        "api.utils.email.leads.tasks._run_send_formulaire",
        lead_id,
        group="emails",
    )


def send_jurist_assigned_notification_task(lead_id: int, jurist_id: int):
    """Envoie immédiatement la notification d'assignation juriste."""
    async_task(
        "api.utils.email.leads.tasks._run_send_jurist_assigned_notification",
        lead_id,
        jurist_id,
        group="emails",
    )