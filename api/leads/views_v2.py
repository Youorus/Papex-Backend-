"""
API V2 Lead ViewSet

CRUD complet sur les leads.
Conçu pour le CRM.
"""

import logging

from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action

from api.core.pagination import CRMLeadPagination
from api.leads.models import Lead
from api.leads.serializers import LeadSerializer

from api.leads_events.models import LeadEvent
from api.leads_events.serializers import LeadEventSerializer

logger = logging.getLogger(__name__)


class LeadViewSetV2(viewsets.ModelViewSet):
    """
    CRUD complet pour les Leads.
    """

    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CRMLeadPagination

    # --------------------------
    # QUERYSET CRM
    # --------------------------

    def get_queryset(self):
        queryset = (
            Lead.objects
            .select_related(
                "status",
                "statut_dossier",
                "statut_dossier_interne",
            )
            .prefetch_related(
                "assigned_to",
                "jurist_assigned",
            )
            .order_by("-created_at")
        )
        return queryset

    # --------------------------
    # EVENTS
    # --------------------------

    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        lead = self.get_object()
        events = (
            LeadEvent.objects
            .filter(lead=lead)
            .select_related("event_type", "actor")
            .order_by("-occurred_at")
        )
        serializer = LeadEventSerializer(events, many=True)
        return Response(serializer.data)

    # --------------------------
    # TASKS
    # --------------------------

    @action(detail=True, methods=["get"])
    def tasks(self, request, pk=None):
        from api.leads_task.models import LeadTask
        from api.leads_task.serializers import LeadTaskSerializer

        lead = self.get_object()
        tasks = (
            LeadTask.objects
            .filter(lead=lead)
            .select_related("task_type", "status", "assigned_to")
        )
        serializer = LeadTaskSerializer(tasks, many=True)
        return Response(serializer.data)

    # --------------------------
    # CREATE
    # --------------------------

    def perform_create(self, serializer):

        lead = serializer.save()

        logger.info(
            "[LeadViewSetV2] Lead créé : id=%s | status=%s",
            lead.id,
            getattr(lead.status, "code", None),
        )

        event = LeadEvent.log(
            lead=lead,
            event_code="LEAD_CREATED",
            actor=self.request.user,
        )

        logger.info(
            "[LeadViewSetV2] Événement LEAD_CREATED loggé : event_id=%s | lead_id=%s",
            event.id if event else "N/A",
            lead.id,
        )

    # --------------------------
    # UPDATE
    # --------------------------

    def perform_update(self, serializer):

        old_status = None

        if serializer.instance:
            old_status = serializer.instance.status

        lead = serializer.save()

        if old_status and old_status != lead.status:

            logger.info(
                "[LeadViewSetV2] Changement de statut détecté : lead_id=%s | %s → %s",
                lead.id,
                getattr(old_status, "code", None),
                getattr(lead.status, "code", None),
            )

            event = LeadEvent.log(
                lead=lead,
                event_code="STATUS_CHANGED",
                actor=self.request.user,
                data={
                    "from": old_status.code,
                    "to": lead.status.code,
                },
            )

            logger.info(
                "[LeadViewSetV2] Événement STATUS_CHANGED loggé : event_id=%s | lead_id=%s",
                event.id if event else "N/A",
                lead.id,
            )

        else:
            logger.debug(
                "[LeadViewSetV2] Mise à jour sans changement de statut : lead_id=%s",
                lead.id,
            )