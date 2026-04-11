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
    """Conversation pour un lead connu."""
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    is_unknown   = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = ["id", "first_name", "last_name", "phone", "last_message", "unread_count", "is_unknown"]

    def get_last_message(self, obj):
        msg = obj.whatsapp_messages.order_by("-timestamp").first()
        return WhatsAppMessageSerializer(msg).data if msg else None

    def get_unread_count(self, obj):
        return obj.whatsapp_messages.filter(is_outbound=False, is_read=False).count()

    def get_is_unknown(self, obj):
        return False


class UnknownConversationSerializer(serializers.Serializer):
    """Conversation pour un numéro inconnu (sans lead)."""
    id           = serializers.IntegerField(allow_null=True, required=False)  # ✅ Fix
    sender_phone = serializers.CharField()
    first_name   = serializers.CharField()
    last_name    = serializers.CharField()
    phone        = serializers.CharField()
    last_message = WhatsAppMessageSerializer(allow_null=True)
    unread_count = serializers.IntegerField()
    is_unknown   = serializers.BooleanField()


class SendMessageSerializer(serializers.Serializer):
    """Payload pour envoyer un message — vers un lead ou un numéro inconnu."""
    lead_id = serializers.IntegerField(required=False, allow_null=True)
    phone   = serializers.CharField(required=False, allow_null=True)
    body    = serializers.CharField(max_length=4096)

    def validate(self, attrs):
        if not attrs.get("lead_id") and not attrs.get("phone"):
            raise serializers.ValidationError("lead_id ou phone est requis.")
        return attrs