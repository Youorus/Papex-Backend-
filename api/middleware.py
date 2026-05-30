# api/middleware.py
from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject, empty
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
    
    Note: On évite de stocker un SimpleLazyObject non évalué dans le ContextVar
    car asgiref l'évaluerait lors des changements de contexte en ASGI,
    provoquant une SynchronousOnlyOperation.
    """

    def process_request(self, request):
        if hasattr(request, "user"):
            user = request.user
            # Si c'est un SimpleLazyObject, on ne le stocke que s'il est déjà évalué
            if isinstance(user, SimpleLazyObject):
                # On vérifie si l'objet est évalué sans déclencher l'évaluation
                if getattr(user, '_wrapped', empty) is not empty:
                    set_current_user(user)
                else:
                    # On ne fait rien, on attendra l'évaluation dans la vue
                    set_current_user(None)
            else:
                set_current_user(user)
        else:
            set_current_user(None)

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Appelé juste avant la vue. À ce stade, DRF ou Django risque d'avoir
        déjà évalué l'utilisateur (surtout avec SessionAuthentication).
        """
        if hasattr(request, "user"):
            user = request.user
            if isinstance(user, SimpleLazyObject):
                if getattr(user, '_wrapped', empty) is not empty:
                    set_current_user(user)
            else:
                set_current_user(user)
        return None

    def process_response(self, request, response):
        set_current_user(None)
        return response
