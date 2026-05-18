from rest_framework.permissions import BasePermission

from api.users.roles import UserRoles


class IsAdminOrStaff(BasePermission):
    """
    Autorise l'accès uniquement aux administrateurs réels.

    Conditions acceptées :
    - utilisateur authentifié
    - superuser Django
    - rôle applicatif ADMIN

    Note :
    On n'utilise pas `is_staff` seul, car dans ce projet certains rôles
    peuvent avoir `is_staff=True` sans être administrateurs métier.
    """

    message = "Vous n'avez pas les droits nécessaires pour accéder à cette ressource."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if not getattr(user, "is_active", False):
            return False

        return bool(
            getattr(user, "is_superuser", False)
            or getattr(user, "role", None) == UserRoles.ADMIN
        )