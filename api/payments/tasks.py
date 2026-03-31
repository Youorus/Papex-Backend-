# api/payments/tasks.py
# ✅ Migré Celery → Django-Q2

import logging
from datetime import timedelta

from django_q.tasks import async_task
from django.utils import timezone

from api.payments.models import PaymentReceipt
from api.utils.email.recus.notifications import send_payment_due_email

logger = logging.getLogger(__name__)


# ================================================================
# WORKER — rappels paiement
# ================================================================

def _run_send_payment_due_reminders():
    """
    Tâche planifiée — rappels paiement J-3 et J-1.
    Protection anti-doublons via last_reminder_sent.
    """
    today = timezone.localdate()
    in_1_day = today + timedelta(days=1)
    in_3_days = today + timedelta(days=3)

    receipts = (
        PaymentReceipt.objects
        .filter(next_due_date__in=[in_1_day, in_3_days])
        .select_related("client", "contract")
    )

    now = timezone.now()

    for receipt in receipts:
        client = receipt.client
        email = getattr(client.lead, "email", None)

        if not email:
            logger.warning("⚠️ Aucun email pour client #%s — skip.", client.id)
            continue

        # Anti-spam : >= 12h entre deux envois
        if receipt.last_reminder_sent and (now - receipt.last_reminder_sent).total_seconds() < 43200:
            logger.info("⏩ Rappel déjà envoyé récemment pour client #%s — skip.", client.id)
            continue

        try:
            amount_due = receipt.contract.amount - receipt.contract.total_paid

            send_payment_due_email(
                client=client,
                receipt=receipt,
                due_date=receipt.next_due_date,
                amount=amount_due,
            )

            receipt.last_reminder_sent = now
            receipt.save(update_fields=["last_reminder_sent"])

            logger.info(
                "📧 Rappel paiement envoyé à %s (client #%s, échéance %s, montant %s)",
                email, client.id, receipt.next_due_date, amount_due
            )
        except Exception as e:
            logger.error("❌ Erreur rappel paiement client #%s : %s", client.id, e)


# ================================================================
# WORKER — email contrat
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
# WORKER — email reçus
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


# ================================================================
# WORKER — email mise à jour échéance
# ================================================================

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
# API PUBLIQUE — dispatchers (remplacent .delay() / .apply_async())
# ================================================================

def send_payment_due_reminders():
    """Lancé par le scheduler Django-Q2 (anciennement Celery Beat)."""
    async_task(
        "api.payments.tasks._run_send_payment_due_reminders",
        group="emails",
    )


def send_contract_email_task(contract_id: int):
    """Anciennement send_contract_email_task.delay(contract_id)"""
    async_task(
        "api.payments.tasks._run_send_contract_email",
        contract_id,
        group="emails",
    )


def send_receipts_email_task(lead_id: int, receipt_ids: list = None):
    """Anciennement send_receipts_email_task.delay(lead_id, receipt_ids)"""
    async_task(
        "api.payments.tasks._run_send_receipts_email",
        lead_id,
        receipt_ids,
        group="emails",
    )


def send_due_date_updated_email_task(receipt_id: int, new_due_date: str):
    """Anciennement send_due_date_updated_email_task.delay(receipt_id, new_due_date)"""
    async_task(
        "api.payments.tasks._run_send_due_date_updated_email",
        receipt_id,
        new_due_date,
        group="emails",
    )