# api/leads/automation/handlers/lead_created.py

import logging
from api.leads.constants import RDV_A_CONFIRMER
from api.lead_status.models import LeadStatus
from api.sms.tasks import (
    send_appointment_confirmation_sms_task,
    send_confirm_presence_sms_task
)
from api.utils.email.leads.tasks import (
    send_appointment_confirmation_task
)
logger = logging.getLogger(__name__)

def handle_lead_created(event):
    lead = event.lead

    # 1. Mise à jour du statut vers "RDV à confirmer"
    status = LeadStatus.objects.get(code=RDV_A_CONFIRMER)
    lead.status = status
    lead.save(update_fields=["status"])

    # 2. SMS Confirmation Immédiate
    send_appointment_confirmation_sms_task(lead.id)

    # 3. EMAIL Confirmation Immédiate (AJOUTÉ)
    # On vérifie si le lead a un email avant de lancer la tâche pour économiser des ressources
    if lead.email:
        send_appointment_confirmation_task(lead.id)
    else:
        logger.warning("[handle_lead_created] Lead #%s n'a pas d'email, envoi annulé.", lead.id)

    # 4. PLANIFICATION : SMS Confirmation Présence (2h après)
    # countdown=7200 secondes (2h)
    send_confirm_presence_sms_task.apply_async(
        args=[lead.id],
        countdown=60 * 120
    )

    logger.info("[handle_lead_created] Automation complète (SMS + Email) pour lead #%s", lead.id)