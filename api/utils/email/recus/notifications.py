import logging
from datetime import datetime

from api.utils.cloud.scw.utils import download_file_from_s3, extract_s3_key_from_url
from api.utils.email import send_html_email
from api.utils.email.config import _build_context

logger = logging.getLogger(__name__)


def send_receipts_email_to_lead(lead, receipts):
    """
    Envoie un ou plusieurs reçus PDF par mail au lead associé à un client.

    - Utilise le template `email/recus/receipts_send.html`
    - Télécharge chaque reçu depuis Scaleway S3 via boto3
    """
    if not lead or not lead.email:
        logger.warning("Aucun email trouvé pour le lead.")
        return

    attachments = []
    for receipt in receipts:
        logger.info(f"Téléchargement du reçu : {receipt.receipt_url}")
        try:
            key = extract_s3_key_from_url(receipt.receipt_url)
            pdf_content, pdf_filename = download_file_from_s3("receipts", key)
        except Exception as e:
            logger.error(f"Échec du téléchargement du reçu {receipt.id} : {e}")
            continue

        attachments.append(
            {
                "filename": pdf_filename,
                "content": pdf_content,
                "mimetype": "application/pdf",
            }
        )

    if not attachments:
        logger.warning(f"Aucune pièce jointe valide pour le lead {lead}.")
        return

    context = _build_context(lead=lead, extra={"receipts": receipts})

    send_html_email(
        to_email=lead.email,
        subject="Vos reçus de paiement – TDS France",
        template_name="email/recus/receipts_send.html",
        context=context,
        attachments=attachments,
    )

    logger.info(f"📩 Reçus envoyés à {lead.email}")


def send_payment_due_email(client, receipt, due_date: datetime, amount: float):
    """
    Envoie un rappel par email concernant un paiement à venir.

    - Utilise le template `email/recus/payment_reminder.html`
    - Ajoute dans le contexte : client, reçu, date d’échéance, montant
    - Envoie à client.lead.email
    """
    lead = getattr(client, "lead", None)
    recipient = getattr(lead, "email", None)

    if not recipient:
        logger.warning(f"Aucun email trouvé pour le client {client}")
        return

    context = _build_context(
        lead=lead,
        extra={
            "client": client,
            "receipt": receipt,
            "due_date": due_date.strftime("%d/%m/%Y"),
            "amount": f"{amount:.2f}€",
        },
    )

    subject = "Rappel : Échéance de paiement"
    send_html_email(
        to_email=recipient,
        subject=subject,
        template_name="email/recus/payment_reminder.html",
        context=context,
    )

    logger.info(f"📩 Rappel de paiement envoyé à {recipient}")

def send_due_date_updated_email(receipt, new_due_date):
    lead = getattr(receipt.client, "lead", None)
    if not lead or not lead.email:
        logger.warning("Aucun e-mail trouvé pour le client.")
        return

    context = _build_context(
        lead=lead,
        extra={
            "receipt": receipt,
            "new_due_date": new_due_date.strftime("%d/%m/%Y"),
            "amount": f"{receipt.contract.balance_due:.2f}",
            "phone": "01 84 80 62 00",  # ou settings.TDS_CONTACT_PHONE
        },
    )

    send_html_email(
        to_email=lead.email,
        subject="Nouvelle date d’échéance enregistrée",
        template_name="email/recus/payment_updated.html",
        context=context,
    )

    logger.info(f"📩 Email de modification d’échéance envoyé à {lead.email}")