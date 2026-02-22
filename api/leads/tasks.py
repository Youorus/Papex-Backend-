import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from api.lead_status.models import LeadStatus
from api.leads.constants import ABSENT, RDV_CONFIRME
from api.leads.models import Lead
from api.sms.notifications.leads import send_appointment_reminder_sms
from api.utils.email import (
    send_appointment_reminder_email,
    send_missed_appointment_email,
)

logger = logging.getLogger(__name__)


# ============================================================
# ⏰ RAPPEL J-1 — EMAIL + SMS
# ============================================================

@shared_task
def send_appointment_reminders():
    """
    Envoie un rappel un jour avant le rendez-vous confirmé par Email et SMS.
    (Tourne via Celery Beat, idéalement une fois par jour vers 07h00).
    """
    now = timezone.now()
    tomorrow = now.date() + timedelta(days=1)

    # 1. On cherche les RDV confirmés prévus demain qui n'ont pas encore eu de rappel
    leads = Lead.objects.filter(
        status__code=RDV_CONFIRME,
        appointment_date__date=tomorrow,
        last_reminder_sent__isnull=True,
    )

    if not leads.exists():
        logger.info("📭 Aucun rappel à envoyer pour les rendez-vous de demain.")
        return

    for lead in leads:
        email_ok = False
        sms_ok = False

        # Envoi Email
        if lead.email:
            try:
                send_appointment_reminder_email(lead)
                email_ok = True
                logger.info(f"📧 Email de rappel envoyé à {lead.email} (lead #{lead.id})")
            except Exception as e:
                logger.error(f"❌ Erreur lors de l'envoi de l'email à {lead.email}: {e}")

        # Envoi SMS
        if lead.phone:
            try:
                send_appointment_reminder_sms(lead)
                sms_ok = True
                logger.info(f"📱 SMS de rappel envoyé au {lead.phone} (lead #{lead.id})")
            except Exception as e:
                logger.error(f"❌ Erreur lors de l'envoi du SMS au {lead.phone}: {e}")

        # Mise à jour si au moins une notification est partie
        if email_ok or sms_ok:
            lead.last_reminder_sent = now
            lead.save(update_fields=["last_reminder_sent"])


# ============================================================
# 🚫 MARQUER ABSENT + EMAIL
# ============================================================

@shared_task
def mark_absent_leads():
    """
    Tâche pour marquer comme absents les leads dont le rendez-vous confirmé est passé.
    Un mail d'absence est envoyé si l'email du lead est présent.
    """
    now = timezone.now()

    # Sécuriser la récupération du statut au cas où la base serait vide
    try:
        absent_status = LeadStatus.objects.get(code=ABSENT)
    except LeadStatus.DoesNotExist:
        logger.error("❌ Statut 'ABSENT' introuvable dans la base de données.")
        return

    # On cible les RDV confirmés dont la date est dépassée
    leads_to_mark = Lead.objects.filter(
        status__code=RDV_CONFIRME,
        appointment_date__lt=now,
    )

    for lead in leads_to_mark:
        lead.status = absent_status
        lead.save(update_fields=["status"])
        logger.info(f"✅ Lead #{lead.id} marqué comme ABSENT")

        # Envoi de l'email d'absence
        if lead.email:
            try:
                send_missed_appointment_email(lead)
                logger.info(f"📧 Mail d'absence envoyé à {lead.email} (lead #{lead.id})")
            except Exception as e:
                logger.error(f"❌ Erreur lors de l'envoi du mail d'absence à {lead.email}: {e}")