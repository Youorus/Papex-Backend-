from rest_framework.permissions import BasePermission


class IsCommentAuthorOrAdmin(BasePermission):
    """
    Permission personnalisée : seul l'auteur ou un admin peut éditer/supprimer un commentaire.
    """

    def has_object_permission(self, request, view, obj):
        return request.user == obj.author or request.user.is_superuser
