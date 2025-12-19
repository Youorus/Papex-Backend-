from urllib.parse import unquote, urlparse

from rest_framework import serializers

from api.candidate.models import Candidate
from api.utils.cloud.scw.bucket_utils import generate_presigned_url


class CandidateSerializer(serializers.ModelSerializer):
    """
    Serializer CRUD pour les candidatures.
    - Le CV est stocké en base comme URL brute
    - L’API retourne TOUJOURS une URL signée temporaire
    """

    cv_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Candidate
        fields = [
            "id",
            "job",
            "first_name",
            "last_name",
            "email",
            "cv_url",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "cv_url"]

    # -------------------------
    # URL SIGNÉE
    # -------------------------

    def get_cv_url(self, obj):
        if not obj.cv_url:
            return None

        parsed = urlparse(obj.cv_url)
        path = unquote(parsed.path)
        key = "/".join(path.strip("/").split("/")[1:])  # enlève le bucket

        return generate_presigned_url("candidates", key)

    # -------------------------
    # Validations simples
    # -------------------------

    def validate_first_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError(
                "Le prénom doit contenir au moins 2 caractères."
            )
        return value

    def validate_last_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError(
                "Le nom doit contenir au moins 2 caractères."
            )
        return value
