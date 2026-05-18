from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CreatorsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.creators"
    verbose_name = _("Gestion des Créateurs")
