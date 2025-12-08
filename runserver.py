#!/usr/bin/env python
import os
import sys
import time
import asyncio
import threading

import django
import uvicorn
import redis
import websockets
import boto3
from botocore.exceptions import ClientError


# ----------------------------------------------------------------------
# 🌐 CHECK WEBSOCKET
# ----------------------------------------------------------------------
async def check_websocket():
    """
    Vérifie si le WebSocket accepte la connexion et répond au ping/pong.
    """
    print("🌐 Checking WebSocket...")

    ws_url = "ws://127.0.0.1:8000/ws/health/"

    try:
        async with websockets.connect(ws_url) as ws:
            await ws.send('{"type":"ping"}')
            response = await ws.recv()

            if "pong" in response:
                print("🟢 WebSocket ping/pong OK")
                return True

            print("🔴 Unexpected WebSocket response:", response)
            return False

    except Exception as e:
        print("🔴 WebSocket connection failed:", e)
        return False


def start_websocket_test():
    """
    Attends que uvicorn démarre, puis teste le WebSocket en background.
    """
    # attendre que uvicorn soit lancé
    time.sleep(1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    ok = loop.run_until_complete(check_websocket())

    if ok:
        print("🟢 WebSocket ready!")
    else:
        print("❌ WebSocket failed — aborting server.")
        os._exit(1)


# ----------------------------------------------------------------------
# 📦 CHECK STORAGE S3
# ----------------------------------------------------------------------
def check_s3_storage():
    print("📦 Checking S3 storage...")

    from django.conf import settings

    # S3 absent => skip
    if not settings.AWS_S3_ENDPOINT_URL:
        print("⚠️ S3 not configured (AWS_S3_ENDPOINT_URL empty). Skipping.")
        return True

    buckets = {
        "main": settings.AWS_STORAGE_BUCKET_NAME,
        "avatars": getattr(settings, "BUCKET_USERS_AVATARS", None),
        "documents": getattr(settings, "BUCKET_CLIENT_DOCUMENTS", None),
        "contracts": getattr(settings, "BUCKET_CONTRACTS", None),
        "receipts": getattr(settings, "BUCKET_RECEIPTS", None),
        "invoices": getattr(settings, "BUCKET_INVOICES", None),
    }
    buckets = {k: v for k, v in buckets.items() if v}

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

    for label, bucket_name in buckets.items():
        print(f"\n📁 Testing bucket: {bucket_name} ({label})")

        test_key = f"health-check-{label}.txt"
        test_content = b"S3 health check OK"

        # existence
        try:
            s3.head_bucket(Bucket=bucket_name)
            print("🟢 Bucket exists")
        except ClientError as e:
            print(f"🔴 Bucket not accessible ({bucket_name}):", e)
            return False

        # upload
        try:
            s3.put_object(Bucket=bucket_name, Key=test_key, Body=test_content)
            print("🟢 Upload OK")
        except Exception as e:
            print("🔴 Upload failed:", e)
            return False

        # download
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

        # delete
        try:
            s3.delete_object(Bucket=bucket_name, Key=test_key)
            print("🟢 Delete OK")
        except Exception as e:
            print("🔴 Delete failed:", e)
            return False

    print("\n🟢 All S3 buckets healthy!")
    return True


# ----------------------------------------------------------------------
# 🧪 CHECK CORE SERVICES
# ----------------------------------------------------------------------
def health_checks():
    print("🔍 Running startup health checks...")

    # DB
    from django.db import connections
    from django.db.utils import OperationalError
    try:
        connections["default"].cursor()
        print("🟢 Database connected.")
    except OperationalError as e:
        print("🔴 Database connection failed:", e)
        return False

    # REDIS
    try:
        r = redis.from_url(os.getenv("REDIS_URL"))
        r.ping()
        print("🟢 Redis connected.")
    except Exception as e:
        print("🔴 Redis connection failed:", e)
        return False

    # S3
    if not check_s3_storage():
        return False

    print("🟢 Core services ready.")
    return True


# ----------------------------------------------------------------------
# 🚀 START APPLICATION
# ----------------------------------------------------------------------
def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")

    django.setup()

    # health check avant le démarrage
    if not os.environ.get("UVICORN_RELOAD"):
        if not health_checks():
            print("❌ Startup aborted due to failed health checks.")
            sys.exit(1)

    # check websocket après démarrage
    threading.Thread(target=start_websocket_test, daemon=True).start()

    print("🚀 Starting Uvicorn...")
    uvicorn.run(
        "papex.asgi:application",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
