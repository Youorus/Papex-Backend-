from rest_framework.permissions import BasePermission

from api.users.roles import UserRoles


class IsAdminOrReadOnly(BasePermission):
    """
    Autorise les admins à tout faire, les autres à lire seulement.
    """

    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return request.user.is_authenticated
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", None) == UserRoles.ADMIN
        )
