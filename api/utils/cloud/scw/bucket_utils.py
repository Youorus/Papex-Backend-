import mimetypes
from urllib.parse import urlparse, unquote

from django.conf import settings

from .s3_client import get_s3_client


def get_object(bucket_key: str, key: str) -> bytes:
    s3     = get_s3_client()
    bucket = settings.SCW_BUCKETS[bucket_key]
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def delete_object(bucket_key: str, key: str):
    s3     = get_s3_client()
    bucket = settings.SCW_BUCKETS[bucket_key]
    s3.delete_object(Bucket=bucket, Key=key)


def put_object(
    bucket_key: str,
    key: str,
    content: bytes,
    content_type: str = "application/octet-stream",
):
    s3     = get_s3_client()
    bucket = settings.SCW_BUCKETS[bucket_key]
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=content,
        ContentType=content_type,
        ContentDisposition="inline",
    )


def generate_presigned_url(
    bucket_key: str,
    key: str,
    expires_in: int = 3600,
    disposition: str = "inline",
    filename: str | None = None,
) -> str:
    """
    Génère une URL présignée S3/SCW.

    Args:
        bucket_key : clé du bucket dans settings.SCW_BUCKETS
        key        : clé S3 de l'objet (ou URL complète, auto-extraite)
        expires_in : durée de validité en secondes (défaut 1h)
        disposition: "inline"     -> affichage navigateur (viewer)
                     "attachment" -> force le téléchargement
        filename   : nom affiché lors du téléchargement.
                     Si absent, déduit depuis la clé S3.

    Returns:
        URL présignée prête à l'emploi.
    """
    s3     = get_s3_client()
    bucket = settings.SCW_BUCKETS[bucket_key]

    # Étape 1 : extraire la clé si une URL complète est passée
    if key.startswith("http://") or key.startswith("https://"):
        parsed   = urlparse(key)
        key_path = unquote(parsed.path)
        key      = "/".join(key_path.strip("/").split("/")[1:])

    # Étape 2 : détecter le content-type via l'extension
    content_type, _ = mimetypes.guess_type(key)
    if not content_type:
        content_type = "application/octet-stream"

    # Étape 3 : construire le Content-Disposition
    if disposition == "attachment":
        dl_name = filename or key.split("/")[-1]
        content_disposition = f'attachment; filename="{dl_name}"'
    else:
        content_disposition = "inline"

    # Étape 4 : générer l'URL présignée
    signed_url = s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket":                     bucket,
            "Key":                        key,
            "ResponseContentType":        content_type,
            "ResponseContentDisposition": content_disposition,
        },
        ExpiresIn=expires_in,
    )
    return signed_url