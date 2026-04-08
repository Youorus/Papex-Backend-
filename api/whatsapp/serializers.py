from rest_framework import serializers
from .models import WhatsAppMessage
from api.leads.models import Lead

class WhatsAppMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppMessage
        fields = ['id', 'body', 'is_outbound', 'timestamp', 'sender_phone']

class LeadChatSerializer(serializers.ModelSerializer):
    # Affiche le dernier message pour l'aperçu dans la liste
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = ['id', 'first_name', 'last_name', 'phone', 'last_message']

    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        return WhatsAppMessageSerializer(last_msg).data if last_msg else None