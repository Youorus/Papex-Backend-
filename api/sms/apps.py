from django.apps import AppConfig


class SmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.sms"

    def ready(self):
        # 🔥 FORCE l'import des tasks SMS au démarrage
        import api.sms.tasks