from urllib.parse import unquote, urlparse

from rest_framework import serializers

from api.documents.models import Document
from api.utils.cloud.scw.bucket_utils import generate_presigned_url


class DocumentSerializer(serializers.ModelSerializer):
    """
    Serializer de document client, avec URL signée temporaire.
    """

    url = serializers.SerializerMethodField()
    document_type_name = serializers.CharField(
        source="document_type.name",
        read_only=True,
    )

    class Meta:
        model = Document
        fields = [
            "id",
            "client",
            "document_type",        # ✅ ajout
            "document_type_name",   # ✅ ajout (lisible côté front)
            "url",
            "uploaded_at",
        ]
        read_only_fields = ["id", "uploaded_at", "url"]

    def get_url(self, obj):
        """
        Retourne une URL signée temporaire pour le document.
        """
        if not obj.url:
            return None

        try:
            parsed = urlparse(obj.url)
            path = unquote(parsed.path).lstrip("/")

            parts = path.split("/")

            # enlève le prefix bucket si présent
            if len(parts) > 1:
                key = "/".join(parts[1:])
            else:
                key = parts[0]

            return generate_presigned_url("documents", key)

        except Exception:
            return None