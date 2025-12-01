import uuid

from django.conf import settings
from django.utils.text import slugify
from rest_framework import permissions, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from api.profile.serializers import UserAvatarSerializer
from api.users.models import User
from api.users.serializers import UserSerializer
from api.utils.cloud.scw.bucket_utils import delete_object, put_object


class UserAvatarViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour l’upload, la modification et la suppression des avatars utilisateur.
    PATCH = upload/update
    DELETE = suppression
    """

    serializer_class = UserAvatarSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return User.objects.all()

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Utiliser PATCH pour mettre à jour l'avatar."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        user = self.get_object()
        file = request.FILES.get("avatar")
        if not file:
            return Response(
                {"detail": "Aucun fichier reçu."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Supprimer l'ancien avatar
        if user.avatar:
            try:
                delete_object("avatars", user.avatar)
            except Exception as e:
                print(f"[Avatar] Erreur suppression ancien avatar: {e}")

        # Génère le nom de fichier : prénom_nom/uuid.ext
        first = slugify(user.first_name)
        last = slugify(user.last_name)
        ext = file.name.split(".")[-1].lower()
        filename = f"{first}_{last}/{uuid.uuid4().hex}.{ext}"

        # Upload dans Scaleway
        try:
            put_object(
                "avatars", filename, content=file.read(), content_type=file.content_type
            )
        except Exception as e:
            print(f"[Avatar] Erreur upload avatar: {e}")
            return Response(
                {"detail": "Erreur lors de l’envoi de l’avatar."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Mise à jour du champ avatar (stocke uniquement la key)
        user.avatar = filename
        user.save()

        serializer = UserSerializer(user, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user.avatar:
            try:
                delete_object("avatars", user.avatar)
            except Exception as e:
                print(f"[Avatar] Erreur suppression avatar : {e}")
            user.avatar = None
            user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
