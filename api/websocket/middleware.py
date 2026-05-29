import os
import django
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
import jwt
from django.contrib.auth import get_user_model

User = get_user_model()

@database_sync_to_async
def get_user_from_token(token):
    try:
        # On utilise la clé secrète de Django pour décoder le JWT
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
        return User.objects.get(id=user_id)
    except (jwt.ExpiredSignatureError, jwt.DecodeError, User.DoesNotExist):
        return AnonymousUser()

class JWTAuthMiddleware:
    """
    Middleware personnalisé pour authentifier les WebSockets via un token JWT dans les cookies.
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # 1. Récupérer les cookies
        headers = dict(scope.get("headers", {}))
        cookie_header = headers.get(b"cookie", b"").decode()
        
        cookies = {}
        if cookie_header:
            for cookie in cookie_header.split(";"):
                if "=" in cookie:
                    k, v = cookie.strip().split("=", 1)
                    cookies[k] = v

        # 2. Chercher le token (on essaie 'access' ou 'access_token' selon la convention du projet)
        token = cookies.get("access") or cookies.get("access_token")

        if token:
            scope["user"] = await get_user_from_token(token)
        else:
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)
