from rest_framework.routers import DefaultRouter

from api.lead_status.views import LeadStatusViewSet

router = DefaultRouter()
router.register(r"", LeadStatusViewSet, basename="lead-status")
urlpatterns = router.urls
