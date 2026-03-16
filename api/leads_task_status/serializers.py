"""
Serializer DRF pour les statuts de tâches.
"""

from rest_framework import serializers

from .models import LeadTaskStatus


class LeadTaskStatusSerializer(serializers.ModelSerializer):
    """
    Serializer permettant le CRUD complet des statuts de tâches.

    Utilisé pour :
        - configurer les statuts CRM
        - alimenter les selects frontend
        - gérer les workflows
    """

    class Meta:
        model = LeadTaskStatus

        fields = [
            "id",
            "code",
            "label",
            "is_final",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
        ]

    def validate_code(self, value):
        """
        Normalise le code en uppercase.
        """
        return value.upper()