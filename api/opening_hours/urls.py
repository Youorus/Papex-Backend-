# urls.py

from rest_framework.routers import DefaultRouter

from .views import OpeningHoursViewSet

router = DefaultRouter()
router.register(r"", OpeningHoursViewSet, basename="opening-hours")

urlpatterns = router.urls
