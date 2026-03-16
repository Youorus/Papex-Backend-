# api/sms/notifications/leads.py

import logging

from api.sms.templates.leads import (
    tpl_appointment_confirmation,
    tpl_appointment_reminder,
    tpl_absent_urgency,
    tpl_absent_followup,
    tpl_present_no_contract,
    tpl_contract_signed, tpl_confirm_presence,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------
# Envoi SMS centralisé
# ----------------------------------------------------------------

def _send_sms(phone: str, message: str) -> None:
    """
    Point d'envoi unique des SMS.

    C'est ici que tu branches ton provider :
        - Twilio
        - OVH
        - MessageBird
        - Orange SMS
        - autre

    Pour l'instant on log seulement le SMS.
    """

    if not phone:
        logger.warning("[sms] téléphone manquant — SMS ignoré")
        return

    # Exemple futur :
    # sms_provider.send(to=phone, body=message)

    logger.info(
        "[sms] envoi → %s\n%s",
        phone,
        message,
    )


# ============================================================
# 1. CONFIRMATION RDV
# ============================================================

def send_appointment_confirmation_sms(lead) -> None:
    """
    Envoie le SMS de confirmation de RDV.
    """

    message = tpl_appointment_confirmation(lead)

    _send_sms(
        phone=lead.phone,
        message=message,
    )


# ============================================================
# 2. RAPPEL RDV
# ============================================================

def send_appointment_reminder_sms(lead) -> None:
    """
    Envoie le SMS de rappel de RDV (24h avant).
    """

    message = tpl_appointment_reminder(lead)

    _send_sms(
        phone=lead.phone,
        message=message,
    )


# ============================================================
# 3. ABSENT — URGENCE
# ============================================================

def send_absent_urgency_sms(lead) -> None:
    """
    Envoie le SMS si le client est absent au RDV.
    """

    message = tpl_absent_urgency(lead)

    _send_sms(
        phone=lead.phone,
        message=message,
    )


# ============================================================
# 4. ABSENT — RELANCE HEBDOMADAIRE
# ============================================================

def send_absent_followup_sms(lead, week: int = 1) -> None:
    """
    Relance hebdomadaire pour lead absent.
    """

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
    """
    Envoyé après un RDV sans signature.
    """

    message = tpl_present_no_contract(lead)

    _send_sms(
        phone=lead.phone,
        message=message,
    )


# ============================================================
# 6. CONTRAT SIGNÉ
# ============================================================

def send_contract_signed_sms(lead) -> None:
    """
    Envoyé après signature du contrat.
    """

    message = tpl_contract_signed(lead)

    _send_sms(
        phone=lead.phone,
        message=message,
    )

# ============================================================
# 7. DEMANDE CONFIRMATION PRESENCE
# ============================================================

def send_confirm_presence_sms(lead) -> None:
    """
    SMS demandant au client de confirmer sa présence.
    """

    message = tpl_confirm_presence(lead)

    _send_sms(
        phone=lead.phone,
        message=message,
    )