import mimetypes
import os
from urllib.parse import urlparse

from django.conf import settings

from api.utils.cloud.scw.s3_client import get_s3_client


def download_file_from_s3(bucket_key: str, key: str) -> tuple[bytes, str]:
    """
    Télécharge un fichier depuis Scaleway S3 via boto3 (accès privé).
    Retourne le contenu du fichier (bytes) et son nom.
    """
    s3 = get_s3_client()
    bucket = settings.SCW_BUCKETS[bucket_key]

    response = s3.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read()

    filename = os.path.basename(key)
    return content, filename


def extract_s3_key_from_url(url: str) -> str:
    """
    Extrait la clé S3 (key) à partir d'une URL complète.
    Exemple : https://s3.fr-par.scw.cloud/contracts/junior_marc_2/contrat_9.pdf
    => 'junior_marc_2/contrat_9.pdf'
    """
    path = urlparse(url).path  # /contracts/junior_marc_2/contrat_9.pdf
    parts = path.lstrip("/").split("/", 1)
    if len(parts) == 2:
        return parts[1]  # junior_marc_2/contrat_9.pdf
    raise ValueError("Impossible d’extraire la clé S3 depuis l’URL donnée")


# Dans utils.py, ajoute des logs :
def extract_bucket_key_from_url(bucket_key: str, url: str) -> str | None:
    """
    Extrait la clé S3 depuis une URL complète ou un chemin partiel.
    """
    if not url:
        return None

    bucket_name = settings.SCW_BUCKETS[bucket_key]
    parsed = urlparse(url)
    path = parsed.path

    print(f"🔍 [DEBUG] URL reçue : {url}")
    print(f"🔍 [DEBUG] Bucket attendu : {bucket_name}")
    print(f"🔍 [DEBUG] Path extrait : {path}")

    # Exemple : /contracts/nkue-takoumba_marc-junior_5/contrat_123.pdf
    # On veut : nkue-takoumba_marc-junior_5/contrat_123.pdf

    split_token = f"/{bucket_name}/"
    if split_token in path:
        key = path.split(split_token, 1)[1]
        print(f"✅ [DEBUG] Clé extraite : {key}")
        return key.lstrip("/")

    # Fallback : prendre tout après le premier /
    parts = path.strip("/").split("/", 1)
    if len(parts) >= 2:
        key = parts[1]
        print(f"⚠️ [DEBUG] Clé extraite (fallback) : {key}")
        return key

    print(f"❌ [DEBUG] Impossible d'extraire la clé")
    return None
