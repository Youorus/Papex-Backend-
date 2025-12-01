from django.utils.translation import gettext as _
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from api.comments.models import Comment
from api.comments.permissions import IsCommentAuthorOrAdmin
from api.comments.serializers import CommentSerializer


class CommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet principal pour la gestion des commentaires sur les leads.
    """

    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Comment.objects.all().select_related("author", "lead")

    @action(detail=False, methods=["get"], url_path="lead/(?P<lead_id>[^/.]+)")
    def by_lead(self, request, lead_id=None):
        """
        GET /comments/lead/<lead_id>/ : liste les commentaires d’un lead.
        """
        queryset = self.get_queryset().filter(lead__id=lead_id)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        if not IsCommentAuthorOrAdmin().has_object_permission(
            self.request, self, serializer.instance
        ):
            raise PermissionDenied(_("Vous n'êtes pas l'auteur de ce commentaire."))
        serializer.save()

    def perform_destroy(self, instance):
        if not IsCommentAuthorOrAdmin().has_object_permission(
            self.request, self, instance
        ):
            raise PermissionDenied(_("Vous n'êtes pas l'auteur de ce commentaire."))
        instance.delete()
