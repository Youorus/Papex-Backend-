from rest_framework import serializers
from .models import WhatsAppMessage, WhatsAppConversationSettings
from api.leads.models import Lead


class WhatsAppMessageSerializer(serializers.ModelSerializer):
    message_type = serializers.ReadOnlyField()

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
            # Médias
            "message_type",
            "media_id",
            "media_url",
            "media_mime_type",
            "media_caption",
            "media_filename",
        ]
        read_only_fields = [
            "id", "wa_id", "timestamp", "sender_phone",
            "delivery_status", "message_type",
        ]


class AgentSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppConversationSettings
        fields = ["agent_enabled", "updated_at"]
        read_only_fields = ["updated_at"]


class ConversationPreviewSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    is_unknown = serializers.SerializerMethodField()
    agent_enabled = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id",
            "first_name",
            "last_name",
            "phone",
            "last_message",
            "unread_count",
            "is_unknown",
            "agent_enabled",
        ]

    def get_last_message(self, obj):
        msg = obj.whatsapp_messages.order_by("-timestamp").first()
        return WhatsAppMessageSerializer(msg).data if msg else None

    def get_unread_count(self, obj):
        return obj.whatsapp_messages.filter(is_outbound=False, is_read=False).count()

    def get_is_unknown(self, obj):
        return False

    def get_agent_enabled(self, obj):
        try:
            return obj.whatsapp_settings.agent_enabled
        except WhatsAppConversationSettings.DoesNotExist:
            return True


class UnknownConversationSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)
    sender_phone = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    phone = serializers.CharField()
    last_message = WhatsAppMessageSerializer(allow_null=True)
    unread_count = serializers.IntegerField()
    is_unknown = serializers.BooleanField()
    agent_enabled = serializers.BooleanField()


class SendMessageSerializer(serializers.Serializer):
    lead_id = serializers.IntegerField(required=False, allow_null=True)
    phone = serializers.CharField(required=False, allow_null=True)
    body = serializers.CharField(max_length=4096)

    def validate(self, attrs):
        if not attrs.get("lead_id") and not attrs.get("phone"):
            raise serializers.ValidationError("lead_id ou phone est requis.")
        return attrs


class ToggleAgentSerializer(serializers.Serializer):
    agent_enabled = serializers.BooleanField()


class MediaDownloadSerializer(serializers.Serializer):
    """Payload pour demander l'URL de téléchargement d'un média."""
    media_id = serializers.CharField()