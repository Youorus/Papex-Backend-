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
        default=None,
    )

    class Meta:
        model = Document
        fields = [
            "id",
            "client",
            "document_type",
            "document_type_name",
            "url",
            "uploaded_at",
        ]
        read_only_fields = ["id", "uploaded_at", "url"]

    def get_url(self, obj) -> str | None:
        """Retourne une URL signée temporaire (15 min) pour le document."""
        if not obj.url:
            return None

        try:
            parsed = urlparse(obj.url)
            path   = unquote(parsed.path).lstrip("/")
            parts  = path.split("/")
            key    = "/".join(parts[1:]) if len(parts) > 1 else parts[0]
            return generate_presigned_url("documents", key)
        except Exception:
            return None