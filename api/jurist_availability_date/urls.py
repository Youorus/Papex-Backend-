# urls.py

from rest_framework.routers import DefaultRouter

from api.jurist_availability_date.views import JuristGlobalAvailabilityViewSet

router = DefaultRouter()
router.register(
    r"", JuristGlobalAvailabilityViewSet, basename="jurist-global-availability"
)

urlpatterns = router.urls
