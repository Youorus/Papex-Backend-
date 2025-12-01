from rest_framework import serializers

from api.statut_dossier.models import StatutDossier


class StatutDossierSerializer(serializers.ModelSerializer):
    """
    Serializer principal pour StatutDossier.
    """

    class Meta:
        model = StatutDossier
        fields = ["id", "code", "label", "color"]

    def validate_code(self, value):
        # Supprime les espaces en début/fin, met en maj, remplace espaces par _
        return value.strip().upper().replace(" ", "_")

    def create(self, validated_data):
        # Enforce normalization at create level too (in case of missing validate_code)
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
