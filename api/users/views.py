# users/test_views.py

from django.contrib.auth.password_validation import validate_password
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.users.models import User
from api.users.permissions import IsAdminRole
from api.users.roles import UserRoles
from api.users.serializers import UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet principal pour gérer les utilisateurs :
    - CRUD complet
    - Activation/désactivation
    - Changement de mot de passe
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    pagination_class = None  # À adapter si pagination requise

    search_fields = ["email", "first_name", "last_name"]
    ordering_fields = ["date_joined", "email"]

    @action(detail=True, methods=["patch"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        """
        Active ou désactive un utilisateur.
        """
        user = self.get_object()
        is_active = request.data.get("is_active")
        if is_active is None:
            return Response(
                {"is_active": "Ce champ est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = bool(is_active)
        user.save()
        return Response({"is_active": user.is_active}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="juristes")
    def juristes(self, request):
        juristes = User.objects.filter(role=UserRoles.JURISTE, is_active=True)
        serializer = self.get_serializer(juristes, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path="conseillers",
        permission_classes=[IsAuthenticated],
    )
    def conseillers(self, request):
        """
        Retourne la liste des conseillers actifs (role=CONSEILLER, is_active=True).
        Accessible à tous les utilisateurs connectés.
        """
        conseillers = User.objects.filter(role=UserRoles.CONSEILLER, is_active=True)
        serializer = self.get_serializer(conseillers, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["patch"], url_path="change-password")
    def change_password(self, request, pk=None):
        """
        Permet à l’admin de changer le mot de passe d’un utilisateur.
        """
        user = self.get_object()
        new_password = request.data.get("new_password")

        if not new_password:
            return Response(
                {"new_password": "Le nouveau mot de passe est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.check_password(new_password):
            return Response(
                {"new_password": "Le mot de passe doit être différent de l’actuel."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(new_password, user=user)
        except Exception as e:
            raise DRFValidationError({"new_password": list(e.messages)})

        user.set_password(new_password)
        user.save()
        return Response(status=status.HTTP_200_OK)
