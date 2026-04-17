import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
from redis import SSLConnection

# -----------------------------------------------------------------------------
# ENV
# -----------------------------------------------------------------------------
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

ENV = os.getenv("ENV", "production")
DEBUG = True

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me")
DJANGO_LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO").upper()

# -----------------------------------------------------------------------------
# HOSTS / URLS
# -----------------------------------------------------------------------------
ALLOWED_HOSTS = [
    h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()
]
FRONTEND_URL = os.getenv("FRONTEND_URL")

# -----------------------------------------------------------------------------
# APPS
# -----------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",        # ✅ Requis pour /admin/
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "corsheaders",
    "storages",
    "channels",
    "django_q",          # ✅ Django-Q2 remplace django_celery_beat + celery
    "django_filters",
    "drf_spectacular",
    "rest_framework",
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
    "api.leads_event_type",
    "api.leads_events",
    "api.whatsapp",
    "api.leads_task_type",
    "api.leads_task_status",
    "api.leads_task",
    "api.document_types",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# -----------------------------------------------------------------------------
# MIDDLEWARE
# -----------------------------------------------------------------------------
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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

AUTHENTICATION_BACKENDS = [
    "api.custom_auth.authentication.EmailBackend",
]


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# -----------------------------------------------------------------------------
# I18N
# -----------------------------------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

# -----------------------------------------------------------------------------
# REST FRAMEWORK
# -----------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "PAGE_SIZE": 30,
}

# -----------------------------------------------------------------------------
# STATIC
# -----------------------------------------------------------------------------
STATIC_URL = "/static/"

# -----------------------------------------------------------------------------
# CACHES
# -----------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "papex-cache",
        "TIMEOUT": 3600,
    }
}

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# -----------------------------------------------------------------------------
# EMAIL (SMTP)
# -----------------------------------------------------------------------------
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() in ("true", "1")
EMAIL_USE_SSL = False
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    f"Papiers Express <{EMAIL_HOST_USER}>"
)
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# -----------------------------------------------------------------------------
# OVH SMS / PHONE
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


# WhatsApp Meta Cloud API
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN    = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_VERIFY_TOKEN    = os.getenv("WHATSAPP_VERIFY_TOKEN", "papex_secret_2026")

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_DOMAIN = COOKIE_DOMAIN
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_SAMESITE = "None"

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_DOMAIN = COOKIE_DOMAIN
CSRF_COOKIE_PATH = "/"
CSRF_COOKIE_SAMESITE = "None"

SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# -----------------------------------------------------------------------------
# CORS / CSRF
# -----------------------------------------------------------------------------
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

# -----------------------------------------------------------------------------
# DATABASE (Render/Postgres)
# -----------------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL"),
        conn_max_age=60,
        ssl_require=True,
        engine="django.db.backends.postgresql",
    )
}

DATABASES["default"]["OPTIONS"] = {
    "sslmode": "require",
    "connect_timeout": 15,
    "client_encoding": "UTF8",
}

DATABASES["default"].update(
    {
        "ATOMIC_REQUESTS": False,
        "CONN_HEALTH_CHECKS": True,
        "DISABLE_SERVER_SIDE_CURSORS": True,
    }
)

SPECTACULAR_SETTINGS = {
    "TITLE": "Papiers Express API",
    "DESCRIPTION": "Documentation des endpoints de l'application Papex",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Tu peux choisir le style de Swagger
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": True,
    },
}

# -----------------------------------------------------------------------------
# REDIS (uniquement pour Django Channels — WebSocket)
# ✅ Plus utilisé comme broker de tâches (c'est la DB Postgres qui s'en charge)
# -----------------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

USE_UPSTASH = "upstash.io" in REDIS_URL
IS_REDIS_SSL = REDIS_URL.startswith("rediss://")

# -----------------------------------------------------------------------------
# CHANNELS (WebSocket — Redis conservé uniquement ici)
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
# DJANGO-Q2
# ✅ Remplace Celery + Celery Beat + Redis broker
# Broker : ta base Postgres (aucune dépendance externe supplémentaire)
# Un seul worker léger suffit sur 1 CPU / 2 Go RAM
# -----------------------------------------------------------------------------
Q_CLUSTER = {
    "name": "papex",

    # ── Broker ──────────────────────────────────────────────
    # "orm" = ta base Postgres. Aucun Redis, aucun RabbitMQ nécessaire.
    "orm": "default",

    # ── Workers ─────────────────────────────────────────────
    # Sur 1 CPU / 2 Go : 2 workers est le bon équilibre.
    # Augmenter au-delà de 4 saturera le CPU sur Render Standard.
    "workers": 2,

    # ── Taille de la file mémoire par worker ────────────────
    # Limite la RAM consommée (10 tâches max en attente par worker).
    "queue_limit": 10,

    # ── Retry & timeouts ────────────────────────────────────
    "retry": 400,           # Réessaie une tâche échouée après 60 s
    "timeout": 300,        # Tâche killée si > 5 min (évite les zombies)
    "max_attempts": 3,     # 3 tentatives max avant abandon définitif

    # ── Polling ─────────────────────────────────────────────
    # Fréquence de polling de la DB (en secondes).
    # 2 s = réactif sans marteler la base.
    "poll": 2,

    # ── Scheduler ───────────────────────────────────────────
    # Activer le scheduler interne (remplace Celery Beat)
    "schedule_tasks": True,

    # ── Timezone ────────────────────────────────────────────
    "timezone": "Europe/Paris",

    # ── Compression des arguments ───────────────────────────
    # Réduit la taille des payloads stockés en base.
    "compress": True,

    # ── Sauvegarde des résultats réussis ────────────────────
    # Garde les 250 derniers résultats (succès + erreurs)
    "save_limit": 250,

    # ── Log level ───────────────────────────────────────────
    "log_level": "INFO",
}

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

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

if STORAGE_BACKEND == "aws":
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 heures
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# -----------------------------------------------------------------------------
# LOGGING
# -----------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "verbose": {
            "format": "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        },
        "simple": {
            "format": "[%(levelname)s] %(message)s",
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },

    "loggers": {
        # 🔥 Django-Q logs
        "django_q": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },

        # 🔥 Tes apps
        "api": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
    },

    "root": {
        "handlers": ["console"],
        "level": DJANGO_LOG_LEVEL,
    },
}