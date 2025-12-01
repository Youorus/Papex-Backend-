# urls.py

from rest_framework.routers import DefaultRouter

from .views import JuristAppointmentViewSet

router = DefaultRouter()
router.register(r"", JuristAppointmentViewSet, basename="jurist-appointments")

urlpatterns = router.urls
