#!/usr/bin/env python
import os
import sys
import django
import uvicorn
import redis
import boto3
from botocore.exceptions import ClientError


def check_s3_storage():
    """Test pour vérifier TOUS les buckets Scaleway S3 configurés."""
    print("📦 Checking S3 storage...")

    from django.conf import settings

    # Vérification configuration minimale
    if not settings.AWS_S3_ENDPOINT_URL:
        print("⚠️  S3 not configured (AWS_S3_ENDPOINT_URL empty). Skipping.")
        return True

    # ----------------------
    # LISTE DE TOUS LES BUCKETS À TESTER
    # ----------------------
    buckets = {
        "main": settings.AWS_STORAGE_BUCKET_NAME,
        "avatars": getattr(settings, "BUCKET_USERS_AVATARS", None),
        "documents": getattr(settings, "BUCKET_CLIENT_DOCUMENTS", None),
        "contracts": getattr(settings, "BUCKET_CONTRACTS", None),
        "receipts": getattr(settings, "BUCKET_RECEIPTS", None),
        "invoices": getattr(settings, "BUCKET_INVOICES", None),
    }

    # Remove None or empty values
    buckets = {k: v for k, v in buckets.items() if v}

    # ----------------------
    # INITIALISER LE CLIENT S3
    # ----------------------
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            verify=settings.AWS_S3_VERIFY,
        )
    except Exception as e:
        print("🔴 Failed to initialize S3 client:", e)
        return False

    # ----------------------
    # TEST DE CHAQUE BUCKET
    # ----------------------
    for label, bucket_name in buckets.items():
        print(f"\n📁 Testing bucket: {bucket_name} ({label})")

        test_key = f"health-check-{label}.txt"
        test_content = b"S3 health check OK"

        # 1 — Check existence
        try:
            s3.head_bucket(Bucket=bucket_name)
            print(f"🟢 Bucket exists: {bucket_name}")
        except ClientError as e:
            print(f"🔴 Bucket not accessible ({bucket_name}): {e}")
            return False

        # 2 — Upload
        try:
            s3.put_object(Bucket=bucket_name, Key=test_key, Body=test_content)
            print("🟢 Upload OK")
        except Exception as e:
            print("🔴 Upload failed:", e)
            return False

        # 3 — Download
        try:
            obj = s3.get_object(Bucket=bucket_name, Key=test_key)
            data = obj["Body"].read()
            if data == test_content:
                print("🟢 Download OK")
            else:
                print("🔴 Download mismatch!")
                return False
        except Exception as e:
            print("🔴 Download failed:", e)
            return False

        # 4 — Delete
        try:
            s3.delete_object(Bucket=bucket_name, Key=test_key)
            print("🟢 Delete OK")
        except Exception as e:
            print("🔴 Delete failed:", e)
            return False

    print("\n🟢 All S3 buckets healthy!")
    return True



def health_checks():
    print("🔍 Running startup health checks...")

    # -----------------------------
    # DATABASE CHECK
    # -----------------------------
    from django.db import connections
    from django.db.utils import OperationalError

    try:
        connections["default"].cursor()
        print("🟢 Database connected.")
    except OperationalError as e:
        print("🔴 Database connection failed:", e)
        return False

    # -----------------------------
    # REDIS CHECK
    # -----------------------------
    try:
        r = redis.from_url(os.getenv("REDIS_URL"))
        r.ping()
        print("🟢 Redis connected.")
    except Exception as e:
        print("🔴 Redis connection failed:", e)
        return False

    # -----------------------------
    # S3 STORAGE CHECK
    # -----------------------------
    if not check_s3_storage():
        return False

    print("🟢 All services ready.")
    return True


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")

    django.setup()

    # Do not run twice under reload mode
    if not os.environ.get("UVICORN_RELOAD"):
        if not health_checks():
            print("❌ Startup aborted due to failed health checks.")
            sys.exit(1)

    print("🚀 Starting Uvicorn...")
    uvicorn.run(
        "papex.asgi:application",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
