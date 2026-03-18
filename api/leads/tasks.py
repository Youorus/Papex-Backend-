"""
api/leads/tasks/appointments.py

Gestion automatique des rendez-vous :
  - Rappels SMS intelligents 48h et 24h avant le RDV
  - Marquage automatique ABSENT si RDV passé sans présence

À planifier dans Celery Beat :
    process_appointment_reminders  → toutes les 30 minutes
    mark_absent_leads              → toutes les 30 minutes
"""

import logging

from celery import shared_task
from django.utils import timezone

from api.leads.models import Lead
from api.leads.constants import RDV_CONFIRME, ABSENT, RDV_A_CONFIRMER
from api.lead_status.models import LeadStatus
from api.leads_events.models import LeadEvent
from api.sms.notifications.leads import send_confirm_presence_sms

from api.sms.tasks import send_appointment_reminder_sms_task

# from api.whatsapp.tasks import send_appointment_reminder_whatsapp_task
# from api.email.tasks import send_appointment_reminder_email_task

logger = logging.getLogger(__name__)


# ============================================================
# 🔔 RAPPELS INTELLIGENTS (48h et 24h avant le RDV)
# ============================================================

@shared_task
def process_appointment_reminders():
    """
    Vérifie tous les leads avec RDV confirmé et envoie
    les rappels 48h et 24h avant.

    Anti-doublon : un LeadEvent APPOINTMENT_REMINDER_48H /
    APPOINTMENT_REMINDER_24H est loggé après chaque envoi.
    Si l'événement existe déjà pour ce lead → on ne renvoie pas.

    À exécuter toutes les 30 minutes via Celery Beat.
    """
    now   = timezone.now()
    leads = Lead.objects.filter(
        status__code=RDV_CONFIRME,
        appointment_date__isnull=False,
    ).select_related("status")

    for lead in leads:

        delta        = lead.appointment_date - now
        hours_before = delta.total_seconds() / 3600

        if hours_before <= 0:
            continue

        # ------------------------------------------------
        # RAPPEL 48H
        # ------------------------------------------------

        if 47 <= hours_before <= 49:
            _send_reminder_if_needed(lead, reminder_type="48H")

        # ------------------------------------------------
        # RAPPEL 24H
        # ------------------------------------------------

        elif 23 <= hours_before <= 25:
            _send_reminder_if_needed(lead, reminder_type="24H")


def _send_reminder_if_needed(lead, reminder_type: str):
    """
    Vérifie l'anti-doublon via LeadEvent puis dispatche
    les tasks de rappel.
    reminder_type : "48H" ou "24H"
    """
    event_code = f"APPOINTMENT_REMINDER_{reminder_type}"

    already_sent = LeadEvent.objects.filter(
        lead=lead,
        event_type__code=event_code,
    ).exists()

    if already_sent:
        logger.debug(
            "[appointments] Rappel %s déjà envoyé — ignoré : lead_id=%s",
            reminder_type, lead.id,
        )
        return

    # --------------------------------------------------
    # SMS rappel RDV
    # --------------------------------------------------

    send_appointment_reminder_sms_task.delay(lead.id)

    logger.info(
        "[appointments] Task SMS rappel %s dispatchée : lead_id=%s",
        reminder_type, lead.id,
    )

    # --------------------------------------------------
    # WhatsApp rappel RDV (à implémenter)
    # --------------------------------------------------

    # send_appointment_reminder_whatsapp_task.delay(lead.id)

    # --------------------------------------------------
    # Email rappel RDV (à implémenter)
    # --------------------------------------------------

    # send_appointment_reminder_email_task.delay(lead.id)

    # --------------------------------------------------
    # Log de l'envoi → déclenche l'anti-doublon
    # --------------------------------------------------

    LeadEvent.log(
        lead=lead,
        event_code=event_code,
        data={
            "appointment_date": lead.appointment_date.isoformat(),
            "reminder_type":    reminder_type,
        },
    )

    logger.info(
        "[appointments] LeadEvent %s loggé : lead_id=%s",
        event_code, lead.id,
    )


# ============================================================
# 🚫 MARQUER ABSENT + DÉCLENCHER L'AUTOMATION
# ============================================================

@shared_task
def mark_absent_leads():
    """
    Marque les leads comme ABSENT si leur RDV confirmé
    est passé sans qu'ils aient été marqués présents.

    IMPORTANT : log un LeadEvent STATUS_CHANGED pour que
    l'AutomationEngine déclenche handle_status_changed()
    → envoi SMS urgence absence + création tâche rappel.

    À exécuter toutes les 30 minutes via Celery Beat.
    """
    now = timezone.now()

    try:
        absent_status = LeadStatus.objects.get(code=ABSENT)
    except LeadStatus.DoesNotExist:
        logger.error("[appointments] Statut ABSENT introuvable en base")
        return

    leads = Lead.objects.filter(
        status__code=RDV_CONFIRME,
        appointment_date__lt=now,
    ).select_related("status")

    for lead in leads:

        old_status_code = lead.status.code

        lead.status = absent_status
        lead.save(update_fields=["status"])

        logger.info(
            "[appointments] Lead #%s marqué ABSENT (RDV du %s)",
            lead.id, lead.appointment_date,
        )

        # --------------------------------------------------
        # LOG STATUS_CHANGED → déclenche AutomationEngine
        # → handle_status_changed() → SMS urgence absence
        # --------------------------------------------------

        LeadEvent.log(
            lead=lead,
            event_code="STATUS_CHANGED",
            data={
                "from": old_status_code,
                "to":   ABSENT,
            },
        )

        # Log de traçabilité RDV manqué (distinct du STATUS_CHANGED)
        LeadEvent.log(
            lead=lead,
            event_code="APPOINTMENT_MISSED",
            data={
                "appointment_date": lead.appointment_date.isoformat(),
            },
        )


@shared_task(bind=True, queue="sms")
def send_confirm_presence_flow_task(self, lead_id: int):

    lead = (
        Lead.objects
        .select_related("status")
        .filter(id=lead_id)
        .first()
    )

    if not lead:
        logger.warning("[confirm_presence] lead introuvable : %s", lead_id)
        return

    # Vérifier que le statut est toujours RDV_A_CONFIRMER
    if lead.status.code != RDV_A_CONFIRMER:
        logger.info(
            "[confirm_presence] ignoré : statut changé lead=%s status=%s",
            lead.id,
            lead.status.code
        )
        return

    # Anti-doublon
    if LeadEvent.objects.filter(
        lead=lead,
        event_type__code="CONFIRMATION_REQUEST_SENT"
    ).exists():
        logger.info(
            "[confirm_presence] déjà envoyé : lead=%s",
            lead.id
        )
        return

    # --------------------------------------------------
    # SMS
    # --------------------------------------------------

    send_confirm_presence_sms(lead)

    logger.info(
        "[confirm_presence] SMS envoyé → %s (lead #%s)",
        lead.phone,
        lead.id,
    )

    # --------------------------------------------------
    # WhatsApp
    # --------------------------------------------------

    # send_confirm_presence_whatsapp(lead)

    # --------------------------------------------------
    # Email
    # --------------------------------------------------

    # send_confirm_presence_email(lead)

    # --------------------------------------------------
    # Log automation
    # --------------------------------------------------

    LeadEvent.log(
        lead=lead,
        event_code="CONFIRMATION_REQUEST_SENT",
        data={
            "appointment_date": lead.appointment_date.isoformat()
        }
    )