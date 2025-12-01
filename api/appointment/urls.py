# api/appointment/urls.py
from rest_framework.routers import DefaultRouter

from api.appointment.views import AppointmentViewSet

router = DefaultRouter()
router.register(r"", AppointmentViewSet, basename="appointments")

urlpatterns = router.urls
