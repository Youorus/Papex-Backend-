"""
api/leads/tasks/appointments.py

Gestion automatique des rendez-vous :
  - Rappels SMS intelligents 48h et 24h avant le RDV
  - Marquage automatique ABSENT si RDV passé sans présence
  - Relance hebdomadaire des absents
"""

import logging
from datetime import timedelta
from django.utils import timezone
from celery import shared_task

from api.leads.models import Lead
from api.leads.constants import RDV_CONFIRME, ABSENT, RDV_A_CONFIRMER
from api.lead_status.models import LeadStatus
from api.leads_events.models import LeadEvent

from api.sms.notifications.leads import send_confirm_presence_sms
from api.sms.tasks import (
    send_appointment_reminder_sms_task,
    send_absent_followup_sms_task
)

# from api.whatsapp.tasks import send_appointment_reminder_whatsapp_task
# from api.email.tasks import send_appointment_reminder_email_task

logger = logging.getLogger(__name__)


# ============================================================
# 🔔 1. RAPPELS INTELLIGENTS (48h et 24h avant le RDV)
# ============================================================

@shared_task
def process_appointment_reminders():
    """
    Vérifie tous les leads avec RDV confirmé et envoie les rappels 48h et 24h avant.
    Exécution : Toutes les 30 minutes via Celery Beat.
    """
    now = timezone.now()

    # ⚡️ OPTIMISATION RENDER : .iterator(chunk_size=100) évite l'erreur OOM
    leads = Lead.objects.filter(
        status__code=RDV_CONFIRME,
        appointment_date__isnull=False,
    ).select_related("status").iterator(chunk_size=100)

    for lead in leads:

        delta = lead.appointment_date - now
        hours_before = delta.total_seconds() / 3600

        if hours_before <= 0:
            continue

        # RAPPEL 48H
        if 47 <= hours_before <= 49:
            _send_reminder_if_needed(lead, reminder_type="48H")

        # RAPPEL 24H
        elif 23 <= hours_before <= 25:
            _send_reminder_if_needed(lead, reminder_type="24H")


def _send_reminder_if_needed(lead, reminder_type: str):
    """Vérifie l'anti-doublon via LeadEvent puis dispatche les tasks de rappel."""
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

    # SMS rappel RDV
    send_appointment_reminder_sms_task.delay(lead.id)

    logger.info(
        "[appointments] Task SMS rappel %s dispatchée : lead_id=%s",
        reminder_type, lead.id,
    )

    # Log de l'envoi → déclenche l'anti-doublon
    LeadEvent.log(
        lead=lead,
        event_code=event_code,
        data={
            "appointment_date": lead.appointment_date.isoformat(),
            "reminder_type": reminder_type,
        },
    )


# ============================================================
# 🚫 2. MARQUER ABSENT + DÉCLENCHER L'AUTOMATION
# ============================================================

@shared_task
def mark_absent_leads():
    """
    Marque les leads comme ABSENT si leur RDV confirmé est passé.
    Exécution : Toutes les 30 minutes via Celery Beat.
    """
    now = timezone.now()

    try:
        absent_status = LeadStatus.objects.get(code=ABSENT)
    except LeadStatus.DoesNotExist:
        logger.error("[appointments] Statut ABSENT introuvable en base")
        return

    # ⚡️ OPTIMISATION RENDER : .iterator(chunk_size=100) évite l'erreur OOM
    leads = Lead.objects.filter(
        status__code=RDV_CONFIRME,
        appointment_date__lt=now,
    ).select_related("status").iterator(chunk_size=100)

    for lead in leads:

        old_status_code = lead.status.code

        lead.status = absent_status
        lead.save(update_fields=["status"])

        logger.info(
            "[appointments] Lead #%s marqué ABSENT (RDV du %s)",
            lead.id, lead.appointment_date,
        )

        # LOG STATUS_CHANGED → déclenche l'envoi du SMS urgence absence
        LeadEvent.log(
            lead=lead,
            event_code="STATUS_CHANGED",
            data={
                "from": old_status_code,
                "to": ABSENT,
            },
        )

        LeadEvent.log(
            lead=lead,
            event_code="APPOINTMENT_MISSED",
            data={"appointment_date": lead.appointment_date.isoformat()},
        )


# ============================================================
# 🔄 3. RELANCE HEBDOMADAIRE DES ABSENTS (Nouveau !)
# ============================================================

@shared_task
def process_absent_leads_followup():
    """
    Relance les leads ABSENTS depuis exactement 7 jours.
    Exécution conseillée : Tous les jours à 10h00 via Celery Beat.
    """
    seven_days_ago = timezone.now() - timedelta(days=7)

    # ⚡️ OPTIMISATION RENDER : .iterator()
    leads_to_followup = Lead.objects.filter(
        status__code=ABSENT,
        appointment_date__date=seven_days_ago.date()
    ).iterator(chunk_size=100)

    count = 0
    for lead in leads_to_followup:
        # Envoi de la relance Semaine 1
        send_absent_followup_sms_task.delay(lead.id, week=1)
        count += 1

    if count > 0:
        logger.info(f"[appointments] {count} relances hebdomadaires envoyées aux absents.")


# ============================================================
# ❓ 4. CONFIRMATION PRESENCE RDV (H+2)
# ============================================================

@shared_task(bind=True, queue="sms")
def send_confirm_presence_flow_task(self, lead_id: int):
    """
    Envoyé 2h après la création du RDV pour demander confirmation explicite.
    """
    lead = Lead.objects.select_related("status").filter(id=lead_id).first()

    if not lead:
        return

    if lead.status.code != RDV_A_CONFIRMER:
        return

    if LeadEvent.objects.filter(lead=lead, event_type__code="CONFIRMATION_REQUEST_SENT").exists():
        return

    send_confirm_presence_sms(lead)

    logger.info("[confirm_presence] SMS envoyé → %s (lead #%s)", lead.phone, lead.id)

    LeadEvent.log(
        lead=lead,
        event_code="CONFIRMATION_REQUEST_SENT",
        data={"appointment_date": lead.appointment_date.isoformat()}
    )