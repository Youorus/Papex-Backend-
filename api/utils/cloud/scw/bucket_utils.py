from django.conf import settings
import mimetypes
from urllib.parse import urlparse, unquote
from .s3_client import get_s3_client


def get_object(bucket_key: str, key: str) -> bytes:
    s3 = get_s3_client()
    bucket = settings.SCW_BUCKETS[bucket_key]
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def delete_object(bucket_key: str, key: str):
    s3 = get_s3_client()
    bucket = settings.SCW_BUCKETS[bucket_key]
    s3.delete_object(Bucket=bucket, Key=key)


def put_object(
    bucket_key: str, key: str, content: bytes, content_type="application/octet-stream"
):
    s3 = get_s3_client()
    bucket = settings.SCW_BUCKETS[bucket_key]
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=content,
        ContentType=content_type,
        ContentDisposition="inline",
    )


def generate_presigned_url(bucket_key: str, key: str, expires_in: int = 3600) -> str:
    """
    Génère une URL signée temporaire avec détection automatique du type MIME.
    - Supporte aussi bien les clés S3 simples que les URLs complètes.
    """
    s3 = get_s3_client()
    bucket = settings.SCW_BUCKETS[bucket_key]

    # 🔍 Étape 1 — Extraire le vrai chemin depuis l’URL si besoin
    if key.startswith("http://") or key.startswith("https://"):
        parsed = urlparse(key)
        key_path = unquote(parsed.path)  # /avatars-tds/jennifer_koskas/xyz.jpg
        key = "/".join(key_path.strip("/").split("/")[1:])  # enlève le nom du bucket
        print("🔍 Clé extraite de l'URL :", key)

    # 🔍 Étape 2 — Deviner le content-type via l'extension
    content_type, _ = mimetypes.guess_type(key)
    if not content_type:
        content_type = "application/octet-stream"  # Fallback neutre

    # 🔍 Étape 3 — Générer l'URL signée
    signed_url = s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": key,
            "ResponseContentType": content_type,
            "ResponseContentDisposition": "inline",
        },
        ExpiresIn=expires_in,
    )
    return signed_url