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
from rest_framework_simplejwt.tokens import RefreshToken
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
    httponly=False,  # 👈 lisible par Next middleware
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

        # ✅ VÉRIFICATION CRITIQUE : compte actif
        if not user.is_active:
            logger.warning(f"❌ Tentative de connexion d'un compte inactif : {user.email}")
            return Response(
                {"detail": "Ce compte est désactivé. Contactez l'administrateur."},
                status=status.HTTP_403_FORBIDDEN
            )

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
        # ✅ Optionnel : blacklister le refresh token
        refresh_token = request.COOKIES.get("refresh_token")

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
                logger.info("🔒 Refresh token blacklisté")
            except Exception as e:
                logger.warning(f"⚠️ Impossible de blacklister le token : {e}")

        response = Response(status=status.HTTP_204_NO_CONTENT)

        # ✅ Supprimer TOUS les cookies d'auth
        for cookie in ("access_token", "refresh_token", "user_role"):
            response.delete_cookie(
                key=cookie,
                path="/",
                domain=COOKIE_DOMAIN,
                samesite=COOKIE_SAMESITE,
            )

        logger.info("👋 Déconnexion terminée.")
        return response


# =========================================================
# 🔐 REFRESH TOKEN (CORRIGÉ)
# =========================================================

class CustomTokenRefreshView(TokenRefreshView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            logger.warning("❌ Refresh token manquant")
            return Response(
                {"detail": "Missing refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            # ✅ Créer un objet RefreshToken pour rotation
            refresh = RefreshToken(refresh_token)

            # ✅ Générer un NOUVEAU access token
            access_token = str(refresh.access_token)

            # ✅ ROTATION : générer un NOUVEAU refresh token
            refresh.set_jti()
            refresh.set_exp()
            new_refresh_token = str(refresh)

        except (TokenError, InvalidToken) as e:
            logger.warning(f"❌ Refresh token invalide : {e}")
            return Response(
                {"detail": "Invalid refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        response = Response(
            {"detail": "Token refreshed"},
            status=status.HTTP_200_OK
        )

        # ✅ Mettre à jour le cookie access_token
        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=ACCESS_MAX_AGE,
            **COMMON_COOKIE_PARAMS,
        )

        # ✅ CRITIQUE : Mettre à jour le cookie refresh_token
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            max_age=REFRESH_MAX_AGE,
            **COMMON_COOKIE_PARAMS,
        )

        logger.info("♻️ Tokens rafraîchis avec succès")
        return response