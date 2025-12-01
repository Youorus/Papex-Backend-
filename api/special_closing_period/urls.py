# urls.py

from rest_framework.routers import DefaultRouter

from api.special_closing_period.views import SpecialClosingPeriodViewSet

router = DefaultRouter()
router.register(r"", SpecialClosingPeriodViewSet, basename="special-closing-periods")
urlpatterns = router.urls
