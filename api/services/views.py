from rest_framework import viewsets

from .models import Service
from .permissions import IsAdminForUnsafeOnly
from .serializers import ServiceSerializer


class ServiceViewSet(viewsets.ModelViewSet):
    """
    - Lecture (GET) accessible à tous
    - Écriture réservée aux admins
    """

    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [IsAdminForUnsafeOnly]
    pagination_class = None
