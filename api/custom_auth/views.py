from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework_simplejwt.views import TokenRefreshView

from api.custom_auth.serializers import LoginSerializer
import logging

logger = logging.getLogger(__name__)

User = get_user_model()
IS_PROD = True

# 🔐 Paramètres communs pour les cookies, adaptés dynamiquement
COMMON_COOKIE_PARAMS = dict(
    secure=IS_PROD,
    samesite="None" if IS_PROD else "Lax",
    domain=".tds-dossier.fr" if IS_PROD else None,
    path="/",
)

class LoginView(APIView):
    """
    Vue API pour l’authentification d’un utilisateur.
    Pose les cookies JWT (HttpOnly) et renvoie un 200 avec le rôle dans le body.
    """
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            logger.warning("❌ Login invalide : %s", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        tokens = serializer.validated_data["tokens"]

        update_last_login(User, user)

        response = Response(
            {
                "detail": "Login successful",
                "role": user.role,
                "role_display": user.get_role_display(),
            },
            status=status.HTTP_200_OK,
        )

        response.set_cookie(
            key="access_token",
            value=tokens["access"],
            httponly=True,
            max_age=60 * 60,
            **COMMON_COOKIE_PARAMS,
        )
        response.set_cookie(
            key="refresh_token",
            value=tokens["refresh"],
            httponly=True,
            max_age=60 * 60 * 24 * 7,
            **COMMON_COOKIE_PARAMS,
        )

        logger.info("✅ Login réussi pour %s [%s]", user.email, "PROD" if IS_PROD else "DEV")
        return response


@method_decorator(csrf_exempt, name="dispatch")
class LogoutView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        response = Response(status=status.HTTP_204_NO_CONTENT)

        domain = ".tds-dossier.fr" if IS_PROD else None

        response.delete_cookie("access_token", path="/", domain=domain)
        response.delete_cookie("refresh_token", path="/", domain=domain)

        return response


class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response(
                {"detail": "Missing refresh token in cookies"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.data["refresh"] = refresh_token
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200 and "access" in response.data:
            access_token = response.data["access"]

            response.set_cookie(
                key="access_token",
                value=access_token,
                httponly=True,
                max_age=60 * 60,
                **COMMON_COOKIE_PARAMS,
            )
            del response.data["access"]

        return response