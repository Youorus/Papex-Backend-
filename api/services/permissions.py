from rest_framework.permissions import SAFE_METHODS, BasePermission

from api.users.roles import UserRoles


class IsAdminForUnsafeOnly(BasePermission):
    """
    - Lecture (GET, HEAD, OPTIONS) autorisée pour tout le monde
    - Écriture (POST, PUT, DELETE, etc.) uniquement pour les admins (role == ADMIN)
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True  # lecture publique
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == UserRoles.ADMIN
        )
