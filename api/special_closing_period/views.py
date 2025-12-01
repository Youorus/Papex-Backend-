from rest_framework import permissions, viewsets

from .models import SpecialClosingPeriod
from .serializers import SpecialClosingPeriodSerializer


class SpecialClosingPeriodViewSet(viewsets.ModelViewSet):
    queryset = SpecialClosingPeriod.objects.all()
    serializer_class = SpecialClosingPeriodSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]
