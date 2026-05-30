from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

User = get_user_model()


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # 🔹 Si le header Authorization est présent, utiliser la méthode normale
        header = self.get_header(request)
        if header is not None:
            return super().authenticate(request)

        # 🔸 Sinon, on tente de lire le token depuis le cookie HttpOnly
        raw_token = request.COOKIES.get("access_token")
        if raw_token is None:
            return None  # Aucun token fourni → laisser DRF renvoyer 401

        try:
            validated_token = self.get_validated_token(raw_token)
            return self.get_user(validated_token), validated_token
        except Exception:
            raise AuthenticationFailed("Token invalide ou expiré (via cookie)")


class EmailBackend:
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = username or kwargs.get("email")

        if email is None or password is None:
            return None

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return None

        if user.check_password(password) and user.is_active:
            return user

        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None