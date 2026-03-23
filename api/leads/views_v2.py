from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action

from django.utils import timezone

from api.core.pagination import CRMLeadPagination
from api.leads.models import Lead
from api.leads.serializers import LeadSerializer
from api.leads_events.models import LeadEvent


class LeadViewSetV2(viewsets.ModelViewSet):
    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CRMLeadPagination

    # --------------------------
    # QUERYSET
    # --------------------------

    def get_queryset(self):
        return (
            Lead.objects
            .select_related("status", "statut_dossier", "statut_dossier_interne")
            .prefetch_related("assigned_to", "jurist_assigned")
            .order_by("-created_at")
        )

    # --------------------------
    # ASSIGN (1 lead)
    # --------------------------

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        lead = self.get_object()

        user_ids = request.data.get("user_ids", [])

        if not isinstance(user_ids, list):
            return Response({"detail": "user_ids doit être une liste"}, status=400)

        lead.assigned_to.set(user_ids)

        LeadEvent.log(
            lead=lead,
            event_code="LEAD_ASSIGNED",
            actor=request.user,
            data={"assigned_to": user_ids},
        )

        return Response({"success": True})

    # --------------------------
    # ASSIGN JURISTS (1 lead)
    # --------------------------

    @action(detail=True, methods=["post"])
    def assign_jurists(self, request, pk=None):
        lead = self.get_object()

        user_ids = request.data.get("user_ids", [])

        if not isinstance(user_ids, list):
            return Response({"detail": "user_ids doit être une liste"}, status=400)

        lead.jurist_assigned.set(user_ids)
        lead.juriste_assigned_at = timezone.now()
        lead.save(update_fields=["juriste_assigned_at"])

        LeadEvent.log(
            lead=lead,
            event_code="JURIST_ASSIGNED",
            actor=request.user,
            data={"jurists": user_ids},
        )

        return Response({"success": True})

    # --------------------------
    # 🔥 BULK ASSIGN (PLUSIEURS LEADS)
    # --------------------------

    @action(detail=False, methods=["post"], url_path="bulk-assign")
    def bulk_assign(self, request):
        """
        Assigner plusieurs leads en une seule requête
        {
            "lead_ids": [1,2,3],
            "user_ids": [5,6]
        }
        """

        lead_ids = request.data.get("lead_ids", [])
        user_ids = request.data.get("user_ids", [])

        if not isinstance(lead_ids, list) or not isinstance(user_ids, list):
            return Response({"detail": "lead_ids et user_ids doivent être des listes"}, status=400)

        leads = Lead.objects.filter(id__in=lead_ids)

        for lead in leads:
            lead.assigned_to.set(user_ids)

            LeadEvent.log(
                lead=lead,
                event_code="LEAD_ASSIGNED",
                actor=request.user,
                data={"assigned_to": user_ids},
            )

        return Response({
            "success": True,
            "updated": leads.count()
        })

    # --------------------------
    # BULK ASSIGN JURISTS
    # --------------------------

    @action(detail=False, methods=["post"], url_path="bulk-assign-jurists")
    def bulk_assign_jurists(self, request):

        lead_ids = request.data.get("lead_ids", [])
        user_ids = request.data.get("user_ids", [])

        if not isinstance(lead_ids, list) or not isinstance(user_ids, list):
            return Response({"detail": "lead_ids et user_ids doivent être des listes"}, status=400)

        leads = Lead.objects.filter(id__in=lead_ids)

        for lead in leads:
            lead.jurist_assigned.set(user_ids)
            lead.juriste_assigned_at = timezone.now()
            lead.save(update_fields=["juriste_assigned_at"])

            LeadEvent.log(
                lead=lead,
                event_code="JURIST_ASSIGNED",
                actor=request.user,
                data={"jurists": user_ids},
            )

        return Response({
            "success": True,
            "updated": leads.count()
        })

    from rest_framework.decorators import action
    from rest_framework.response import Response

    @action(detail=True, methods=["post"])
    def set_statut_dossier(self, request, pk=None):
        """
        Assigner un statut dossier à un lead
        """
        lead = self.get_object()
        statut_id = request.data.get("statut_dossier_id")

        if not statut_id:
            return Response({"detail": "statut_dossier_id requis"}, status=400)

        from api.statut_dossier.models import StatutDossier

        try:
            statut = StatutDossier.objects.get(pk=statut_id)
        except StatutDossier.DoesNotExist:
            return Response({"detail": "Statut introuvable"}, status=404)

        lead.statut_dossier = statut
        lead.save()

        return Response({
            "success": True,
            "statut_dossier": statut.id
        })

    # --------------------------
    # CREATE
    # --------------------------

    def perform_create(self, serializer):
        lead = serializer.save()

        from api.clients.models import Client
        Client.objects.get_or_create(lead=lead)

        LeadEvent.log(
            lead=lead,
            event_code="LEAD_CREATED",
            actor=self.request.user,
        )

    # --------------------------
    # UPDATE
    # --------------------------

    def perform_update(self, serializer):

        old_status = serializer.instance.status if serializer.instance else None
        lead = serializer.save()

        if old_status and old_status != lead.status:
            LeadEvent.log(
                lead=lead,
                event_code="STATUS_CHANGED",
                actor=self.request.user,
                data={
                    "from": old_status.code,
                    "to": lead.status.code,
                },
            )