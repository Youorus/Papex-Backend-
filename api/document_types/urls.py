from rest_framework.routers import DefaultRouter

from .views import DocumentTypeViewSet

router = DefaultRouter()
router.register(r"", DocumentTypeViewSet, basename="document-type")

urlpatterns = router.urls