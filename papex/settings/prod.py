from .base import *

import os
import ssl

import dj_database_url
from redis import SSLConnection

# ============================================================
# 🔐 SECURITY (PRODUCTION)
# ============================================================
DEBUG = False

ALLOWED_HOSTS = [h for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h]

COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN")

# ✅ Cookies sécurisés en production
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SESSION_COOKIE_DOMAIN = COOKIE_DOMAIN
CSRF_COOKIE_DOMAIN = COOKIE_DOMAIN

# ✅ En prod avec frontend sur même domaine = Lax
# Si frontend sur domaine différent = None (comme dans base.py)
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# ✅ HTTPS derrière Cloudflare / Render / Proxy
SECURE_SSL_REDIRECT = False  # Cloudflare gère déjà HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# ✅ HSTS (optionnel mais recommandé)
SECURE_HSTS_SECONDS = 31536000  # 1 an
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ============================================================
# 🗄️  DATABASE (POSTGRESQL)
# ============================================================
DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL"),
        conn_max_age=600,
        ssl_require=True,
    )
}

# Options additionnelles pour la stabilité
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DATABASES["default"].setdefault("OPTIONS", {})
DATABASES["default"]["OPTIONS"].update(
    {
        "sslmode": "require",
        "connect_timeout": 10,
    }
)

# ============================================================
# 🌍 CORS & CSRF
# ============================================================
# ✅ CRITIQUE pour que les cookies fonctionnent
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = [
    origin for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if origin
]

CSRF_TRUSTED_ORIGINS = [
    origin for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if origin
]

# ============================================================
# ⚡  REDIS / CHANNELS
# ============================================================
REDIS_URL = os.getenv("REDIS_URL")
USE_UPSTASH = REDIS_URL is not None and "upstash.io" in REDIS_URL

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                {
                    "address": REDIS_URL,
                    **({"connection_class": SSLConnection} if USE_UPSTASH else {}),
                }
            ],
            # options tuning
            "capacity": 1500,
            "expiry": 20,
        },
    },
}

# ============================================================
# 🐇  CELERY
# ============================================================
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)

if CELERY_BROKER_URL and CELERY_BROKER_URL.startswith("rediss://"):
    CELERY_BROKER_TRANSPORT_OPTIONS = {"ssl_cert_reqs": ssl.CERT_NONE}
else:
    CELERY_BROKER_TRANSPORT_OPTIONS = {}

CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_RESULT_EXPIRES = 3600

# -------------------------------------------------------------------
# 🔥 SCW Object Storage (compatible S3) — Toujours défini
# -------------------------------------------------------------------
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")

AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL", "")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "fr-par")
AWS_S3_ADDRESSING_STYLE = os.getenv("AWS_S3_ADDRESSING_STYLE", "path")
AWS_S3_VERIFY = os.getenv("AWS_S3_VERIFY", "true").lower() in ("true", "1")

AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "")

# Buckets logiques
BUCKET_USERS_AVATARS = os.getenv("BUCKET_USERS_AVATARS", "avatars-papex")
BUCKET_CLIENT_DOCUMENTS = os.getenv("BUCKET_CLIENT_DOCUMENTS", "clients-document-papex")
BUCKET_CONTRACTS = os.getenv("BUCKET_CONTRACTS", "clients-contracts-papex")
BUCKET_RECEIPTS = os.getenv("BUCKET_RECEIPTS", "clients-payment-receipt-papex")
BUCKET_INVOICES = os.getenv("BUCKET_INVOICES", "clients-invoices-papex")
BUCKET_CV = os.getenv("BUCKET_CV", "candidate-cv-papex")

SCW_BUCKETS = {
    "avatars": BUCKET_USERS_AVATARS,
    "documents": BUCKET_CLIENT_DOCUMENTS,
    "contracts": BUCKET_CONTRACTS,
    "receipts": BUCKET_RECEIPTS,
    "invoices": BUCKET_INVOICES,
    "candidates": BUCKET_CV,
}


# Si l'utilisateur active AWS/SCW dans son .env → utiliser le backend S3
if STORAGE_BACKEND == "aws":
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"