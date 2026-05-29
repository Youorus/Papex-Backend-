from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import update_last_login

logger = __import__("logging").getLogger(__name__)
User = get_user_model()


@sync_to_async
def get_cookie_settings():
    """
    Centralise la configuration des cookies pour la compatibilité prod/local.
    """
    if settings.DEBUG:
        return {
            "domain": None,  # Le navigateur utilisera le domaine actuel (localhost)
            "secure": False, # Autorise les cookies sur HTTP en local
            "samesite": "Lax",
        }
    else:
        # Requis pour l'auth cross-subdomain (api.papiers-express.fr -> creator.papiers-express.fr)
        return {
            "domain": ".papiers-express.fr",
            "secure": True, # N'envoie les cookies que sur HTTPS
            "samesite": "None",
        }


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"detail": "CSRF cookie set"})


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    async def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"detail": "Email et mot de passe requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = await sync_to_async(authenticate)(request, username=email, password=password)

        if user is None:
            return Response(
                {"detail": "Identifiants invalides."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        await sync_to_async(login)(request, user)
        await sync_to_async(update_last_login)(None, user)

        response = Response(
            {
                "detail": "Success",
                "role": getattr(user, "role", None),
                "user": {
                    "id": user.id,
                    "email": user.email,
                },
            },
            status=status.HTTP_200_OK,
        )

        cookie_settings = await get_cookie_settings()

        response.set_cookie(
            "csrftoken",
            get_token(request),
            httponly=False,
            secure=cookie_settings["secure"],
            samesite=cookie_settings["samesite"],
            domain=cookie_settings["domain"],
            path="/",
        )

        response.set_cookie(
            "user_role",
            getattr(user, "role", ""),
            httponly=False,
            secure=cookie_settings["secure"],
            samesite=cookie_settings["samesite"],
            domain=cookie_settings["domain"],
            path="/",
        )

        return response


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)

        response = Response(
            {"detail": "Logged out"},
            status=status.HTTP_200_OK,
        )

        cookie_settings = get_cookie_settings()
        cookie_domain = cookie_settings["domain"]

        # Pour supprimer un cookie, il faut spécifier le même domain et path
        response.delete_cookie("sessionid", domain=cookie_domain, path="/")
        response.delete_cookie("csrftoken", domain=cookie_domain, path="/")
        response.delete_cookie("user_role", domain=cookie_domain, path="/")

        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "id": user.id,
                "email": user.email,
                "role": getattr(user, "role", None),
                "is_authenticated": user.is_authenticated,
            },
            status=status.HTTP_200_OK,
        )