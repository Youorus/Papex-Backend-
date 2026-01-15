from django.conf import settings
from django.middleware.csrf import get_token
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

# Paramètres partagés
COOKIE_PARAMS = {
    'secure': not settings.DEBUG,
    'httponly': True,
    'samesite': 'Lax' if settings.DEBUG else 'None',
    'domain': getattr(settings, "COOKIE_DOMAIN", None),
    'path': "/",
}


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from api.custom_auth.serializers import LoginSerializer
        serializer = LoginSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        tokens = serializer.validated_data["tokens"]
        update_last_login(None, user)

        response = Response({
            "detail": "Success",
            "role": user.role,
        }, status=status.HTTP_200_OK)

        # 1. JWT Cookies (HttpOnly)
        response.set_cookie('access_token', tokens["access"], max_age=settings.ACCESS_MAX_AGE, **COOKIE_PARAMS)
        response.set_cookie('refresh_token', tokens["refresh"], max_age=settings.REFRESH_MAX_AGE, **COOKIE_PARAMS)

        # 2. CSRF Token (Lisible par le JS pour l'intercepteur Axios)
        response.set_cookie('csrftoken', get_token(request), httponly=False, samesite=COOKIE_PARAMS['samesite'],
                            secure=COOKIE_PARAMS['secure'])

        # 3. Role Cookie (Pour le Middleware Next.js)
        response.set_cookie('user_role', user.role, httponly=False, samesite=COOKIE_PARAMS['samesite'],
                            secure=COOKIE_PARAMS['secure'])

        return response


class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            return Response({"detail": "Missing refresh token"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            refresh = RefreshToken(refresh_token)
            data = {"access": str(refresh.access_token)}

            # Rotation du refresh token
            refresh.set_jti()
            refresh.set_exp()
            new_refresh = str(refresh)

            response = Response({"detail": "Refreshed"}, status=status.HTTP_200_OK)
            response.set_cookie('access_token', data["access"], max_age=settings.ACCESS_MAX_AGE, **COOKIE_PARAMS)
            response.set_cookie('refresh_token', new_refresh, max_age=settings.REFRESH_MAX_AGE, **COOKIE_PARAMS)
            return response
        except (TokenError, InvalidToken):
            return Response({"detail": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    def post(self, request):
        response = Response(status=status.HTTP_204_NO_CONTENT)
        for cookie in ("access_token", "refresh_token", "user_role", "csrftoken"):
            response.delete_cookie(cookie, domain=COOKIE_PARAMS['domain'], path="/")
        return response