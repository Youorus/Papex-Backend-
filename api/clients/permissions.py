from rest_framework.permissions import BasePermission


class IsClientCreateOpen(BasePermission):
    """
    Autorise la création d'un client à tout le monde (AllowAny) pour POST.
    Autres méthodes : utilisateur authentifié seulement.
    """

    def has_permission(self, request, view):
        if view.action == "create":
            return True
        return request.user and request.user.is_authenticated
