# api/leads/automation/handlers/contract_signed.py

import logging

from api.sms.tasks import send_contract_signed_sms_task

# from api.whatsapp.tasks import send_contract_signed_whatsapp_task
# from api.email.tasks import send_contract_signed_email_task

logger = logging.getLogger(__name__)

POST_CONTRACT_DELAY = 10


def handle_contract_signed(event):
    """
    Déclenché quand un contrat est créé pour un lead.

    Séquence :
      1. SMS félicitations + déroulement dossier  → +2h
      2. WhatsApp déroulement (à implémenter)     → +2h
      3. Email félicitations (à implémenter)      → +2h
    """

    lead = event.lead

    logger.info(
        "[handle_contract_signed] Contrat signé — lead_id=%s",
        lead.id,
    )

    # 1. SMS félicitations
    send_contract_signed_sms_task.apply_async(
        args=[lead.id],
        countdown=POST_CONTRACT_DELAY,
    )

    logger.info(
        "[handle_contract_signed] Task SMS contrat signé planifiée +2h : lead_id=%s",
        lead.id,
    )

    # 2. WhatsApp déroulement dossier (à implémenter)
    # send_contract_signed_whatsapp_task.apply_async(
    #     args=[lead.id],
    #     countdown=POST_CONTRACT_DELAY,
    # )

    # 3. Email félicitations (à implémenter)
    # send_contract_signed_email_task.apply_async(
    #     args=[lead.id],
    #     countdown=POST_CONTRACT_DELAY,
    # )