# papex/settings/production.py
import os
import ssl
from datetime import timedelta
from pathlib import Path

import dj_database_url
from kombu import Queue
from dotenv import load_dotenv
from redis import SSLConnection

# -----------------------------------------------------------------------------
# ENV
# -----------------------------------------------------------------------------
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

ENV = os.getenv("ENV", "production")
DEBUG = False  # prod = False

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me")
DJANGO_LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO").upper()

# -----------------------------------------------------------------------------
# HOSTS / URLS
# -----------------------------------------------------------------------------
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
FRONTEND_URL = os.getenv("FRONTEND_URL")

# -----------------------------------------------------------------------------
# APPS
# -----------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

CELERY_TASK_QUEUES = (
    Queue("default"),
    Queue("emails"),
    Queue("sms"),
)

CELERY_TASK_DEFAULT_QUEUE = "default"

THIRD_PARTY_APPS = [
    "corsheaders",
    "storages",
    "channels",
    "django_celery_beat",
    "django_extensions",
    "background_task",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
]

LOCAL_APPS = [
    "api.custom_auth",
    "api.clients",
    "api.comments",
    "api.contracts",
    "api.documents",
    "api.lead_status",
    "api.leads",
    "api.payments",
    "api.profile",
    "api.services",
    "api.statut_dossier",
    "api.statut_dossier_interne",
    "api.users",
    "api.booking",
    "api.appointment",
    "api.jurist_appointment",
    "api.websocket",
    "api.special_closing_period",
    "api.opening_hours",
    "api.jurist_availability_date",
    "api.user_unavailability",
    "api.job",
    "api.sms",
    "api.core",
    "api.phone",
    "api.candidate",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# -----------------------------------------------------------------------------
# MIDDLEWARE
# -----------------------------------------------------------------------------
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",
]

ROOT_URLCONF = "papex.urls"
WSGI_APPLICATION = "papex.wsgi.application"
ASGI_APPLICATION = "papex.asgi.application"

# -----------------------------------------------------------------------------
# TEMPLATES
# -----------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

# -----------------------------------------------------------------------------
# AUTH
# -----------------------------------------------------------------------------
AUTH_USER_MODEL = "users.user"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -----------------------------------------------------------------------------
# I18N
# -----------------------------------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

# -----------------------------------------------------------------------------
# REST + JWT
# -----------------------------------------------------------------------------
ACCESS_MAX_AGE = int(os.getenv("ACCESS_TOKEN_LIFETIME_SECONDS", "900"))
REFRESH_MAX_AGE = int(os.getenv("REFRESH_TOKEN_LIFETIME_SECONDS", "604800"))

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "api.custom_auth.authentication.CookieJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 5,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(seconds=ACCESS_MAX_AGE),
    "REFRESH_TOKEN_LIFETIME": timedelta(seconds=REFRESH_MAX_AGE),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# -----------------------------------------------------------------------------
# STATIC
# -----------------------------------------------------------------------------
STATIC_URL = "/static/"

# -----------------------------------------------------------------------------
# CACHES (ok en prod si tu assumes cache local par instance)
# -----------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "papex-cache",
        "TIMEOUT": 3600,
    }
}

# -----------------------------------------------------------------------------
# EMAIL (SMTP)
# -----------------------------------------------------------------------------
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() in ("true", "1")
EMAIL_USE_SSL = False
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", f"Papiers Express <{EMAIL_HOST_USER}>")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# -----------------------------------------------------------------------------
# OVH SMS
# -----------------------------------------------------------------------------
OVH_SMS_APP_KEY = os.getenv("OVH_SMS_APP_KEY")
OVH_SMS_APP_SECRET = os.getenv("OVH_SMS_APP_SECRET")
OVH_SMS_CONSUMER_KEY = os.getenv("OVH_SMS_CONSUMER_KEY")
OVH_SMS_SERVICE_NAME = os.getenv("OVH_SMS_SERVICE_NAME")
OVH_SMS_SENDER = os.getenv("OVH_SMS_SENDER", "PAPEX")



OVH_PHONE_APP_KEY = os.getenv("OVH_PHONE_APP_KEY")
OVH_PHONE_APP_SECRET = os.getenv("OVH_PHONE_APP_SECRET")
OVH_PHONE_CONSUMER_KEY = os.getenv("OVH_PHONE_CONSUMER_KEY")

OVH_PHONE_BILLING_ACCOUNT = os.getenv("OVH_PHONE_BILLING_ACCOUNT")
OVH_PHONE_SIP_LINE = os.getenv("OVH_PHONE_SIP_LINE")


WKHTMLTOPDF_PATH = os.getenv("WKHTMLTOPDF_PATH")

# -----------------------------------------------------------------------------
# SECURITY HEADERS / COOKIES
# -----------------------------------------------------------------------------
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN")

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Cookies cross-subdomains
SESSION_COOKIE_DOMAIN = COOKIE_DOMAIN
CSRF_COOKIE_DOMAIN = COOKIE_DOMAIN

# frontend et backend sur sous-domaines différents => SameSite=None obligatoire
SESSION_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SAMESITE = "None"

# HTTPS derrière proxy/CDN (Cloudflare/Render)
SECURE_SSL_REDIRECT = False  # si Cloudflare force déjà HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# HSTS (recommandé en prod)
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# -----------------------------------------------------------------------------
# CORS / CSRF
# -----------------------------------------------------------------------------
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# -----------------------------------------------------------------------------
# DATABASE (Render/Postgres)
# -----------------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL"),
        conn_max_age=0,      # OK pour éviter les connexions zombies en environnements dynamiques
        ssl_require=True,
        engine="django.db.backends.postgresql",
    )
}

DATABASES["default"]["OPTIONS"] = {
    "sslmode": "require",
    "connect_timeout": 5,
    "client_encoding": "UTF8",
}

DATABASES["default"].update(
    {
        "ATOMIC_REQUESTS": False,
        "CONN_HEALTH_CHECKS": False,
        "DISABLE_SERVER_SIDE_CURSORS": True,
    }
)

# -----------------------------------------------------------------------------
# REDIS (shared for Channels + Celery)
# -----------------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL is required in production.")

USE_UPSTASH = "upstash.io" in REDIS_URL
IS_REDIS_SSL = REDIS_URL.startswith("rediss://")

# -----------------------------------------------------------------------------
# CHANNELS
# -----------------------------------------------------------------------------
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
            "capacity": 1500,
            "expiry": 20,
        },
    },
}

# -----------------------------------------------------------------------------
# CELERY (PROD SAFE)  ✅ C'EST ICI QUE TON PROBLÈME ÉTAIT
# -----------------------------------------------------------------------------
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)

# Transport options robustes contre les resets Redis Cloud
CELERY_BROKER_TRANSPORT_OPTIONS = {
    # si le worker meurt / perd la connexion, Redis ré-expose la tâche après ce délai
    "visibility_timeout": int(os.getenv("CELERY_VISIBILITY_TIMEOUT", "3600")),
    # keepalive + healthcheck pour éviter idle timeout / resets
    "socket_keepalive": True,
    "retry_on_timeout": True,
    "health_check_interval": int(os.getenv("CELERY_HEALTHCHECK_INTERVAL", "30")),
}

CELERY_TASK_ROUTES = {
    # Emails
    "api.utils.email.*": {"queue": "emails"},
    "api.utils.email.**": {"queue": "emails"},

    # SMS
    "api.sms.*": {"queue": "sms"},
    "api.sms.**": {"queue": "sms"},
}

# SSL pour rediss:// si un jour tu passes en TLS
if IS_REDIS_SSL:
    CELERY_BROKER_TRANSPORT_OPTIONS["ssl_cert_reqs"] = ssl.CERT_NONE

# 🔥 LE RÉGLAGE QUI ÉVITE LES MESSAGES "RÉSERVÉS MAIS PAS TRAITÉS"
worker_prefetch_multiplier = int(os.getenv("CELERY_PREFETCH_MULTIPLIER", "1"))

# Comportement ACK solide en cas de coupure broker
task_acks_late = os.getenv("CELERY_ACKS_LATE", "true").lower() in ("true", "1")
task_reject_on_worker_lost = os.getenv("CELERY_REJECT_ON_WORKER_LOST", "true").lower() in ("true", "1")

# Anticipation Celery 6 (ne pas tuer les tâches longues par surprise)
worker_cancel_long_running_tasks_on_connection_loss = (
    os.getenv("CELERY_CANCEL_LONG_RUNNING_ON_CONN_LOSS", "false").lower() in ("true", "1")
)

CELERY_TASK_TRACK_STARTED = True

CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", str(30 * 60)))
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", str(25 * 60)))

CELERY_RESULT_EXPIRES = int(os.getenv("CELERY_RESULT_EXPIRES", "3600"))

# -----------------------------------------------------------------------------
# STORAGE (Scaleway S3)
# -----------------------------------------------------------------------------
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL", "")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "fr-par")
AWS_S3_ADDRESSING_STYLE = os.getenv("AWS_S3_ADDRESSING_STYLE", "path")
AWS_S3_VERIFY = os.getenv("AWS_S3_VERIFY", "true").lower() in ("true", "1")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "")

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

if STORAGE_BACKEND == "aws":
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

# -----------------------------------------------------------------------------
# LOGGING
# -----------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": DJANGO_LOG_LEVEL,
    },
}