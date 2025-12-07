import logging

from api.utils.cloud.scw.utils import (
    download_file_from_s3,
    extract_s3_key_from_url,
)
from api.utils.email import send_html_email
from api.utils.email.config import _build_context

logger = logging.getLogger(__name__)


def send_contract_email_to_lead(contract):
    """
    Envoie au lead un e-mail contenant son contrat en pièce jointe.

    - Télécharge le PDF depuis Scaleway S3 (bucket privé)
    - Injecte le contexte lié au contrat dans le template
    - Utilise le template `email/contract/contract_send.html`
    """

    client = contract.client
    lead = getattr(client, "lead", None)

    # Vérification minimale
    if not lead or not lead.email:
        logger.warning(f"[ContractEmail] Aucun email associé au lead pour le client #{client.id}")
        return

    # Récupération clé S3
    try:
        s3_key = extract_s3_key_from_url(contract.contract_url)
        pdf_content, pdf_filename = download_file_from_s3("contracts", s3_key)
    except Exception as e:
        logger.error(f"[ContractEmail] Impossible de récupérer le fichier pour lead #{lead.id}: {e}")
        return

    # Contexte email
    context = _build_context(
        lead,
        extra={
            "contract": contract,
        },
    )

    # Envoi email
    send_html_email(
        to_email=lead.email,
        subject="Votre contrat est disponible – Papiers Express",
        template_name="email/contract/contract_send.html",
        context=context,
        attachments=[
            {
                "filename": pdf_filename,
                "content": pdf_content,
                "mimetype": "application/pdf",
            }
        ],
    )

    logger.info(f"[ContractEmail] Contrat #{contract.id} envoyé à {lead.email}")
