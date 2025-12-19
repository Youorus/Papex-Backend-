"""
Sérialiseurs pour l'application Jobs.
"""

from rest_framework import serializers
from api.job.models import Job


class JobSerializer(serializers.ModelSerializer):
    """
    Serializer complet pour le modèle Job.
    - slug généré côté modèle (read-only)
    - missions / profile : listes de chaînes validées
    """

    class Meta:
        model = Job
        fields = [
            "id",
            "slug",
            "title",
            "location",
            "type",
            "description",
            "missions",
            "profile",
            "diploma",
            "start_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    # -------------------------
    # Helpers
    # -------------------------
    def _validate_str_min(self, value, min_len, message):
        if value in (None, ""):
            return value
        value = value.strip()
        if len(value) < min_len:
            raise serializers.ValidationError(message)
        return value

    def _validate_list_of_str(
        self,
        value,
        min_items,
        min_len,
        empty_message,
        item_message,
    ):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Ce champ doit être une liste de chaînes de caractères."
            )

        cleaned = []
        for i, item in enumerate(value, start=1):
            if not isinstance(item, str):
                raise serializers.ValidationError(item_message.format(i=i))
            s = item.strip()
            if len(s) < min_len:
                raise serializers.ValidationError(
                    f"{item_message.format(i=i)} (minimum {min_len} caractères)"
                )
            cleaned.append(s)

        if len(cleaned) < min_items:
            raise serializers.ValidationError(empty_message)

        return cleaned

    # -------------------------
    # Validations champs simples
    # -------------------------
    def validate_title(self, value):
        return self._validate_str_min(
            value,
            5,
            "Le titre du poste doit contenir au moins 5 caractères.",
        )

    def validate_location(self, value):
        return self._validate_str_min(
            value,
            2,
            "Le lieu de travail doit être renseigné (minimum 2 caractères).",
        )

    def validate_type(self, value):
        return self._validate_str_min(
            value,
            2,
            "Le type de contrat doit être renseigné (minimum 2 caractères).",
        )

    def validate_description(self, value):
        value = self._validate_str_min(
            value,
            10,
            "La description courte doit contenir au moins 10 caractères.",
        )
        if value and len(value) > 500:
            raise serializers.ValidationError(
                "La description courte ne doit pas dépasser 500 caractères."
            )
        return value

    def validate_diploma(self, value):
        # Champ optionnel (blank=True dans le modèle)
        if not value:
            return ""
        return self._validate_str_min(
            value,
            5,
            "Le diplôme requis doit contenir au moins 5 caractères.",
        )

    def validate_start_date(self, value):
        # Champ optionnel (blank=True dans le modèle)
        if not value:
            return ""
        return self._validate_str_min(
            value,
            3,
            "La date de début doit contenir au moins 3 caractères.",
        )

    # -------------------------
    # Validations listes JSON
    # -------------------------
    def validate_missions(self, value):
        return self._validate_list_of_str(
            value=value,
            min_items=1,
            min_len=5,
            empty_message="Veuillez renseigner au moins une mission.",
            item_message="La mission #{i} doit être une chaîne de caractères valide.",
        )

    def validate_profile(self, value):
        return self._validate_list_of_str(
            value=value,
            min_items=1,
            min_len=5,
            empty_message="Veuillez renseigner au moins un élément de profil recherché.",
            item_message="Le critère #{i} du profil doit être une chaîne de caractères valide.",
        )


class JobListSerializer(serializers.ModelSerializer):
    """
    Serializer simplifié pour la liste des offres d'emploi.
    """

    class Meta:
        model = Job
        fields = [
            "id",
            "slug",
            "title",
            "location",
            "type",
            "description",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields