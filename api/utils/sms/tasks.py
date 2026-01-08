# api/utils/sms/tasks.py

import logging
from celery import shared_task

from api.leads.models import Lead
from api.utils.sms.notifications.leads import (
    send_appointment_confirmation_sms,
    send_appointment_reminder_sms,
)

logger = logging.getLogger(__name__)


# ============================================================
# 📲 SMS — CONFIRMATION DE RDV
# ============================================================

@shared_task(
    bind=True,
    autoretry_for=(),   # ❌ PAS de retry automatique
)
def send_appointment_confirmation_sms_task(self, lead_id: int):
    """
    Task Celery NON BLOQUANTE
    → Envoie SMS confirmation
    → N'interrompt JAMAIS le worker
    """
    try:
        lead = Lead.objects.filter(id=lead_id).first()

        if not lead:
            logger.warning(
                f"⚠️ Lead #{lead_id} introuvable — SMS confirmation ignoré"
            )
            return

        if not lead.phone:
            logger.info(
                f"ℹ️ Lead #{lead_id} sans téléphone — SMS confirmation ignoré"
            )
            return

        send_appointment_confirmation_sms(lead)

        logger.info(
            f"📲 SMS confirmation envoyé à {lead.phone} (lead #{lead.id})"
        )

    except Exception:
        # 🔥 Catch GLOBAL — NE JAMAIS LAISSER REMONTER
        logger.error(
            f"❌ Échec SMS confirmation (lead #{lead_id}) — erreur absorbée",
            exc_info=True,
        )
        return


# ============================================================
# ⏰ SMS — RAPPEL DE RDV
# ============================================================

@shared_task(
    bind=True,
    autoretry_for=(),   # ❌ PAS de retry automatique
)
def send_appointment_reminder_sms_task(self, lead_id: int):
    """
    Task Celery NON BLOQUANTE
    → Envoie SMS de rappel
    → N'interrompt JAMAIS le worker
    """
    try:
        lead = Lead.objects.filter(id=lead_id).first()

        if not lead:
            logger.warning(
                f"⚠️ Lead #{lead_id} introuvable — SMS rappel ignoré"
            )
            return

        if not lead.phone:
            logger.info(
                f"ℹ️ Lead #{lead_id} sans téléphone — SMS rappel ignoré"
            )
            return

        send_appointment_reminder_sms(lead)

        logger.info(
            f"⏰ SMS rappel envoyé à {lead.phone} (lead #{lead.id})"
        )

    except Exception:
        logger.error(
            f"❌ Échec SMS rappel (lead #{lead_id}) — erreur absorbée",
            exc_info=True,
        )
        return