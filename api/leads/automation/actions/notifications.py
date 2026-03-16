import logging

from api.utils.email import send_html_email

logger = logging.getLogger(__name__)


# --------------------------------------------------
# EMAIL BIENVENUE
# --------------------------------------------------

def send_welcome_email(lead):
    if not lead.email:
        logger.info(
            "[send_welcome_email] Pas d'email — ignoré : lead_id=%s", lead.id
        )
        return

    try:
        send_html_email(
            lead.email,
            "Bienvenue chez Papiers Express",
            "emails/welcome.html",
            {"lead": lead},
        )
        logger.info(
            "[send_welcome_email] Email envoyé → %s (lead_id=%s)",
            lead.email, lead.id,
        )
    except Exception as e:
        logger.error(
            "[send_welcome_email] Échec email lead_id=%s : %s", lead.id, e
        )


# --------------------------------------------------
# SMS CONFIRMATION RDV
# --------------------------------------------------

def send_appointment_confirmation_if_needed(lead, event):
    """
    Dispatche la task Celery de confirmation RDV sous trois conditions :
      1. Le lead a un téléphone
      2. Le lead a une appointment_date
      3. Ce SMS n'a pas déjà été envoyé pour cette date précise

    Anti-doublon via LeadEvent APPOINTMENT_CONFIRMATION_SENT.
    Si la date change → nouveau SMS autorisé.
    """
    from api.leads_events.models import LeadEvent
    from api.leads.constants import RDV_A_CONFIRMER
    from api.sms.notifications.leads import send_appointment_confirmation_sms_task

    if not lead.phone:
        logger.info(
            "[send_appointment_confirmation_if_needed] Pas de téléphone — ignoré : lead_id=%s",
            lead.id,
        )
        return

    if not lead.appointment_date:
        logger.info(
            "[send_appointment_confirmation_if_needed] Pas de date RDV — ignoré : lead_id=%s",
            lead.id,
        )
        return

    if not lead.status or lead.status.code != RDV_A_CONFIRMER:
        logger.info(
            "[send_appointment_confirmation_if_needed] Statut (%s) != RDV_A_CONFIRMER — ignoré : lead_id=%s",
            getattr(lead.status, "code", None), lead.id,
        )
        return

    # Anti-doublon : déjà envoyé pour cette date exacte ?
    appointment_date_str = lead.appointment_date.isoformat()

    already_sent = LeadEvent.objects.filter(
        lead=lead,
        event_type__code="APPOINTMENT_CONFIRMATION_SENT",
        data__appointment_date=appointment_date_str,
    ).exists()

    if already_sent:
        logger.info(
            "[send_appointment_confirmation_if_needed] Déjà envoyé pour cette date (%s) — ignoré : lead_id=%s",
            appointment_date_str, lead.id,
        )
        return

    # Dispatch Celery
    send_appointment_confirmation_sms_task.delay(lead.id)

    logger.info(
        "[send_appointment_confirmation_if_needed] Task SMS dispatchée → lead_id=%s | date=%s",
        lead.id, appointment_date_str,
    )

    # Trace l'envoi pour la déduplication
    LeadEvent.log(
        lead=lead,
        event_code="APPOINTMENT_CONFIRMATION_SENT",
        actor=None,
        data={"appointment_date": appointment_date_str},
    )