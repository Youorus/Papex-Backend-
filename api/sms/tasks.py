# api/sms/tasks.py

import logging
from celery import shared_task

from api.leads.models import Lead

from api.sms.notifications.leads import (
    send_appointment_confirmation_sms,
    send_appointment_reminder_sms,
    send_absent_urgency_sms,
    send_absent_followup_sms,
    send_present_no_contract_sms,
    send_contract_signed_sms,
    send_confirm_presence_sms,
    send_dossier_status_updated_sms,  # ✅ AJOUT
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------
# Helper interne
# ----------------------------------------------------------------

def _get_lead(lead_id: int, task_name: str):
    """
    Récupère le lead avec les relations nécessaires aux templates SMS.
    """

    lead = (
        Lead.objects
        .select_related("status", "statut_dossier")  # ✅ OPTI
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


# ============================================================
# 1. SMS — CONFIRMATION RDV
# ============================================================

@shared_task(bind=True, queue="sms")
def send_appointment_confirmation_sms_task(self, lead_id: int):
    lead = _get_lead(lead_id, "sms_confirmation")

    if not lead:
        return

    send_appointment_confirmation_sms(lead)

    logger.info("[sms_confirmation] → %s (lead #%s)", lead.phone, lead.id)


# ============================================================
# 2. SMS — RAPPEL RDV
# ============================================================

@shared_task(bind=True, queue="sms")
def send_appointment_reminder_sms_task(self, lead_id: int):
    lead = _get_lead(lead_id, "sms_reminder")

    if not lead:
        return

    send_appointment_reminder_sms(lead)

    logger.info("[sms_reminder] → %s (lead #%s)", lead.phone, lead.id)


# ============================================================
# 3. SMS — ABSENT URGENCE
# ============================================================

@shared_task(bind=True, queue="sms")
def send_absent_urgency_sms_task(self, lead_id: int):
    lead = _get_lead(lead_id, "sms_absent_urgency")

    if not lead:
        return

    send_absent_urgency_sms(lead)

    logger.info("[sms_absent_urgency] → %s (lead #%s)", lead.phone, lead.id)


# ============================================================
# 4. SMS — RELANCE ABSENT
# ============================================================

@shared_task(bind=True, queue="sms")
def send_absent_followup_sms_task(self, lead_id: int, week: int = 1):
    lead = _get_lead(lead_id, "sms_absent_followup")

    if not lead:
        return

    send_absent_followup_sms(lead, week=week)

    logger.info(
        "[sms_absent_followup] semaine=%s → %s (lead #%s)",
        week,
        lead.phone,
        lead.id,
    )


# ============================================================
# 5. SMS — PRESENT SANS CONTRAT
# ============================================================

@shared_task(bind=True, queue="sms")
def send_present_no_contract_sms_task(self, lead_id: int):
    lead = _get_lead(lead_id, "sms_present_no_contract")

    if not lead:
        return

    send_present_no_contract_sms(lead)

    logger.info("[sms_present_no_contract] → %s (lead #%s)", lead.phone, lead.id)


# ============================================================
# 6. SMS — CONTRAT SIGNE
# ============================================================

@shared_task(bind=True, queue="sms")
def send_contract_signed_sms_task(self, lead_id: int):
    lead = _get_lead(lead_id, "sms_contract_signed")

    if not lead:
        return

    send_contract_signed_sms(lead)

    logger.info("[sms_contract_signed] → %s (lead #%s)", lead.phone, lead.id)


# ============================================================
# 7. SMS — CONFIRMATION PRESENCE RDV
# ============================================================

@shared_task(bind=True, queue="sms")
def send_confirm_presence_sms_task(self, lead_id: int):
    lead = _get_lead(lead_id, "sms_confirm_presence")

    if not lead:
        return

    send_confirm_presence_sms(lead)

    logger.info("[sms_confirm_presence] → %s (lead #%s)", lead.phone, lead.id)


# ============================================================
# 8. SMS — DOSSIER STATUS UPDATED 🔥
# ============================================================

@shared_task(bind=True, queue="sms")
def send_dossier_status_updated_sms_task(self, lead_id: int):
    """
    Envoyé lors d’un changement de statut dossier.
    """

    lead = _get_lead(lead_id, "sms_dossier_status_updated")

    if not lead:
        return

    send_dossier_status_updated_sms(lead)

    logger.info(
        "[sms_dossier_status_updated] → %s (lead #%s)",
        lead.phone,
        lead.id,
    )