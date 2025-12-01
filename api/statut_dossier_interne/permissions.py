from rest_framework.permissions import BasePermission
from api.users.roles import UserRoles


class IsAdminOrReadOnly(BasePermission):
    """
    Seuls les admins peuvent créer / modifier / supprimer.
    Les autres utilisateurs authentifiés ont uniquement la lecture.
    """

    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return request.user.is_authenticated
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", None) == UserRoles.ADMIN
        )