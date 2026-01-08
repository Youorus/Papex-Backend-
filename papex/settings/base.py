import os
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------------------------
# BASE DIR
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# -------------------------------------------------------------------
# ENV / DEBUG / SECRET
# -------------------------------------------------------------------
ENV = os.getenv("ENV", "production")
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me")

# En base on met False, et on override ailleurs si besoin
DEBUG = ENV != "production"

DJANGO_LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO").upper()

# ✅ JWT cookies max-age (en secondes)
ACCESS_MAX_AGE = int(os.getenv("ACCESS_TOKEN_LIFETIME_SECONDS", "900"))  # 15 min par défaut
REFRESH_MAX_AGE = int(os.getenv("REFRESH_TOKEN_LIFETIME_SECONDS", "604800"))  # 7 jours

ALLOWED_HOSTS = []  # Complété dans prod/local_prod

# -------------------------------------------------------------------
# APPS
# -------------------------------------------------------------------
DJANGO_APPS = [
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
    "django_celery_beat",
    "django_extensions",
    "background_task",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # ✅ AJOUTÉ pour blacklist
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
    "api.candidate"
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# -------------------------------------------------------------------
# MIDDLEWARE
# -------------------------------------------------------------------
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

# -------------------------------------------------------------------
# TEMPLATES
# -------------------------------------------------------------------
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

# -------------------------------------------------------------------
# AUTH
# -------------------------------------------------------------------
AUTH_USER_MODEL = "users.user"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -------------------------------------------------------------------
# I18N
# -------------------------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

# -------------------------------------------------------------------
# REST + JWT
# -------------------------------------------------------------------
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
    "PAGE_SIZE": 100,
}

# ✅ CONFIGURATION JWT AMÉLIORÉE
SIMPLE_JWT = {
    # Durées de vie
    "ACCESS_TOKEN_LIFETIME": timedelta(seconds=ACCESS_MAX_AGE),
    "REFRESH_TOKEN_LIFETIME": timedelta(seconds=REFRESH_MAX_AGE),

    # ✅ ROTATION ET BLACKLIST (CRITIQUE)
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,

    # Algorithme
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,

    # Headers
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",

    # Claims
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",

    # ✅ Token types
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",

    # ✅ Sliding tokens (optionnel)
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
    "SLIDING_TOKEN_LIFETIME": timedelta(days=7),
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",

    # ✅ Claims de base
    "JTI_CLAIM": "jti",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
}

# -------------------------------------------------------------------
# STATIC FILES
# -------------------------------------------------------------------
STATIC_URL = "/static/"

# -------------------------------------------------------------------
# CACHES (locmem par défaut, safe)
# -------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "papex-cache",
        "TIMEOUT": 3600,
    }
}

# -------------------------------------------------------------------
# EMAIL
# -------------------------------------------------------------------
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND")
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)

# -------------------------------------------------------------------
# FRONTEND URL
# -------------------------------------------------------------------
FRONTEND_URL = os.getenv("FRONTEND_URL")

# -------------------------------------------------------------------
# 📩 OVH SMS
# -------------------------------------------------------------------
APP_KEY = os.getenv("APP_KEY")
APP_SECRET = os.getenv("APP_SECRET")
CONSUMER_KEY = os.getenv("CONSUMER_KEY")

SERVICE_SMS = os.getenv("SERVICE_SMS")
SENDER = os.getenv("SENDER", "PAPEX")

WKHTMLTOPDF_PATH = os.getenv("WKHTMLTOPDF_PATH", None)

# -------------------------------------------------------------------
# SECURITY HEADERS (safe aussi en dev)
# -------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# En base on aligne SameSite sur la config JWT
SESSION_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SAMESITE = "None"

# -------------------------------------------------------------------
# LOGGING
# -------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[{levelname}] {asctime} — {name} — {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {"handlers": ["console"], "level": DJANGO_LOG_LEVEL},
}