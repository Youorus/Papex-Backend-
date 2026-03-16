"""
api/leads_task/views.py

API CRUD pour les tâches de leads.
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import LeadTask
from .serializers import LeadTaskSerializer


class LeadTaskViewSet(viewsets.ModelViewSet):
    """
    CRUD complet pour les tâches.

    Endpoints :

        GET     /lead-tasks/
        POST    /lead-tasks/

        GET     /lead-tasks/{id}/
        PATCH   /lead-tasks/{id}/
        DELETE  /lead-tasks/{id}/
    """

    queryset = LeadTask.objects.select_related(
        "task_type",
        "status",
        "assigned_to",
        "lead",
    )

    serializer_class = LeadTaskSerializer

    permission_classes = [IsAuthenticated]

    lookup_field = "id"

    def perform_create(self, serializer):
        """
        Définit automatiquement le créateur.
        """
        serializer.save(created_by=self.request.user)