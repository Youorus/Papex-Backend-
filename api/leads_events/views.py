"""
api/leads/events/views.py

Endpoints :
    GET    /lead-events/                      → liste filtrée
    POST   /lead-events/                      → créer un événement
    GET    /lead-events/{id}/                 → détail
    GET    /lead-events/timeline/?lead={id}   → nodes + edges React Flow
    PATCH  /lead-events/{id}/position/        → mise à jour position canvas
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import LeadEvent
from .serializers import LeadEventSerializer
from .services import LeadEventService


class LeadEventViewSet(viewsets.ModelViewSet):
    """
    Gestion complète des événements d'un lead + endpoint timeline.
    """

    serializer_class = LeadEventSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = (
            LeadEvent.objects
            .select_related("actor", "event_type")
            .prefetch_related("attachments", "children")
        )
        lead_id = self.request.query_params.get("lead")
        if lead_id:
            queryset = queryset.filter(lead_id=lead_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(actor=self.request.user)

    # ─────────────────────────────────────────────────
    # TIMELINE — format React Flow
    # ─────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="timeline")
    def timeline(self, request):
        """
        GET /lead-events/timeline/?lead=<id>

        Retourne { nodes, edges } prêt à consommer par React Flow.
        """
        lead_id = request.query_params.get("lead")
        if not lead_id:
            return Response(
                {"detail": "Paramètre 'lead' requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = LeadEventService.get_timeline_for_react_flow(lead_id)
        return Response(result)

    # ─────────────────────────────────────────────────
    # POSITION — mise à jour canvas uniquement
    # ─────────────────────────────────────────────────

    @action(detail=True, methods=["patch"], url_path="position")
    def update_position(self, request, pk=None):
        """
        PATCH /lead-events/{id}/position/
        Body: { "x": 120.5, "y": 340.0 }

        Seule modification autorisée sur un LeadEvent (immutabilité métier préservée).
        """
        x = request.data.get("x")
        y = request.data.get("y")

        if x is None or y is None:
            return Response(
                {"detail": "x et y sont requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            LeadEventService.update_node_position(
                event_id=int(pk),
                x=float(x),
                y=float(y),
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"ok": True})

    # ─────────────────────────────────────────────────
    # OVERRIDE partial_update — bloque les champs métier
    # ─────────────────────────────────────────────────

    def partial_update(self, request, *args, **kwargs):
        """
        Seules position_x et position_y sont mutables.
        Pour tout le reste, utilise l'endpoint /position/.
        """
        allowed = {"position_x", "position_y"}
        forbidden = set(request.data.keys()) - allowed
        if forbidden:
            return Response(
                {
                    "detail": (
                        f"LeadEvent est immuable. "
                        f"Champs interdits : {', '.join(forbidden)}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)