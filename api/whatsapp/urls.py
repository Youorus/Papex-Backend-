# api/whatsapp/urls.py
from django.urls import path
from .views import whatsapp_webhook

urlpatterns = [
    # api/whatsapp/urls.py
    path("", whatsapp_webhook, name="whatsapp_webhook"), # On enlève 'webhook/' pour tester
]