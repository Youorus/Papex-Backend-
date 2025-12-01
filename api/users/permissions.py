# users/test_permissions.py
from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """
    Autorise seulement les utilisateurs ayant le rôle ADMIN.
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", None) == "ADMIN"
        )
