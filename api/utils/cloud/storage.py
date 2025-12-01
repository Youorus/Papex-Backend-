from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.text import slugify

from api.storage_backends import (
    MinioContractStorage,
    MinioDocumentStorage,
    MinioReceiptStorage,
    MinioInvoiceStorage,  # À créer si pas encore fait
)


def store_receipt_pdf(receipt, pdf_bytes: bytes) -> str:
    """
    Stocke le PDF d'un reçu dans MinIO/S3 et retourne l'URL publique.
    :param receipt: instance PaymentReceipt
    :param pdf_bytes: bytes du PDF
    :return: URL publique du reçu PDF
    """
    lead = receipt.client.lead
    client_id = receipt.client.id
    client_slug = slugify(f"{lead.last_name}_{lead.first_name}_{client_id}")
    date_str = receipt.payment_date.strftime("%Y%m%d")
    filename = f"{client_slug}/recu_{receipt.id}_{date_str}.pdf"

    file_content = ContentFile(pdf_bytes)
    storage = MinioReceiptStorage()
    saved_path = storage.save(filename, file_content)

    location = f"{storage.location}/" if storage.location else ""
    url = f"{settings.AWS_S3_ENDPOINT_URL}/{storage.bucket_name}/{location}{saved_path}"

    return url


def store_contract_pdf(contract, pdf_bytes: bytes) -> str:
    """
    Stocke le PDF d'un contrat dans MinIO/S3 et retourne l'URL publique.
    :param contract: instance Contract
    :param pdf_bytes: bytes du PDF
    :return: URL publique du contrat PDF
    """
    client = contract.client
    lead = client.lead
    client_id = client.id
    client_slug = slugify(f"{lead.last_name}_{lead.first_name}_{client_id}")
    date_str = contract.created_at.strftime("%Y%m%d")
    filename = f"{client_slug}/contrat_{contract.id}_{date_str}.pdf"

    file_content = ContentFile(pdf_bytes)
    storage = MinioContractStorage()
    saved_path = storage.save(filename, file_content)

    # Construction manuelle de l'URL publique
    location = f"{storage.location}/" if storage.location else ""
    endpoint = getattr(settings, "AWS_S3_ENDPOINT_URL", "")
    url = f"{endpoint}/{storage.bucket_name}/{location}{saved_path}"

    return url


def store_invoice_pdf(contract, pdf_bytes: bytes, invoice_ref: str) -> str:
    """
    Stocke le PDF d'une facture dans MinIO/S3 et retourne l'URL publique.
    :param contract: instance Contract (pour récupérer les infos client)
    :param pdf_bytes: bytes du PDF
    :param invoice_ref: référence de la facture (ex: "TDS-000123")
    :return: URL publique de la facture PDF
    """
    client = contract.client
    lead = client.lead
    client_id = client.id
    client_slug = slugify(f"{lead.last_name}_{lead.first_name}_{client_id}")
    date_str = contract.created_at.strftime("%Y%m%d")

    # Nom du fichier avec la référence de facture
    filename = f"{client_slug}/facture_{invoice_ref}_{date_str}.pdf"

    file_content = ContentFile(pdf_bytes)
    storage = MinioInvoiceStorage()
    saved_path = storage.save(filename, file_content)

    # Construction manuelle de l'URL publique
    location = f"{storage.location}/" if storage.location else ""
    endpoint = getattr(settings, "AWS_S3_ENDPOINT_URL", "")
    url = f"{endpoint}/{storage.bucket_name}/{location}{saved_path}"

    return url


def store_client_document(client, file_content, original_filename) -> str:
    """
    Stocke un document client dans MinIO/S3, retourne l'URL publique.
    :param client: instance Client
    :param file_content: bytes ou ContentFile ou InMemoryUploadedFile
    :param original_filename: str, nom d'origine (ex: "CNI.pdf")
    :return: URL publique du document
    """
    client_slug = slugify(
        f"{client.lead.last_name}_{client.lead.first_name}_{client.id}"
    )
    ext = original_filename.split(".")[-1] if "." in original_filename else "pdf"
    safe_filename = slugify(original_filename.rsplit(".", 1)[0])
    filename = f"{client_slug}/{safe_filename}.{ext}"

    storage = MinioDocumentStorage()
    if isinstance(file_content, bytes):
        file_content = ContentFile(file_content, name=filename)
    saved_path = storage.save(filename, file_content)

    location = f"{storage.location}/" if storage.location else ""
    endpoint = getattr(settings, "AWS_S3_ENDPOINT_URL", "")
    url = f"{endpoint}/{storage.bucket_name}/{location}{saved_path}"
    return url