# api/sms/tasks.py

import logging
from datetime import timedelta

from django.utils import timezone
from django.db import transaction
from django_q.tasks import async_task

from api.leads.models import Lead
from api.lead_status.models import LeadStatus
from api.leads.constants import (
    PRESENT, ABSENT, RDV_A_CONFIRMER,
    A_RAPPELER, RDV_CONFIRME, RDV_PLANIFIE
)

from api.sms.notifications.leads import (
    send_appointment_confirmation_sms,
    send_appointment_reminder_sms,
    send_absent_urgency_sms,
    send_absent_followup_sms,
    send_present_no_contract_sms,
    send_contract_signed_sms,
    send_confirm_presence_sms,
    send_dossier_status_updated_sms,
    send_appointment_reminder_48h_sms,
    send_appointment_reminder_24h_sms,
)

# ✅ IMPORT DES EMAILS AJOUTÉ
from api.utils.email.leads.tasks import (
    send_appointment_absent_email_task,
    send_appointment_reminder_email_task,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------
# Helper interne
# ----------------------------------------------------------------
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


def _has_valid_phone(lead, task_name: str) -> bool:
    """Vérifie si le lead a un numéro de téléphone valide"""
    if not lead.phone:
        logger.warning(f"[{task_name}] Lead #{lead.id} n'a pas de numéro de téléphone")
        return False
    return True


# ================================================================
# WORKERS (TOUJOURS AVEC **kwargs)
# ================================================================

def _run_send_appointment_confirmation_sms(lead_id: int, **kwargs):
    lead = _get_lead(lead_id, "sms_confirmation")
    if not lead or not _has_valid_phone(lead, "sms_confirmation"):
        return
    send_appointment_confirmation_sms(lead)
    logger.info("[sms_confirmation] → %s (lead #%s)", lead.phone, lead.id)


def _run_send_appointment_reminder_sms(lead_id: int, **kwargs):
    lead = _get_lead(lead_id, "sms_reminder")
    if not lead or not _has_valid_phone(lead, "sms_reminder"):
        return
    send_appointment_reminder_sms(lead)
    logger.info("[sms_reminder] → %s (lead #%s)", lead.phone, lead.id)


def _run_send_appointment_reminder_48h_sms(lead_id: int, **kwargs):
    lead = _get_lead(lead_id, "sms_reminder_48h")
    if not lead or not _has_valid_phone(lead, "sms_reminder_48h"):
        return
    send_appointment_reminder_48h_sms(lead)
    logger.info("[sms_reminder_48h] → %s (lead #%s)", lead.phone, lead.id)


def _run_send_appointment_reminder_24h_sms(lead_id: int, **kwargs):
    lead = _get_lead(lead_id, "sms_reminder_24h")
    if not lead or not _has_valid_phone(lead, "sms_reminder_24h"):
        return
    send_appointment_reminder_24h_sms(lead)
    logger.info("[sms_reminder_24h] → %s (lead #%s)", lead.phone, lead.id)


def _run_send_absent_urgency_sms(lead_id: int, **kwargs):
    lead = _get_lead(lead_id, "sms_absent_urgency")
    if not lead or not _has_valid_phone(lead, "sms_absent_urgency"):
        return
    send_absent_urgency_sms(lead)
    logger.info("[sms_absent_urgency] → %s (lead #%s)", lead.phone, lead.id)


def _run_send_absent_followup_sms(lead_id: int, week: int = 1, **kwargs):
    lead = _get_lead(lead_id, "sms_absent_followup")
    if not lead or not _has_valid_phone(lead, "sms_absent_followup"):
        return
    send_absent_followup_sms(lead, week=week)
    logger.info(
        "[sms_absent_followup] semaine=%s → %s (lead #%s)",
        week, lead.phone, lead.id,
    )


def _run_send_present_no_contract_sms(lead_id: int, **kwargs):
    lead = _get_lead(lead_id, "sms_present_no_contract")
    if not lead or not _has_valid_phone(lead, "sms_present_no_contract"):
        return
    send_present_no_contract_sms(lead)
    logger.info("[sms_present_no_contract] → %s (lead #%s)", lead.phone, lead.id)


def _run_send_contract_signed_sms(lead_id: int, **kwargs):
    lead = _get_lead(lead_id, "sms_contract_signed")
    if not lead or not _has_valid_phone(lead, "sms_contract_signed"):
        return
    send_contract_signed_sms(lead)
    logger.info("[sms_contract_signed] → %s (lead #%s)", lead.phone, lead.id)


def _run_send_confirm_presence_sms(lead_id: int, **kwargs):
    lead = _get_lead(lead_id, "sms_confirm_presence")
    if not lead or not _has_valid_phone(lead, "sms_confirm_presence"):
        return
    send_confirm_presence_sms(lead)
    logger.info("[sms_confirm_presence] → %s (lead #%s)", lead.phone, lead.id)


def _run_send_dossier_status_updated_sms(lead_id: int, **kwargs):
    lead = _get_lead(lead_id, "sms_dossier_status_updated")
    if not lead or not _has_valid_phone(lead, "sms_dossier_status_updated"):
        return
    send_dossier_status_updated_sms(lead)
    logger.info(
        "[sms_dossier_status_updated] → %s (lead #%s)",
        lead.phone, lead.id,
    )


# ================================================================
# DISPATCHERS
# ================================================================

def send_appointment_confirmation_sms_task(lead_id: int):
    async_task(
        "api.sms.tasks._run_send_appointment_confirmation_sms",
        lead_id,
        group="sms",
    )


def send_appointment_reminder_sms_task(lead_id: int):
    async_task(
        "api.sms.tasks._run_send_appointment_reminder_sms",
        lead_id,
        group="sms",
    )


def send_appointment_reminder_48h_sms_task(lead_id: int):
    async_task(
        "api.sms.tasks._run_send_appointment_reminder_48h_sms",
        lead_id,
        group="sms",
    )


def send_appointment_reminder_24h_sms_task(lead_id: int):
    async_task(
        "api.sms.tasks._run_send_appointment_reminder_24h_sms",
        lead_id,
        group="sms",
    )


def send_absent_urgency_sms_task(lead_id: int):
    async_task(
        "api.sms.tasks._run_send_absent_urgency_sms",
        lead_id,
        group="sms",
    )


def send_absent_followup_sms_task(lead_id: int, week: int = 1):
    async_task(
        "api.sms.tasks._run_send_absent_followup_sms",
        lead_id,
        week,
        group="sms",
    )


def send_present_no_contract_sms_task(lead_id: int, countdown: int = 0):
    kwargs = {"group": "sms"}

    if countdown:
        kwargs["scheduled"] = timezone.now() + timedelta(seconds=countdown)

    async_task(
        "api.sms.tasks._run_send_present_no_contract_sms",
        lead_id,
        **kwargs,
    )


def send_contract_signed_sms_task(lead_id: int, countdown: int = 0):
    kwargs = {"group": "sms"}

    if countdown:
        kwargs["scheduled"] = timezone.now() + timedelta(seconds=countdown)

    async_task(
        "api.sms.tasks._run_send_contract_signed_sms",
        lead_id,
        **kwargs,
    )


def send_confirm_presence_sms_task(lead_id: int, countdown: int = 0):
    kwargs = {"group": "sms"}

    if countdown:
        kwargs["scheduled"] = timezone.now() + timedelta(seconds=countdown)

    async_task(
        "api.sms.tasks._run_send_confirm_presence_sms",
        lead_id,
        **kwargs,
    )


def send_dossier_status_updated_sms_task(lead_id: int):
    async_task(
        "api.sms.tasks._run_send_dossier_status_updated_sms",
        lead_id,
        group="sms",
    )


# ================================================================
# FONCTIONS DE RELANCE (utilisent les dispatchers)
# ================================================================

def mark_missed_appointments_as_absent():
    """Passe les leads en ABSENT si RDV passé et non PRESENT"""

    now = timezone.now()

    try:
        absent_status = LeadStatus.objects.get(code=ABSENT)
    except LeadStatus.DoesNotExist:
        logger.error("Status ABSENT non trouvé")
        return "0 leads updated - Status ABSENT missing"

    leads_qs = Lead.objects.filter(
        appointment_date__isnull=False,
        appointment_date__lt=now,
    ).exclude(
        status__code__in=[PRESENT, ABSENT]
    )

    lead_ids = list(leads_qs.values_list("id", flat=True))

    if not lead_ids:
        logger.info("Aucun lead à marquer comme absent")
        return "0 leads updated"

    with transaction.atomic():
        updated_count = leads_qs.update(status=absent_status)

    # 🚀 Notifications async (SMS + EMAIL)
    for lead_id in lead_ids:
        send_absent_urgency_sms_task(lead_id)
        send_appointment_absent_email_task(lead_id)  # ✅ ACTIVÉ

    logger.info(f"{updated_count} leads marqués absents, notifications envoyées")
    return f"{updated_count} leads marked as ABSENT + SMS + EMAIL sent"


def send_appointment_reminders():
    """
    Envoie des rappels de rendez-vous :
    - 48h avant → SMS + EMAIL
    - 24h avant → SMS + EMAIL

    Anti-doublon inclus
    """

    now = timezone.now()
    reminder_windows = [
        (timedelta(hours=48), "48h", send_appointment_reminder_48h_sms_task),
        (timedelta(hours=24), "24h", send_appointment_reminder_24h_sms_task),
    ]

    tolerance = timedelta(minutes=5)
    total_sent = 0

    for delta, label, sms_task_func in reminder_windows:
        target_time = now + delta
        window_start = target_time - tolerance
        window_end = target_time + tolerance

        leads = Lead.objects.filter(
            appointment_date__gte=window_start,
            appointment_date__lte=window_end,
            status__code__in=[RDV_CONFIRME, RDV_PLANIFIE],
        )

        for lead in leads:
            # 🔒 Anti doublon
            if lead.last_reminder_sent:
                if (now - lead.last_reminder_sent) < timedelta(hours=20):
                    logger.debug(f"Lead #{lead.id} - anti-doublon actif")
                    continue

            # 🚀 Envoi SMS + EMAIL
            sms_task_func(lead.id)
            send_appointment_reminder_email_task(lead.id)  # ✅ ACTIVÉ

            # 🧠 Tracking
            lead.last_reminder_sent = now
            lead.save(update_fields=["last_reminder_sent"])

            total_sent += 1
            logger.info(f"Rappel {label} envoyé (SMS+EMAIL) pour lead #{lead.id}")

    logger.info(f"Total rappels envoyés : {total_sent}")
    return f"{total_sent} reminders sent (SMS+EMAIL)"