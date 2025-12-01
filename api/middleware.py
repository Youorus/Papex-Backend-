# api/middleware.py
from django.utils.deprecation import MiddlewareMixin


class CookieToHeaderMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if (
            "access_token" in request.COOKIES
            and not "HTTP_AUTHORIZATION" in request.META
        ):
            request.META["HTTP_AUTHORIZATION"] = (
                f"Bearer {request.COOKIES['access_token']}"
            )
