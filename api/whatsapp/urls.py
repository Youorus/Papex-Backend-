# api/whatsapp/urls.py
from django.urls import path
from .views import (
    whatsapp_webhook,
    conversation_list,
    message_list,
    send_message,
    mark_as_read,
)

urlpatterns = [
    # Webhook Meta (GET = vérification, POST = réception)
    path("webhook/",                                    whatsapp_webhook, name="whatsapp_webhook"),

    # Liste de toutes les conversations (leads avec messages)
    path("conversations/",                              conversation_list, name="whatsapp_conversations"),

    # Messages d'un lead spécifique
    path("conversations/<int:lead_id>/messages/",       message_list, name="whatsapp_messages"),

    # Marquer les messages d'un lead comme lus
    path("conversations/<int:lead_id>/read/",           mark_as_read, name="whatsapp_mark_read"),

    # Envoyer un message
    path("send/",                                       send_message, name="whatsapp_send"),
]

# À inclure dans le router principal :
# path("api/whatsapp/", include("api.whatsapp.urls")),
