# -----------------------------------------------------------------------------
# CACHES
# ✅ DatabaseCache partagé entre tous les process (webhook + workers Q)
# Le LocMemCache était isolé par process → le debounce token était invisible
# du worker Django-Q, causant des tâches ignorées ou en double.
# -----------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
        "TIMEOUT": 3600,
    }
}

# -----------------------------------------------------------------------------
# DJANGO-Q2
# ✅ Remplace Celery + Celery Beat + Redis broker
# Broker : ta base Postgres (aucune dépendance externe supplémentaire)
# -----------------------------------------------------------------------------
Q_CLUSTER = {
    "name": "papex",

    # ── Broker ──────────────────────────────────────────────
    "orm": "default",  # Postgres — aucun Redis nécessaire pour les tâches

    # ── Workers ─────────────────────────────────────────────
    "workers": 4,

    # ── File mémoire par worker ──────────────────────────────
    "queue_limit": 5,

    # ── Retry & timeouts ────────────────────────────────────
    # ⚠️  RÈGLE : retry DOIT être > timeout (sinon Django-Q relance
    #     la tâche avant qu'elle soit finie → comportement cassé)
    # Kemora : ~10s nominal, 90s max avec timeout réseau
    "timeout": 90,
    "retry": 120,       # ← était 60, corrigé à 120 (> timeout=90)
    "max_attempts": 2,

    # ── Polling ─────────────────────────────────────────────
    "poll": 1,

    # ── Scheduler ───────────────────────────────────────────
    "schedule_tasks": True,

    # ── Timezone ────────────────────────────────────────────
    "timezone": "Europe/Paris",

    # ── Compression des arguments ───────────────────────────
    "compress": True,

    # ── Sauvegarde des résultats ────────────────────────────
    "save_limit": 500,

    # ── Log level ───────────────────────────────────────────
    "log_level": "INFO",
}