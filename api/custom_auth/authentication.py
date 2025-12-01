from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


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
