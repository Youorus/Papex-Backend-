"""
Serializer DRF pour LeadTaskType
"""

from rest_framework import serializers

from api.leads_task_type.models import LeadTaskType


class LeadTaskTypeSerializer(serializers.ModelSerializer):
    """
    Serializer permettant le CRUD complet des types de tâches.
    """

    class Meta:
        model = LeadTaskType
        fields = [
            "id",
            "code",
            "label",
            "description",
            "is_active",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
        ]