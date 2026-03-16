"""
api/leads/events/views.py
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import LeadEventType
from .serializers import LeadEventTypeSerializer


class LeadEventTypeViewSet(viewsets.ModelViewSet):
    """
    API permettant de gérer les types d'événements.

    Endpoints disponibles :

        GET     /api/lead-event-types/
        POST    /api/lead-event-types/
        GET     /api/lead-event-types/{id}/
        PATCH   /api/lead-event-types/{id}/
        DELETE  /api/lead-event-types/{id}/
    """

    queryset = LeadEventType.objects.all()
    serializer_class = LeadEventTypeSerializer
    permission_classes = [IsAuthenticated]

    search_fields = ["code", "label"]
    ordering_fields = ["code", "label", "created_at"]