from rest_framework.permissions import SAFE_METHODS, BasePermission

from api.users.roles import UserRoles  # Utilisation de la source unique des rôles


class IsContractEditor(BasePermission):
    """
    Autorise uniquement les utilisateurs internes (ADMIN, JURISTE, COMPTABILITE)
    à créer/modifier/supprimer un contrat.
    Lecture seule pour les autres utilisateurs authentifiés.
    """

    ALLOWED_ROLES = (
        UserRoles.ADMIN,
        UserRoles.CONSEILLER,
        UserRoles.JURISTE,
    )

    def has_permission(self, request, view):
        # Autorise la lecture à tous les authentifiés
        if request.method in SAFE_METHODS:
            return request.user.is_authenticated
        # Pour création/MAJ/suppression → rôle requis
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", None) in self.ALLOWED_ROLES
        )
