# api/utils/email/contracts/tasks.py
# ✅ Migré Celery → Django-Q2

import logging

from django_q.tasks import async_task

logger = logging.getLogger(__name__)


# ================================================================
# WORKER
# ================================================================

def _run_send_contract_email(contract_id: int):
    from api.contracts.models import Contract
    from api.utils.email.contracts.notifications import send_contract_email_to_lead

    contract = (
        Contract.objects
        .select_related("client__lead")
        .filter(id=contract_id)
        .first()
    )

    if contract and contract.client and contract.client.lead and contract.client.lead.email:
        send_contract_email_to_lead(contract)
        logger.info("📩 Contrat #%s envoyé à %s", contract.id, contract.client.lead.email)
    else:
        logger.warning("❌ Contrat #%s non envoyé — données incomplètes", contract_id)


# ================================================================
# API PUBLIQUE
# ================================================================

def send_contract_email_task(contract_id: int):
    """Anciennement send_contract_email_task.delay(contract_id)"""
    async_task(
        "api.utils.email.contracts.tasks._run_send_contract_email",
        contract_id,
        group="emails",
    )