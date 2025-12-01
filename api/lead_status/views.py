from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api.lead_status.models import LeadStatus
from api.lead_status.permissions import IsAdminRole
from api.lead_status.serializer import LeadStatusSerializer

PROTECTED_CODES = {"ABSENT", "PRESENT", "RDV_CONFIRME", "RDV_PLANIFIE"}


class LeadStatusViewSet(viewsets.ModelViewSet):
    queryset = LeadStatus.objects.all()
    serializer_class = LeadStatusSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsAdminRole()]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Toujours comparer en MAJ (robuste !)
        code = (instance.code or "").upper()
        if code in PROTECTED_CODES:
            return Response(
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)
