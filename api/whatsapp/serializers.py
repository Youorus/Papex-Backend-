# api/whatsapp/serializers.py
from rest_framework import serializers
from .models import WhatsAppMessage
from api.leads.models import Lead


class WhatsAppMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppMessage
        fields = [
            "id",
            "wa_id",
            "body",
            "is_outbound",
            "is_read",
            "delivery_status",
            "timestamp",
            "sender_phone",
        ]
        read_only_fields = ["id", "wa_id", "timestamp", "sender_phone", "delivery_status"]


class ConversationPreviewSerializer(serializers.ModelSerializer):
    """
    Utilisé dans la liste de gauche : un lead + son dernier message + nb non lus.
    """
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = ["id", "first_name", "last_name", "phone", "last_message", "unread_count"]

    def get_last_message(self, obj):
        msg = obj.whatsapp_messages.last()
        return WhatsAppMessageSerializer(msg).data if msg else None

    def get_unread_count(self, obj):
        return obj.whatsapp_messages.filter(is_outbound=False, is_read=False).count()


class SendMessageSerializer(serializers.Serializer):
    """
    Payload pour envoyer un message depuis l'app vers un lead.
    """
    lead_id = serializers.IntegerField()
    body = serializers.CharField(max_length=4096)
