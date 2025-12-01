from rest_framework.routers import DefaultRouter

from api.user_unavailability.views import UserUnavailabilityViewSet

router = DefaultRouter()
router.register(r"", UserUnavailabilityViewSet, basename="user-unavailability")

urlpatterns = router.urls
