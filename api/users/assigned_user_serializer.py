# assigned_user_serializer.py
from rest_framework import serializers

from api.users.models import User
from api.utils.cloud.scw.bucket_utils import generate_presigned_url


class AssignedUserSerializer(serializers.ModelSerializer):
    """
    Serializer minimaliste pour afficher l’utilisateur assigné à une ressource.
    Inclut l’URL signée complète de l’avatar.
    """

    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "email", "avatar", "avatar_url")

    def get_avatar_url(self, obj):
        if obj.avatar:
            return generate_presigned_url("avatars", obj.avatar)
        return None