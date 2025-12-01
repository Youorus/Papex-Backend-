from rest_framework import serializers

from api.users.models import User
from api.utils.cloud.scw.bucket_utils import generate_presigned_url  # ou cloud.signing


class UserAvatarSerializer(serializers.ModelSerializer):
    """
    Serializer pour l’upload, la modification et l’affichage de l’avatar utilisateur.
    Tous les champs sauf avatar sont read-only pour l’intégrité.
    """

    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "avatar_url"]
        read_only_fields = ["id", "email", "first_name", "last_name", "avatar_url"]

    def get_avatar_url(self, obj):
        if obj.avatar:
            return generate_presigned_url(bucket_key="avatars", key=obj.avatar)
        return None
