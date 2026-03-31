# api/sms/tasks.py
# ✅ Migré de Celery (@shared_task / .delay()) vers Django-Q2 (async_task)

import logging

from django_q.tasks import async_task

from api.leads.models import Lead

from api.sms.notifications.leads import (
    send_appointment_confirmation_sms,
    send_appointment_reminder_sms,
    send_absent_urgency_sms,
    send_absent_followup_sms,
    send_present_no_contract_sms,
    send_contract_signed_sms,
    send_confirm_presence_sms,
    send_dossier_status_updated_sms,
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
# Fonctions exécutées par les workers Django-Q2
# (appelées via async_task — pas de décorateur requis)
# ================================================================

def _run_send_appointment_confirmation_sms(lead_id: int):
    lead = _get_lead(lead_id, "sms_confirmation")
    if not lead:
        return
    send_appointment_confirmation_sms(lead)
    logger.info("[sms_confirmation] → %s (lead #%s)", lead.phone, lead.id)


def _run_send_appointment_reminder_sms(lead_id: int):
    lead = _get_lead(lead_id, "sms_reminder")
    if not lead:
        return
    send_appointment_reminder_sms(lead)
    logger.info("[sms_reminder] → %s (lead #%s)", lead.phone, lead.id)


def _run_send_absent_urgency_sms(lead_id: int):
    lead = _get_lead(lead_id, "sms_absent_urgency")
    if not lead:
        return
    send_absent_urgency_sms(lead)
    logger.info("[sms_absent_urgency] → %s (lead #%s)", lead.phone, lead.id)


def _run_send_absent_followup_sms(lead_id: int, week: int = 1):
    lead = _get_lead(lead_id, "sms_absent_followup")
    if not lead:
        return
    send_absent_followup_sms(lead, week=week)
    logger.info(
        "[sms_absent_followup] semaine=%s → %s (lead #%s)",
        week, lead.phone, lead.id,
    )


def _run_send_present_no_contract_sms(lead_id: int):
    lead = _get_lead(lead_id, "sms_present_no_contract")
    if not lead:
        return
    send_present_no_contract_sms(lead)
    logger.info("[sms_present_no_contract] → %s (lead #%s)", lead.phone, lead.id)


def _run_send_contract_signed_sms(lead_id: int):
    lead = _get_lead(lead_id, "sms_contract_signed")
    if not lead:
        return
    send_contract_signed_sms(lead)
    logger.info("[sms_contract_signed] → %s (lead #%s)", lead.phone, lead.id)


def _run_send_confirm_presence_sms(lead_id: int):
    lead = _get_lead(lead_id, "sms_confirm_presence")
    if not lead:
        return
    send_confirm_presence_sms(lead)
    logger.info("[sms_confirm_presence] → %s (lead #%s)", lead.phone, lead.id)


def _run_send_dossier_status_updated_sms(lead_id: int):
    lead = _get_lead(lead_id, "sms_dossier_status_updated")
    if not lead:
        return
    send_dossier_status_updated_sms(lead)
    logger.info(
        "[sms_dossier_status_updated] → %s (lead #%s)",
        lead.phone, lead.id,
    )


# ================================================================
# API publique — fonctions de dispatch
# Appelées depuis les handlers / views (remplacent le .delay())
# ================================================================

def send_appointment_confirmation_sms_task(lead_id: int):
    """Envoie immédiatement le SMS de confirmation RDV."""
    async_task(
        "api.sms.tasks._run_send_appointment_confirmation_sms",
        lead_id,
        group="sms",
    )


def send_appointment_reminder_sms_task(lead_id: int):
    """Envoie immédiatement le SMS de rappel RDV."""
    async_task(
        "api.sms.tasks._run_send_appointment_reminder_sms",
        lead_id,
        group="sms",
    )


def send_absent_urgency_sms_task(lead_id: int):
    """Envoie immédiatement le SMS d'urgence absent."""
    async_task(
        "api.sms.tasks._run_send_absent_urgency_sms",
        lead_id,
        group="sms",
    )


def send_absent_followup_sms_task(lead_id: int, week: int = 1):
    """Envoie immédiatement le SMS de relance absent."""
    async_task(
        "api.sms.tasks._run_send_absent_followup_sms",
        lead_id,
        week,
        group="sms",
    )


def send_present_no_contract_sms_task(lead_id: int, countdown: int = 0):
    """
    Envoie le SMS "présent sans contrat".
    countdown : délai en secondes avant exécution (ex: 7200 pour +2h).
    """
    from django_q.tasks import async_task as _async
    kwargs = {"group": "sms"}
    if countdown:
        from django.utils import timezone
        from datetime import timedelta
        kwargs["scheduled"] = timezone.now() + timedelta(seconds=countdown)

    _async(
        "api.sms.tasks._run_send_present_no_contract_sms",
        lead_id,
        **kwargs,
    )


def send_contract_signed_sms_task(lead_id: int, countdown: int = 0):
    """
    Envoie le SMS de félicitations contrat signé.
    countdown : délai en secondes (ex: 10 pour +10s).
    """
    from django_q.tasks import async_task as _async
    kwargs = {"group": "sms"}
    if countdown:
        from django.utils import timezone
        from datetime import timedelta
        kwargs["scheduled"] = timezone.now() + timedelta(seconds=countdown)

    _async(
        "api.sms.tasks._run_send_contract_signed_sms",
        lead_id,
        **kwargs,
    )


def send_confirm_presence_sms_task(lead_id: int, countdown: int = 0):
    """
    Envoie le SMS de confirmation de présence.
    countdown : délai en secondes (ex: 7200 pour +2h).
    """
    from django_q.tasks import async_task as _async
    kwargs = {"group": "sms"}
    if countdown:
        from django.utils import timezone
        from datetime import timedelta
        kwargs["scheduled"] = timezone.now() + timedelta(seconds=countdown)

    _async(
        "api.sms.tasks._run_send_confirm_presence_sms",
        lead_id,
        **kwargs,
    )


def send_dossier_status_updated_sms_task(lead_id: int):
    """Envoie immédiatement le SMS de changement de statut dossier."""
    async_task(
        "api.sms.tasks._run_send_dossier_status_updated_sms",
        lead_id,
        group="sms",
    )