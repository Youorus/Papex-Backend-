# api/leads/automation/handlers/lead_created.py

import logging
from api.leads.constants import RDV_A_CONFIRMER
from api.lead_status.models import LeadStatus
from api.sms.tasks import (
    send_appointment_confirmation_sms_task,
    send_confirm_presence_sms_task  # <--- AJOUTÉ
)

logger = logging.getLogger(__name__)


def handle_lead_created(event):
    lead = event.lead

    # 1. Mise à jour statut
    status = LeadStatus.objects.get(code=RDV_A_CONFIRMER)
    lead.status = status
    lead.save(update_fields=["status"])

    # 2. SMS Confirmation Immédiate
    send_appointment_confirmation_sms_task.delay(lead.id)

    # 3. PLANIFICATION : SMS Confirmation Présence (2h après)
    # countdown=7200 secondes (2h)
    send_confirm_presence_sms_task.apply_async(
        args=[lead.id],
        countdown=60 * 120
    )

    logger.info("[handle_lead_created] Automation complète pour lead #%s", lead.id)