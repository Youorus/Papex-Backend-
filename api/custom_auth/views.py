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
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

import logging

from api.custom_auth.serializers import LoginSerializer

logger = logging.getLogger(__name__)
User = get_user_model()

# =========================================================
# 🔐 PARAMÈTRES CENTRALISÉS
# =========================================================

COOKIE_DOMAIN = getattr(settings, "COOKIE_DOMAIN", None)
COOKIE_SECURE = not settings.DEBUG
COOKIE_SAMESITE = "None" if COOKIE_SECURE else "Lax"

ACCESS_MAX_AGE = settings.ACCESS_MAX_AGE
REFRESH_MAX_AGE = settings.REFRESH_MAX_AGE

COMMON_COOKIE_PARAMS = dict(
    secure=COOKIE_SECURE,
    httponly=True,
    samesite=COOKIE_SAMESITE,
    domain=COOKIE_DOMAIN,
    path="/",
)

# Cookie non sensible (UX uniquement)
ROLE_COOKIE_PARAMS = dict(
    secure=COOKIE_SECURE,
    httponly=False,          # 👈 lisible par Next middleware
    samesite=COOKIE_SAMESITE,
    domain=COOKIE_DOMAIN,
    path="/",
)

# =========================================================
# 🔐 LOGIN
# =========================================================

class LoginView(APIView):
    authentication_classes = []
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

        # 🔑 JWT cookies (HttpOnly)
        response.set_cookie(
            key="access_token",
            value=tokens["access"],
            max_age=ACCESS_MAX_AGE,
            **COMMON_COOKIE_PARAMS,
        )

        response.set_cookie(
            key="refresh_token",
            value=tokens["refresh"],
            max_age=REFRESH_MAX_AGE,
            **COMMON_COOKIE_PARAMS,
        )

        # 🎯 Cookie UX pour middleware (non sensible)
        response.set_cookie(
            key="user_role",
            value=user.role,
            max_age=REFRESH_MAX_AGE,
            **ROLE_COOKIE_PARAMS,
        )

        logger.info(
            f"✅ Login OK — {user.email} | ROLE={user.role} | HTTPS={COOKIE_SECURE}"
        )

        return response


# =========================================================
# 🔐 LOGOUT
# =========================================================

@method_decorator(csrf_exempt, name="dispatch")
class LogoutView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        response = Response(status=status.HTTP_204_NO_CONTENT)

        for cookie in ("access_token", "refresh_token", "user_role"):
            response.delete_cookie(
                key=cookie,
                path="/",
                domain=COOKIE_DOMAIN,
            )

        logger.info("👋 Déconnexion terminée.")
        return response


# =========================================================
# 🔐 REFRESH TOKEN
# =========================================================

class CustomTokenRefreshView(TokenRefreshView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response(
                {"detail": "Missing refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = self.get_serializer(data={"refresh": refresh_token})

        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken):
            return Response(
                {"detail": "Invalid refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        access_token = serializer.validated_data["access"]

        response = Response(status=status.HTTP_200_OK)
        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=ACCESS_MAX_AGE,
            **COMMON_COOKIE_PARAMS,
        )

        return response

