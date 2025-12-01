# api/leads/test_permissions.py

from rest_framework.permissions import SAFE_METHODS, BasePermission

from api.users.roles import UserRoles


class IsLeadCreator(BasePermission):
    """
    - ADMIN et ACCUEIL peuvent créer (POST)
    - Tous les utilisateurs authentifiés peuvent lire, modifier, supprimer
    - Route spéciale `public_create` toujours ouverte (vue custom)
    """

    def has_permission(self, request, view):
        # Route ouverte à tous
        if getattr(view, "action", None) == "public_create":
            return True
        # Création classique (POST /leads/)
        if view.action == "create":
            return request.user.is_authenticated and getattr(
                request.user, "role", None
            ) in [UserRoles.ADMIN, UserRoles.ACCUEIL, UserRoles.CONSEILLER, UserRoles.JURISTE]
        # Update/delete/read: tout utilisateur connecté
        if request.user and request.user.is_authenticated:
            return True
        return False


class IsConseillerOrAdmin(BasePermission):
    """
    Seuls les CONSEILLER ou ADMIN peuvent assigner ou se désassigner.
    """

    def has_permission(self, request, view):
        return (
                request.user
                and request.user.is_authenticated
                and request.user.role in [UserRoles.ADMIN, UserRoles.CONSEILLER]
        )