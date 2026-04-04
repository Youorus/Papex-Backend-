# api/utils/email/leads/tasks.py

import logging
from datetime import timedelta

from django.utils import timezone
from django_q.tasks import async_task

from api.leads.models import Lead
from api.leads.constants import RDV_CONFIRME, RDV_PLANIFIE

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
# HELPER
# ================================================================

def _get_lead(lead_id: int, task_name: str):
    """Récupère un lead avec ses relations"""
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


# ================================================================
# WORKERS (AVEC **kwargs POUR COMPATIBILITÉ)
# ================================================================

def _run_send_appointment_confirmation(lead_id: int, **kwargs):
    """Worker - Envoi email confirmation RDV"""
    lead = _get_lead(lead_id, "email_confirmation")
    if lead and lead.email:
        send_appointment_confirmation_email(lead)
        logger.info("📧 Confirmation envoyée → %s (lead #%s)", lead.email, lead.id)
    elif lead and not lead.email:
        logger.warning("📧 Lead #%s n'a pas d'email - confirmation ignorée", lead.id)


def _run_send_appointment_planned(lead_id: int, **kwargs):
    """Worker - Email RDV planifié"""
    lead = _get_lead(lead_id, "email_planned")
    if lead and lead.email:
        send_appointment_planned_email(lead)
        logger.info("📅 RDV planifié → %s (lead #%s)", lead.email, lead.id)
    elif lead and not lead.email:
        logger.warning("📅 Lead #%s n'a pas d'email - RDV planifié ignoré", lead.id)


def _run_send_dossier_status_notification(lead_id: int, **kwargs):
    """Worker - Notification statut dossier"""
    lead = _get_lead(lead_id, "email_dossier_status")
    if lead and lead.statut_dossier and lead.email:
        send_dossier_status_email(lead)
        logger.info(
            "📨 Statut dossier '%s' envoyé à %s (lead #%s)",
            lead.statut_dossier.label, lead.email, lead.id,
        )
    elif lead and not lead.email:
        logger.warning("📨 Lead #%s n'a pas d'email - statut dossier ignoré", lead.id)


def _run_send_formulaire(lead_id: int, **kwargs):
    """Worker - Envoi formulaire"""
    lead = _get_lead(lead_id, "email_formulaire")
    if lead and lead.email:
        send_formulaire_email(lead)
        logger.info("📤 Formulaire envoyé à %s (lead #%s)", lead.email, lead.id)
    elif lead and not lead.email:
        logger.warning("📤 Lead #%s n'a pas d'email - formulaire ignoré", lead.id)


def _run_send_jurist_assigned_notification(lead_id: int, jurist_id: int, **kwargs):
    """Worker - Notification assignation juriste"""
    from api.users.models import User

    lead = _get_lead(lead_id, "email_jurist")
    jurist = User.objects.filter(id=jurist_id).first()

    if lead and jurist and lead.email:
        send_jurist_assigned_email(lead, jurist)
        logger.info("📩 Juriste %s assigné → %s (lead #%s)", jurist.email, lead.email, lead.id)
    elif lead and not lead.email:
        logger.warning("📩 Lead #%s n'a pas d'email - assignation juriste ignorée", lead.id)
    elif lead and not jurist:
        logger.warning("📩 Juriste #%s introuvable - assignation ignorée", jurist_id)


def _run_send_appointment_absent(lead_id: int, **kwargs):
    """Worker - Email d'absence au rendez-vous"""
    lead = _get_lead(lead_id, "email_absent")
    if lead and lead.email:
        send_appointment_absent_email(lead)
        logger.info("❌ ABSENT email → %s (lead #%s)", lead.email, lead.id)
    elif lead and not lead.email:
        logger.warning("❌ Lead #%s n'a pas d'email - email absent ignoré", lead.id)


def _run_send_appointment_reminder(lead_id: int, **kwargs):
    """Worker - Email de rappel de rendez-vous"""
    lead = _get_lead(lead_id, "email_reminder")
    if lead and lead.email:
        send_appointment_reminder_email(lead)
        logger.info("⏰ Reminder email → %s (lead #%s)", lead.email, lead.id)
    elif lead and not lead.email:
        logger.warning("⏰ Lead #%s n'a pas d'email - reminder ignoré", lead.id)


# ================================================================
# DISPATCHERS (API PUBLIQUE)
# ================================================================

def send_appointment_confirmation_task(lead_id: int, countdown: int = 0):
    """Planifie l'envoi d'email de confirmation"""
    kwargs = {"group": "emails"}
    if countdown:
        kwargs["scheduled"] = timezone.now() + timedelta(seconds=countdown)

    async_task(
        "api.utils.email.leads.tasks._run_send_appointment_confirmation",
        lead_id,
        **kwargs,
    )


def send_appointment_planned_task(lead_id: int, countdown: int = 0):
    """Planifie l'envoi d'email de RDV planifié"""
    kwargs = {"group": "emails"}
    if countdown:
        kwargs["scheduled"] = timezone.now() + timedelta(seconds=countdown)

    async_task(
        "api.utils.email.leads.tasks._run_send_appointment_planned",
        lead_id,
        **kwargs,
    )


def send_dossier_status_notification_task(lead_id: int, countdown: int = 0):
    """Planifie l'envoi de notification de statut dossier"""
    kwargs = {"group": "emails"}
    if countdown:
        kwargs["scheduled"] = timezone.now() + timedelta(seconds=countdown)

    async_task(
        "api.utils.email.leads.tasks._run_send_dossier_status_notification",
        lead_id,
        **kwargs,
    )


def send_formulaire_task(lead_id: int, countdown: int = 0):
    """Planifie l'envoi de formulaire"""
    kwargs = {"group": "emails"}
    if countdown:
        kwargs["scheduled"] = timezone.now() + timedelta(seconds=countdown)

    async_task(
        "api.utils.email.leads.tasks._run_send_formulaire",
        lead_id,
        **kwargs,
    )


def send_jurist_assigned_notification_task(lead_id: int, jurist_id: int, countdown: int = 0):
    """Planifie la notification d'assignation de juriste"""
    kwargs = {"group": "emails"}
    if countdown:
        kwargs["scheduled"] = timezone.now() + timedelta(seconds=countdown)

    async_task(
        "api.utils.email.leads.tasks._run_send_jurist_assigned_notification",
        lead_id,
        jurist_id,
        **kwargs,
    )


def send_appointment_absent_email_task(lead_id: int, countdown: int = 0):
    """Planifie l'envoi d'email d'absence"""
    kwargs = {"group": "emails"}
    if countdown:
        kwargs["scheduled"] = timezone.now() + timedelta(seconds=countdown)

    async_task(
        "api.utils.email.leads.tasks._run_send_appointment_absent",
        lead_id,
        **kwargs,
    )


def send_appointment_reminder_email_task(lead_id: int, countdown: int = 0):
    """Planifie l'envoi d'email de rappel"""
    kwargs = {"group": "emails"}
    if countdown:
        kwargs["scheduled"] = timezone.now() + timedelta(seconds=countdown)

    async_task(
        "api.utils.email.leads.tasks._run_send_appointment_reminder",
        lead_id,
        **kwargs,
    )


# ================================================================
# FONCTIONS DE MASSE (UTILITAIRES)
# ================================================================

def send_mass_appointment_reminders():
    """
    Envoie des emails de rappel pour tous les RDV à venir
    (48h et 24h avant)
    """
    now = timezone.now()
    reminder_windows = [
        (timedelta(hours=48), "48h", send_appointment_reminder_email_task),
        (timedelta(hours=24), "24h", send_appointment_reminder_email_task),
    ]

    tolerance = timedelta(minutes=5)
    total_sent = 0

    for delta, label, task_func in reminder_windows:
        target_time = now + delta
        window_start = target_time - tolerance
        window_end = target_time + tolerance

        leads = Lead.objects.filter(
            appointment_date__gte=window_start,
            appointment_date__lte=window_end,
            status__code__in=[RDV_CONFIRME, RDV_PLANIFIE],
            email__isnull=False,  # ⚠️ Important : filtre les emails null
        ).exclude(email="")  # Exclut les emails vides

        for lead in leads:
            # Anti-doublon via last_reminder_sent
            if lead.last_reminder_sent:
                if (now - lead.last_reminder_sent) < timedelta(hours=20):
                    continue

            task_func(lead.id)
            lead.last_reminder_sent = now
            lead.save(update_fields=["last_reminder_sent"])
            total_sent += 1
            logger.info(f"Email rappel {label} envoyé pour lead #{lead.id}")

    return f"{total_sent} emails de rappel envoyés"