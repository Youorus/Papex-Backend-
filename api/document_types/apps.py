from django.apps import AppConfig


class DocumentTypesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.document_types"
    label = "document_types"  # 🔥 CRUCIAL