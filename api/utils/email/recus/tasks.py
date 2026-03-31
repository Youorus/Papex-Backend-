# api/utils/email/recus/tasks.py
# ✅ Migré Celery → Django-Q2

import logging

from django_q.tasks import async_task

logger = logging.getLogger(__name__)


# ================================================================
# WORKERS
# ================================================================

def _run_send_receipts_email(lead_id: int, receipt_ids: list = None):
    from api.leads.models import Lead
    from api.payments.models import PaymentReceipt
    from api.utils.email.recus.notifications import send_receipts_email_to_lead

    lead = Lead.objects.filter(id=lead_id).first()

    if not lead or not lead.email:
        logger.warning("❌ Reçus non envoyés — lead #%s introuvable ou sans email.", lead_id)
        return

    qs = PaymentReceipt.objects.filter(client__lead=lead).exclude(receipt_url__isnull=True)
    if receipt_ids:
        qs = qs.filter(id__in=receipt_ids)

    if not qs.exists():
        logger.warning("❌ Aucun reçu à envoyer pour le lead #%s.", lead_id)
        return

    send_receipts_email_to_lead(lead, qs)
    logger.info("📩 %s reçu(s) envoyé(s) à %s", qs.count(), lead.email)


def _run_send_due_date_updated_email(receipt_id: int, new_due_date: str):
    from datetime import datetime
    from api.payments.models import PaymentReceipt
    from api.utils.email.recus.notifications import send_due_date_updated_email

    try:
        receipt = (
            PaymentReceipt.objects
            .select_related("client__lead", "contract__service")
            .get(id=receipt_id)
        )
        parsed_date = datetime.fromisoformat(new_due_date)
        send_due_date_updated_email(receipt, parsed_date)
        logger.info(
            "📧 Email mise à jour échéance envoyé (reçu #%s, %s)",
            receipt.id, receipt.client.lead.email
        )
    except PaymentReceipt.DoesNotExist:
        logger.warning("❌ Reçu #%s introuvable — email non envoyé.", receipt_id)
    except Exception as e:
        logger.error("❌ Erreur email modification date : %s", e, exc_info=True)


# ================================================================
# API PUBLIQUE
# ================================================================

def send_receipts_email_task(lead_id: int, receipt_ids: list = None):
    """Anciennement send_receipts_email_task.delay(lead_id)"""
    async_task(
        "api.utils.email.recus.tasks._run_send_receipts_email",
        lead_id,
        receipt_ids,
        group="emails",
    )


def send_due_date_updated_email_task(receipt_id: int, new_due_date: str):
    """Anciennement send_due_date_updated_email_task.delay(receipt_id, new_due_date)"""
    async_task(
        "api.utils.email.recus.tasks._run_send_due_date_updated_email",
        receipt_id,
        new_due_date,
        group="emails",
    )