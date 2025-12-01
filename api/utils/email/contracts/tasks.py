import logging

from celery import shared_task

logger = logging.getLogger(__name__)


import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def send_contract_email_task(contract_id: int):
    """
    Tâche asynchrone pour envoyer un contrat par email au lead.
    """
    from api.contracts.models import Contract
    from api.utils.email.contracts.notifications import send_contract_email_to_lead

    contract = (
        Contract.objects.select_related("client__lead").filter(id=contract_id).first()
    )

    if (
        contract
        and contract.client
        and contract.client.lead
        and contract.client.lead.email
    ):
        send_contract_email_to_lead(contract)
        logger.info(f"📩 Contrat #{contract.id} envoyé à {contract.client.lead.email}")
    else:
        logger.warning(f"❌ Contrat #{contract_id} non envoyé – données incomplètes.")


@shared_task
def send_contract_signed_notification_task(contract_id: int):
    """
    Tâche asynchrone pour notifier l'équipe qu'un contrat a été signé.
    """
    from api.contracts.models import Contract
    from api.utils.email.contracts.notifications import send_contract_signed_notification

    contract = Contract.objects.select_related("client__lead", "created_by").filter(id=contract_id).first()

    if not contract:
        logger.warning(f"❌ Contrat #{contract_id} introuvable pour notification de signature.")
        return

    send_contract_signed_notification(contract)