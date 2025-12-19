from rest_framework.permissions import SAFE_METHODS, BasePermission

from api.users.roles import UserRoles


class IsJobEditor(BasePermission):
    """
    Autorise la gestion des offres d'emploi uniquement aux rôles internes.

    - Lecture (SAFE_METHODS) : accès public
    - Écriture : rôles autorisés uniquement
    """

    ALLOWED_ROLES = (
        UserRoles.ADMIN,
        UserRoles.CONSEILLER,
        UserRoles.JURISTE,
    )

    def has_permission(self, request, view):
        # Lecture : autorisée à tous
        if request.method in SAFE_METHODS:
            return True

        # Écriture : utilisateur authentifié + rôle autorisé
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", None) in self.ALLOWED_ROLES
        )