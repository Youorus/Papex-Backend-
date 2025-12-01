from .base import *
import os
import dj_database_url
from redis import SSLConnection
import ssl

DEBUG = False
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",")

DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL"),
        conn_max_age=600,
        ssl_require=True,
    )
}

STATIC_URL = "/static/"
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
CSRF_TRUSTED_ORIGINS = os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_DOMAIN = ".tds-dossier.fr"
CSRF_COOKIE_DOMAIN = ".tds-dossier.fr"
SESSION_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SAMESITE = "None"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

STORAGE_BACKEND = "aws"
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "fr-par")
AWS_S3_ADDRESSING_STYLE = os.getenv("AWS_S3_ADDRESSING_STYLE", "path")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
AWS_S3_VERIFY = os.getenv("AWS_S3_VERIFY", "True").lower() in ("true", "1", "yes")

USE_UPSTASH = "upstash.io" in os.getenv("REDIS_URL", "")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [{
                "address": os.getenv("REDIS_URL"),
                **({"connection_class": SSLConnection} if USE_UPSTASH else {}),
            }],
        },
    },
}

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
if CELERY_BROKER_URL and CELERY_BROKER_URL.startswith("rediss://"):
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        "ssl_cert_reqs": ssl.CERT_NONE
    }
else:
    CELERY_BROKER_TRANSPORT_OPTIONS = {}

CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"