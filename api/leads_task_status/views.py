"""
API ViewSet pour les statuts de tâches.
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import LeadTaskStatus
from .serializers import LeadTaskStatusSerializer


class LeadTaskStatusViewSet(viewsets.ModelViewSet):
    """
    CRUD complet des statuts de tâches.

    Endpoints disponibles :

        GET     /lead-task-status/
        POST    /lead-task-status/

        GET     /lead-task-status/{id}/
        PATCH   /lead-task-status/{id}/
        DELETE  /lead-task-status/{id}/
    """

    queryset = LeadTaskStatus.objects.all()

    serializer_class = LeadTaskStatusSerializer

    permission_classes = [IsAuthenticated]

    lookup_field = "id"

    def get_queryset(self):
        """
        Retourne uniquement les statuts actifs.

        Peut être étendu pour filtrer.
        """
        return LeadTaskStatus.objects.all().order_by("label")