import logging

from api.utils.email.contracts.tasks import send_contract_email_task

logger = logging.getLogger(__name__)


def handle_contract_email_sent(event):
    """
    Déclenché quand on clique sur "envoyer le contrat"
    """

    lead = event.lead
    contract_id = event.data.get("contract_id")

    if not lead:
        return

    # 📧 EMAIL
    if lead.email:
        send_contract_email_task(contract_id)

    logger.info(
        "📨 Contrat #%s envoyé pour Lead #%s",
        contract_id,
        lead.id,
    )