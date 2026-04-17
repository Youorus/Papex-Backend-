# api/whatsapp/urls.py
from django.urls import path
from .views import (
    whatsapp_webhook,
    conversation_list,
    message_list,
    message_list_unknown,
    send_message,
    mark_as_read,
    mark_as_read_unknown,
    agent_settings_lead,
    agent_settings_unknown,
)

urlpatterns = [
    # Webhook Meta
    path("webhook/",
         whatsapp_webhook, name="whatsapp_webhook"),

    # Conversations
    path("conversations/",
         conversation_list, name="whatsapp_conversations"),

    # Messages — lead connu
    path("conversations/<int:lead_id>/messages/",
         message_list, name="whatsapp_messages"),

    # Messages — inconnu
    path("conversations/unknown/<str:phone>/messages/",
         message_list_unknown, name="whatsapp_messages_unknown"),

    # Marquer lu — lead connu
    path("conversations/<int:lead_id>/read/",
         mark_as_read, name="whatsapp_mark_read"),

    # Marquer lu — inconnu
    path("conversations/unknown/<str:phone>/read/",
         mark_as_read_unknown, name="whatsapp_mark_read_unknown"),

    # Toggle agent — lead connu
    path("conversations/<int:lead_id>/agent/",
         agent_settings_lead, name="whatsapp_agent_lead"),

    # Toggle agent — inconnu
    path("conversations/unknown/<str:phone>/agent/",
         agent_settings_unknown, name="whatsapp_agent_unknown"),

    # Envoi manuel
    path("send/",
         send_message, name="whatsapp_send"),
]