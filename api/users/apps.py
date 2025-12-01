# api/users/apps.py

from django.apps import AppConfig

class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.users"

    def ready(self):
        import api.websocket.signals.leads
        import api.websocket.signals.clients