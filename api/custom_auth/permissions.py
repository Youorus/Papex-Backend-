from rest_framework import permissions

class HasRole(permissions.BasePermission):
    """
    Vérifie si l'utilisateur possède l'un des rôles requis.
    Usage: required_roles = ['ADMIN', 'JURISTE']
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        allowed_roles = getattr(view, 'required_roles', [])
        return request.user.role in allowed_roles