import logging
from datetime import datetime

from api.utils.cloud.scw.utils import (
    download_file_from_s3,
    extract_s3_key_from_url,
)
from api.utils.email import send_html_email
from api.utils.email.config import _build_context

logger = logging.getLogger(__name__)


def send_receipts_email_to_lead(lead, receipts):
    """
    Envoie au lead les reçus PDF liés à ses paiements.
    - Télécharge chaque reçu depuis Scaleway S3
    - Attache les fichiers PDF à l'email
    - Utilise le template : email/recus/receipts_send.html
    """

    if not lead or not lead.email:
        logger.warning("[ReceiptsEmail] Aucun email associé au lead.")
        return

    attachments = []

    for receipt in receipts:
        try:
            s3_key = extract_s3_key_from_url(receipt.receipt_url)
            pdf_content, pdf_filename = download_file_from_s3("receipts", s3_key)
        except Exception as e:
            logger.error(
                f"[ReceiptsEmail] Échec téléchargement reçu #{receipt.id}: {e}"
            )
            continue

        attachments.append({
            "filename": pdf_filename,
            "content": pdf_content,
            "mimetype": "application/pdf",
        })

    if not attachments:
        logger.warning(f"[ReceiptsEmail] Aucun reçu valide pour lead #{lead.id}")
        return

    context = _build_context(
        lead,
        extra={"receipts": receipts},
    )

    send_html_email(
        to_email=lead.email,
        subject="Vos reçus de paiement – Papiers Express",
        template_name="email/recus/receipts_send.html",
        context=context,
        attachments=attachments,
    )

    logger.info(f"[ReceiptsEmail] {len(attachments)} reçu(s) envoyé(s) à {lead.email}")


def send_payment_due_email(client, receipt, due_date: datetime, amount: float):
    """
    Envoie un rappel concernant une échéance de paiement à venir.
    - Utilise le template : email/recus/payment_reminder.html
    """

    lead = getattr(client, "lead", None)
    if not lead or not lead.email:
        logger.warning(f"[PaymentReminder] Aucun email pour le client #{client.id}")
        return

    context = _build_context(
        lead,
        extra={
            "client": client,
            "receipt": receipt,
            "due_date": due_date.strftime("%d/%m/%Y"),
            "amount": f"{amount:.2f} €",
        },
    )

    send_html_email(
        to_email=lead.email,
        subject="Rappel : échéance de paiement",
        template_name="email/recus/payment_reminder.html",
        context=context,
    )

    logger.info(f"[PaymentReminder] Rappel envoyé à {lead.email}")


def send_due_date_updated_email(receipt, new_due_date):
    """
    Informe le lead qu'une nouvelle date d'échéance a été enregistrée.
    - Utilise le template : email/recus/payment_updated.html
    """

    lead = getattr(receipt.client, "lead", None)
    if not lead or not lead.email:
        logger.warning("[PaymentUpdate] Aucun email pour le lead associé.")
        return

    context = _build_context(
        lead,
        extra={
            "receipt": receipt,
            "new_due_date": new_due_date.strftime("%d/%m/%Y"),
            "amount": f"{receipt.contract.balance_due:.2f} €",
        },
    )

    send_html_email(
        to_email=lead.email,
        subject="Nouvelle date d’échéance enregistrée",
        template_name="email/recus/payment_updated.html",
        context=context,
    )

    logger.info(f"[PaymentUpdate] Notification d'échéance envoyée à {lead.email}")
