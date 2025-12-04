import logging
from api.utils.cloud.scw.bucket_utils import delete_object
from api.utils.cloud.scw.utils import extract_bucket_key_from_url

logger = logging.getLogger(__name__)


def delete_s3_file_safe(bucket_key: str, url: str, file_type: str = "fichier"):
    """
    Supprime un fichier S3 de manière sécurisée.
    Retourne True si succès, False sinon.
    """
    if not url:
        return False

    try:
        key = extract_bucket_key_from_url(bucket_key, url)
        if key:
            delete_object(bucket_key, key)
            logger.info(f"✅ {file_type} supprimé : {key}")
            return True
        else:
            logger.warning(f"⚠️ Impossible d'extraire la clé S3 de : {url}")
            return False
    except Exception as e:
        logger.error(f"❌ Erreur suppression {file_type} ({url}) : {e}")
        return False


def cleanup_client_cascade_s3(client) -> dict:
    """
    Supprime TOUS les fichiers S3 d'un client et ses relations.
    Version simplifiée qui prend directement le client.
    """
    stats = {
        'clients': 0,
        'contracts': 0,
        'receipts': 0,
        'documents': 0,
        'total': 0
    }

    logger.info(f"🗑️ NETTOYAGE S3 pour Client #{client.pk}")

    try:
        # 1️⃣ Documents du client
        if hasattr(client, 'documents'):
            for doc in client.documents.all():
                if hasattr(doc, 'file_url') and doc.file_url:
                    if delete_s3_file_safe('documents', doc.file_url, f"Document #{doc.pk}"):
                        stats['documents'] += 1
                        stats['total'] += 1

        # 2️⃣ Reçus de paiement
        for receipt in client.receipts.all():
            if receipt.receipt_url:
                if delete_s3_file_safe('receipts', receipt.receipt_url, f"Reçu #{receipt.pk}"):
                    stats['receipts'] += 1
                    stats['total'] += 1

        # 3️⃣ Contrats (PDF contrat + facture)
        for contract in client.contracts.all():
            if contract.contract_url:
                if delete_s3_file_safe('contracts', contract.contract_url, f"Contrat #{contract.pk}"):
                    stats['contracts'] += 1
                    stats['total'] += 1

            if contract.invoice_url:
                if delete_s3_file_safe('invoices', contract.invoice_url, f"Facture #{contract.pk}"):
                    stats['contracts'] += 1
                    stats['total'] += 1

        # 4️⃣ Avatar du client (si applicable)
        if hasattr(client, 'avatar_url') and client.avatar_url:
            if delete_s3_file_safe('avatars', client.avatar_url, f"Avatar Client #{client.pk}"):
                stats['clients'] += 1
                stats['total'] += 1

        logger.info(
            f"✅ Nettoyage S3 Client #{client.pk} terminé : {stats['total']} fichiers "
            f"(documents: {stats['documents']}, contrats: {stats['contracts']}, "
            f"reçus: {stats['receipts']}, avatars: {stats['clients']})"
        )

    except Exception as e:
        logger.error(f"❌ Erreur lors du nettoyage S3 Client #{client.pk} : {e}")

    return stats