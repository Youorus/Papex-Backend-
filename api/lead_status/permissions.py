from rest_framework.permissions import BasePermission

from api.users.roles import UserRoles


class IsAdminRole(BasePermission):
    """
    Autorise uniquement les utilisateurs ayant le rôle 'ADMIN'.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return getattr(user, "role", "").upper() == UserRoles.ADMIN
