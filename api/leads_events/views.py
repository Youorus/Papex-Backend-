"""
api/leads/events/views.py
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import LeadEvent
from .serializers import LeadEventSerializer


class LeadEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lecture de l'historique des événements d'un lead.
    """

    serializer_class = LeadEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        queryset = LeadEvent.objects.select_related(
            "actor",
            "event_type",
        )

        lead_id = self.request.query_params.get("lead")

        if lead_id:
            queryset = queryset.filter(lead_id=lead_id)

        return queryset