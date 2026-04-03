# api/sms/notifications/leads.py

import logging

from api.sms.sender import send_sms as ovh_send_sms
from api.sms.templates.leads import (
    tpl_appointment_confirmation,
    tpl_appointment_reminder,
    tpl_absent_urgency,
    tpl_absent_followup,
    tpl_present_no_contract,
    tpl_contract_signed,
    tpl_confirm_presence,
    tpl_dossier_status_updated,
    tpl_appointment_reminder_48h,
    tpl_appointment_reminder_24h,

)

from api.sms.utils import build_sms, normalize_phone  # ✅ IMPORTANT

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------
# Envoi SMS centralisé (ULTRA IMPORTANT)
# ----------------------------------------------------------------

def _send_sms(phone: str, message: str) -> None:
    """
    Point d'envoi unique des SMS via OVH.
    - Normalise le numéro
    - Applique le pipeline SMS (GSM + 1 crédit)
    """

    phone = normalize_phone(phone)

    if not phone:
        logger.warning("[sms] téléphone invalide — SMS ignoré")
        return

    try:
        # 🔥 PIPELINE FINAL (GARANTIE 1 SMS)
        message = build_sms(message)

        ovh_send_sms(
            message=message,
            receivers=[phone]
        )

        logger.info("[sms] envoi réussi → %s", phone)

    except Exception as e:
        logger.error("[sms] Échec envoi à %s : %s", phone, str(e))


# ============================================================
# 1. CONFIRMATION RDV
# ============================================================

def send_appointment_confirmation_sms(lead) -> None:
    message = tpl_appointment_confirmation(lead)

    _send_sms(
        phone=lead.phone,
        message=message,
    )


def send_appointment_reminder_48h_sms(lead) -> None:
    message = tpl_appointment_reminder_48h(lead)
    _send_sms(phone=lead.phone, message=message)


def send_appointment_reminder_24h_sms(lead) -> None:
    message = tpl_appointment_reminder_24h(lead)
    _send_sms(phone=lead.phone, message=message)


# ============================================================
# 2. RAPPEL RDV
# ============================================================

def send_appointment_reminder_sms(lead) -> None:
    message = tpl_appointment_reminder(lead)

    _send_sms(
        phone=lead.phone,
        message=message,
    )


# ============================================================
# 3. ABSENT — URGENCE
# ============================================================

def send_absent_urgency_sms(lead) -> None:
    message = tpl_absent_urgency(lead)

    _send_sms(
        phone=lead.phone,
        message=message,
    )


# ============================================================
# 4. ABSENT — RELANCE HEBDOMADAIRE
# ============================================================

def send_absent_followup_sms(lead, week: int = 1) -> None:
    message = tpl_absent_followup(
        lead,
        week=week,
    )

    _send_sms(
        phone=lead.phone,
        message=message,
    )


# ============================================================
# 5. PRÉSENT SANS CONTRAT
# ============================================================

def send_present_no_contract_sms(lead) -> None:
    message = tpl_present_no_contract(lead)

    _send_sms(
        phone=lead.phone,
        message=message,
    )


# ============================================================
# 6. CONTRAT SIGNÉ
# ============================================================

def send_contract_signed_sms(lead) -> None:
    message = tpl_contract_signed(lead)

    _send_sms(
        phone=lead.phone,
        message=message,
    )


# ============================================================
# 7. DEMANDE CONFIRMATION PRESENCE
# ============================================================

def send_confirm_presence_sms(lead) -> None:
    message = tpl_confirm_presence(lead)

    _send_sms(
        phone=lead.phone,
        message=message,
    )


# ============================================================
# 8. DOSSIER STATUS UPDATED 🔥
# ============================================================

def send_dossier_status_updated_sms(lead) -> None:
    """
    Envoyé lors d’un changement de statut dossier.
    """

    message = tpl_dossier_status_updated(lead)

    _send_sms(
        phone=lead.phone,
        message=message,
    )