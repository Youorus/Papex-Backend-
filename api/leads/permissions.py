# api/leads/permissions.py

from rest_framework.permissions import BasePermission
from api.users.roles import UserRoles

# Rôles avec droits complets (équivalents ADMIN)
FULL_ACCESS_ROLES = [
    UserRoles.ADMIN,
    UserRoles.JURISTE,
]


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

        # Création d'un lead
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
    ADMIN, CONSEILLER et JURISTE peuvent gérer les assignations.
    ✅ JURISTE ajouté — droits équivalents à ADMIN.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in [
                UserRoles.ADMIN,
                UserRoles.CONSEILLER,
                UserRoles.JURISTE,  # ✅ ajouté
            ]
        )


class CanAssignLead(BasePermission):
    """
    ADMIN, CONSEILLER et JURISTE peuvent assigner n'importe qui.
    ✅ JURISTE a les mêmes droits qu'ADMIN (plus de restriction auto-assignation).
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