from urllib.parse import unquote, urlparse

from rest_framework import serializers

from api.documents.models import Document
from api.utils.cloud.scw.bucket_utils import generate_presigned_url


class DocumentSerializer(serializers.ModelSerializer):
    """
    Serializer de document client, avec URL signée temporaire.
    """

    url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ["id", "client", "url", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at", "url"]

    def get_url(self, obj):
        """
        Retourne une URL signée temporaire pour le document.
        """
        if obj.url:
            parsed = urlparse(obj.url)
            path = unquote(parsed.path)  # /documents-clients/fichier.pdf
            key = "/".join(path.strip("/").split("/")[1:])  # enlève "documents-clients"
            return generate_presigned_url("documents", key)
        return None
