from rest_framework import serializers
from api.statut_dossier_interne.models import StatutDossierInterne


class StatutDossierInterneSerializer(serializers.ModelSerializer):
    """
    Serializer principal pour StatutDossierInterne.
    Normalise automatiquement le champ code.
    """

    class Meta:
        model = StatutDossierInterne
        fields = ["id", "code", "label", "description", "color"]
        extra_kwargs = {
            "label": {"required": False, "allow_blank": True},
            "description": {"required": False, "allow_blank": True},
        }

    def validate_code(self, value):
        # Supprime espaces, majuscules, underscore
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