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
            or getattr(user, "role", None) == UserRoles.ACCUEIL
        )


class IsAdminOrCreator(BasePermission):
    """
    Autorise l'accès aux administrateurs OU au créateur lui-même.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        from api.creators.models import CreatorProfile
        user = request.user
        
        # Admin / Staff
        if user.is_superuser or getattr(user, "role", None) == UserRoles.ACCUEIL:
            return True
            
        # Creator checking their own profile
        if isinstance(obj, CreatorProfile):
            return obj.user == user
            
        # Creator checking their own PromoCode
        if hasattr(obj, 'creator'):
            return obj.creator.user == user
            
        return False