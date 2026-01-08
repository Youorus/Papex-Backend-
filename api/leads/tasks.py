import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from api.lead_status.models import LeadStatus
from api.leads.constants import ABSENT, RDV_CONFIRME
from api.leads.models import Lead

from api.utils.email import (
    send_appointment_reminder_email,
    send_missed_appointment_email,
)

from api.utils.sms.notifications.leads import (
    send_appointment_reminder_sms,
)

logger = logging.getLogger(__name__)


@shared_task
def send_reminder_emails():
    """
    Envoie un rappel J-1 pour les rendez-vous confirmés.
    👉 Email ET SMS sont envoyés ensemble.
    👉 Un seul envoi grâce au champ last_reminder_sent.
    """
    now = timezone.now()
    tomorrow = now.date() + timedelta(days=1)

    leads = Lead.objects.filter(
        status__code=RDV_CONFIRME,
        appointment_date__date=tomorrow,
    )

    for lead in leads:
        # 🔒 Anti double rappel
        if lead.last_reminder_sent:
            continue

        # 📧 EMAIL
        if lead.email:
            try:
                send_appointment_reminder_email(lead)
                logger.info(
                    f"📧 Rappel J-1 email envoyé à {lead.email} (lead #{lead.id})"
                )
            except Exception as e:
                logger.error(
                    f"❌ Erreur envoi email rappel lead #{lead.id}: {e}",
                    exc_info=True,
                )

        # 📲 SMS
        if lead.phone:
            try:
                send_appointment_reminder_sms(lead)
                logger.info(
                    f"📲 Rappel J-1 SMS envoyé à {lead.phone} (lead #{lead.id})"
                )
            except Exception as e:
                logger.error(
                    f"❌ Erreur envoi SMS rappel lead #{lead.id}: {e}",
                    exc_info=True,
                )

        # 🔒 Verrouillage APRES les deux tentatives
        lead.last_reminder_sent = now
        lead.save(update_fields=["last_reminder_sent"])


@shared_task
def mark_absent_leads():
    """
    Marque comme ABSENT les leads dont le rendez-vous confirmé est passé.
    Envoie un mail d'absence si possible.
    """
    now = timezone.now()

    try:
        absent_status = LeadStatus.objects.get(code=ABSENT)
        confirmed_status = LeadStatus.objects.get(code=RDV_CONFIRME)
    except LeadStatus.DoesNotExist:
        logger.error("❌ Statuts 'ABSENT' ou 'RDV_CONFIRME' introuvables.")
        return

    leads_to_mark = Lead.objects.filter(
        status=confirmed_status,
        appointment_date__lt=now,
    )

    for lead in leads_to_mark:
        lead.status = absent_status
        lead.save(update_fields=["status"])
        logger.info(f"✅ Lead #{lead.id} marqué comme ABSENT")

        if lead.email:
            try:
                send_missed_appointment_email(lead)
                logger.info(
                    f"📧 Mail d'absence envoyé à {lead.email} (lead #{lead.id})"
                )
            except Exception as e:
                logger.error(
                    f"❌ Erreur mail absence lead #{lead.id}: {e}",
                    exc_info=True,
                )
        else:
            logger.warning(
                f"⚠️ Email manquant pour lead #{lead.id}, pas d'envoi possible."
            )