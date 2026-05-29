# api/middleware.py
from django.utils.deprecation import MiddlewareMixin
from api.utils.context import set_current_user


class CookieToHeaderMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if (
            "access_token" in request.COOKIES
            and not "HTTP_AUTHORIZATION" in request.META
        ):
            request.META["HTTP_AUTHORIZATION"] = (
                f"Bearer {request.COOKIES['access_token']}"
            )


class CurrentUserMiddleware(MiddlewareMixin):
    """
    Middleware pour capturer l'utilisateur de la requête et le rendre accessible
    partout (notamment dans les signaux) via api.utils.context.
    """

    def process_request(self, request):
        if hasattr(request, "user"):
            set_current_user(request.user)

    def process_response(self, request, response):
        set_current_user(None)
        return response
