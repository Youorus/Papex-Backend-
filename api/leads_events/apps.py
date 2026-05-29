from django.apps import AppConfig


class LeadsEventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.leads_events"
    verbose_name = "Lead Events"

    def ready(self):
        import api.leads_events.audit_signals
