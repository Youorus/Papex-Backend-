# api/leads/automation/handlers/lead_created.py

import logging

from api.leads.constants import RDV_A_CONFIRMER
from api.lead_status.models import LeadStatus
from api.sms.tasks import send_appointment_confirmation_sms_task

# from api.whatsapp.tasks import send_welcome_whatsapp_task
# from api.email.tasks import send_welcome_email_task

logger = logging.getLogger(__name__)


def handle_lead_created(event):

    lead = event.lead

    logger.info("[handle_lead_created] Déclenchement pour lead_id=%s", lead.id)

    # --------------------------------------------------
    # 1. Mise à jour du statut → RDV_A_CONFIRMER
    # --------------------------------------------------

    status = LeadStatus.objects.get(code=RDV_A_CONFIRMER)
    lead.status = status
    lead.save(update_fields=["status"])

    logger.info(
        "[handle_lead_created] Statut mis à jour : lead_id=%s | nouveau_statut=%s",
        lead.id, RDV_A_CONFIRMER,
    )

    # --------------------------------------------------
    # 2. SMS confirmation RDV
    #    Conditions vérifiées dans notifications/leads.py :
    #      - lead.phone valide
    #      - lead.appointment_date présente
    #      - statut == RDV_A_CONFIRMER
    #      - SMS non déjà envoyé pour cette date (LeadEvent)
    # --------------------------------------------------

    send_appointment_confirmation_sms_task.delay(lead.id)

    logger.info(
        "[handle_lead_created] Task SMS confirmation dispatchée : lead_id=%s",
        lead.id,
    )

    # --------------------------------------------------
    # 3. WhatsApp bienvenue (à implémenter)
    #    Envoi du message de bienvenue expliquant le service
    #    et ses modalités.
    # --------------------------------------------------

    # send_welcome_whatsapp_task.delay(lead.id)

    # --------------------------------------------------
    # 4. Email bienvenue (à implémenter)
    #    Envoi de l'email de bienvenue avec le détail
    #    du processus et les prochaines étapes.
    # --------------------------------------------------

    # send_welcome_email_task.delay(lead.id)