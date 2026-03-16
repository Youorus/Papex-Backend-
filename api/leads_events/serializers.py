"""
api/leads/events/serializers.py
"""

from rest_framework import serializers
from .models import LeadEvent


class LeadEventSerializer(serializers.ModelSerializer):

    actor_name = serializers.SerializerMethodField()
    event_label = serializers.CharField(source="event_type.label", read_only=True)

    class Meta:
        model = LeadEvent
        fields = [
            "id",
            "lead",
            "event_type",
            "event_label",
            "actor",
            "actor_name",
            "data",
            "note",
            "occurred_at",
        ]

        read_only_fields = [
            "id",
            "occurred_at",
        ]

    def get_actor_name(self, obj):
        if obj.actor:
            return obj.actor.get_full_name()
        return "Système"