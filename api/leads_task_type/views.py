"""
ViewSet pour gérer les types de tâches CRM.
"""

from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from api.leads_task_type.models import LeadTaskType
from api.leads_task_type.serializers import LeadTaskTypeSerializer


class LeadTaskTypeViewSet(ModelViewSet):
    """
    CRUD complet pour les types de tâches.
    """

    queryset = LeadTaskType.objects.all()
    serializer_class = LeadTaskTypeSerializer
    permission_classes = [IsAuthenticated]