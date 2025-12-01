from rest_framework import serializers

from api.lead_status.models import LeadStatus


class LeadStatusSerializer(serializers.ModelSerializer):
    """
    Serializer pour exposer les informations publiques d’un statut de lead.
    Utilisé dans les listes déroulantes, le filtrage ou l’affichage détaillé.
    """

    class Meta:
        model = LeadStatus
        fields = ["id", "label", "color", "code"]

    def validate_code(self, value):
        return value.strip().upper().replace(" ", "_")

    def create(self, validated_data):
        validated_data["code"] = (
            validated_data["code"].strip().upper().replace(" ", "_")
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "code" in validated_data:
            validated_data["code"] = (
                validated_data["code"].strip().upper().replace(" ", "_")
            )
        return super().update(instance, validated_data)
