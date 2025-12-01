# api/apps.py
from django.apps import AppConfig


class ApiConfig(AppConfig):
    """
    Configuration de l’application « api ».
    - Active les signaux WebSocket (création / mise à jour / suppression de Lead)
    - Initialise tout autre code de démarrage propre à l’app
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self) -> None:  # noqa: D401
        """
        Méthode appelée automatiquement par Django au démarrage.
        On y importe les modules qui doivent enregistrer des « side-effects »
        (signaux, caches warm-up, etc.) afin d’éviter les importations circulaires.
        """
        # Signaux WebSocket pour notifier les événements Lead
        import api.websocket.signals.clients  # noqa: F401
        import api.websocket.signals.comments  # noqa: F401
        import api.websocket.signals.contracts  # noqa: F401
        import api.websocket.signals.leads  # noqa: F401
        import api.websocket.signals.payments  # noqa: F401
