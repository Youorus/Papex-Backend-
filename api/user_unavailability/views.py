from rest_framework import filters, permissions, viewsets

from .models import UserUnavailability
from .serializers import UserUnavailabilitySerializer


class UserUnavailabilityViewSet(viewsets.ModelViewSet):
    queryset = UserUnavailability.objects.select_related("user").all()
    serializer_class = UserUnavailabilitySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["user__first_name", "user__last_name", "user__email", "label"]
    ordering_fields = ["start_date", "end_date", "user"]

    def get_permissions(self):
        # Lecture pour tous, écriture pour admin/staff (adapte selon besoin)
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]
