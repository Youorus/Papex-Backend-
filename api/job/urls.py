from rest_framework.routers import DefaultRouter

from api.job.views import JobViewSet

router = DefaultRouter()
router.register(r"", JobViewSet, basename="jobs")

urlpatterns = router.urls