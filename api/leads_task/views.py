"""
api/leads_task/views.py
"""

from django.utils.dateparse import parse_datetime
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import LeadTask, LeadTaskComment
from .serializers import LeadTaskSerializer, LeadTaskCommentSerializer


# ─────────────────────────────────────────────
# LEAD TASK VIEWSET
# ─────────────────────────────────────────────

class LeadTaskViewSet(viewsets.ModelViewSet):
    serializer_class = LeadTaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # On garde les select_related pour éviter les requêtes N+1
        queryset = LeadTask.objects.select_related(
            "task_type",
            "assigned_to",
            "created_by",
            "lead",
            "triggered_by_event",
        ).prefetch_related("comments__author")

        # Filtrage par Lead
        lead_id = self.request.query_params.get("lead")
        if lead_id:
            queryset = queryset.filter(lead_id=lead_id)

        # Filtrage par Statut
        # Note: Si tu veux supporter la multi-sélection du front, utilise:
        # status_filter = self.request.query_params.get("status")
        # if status_filter:
        #    queryset = queryset.filter(status__in=status_filter.split(','))
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filtrage par Priorité (Désormais limité à MEDIUM et URGENT)
        priority_filter = self.request.query_params.get("priority")
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)

        # Filtrage par Assignation
        assigned_to = self.request.query_params.get("assigned_to")
        if assigned_to == "me":
            queryset = queryset.filter(assigned_to=self.request.user)
        elif assigned_to:
            queryset = queryset.filter(assigned_to_id=assigned_to)

        return queryset.order_by("due_at")

    def perform_create(self, serializer):
        # On injecte l'utilisateur connecté comme créateur
        serializer.save(created_by=self.request.user)

    def update(self, request, *args, **kwargs):
        # Sécurité pour forcer l'usage du reschedule() pour la date
        if "due_at" in request.data:
            return Response(
                {"detail": "Utilisez l'endpoint reschedule pour modifier l'échéance."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def reschedule(self, request, pk=None):
        task = self.get_object()
        raw_due_at = request.data.get("due_at")
        reason = request.data.get("reason", "")

        if not raw_due_at:
            return Response({"detail": "Le champ due_at est requis."}, status=status.HTTP_400_BAD_REQUEST)

        new_due_at = parse_datetime(raw_due_at)
        if not new_due_at:
            return Response({"detail": "Format de date invalide."}, status=status.HTTP_400_BAD_REQUEST)

        # Appel de la méthode métier définie dans le modèle
        task.reschedule(
            new_due_at=new_due_at,
            reason=reason,
            rescheduled_by=request.user,
        )

        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        task = self.get_object()
        task.complete() # Appel de la méthode métier
        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────
# LEAD TASK COMMENT VIEWSET
# ─────────────────────────────────────────────

class LeadTaskCommentViewSet(viewsets.ModelViewSet):
    serializer_class = LeadTaskCommentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = LeadTaskComment.objects.select_related("author", "task")
        task_id = self.request.query_params.get("task")
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        return queryset.order_by("created_at")

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def update(self, request, *args, **kwargs):
        comment = self.get_object()
        if comment.author != request.user:
            return Response(
                {"detail": "Vous ne pouvez modifier que vos propres commentaires."},
                status=status.HTTP_403_FORBIDDEN,
            )
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        comment = self.get_object()
        # Seul l'auteur ou un admin peut supprimer
        if comment.author != request.user and not request.user.is_staff:
            return Response(
                {"detail": "Vous ne pouvez supprimer que vos propres commentaires."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)