# api/leads/test_permissions.py

from rest_framework.permissions import SAFE_METHODS, BasePermission

from api.users.roles import UserRoles


class IsLeadCreator(BasePermission):
    """
    Permissions générales sur les leads.

    - Route public_create : ouverte à tous
    - Création (POST /leads/) :
        ADMIN, ACCUEIL, CONSEILLER, JURISTE
    - Lecture / modification / suppression :
        tout utilisateur authentifié
    """

    def has_permission(self, request, view):
        # Route publique
        if getattr(view, "action", None) == "public_create":
            return True

        # Création d’un lead
        if view.action == "create":
            return (
                request.user
                and request.user.is_authenticated
                and request.user.role in [
                    UserRoles.ADMIN,
                    UserRoles.ACCUEIL,
                    UserRoles.CONSEILLER,
                    UserRoles.JURISTE,
                ]
            )

        # Lecture / modification / suppression
        return bool(request.user and request.user.is_authenticated)


class IsConseillerOrAdmin(BasePermission):
    """
    Seuls ADMIN ou CONSEILLER peuvent gérer les assignations.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in [
                UserRoles.ADMIN,
                UserRoles.CONSEILLER,
            ]
        )



class CanAssignLead(BasePermission):
    """
    ADMIN, CONSEILLER et JURISTE peuvent accéder à l'endpoint d'assignation.
    - ADMIN : peut assigner/désassigner n'importe qui
    - CONSEILLER / JURISTE : auto-assignation uniquement
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        return user.role in [
            UserRoles.ADMIN,
            UserRoles.CONSEILLER,
            UserRoles.JURISTE,
        ]
