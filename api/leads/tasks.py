import logging
from datetime import datetime, timedelta, time

from celery import shared_task
from django.db import transaction
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

@shared_task(bind=True)
def send_reminder_notifications(self):
    """
    Envoie le rappel J-1 pour les rendez-vous confirmés.

    Garanties :
    - J-1 réel (timezone Europe/Paris)
    - aucun doublon
    - safe multi-workers
    - email et SMS indépendants
    """

    now = timezone.now()
    tomorrow = timezone.localdate() + timedelta(days=1)

    start = timezone.make_aware(datetime.combine(tomorrow, time.min))
    end = timezone.make_aware(datetime.combine(tomorrow, time.max))

    leads = Lead.objects.filter(
        status__code=RDV_CONFIRME,
        appointment_date__range=(start, end),
        last_reminder_sent__isnull=True,
    )

    logger.info(f"🔔 Rappel J-1 — {leads.count()} lead(s) trouvé(s)")

    for lead in leads:
        # 🔒 verrou transactionnel anti double envoi
        with transaction.atomic():
            lead = Lead.objects.select_for_update().get(pk=lead.pk)

            if lead.last_reminder_sent:
                continue

            lead.last_reminder_sent = now
            lead.save(update_fields=["last_reminder_sent"])

        logger.info(f"➡️ Rappel envoyé au lead #{lead.id}")

        # =========================
        # 📧 EMAIL
        # =========================
        if lead.email:
            try:
                send_appointment_reminder_email(lead)
                logger.info(
                    f"📧 Email rappel envoyé à {lead.email} (lead #{lead.id})"
                )
            except Exception:
                logger.exception(
                    f"❌ Erreur email rappel lead #{lead.id}"
                )

        # =========================
        # 📲 SMS
        # =========================
        if lead.phone:
            try:
                send_appointment_reminder_sms(lead)
                logger.info(
                    f"📲 SMS rappel envoyé à {lead.phone} (lead #{lead.id})"
                )
            except Exception:
                logger.exception(
                    f"❌ Erreur SMS rappel lead #{lead.id}"
                )


# ============================================================
# 🚫 MARQUER ABSENT + EMAIL
# ============================================================

@shared_task(bind=True)
def mark_absent_leads(self):
    """
    Marque les leads comme ABSENT lorsque le rendez-vous est passé.

    Le changement de statut sert de verrou métier :
    un lead déjà ABSENT ne sera jamais retraité.
    """

    now = timezone.now()

    try:
        absent_status = LeadStatus.objects.get(code=ABSENT)
    except LeadStatus.DoesNotExist:
        logger.error("❌ Statut ABSENT introuvable")
        return

    leads = Lead.objects.filter(
        status__code=RDV_CONFIRME,
        appointment_date__lt=now,
    )

    logger.info(f"🚫 Marquage ABSENT — {leads.count()} lead(s) à traiter")

    for lead in leads:
        with transaction.atomic():
            lead = Lead.objects.select_for_update().get(pk=lead.pk)

            # déjà traité
            if lead.status.code == ABSENT:
                continue

            lead.status = absent_status
            lead.save(update_fields=["status"])

        logger.info(f"✅ Lead #{lead.id} marqué ABSENT")

        if lead.email:
            try:
                send_missed_appointment_email(lead)
                logger.info(
                    f"📧 Email absence envoyé à {lead.email} (lead #{lead.id})"
                )
            except Exception:
                logger.exception(
                    f"❌ Erreur email absence lead #{lead.id}"
                )