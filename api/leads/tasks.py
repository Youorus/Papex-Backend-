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
# ⏰ RAPPEL J-1 — EMAIL + SMS (NON BLOQUANT)
# ============================================================

@shared_task(bind=True)
def send_reminder_notifications(self):
    """
    Envoie un rappel J-1 pour les rendez-vous confirmés.

    - Email et SMS sont indépendants
    - Aucun échec ne bloque la task
    - last_reminder_sent est posé quoi qu’il arrive
    """
    now = timezone.now()
    tomorrow = now.date() + timedelta(days=1)

    leads = Lead.objects.filter(
        status__code=RDV_CONFIRME,
        appointment_date__date=tomorrow,
    )

    logger.info(f"🔔 Rappel J-1 — {leads.count()} lead(s) trouvé(s)")

    for lead in leads:
        # 🔒 Anti double envoi
        if lead.last_reminder_sent:
            logger.debug(
                f"⏭️ Lead #{lead.id} déjà rappelé — ignoré"
            )
            continue

        logger.info(f"➡️ Traitement rappel lead #{lead.id}")

        # =========================
        # 📧 EMAIL
        # =========================
        if lead.email:
            try:
                send_appointment_reminder_email(lead)
                logger.info(
                    f"📧 Rappel email envoyé à {lead.email} (lead #{lead.id})"
                )
            except Exception:
                logger.error(
                    f"❌ Erreur email rappel lead #{lead.id}",
                    exc_info=True,
                )
        else:
            logger.info(
                f"ℹ️ Lead #{lead.id} sans email — rappel email ignoré"
            )

        # =========================
        # 📲 SMS
        # =========================
        if lead.phone:
            try:
                send_appointment_reminder_sms(lead)
                logger.info(
                    f"📲 Rappel SMS envoyé à {lead.phone} (lead #{lead.id})"
                )
            except Exception:
                logger.error(
                    f"❌ Erreur SMS rappel lead #{lead.id}",
                    exc_info=True,
                )
        else:
            logger.info(
                f"ℹ️ Lead #{lead.id} sans téléphone — rappel SMS ignoré"
            )

        # =========================
        # 🔒 VERROU FINAL
        # =========================
        lead.last_reminder_sent = now
        lead.save(update_fields=["last_reminder_sent"])

        logger.info(
            f"🔒 Rappel verrouillé pour lead #{lead.id}"
        )


# ============================================================
# 🚫 MARQUER ABSENT + EMAIL (NON BLOQUANT)
# ============================================================

@shared_task(bind=True)
def mark_absent_leads(self):
    """
    Marque comme ABSENT les leads dont le RDV est passé.
    Envoie un email d'absence si possible.
    """
    now = timezone.now()

    try:
        absent_status = LeadStatus.objects.get(code=ABSENT)
        confirmed_status = LeadStatus.objects.get(code=RDV_CONFIRME)
    except LeadStatus.DoesNotExist:
        logger.error(
            "❌ Statuts ABSENT ou RDV_CONFIRME introuvables — arrêt task"
        )
        return

    leads_to_mark = Lead.objects.filter(
        status=confirmed_status,
        appointment_date__lt=now,
    )

    logger.info(
        f"🚫 Marquage ABSENT — {leads_to_mark.count()} lead(s)"
    )

    for lead in leads_to_mark:
        lead.status = absent_status
        lead.save(update_fields=["status"])

        logger.info(
            f"✅ Lead #{lead.id} marqué ABSENT"
        )

        if lead.email:
            try:
                send_missed_appointment_email(lead)
                logger.info(
                    f"📧 Email absence envoyé à {lead.email} (lead #{lead.id})"
                )
            except Exception:
                logger.error(
                    f"❌ Erreur email absence lead #{lead.id}",
                    exc_info=True,
                )
        else:
            logger.info(
                f"ℹ️ Lead #{lead.id} sans email — pas d’email d’absence"
            )