import logging

from api.utils.email.recus.tasks import send_receipts_email_task

logger = logging.getLogger(__name__)


def handle_receipts_email_sent(event):
    """
    Déclenché quand on envoie des reçus par email
    """

    lead = event.lead
    receipt_ids = event.data.get("receipt_ids", [])

    if not lead:
        return

    # 📧 TASK
    send_receipts_email_task.delay(
        lead_id=lead.id,
        receipt_ids=receipt_ids,
    )

    logger.info(
        "📨 Reçus envoyés pour Lead #%s (%s reçus)",
        lead.id,
        len(receipt_ids),
    )