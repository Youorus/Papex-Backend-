import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from api.payments.models import PaymentReceipt
from api.utils.email.recus.notifications import send_payment_due_email

logger = logging.getLogger(__name__)


@shared_task
def send_payment_due_reminders():
    """
    Tâche pour envoyer des rappels de paiement :
    - J-3 : trois jours avant l’échéance
    - J-1 : un jour avant l’échéance
    ⚠️ Protection anti-doublons via `last_reminder_sent`.
    """
    today = timezone.localdate()
    in_1_day = today + timedelta(days=1)
    in_3_days = today + timedelta(days=3)

    receipts = (
        PaymentReceipt.objects.filter(next_due_date__in=[in_1_day, in_3_days])
        .select_related("client", "contract")
    )

    now = timezone.now()

    for receipt in receipts:
        client = receipt.client
        email = getattr(client.lead, "email", None)

        if not email:
            logger.warning(
                f"⚠️ Aucun email trouvé pour le client #{client.id}, skip rappel paiement."
            )
            continue

        # Protection anti-spam : ≥ 12h entre deux envois
        if receipt.last_reminder_sent and (now - receipt.last_reminder_sent).total_seconds() < 43200:
            logger.info(
                f"⏩ Rappel déjà envoyé récemment pour client #{client.id}, skip."
            )
            continue

        try:
            # 💸 Calcul du reste à payer
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
                f"📧 Rappel paiement envoyé à {email} "
                f"(client #{client.id}, échéance {receipt.next_due_date}, montant {amount_due})"
            )
        except Exception as e:
            logger.error(
                f"❌ Erreur lors de l’envoi du rappel paiement client #{client.id} : {e}"
            )

