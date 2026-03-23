"""
api/leads_task/views.py
"""

from django.utils.dateparse import parse_datetime

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import LeadTask
from .serializers import LeadTaskSerializer


class LeadTaskViewSet(viewsets.ModelViewSet):
    """
    CRUD complet pour les tâches.

    Endpoints :

        GET     /lead-tasks/
        POST    /lead-tasks/

        GET     /lead-tasks/{pk}/
        PATCH   /lead-tasks/{pk}/
        DELETE  /lead-tasks/{pk}/

        POST    /lead-tasks/{pk}/reschedule/
        POST    /lead-tasks/{pk}/complete/
    """

    serializer_class = LeadTaskSerializer
    permission_classes = [IsAuthenticated]

    # ─────────────────────────────
    # QUERYSET OPTIMISÉ
    # ─────────────────────────────
    def get_queryset(self):
        queryset = LeadTask.objects.select_related(
            "task_type",
            "assigned_to",
            "created_by",
            "lead",
            "triggered_by_event",
        )

        lead_id = self.request.query_params.get("lead")
        if lead_id:
            queryset = queryset.filter(lead_id=lead_id)

        return queryset.order_by("due_at")

    # ─────────────────────────────
    # CREATE
    # ─────────────────────────────
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    # ─────────────────────────────
    # UPDATE
    # Empêche modification directe de due_at
    # ─────────────────────────────
    def update(self, request, *args, **kwargs):
        if "due_at" in request.data:
            return Response(
                {"detail": "Utilisez l'endpoint reschedule pour modifier la date."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    # ─────────────────────────────
    # RESCHEDULE
    # ─────────────────────────────
    @action(detail=True, methods=["post"])
    def reschedule(self, request, pk=None):
        task = self.get_object()

        raw_due_at = request.data.get("due_at")
        reason = request.data.get("reason", "")

        if not raw_due_at:
            return Response(
                {"detail": "Le champ due_at est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_due_at = parse_datetime(raw_due_at)

        if not new_due_at:
            return Response(
                {"detail": "Format de date invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task.reschedule(
            new_due_at=new_due_at,
            reason=reason,
            rescheduled_by=request.user,
        )

        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ─────────────────────────────
    # COMPLETE
    # ─────────────────────────────
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        task = self.get_object()

        # 🔥 utilise ta méthode model corrigée
        task.complete()

        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)