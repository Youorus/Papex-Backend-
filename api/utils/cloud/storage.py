from datetime import date

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.text import slugify

from api.storage_backends import (
    MinioContractStorage,
    MinioDocumentStorage,
    MinioReceiptStorage,
    MinioInvoiceStorage, MinioCandidateCVStorage,  # À créer si pas encore fait
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


def store_client_document(client, file_content, final_filename: str) -> str:
    """
    Stocke un document client dans MinIO/S3 et retourne l'URL publique.

    :param client:         Instance Client (non utilisée ici, conservée pour compatibilité)
    :param file_content:   bytes | ContentFile | InMemoryUploadedFile
    :param final_filename: Nom de fichier FINAL déjà construit par _build_filename()
                           — ne pas re-slugifier ici, le nom est prêt à l'emploi.
    :return: URL publique du document stocké

    Exemple de chemin stocké : "jean_dupont_contrat.pdf"
    Exemple d'URL retournée  : "https://s3.example.com/documents/jean_dupont_contrat.pdf"
    """
    storage = MinioDocumentStorage()

    if isinstance(file_content, bytes):
        file_content = ContentFile(file_content, name=final_filename)
    else:
        # Pour InMemoryUploadedFile / TemporaryUploadedFile : on force le nom
        file_content.name = final_filename

    saved_path = storage.save(final_filename, file_content)

    location = f"{storage.location}/" if storage.location else ""
    endpoint = getattr(settings, "AWS_S3_ENDPOINT_URL", "")
    url = f"{endpoint}/{storage.bucket_name}/{location}{saved_path}"

    return url

def store_candidate_cv(candidate, cv_file) -> str:
    """
    Stocke le CV d’un candidat dans MinIO/S3 et retourne l’URL publique.
    Organisation :
    <slug-job>/cv-prenom-nom-YYYYMMDD.pdf
    """

    job_slug = candidate.job.slug
    first_name = slugify(candidate.first_name)
    last_name = slugify(candidate.last_name)
    date_str = date.today().strftime("%Y%m%d")

    filename = f"{job_slug}/cv-{first_name}-{last_name}-{date_str}.pdf"

    storage = MinioCandidateCVStorage()

    if isinstance(cv_file, bytes):
        cv_file = ContentFile(cv_file, name=filename)

    saved_path = storage.save(filename, cv_file)

    location = f"{storage.location}/" if storage.location else ""
    endpoint = getattr(settings, "AWS_S3_ENDPOINT_URL", "")
    url = f"{endpoint}/{storage.bucket_name}/{location}{saved_path}"

    return url