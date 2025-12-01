from rest_framework.permissions import SAFE_METHODS, BasePermission

from api.users.models import UserRoles  # adapte le chemin si nécessaire


class IsPaymentEditor(BasePermission):
    """
    Autorise uniquement les utilisateurs internes (ADMIN, JURISTE, COMPTABILITE)
    à éditer/créer/supprimer un reçu. Lecture seule pour les autres utilisateurs authentifiés.
    """

    ALLOWED_ROLES = (
        UserRoles.ADMIN,
        UserRoles.CONSEILLER,
        UserRoles.ACCUEIL,
        UserRoles.JURISTE,
    )

    def has_permission(self, request, view):
        # Lecture pour tous les authentifiés
        if request.method in SAFE_METHODS:
            return request.user.is_authenticated
        # Écriture pour les rôles autorisés uniquement
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", None) in self.ALLOWED_ROLES
        )
