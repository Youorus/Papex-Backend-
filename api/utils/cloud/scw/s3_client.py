# api/utils/cloud/scw/s3_client.py

import boto3
from django.conf import settings


def get_s3_client():
    """
    Retourne un client S3 configuré avec les identifiants Scaleway ou MinIO.
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
        verify=settings.AWS_S3_VERIFY,
    )
