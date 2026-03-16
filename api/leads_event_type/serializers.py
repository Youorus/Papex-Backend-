"""
api/leads/events/serializers.py
"""

from rest_framework import serializers
from .models import LeadEventType


class LeadEventTypeSerializer(serializers.ModelSerializer):
    """
    Serializer pour exposer les types d'événements via l'API.
    """

    class Meta:
        model = LeadEventType
        fields = [
            "id",
            "code",
            "label",
            "description",
            "is_system",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]