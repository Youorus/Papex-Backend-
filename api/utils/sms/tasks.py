# api/utils/sms/tasks.py

import logging
from celery import shared_task

from api.leads.models import Lead
from api.utils.sms.notifications.leads import (
    send_appointment_confirmation_sms,
)

logger = logging.getLogger(__name__)


@shared_task
def send_appointment_confirmation_sms_task(lead_id: int):
    lead = Lead.objects.filter(id=lead_id).first()

    if lead and lead.phone:
        send_appointment_confirmation_sms(lead)
        logger.info(
            f"📲 SMS confirmation envoyé à {lead.phone} (lead #{lead.id})"
        )
    else:
        logger.warning(
            f"❌ SMS non envoyé (lead #{lead_id} inexistant ou sans téléphone)"
        )
