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
)

urlpatterns = [
    path("webhook/",                                        whatsapp_webhook,        name="whatsapp_webhook"),
    path("conversations/",                                  conversation_list,        name="whatsapp_conversations"),
    path("conversations/<int:lead_id>/messages/",           message_list,             name="whatsapp_messages"),
    path("conversations/unknown/<str:phone>/messages/",     message_list_unknown,     name="whatsapp_messages_unknown"),
    path("conversations/<int:lead_id>/read/",               mark_as_read,             name="whatsapp_mark_read"),
    path("conversations/unknown/<str:phone>/read/",         mark_as_read_unknown,     name="whatsapp_mark_read_unknown"),
    path("send/",                                           send_message,             name="whatsapp_send"),
]