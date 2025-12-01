from rest_framework.routers import DefaultRouter

from api.services.views import ServiceViewSet

# Création d'un router DRF pour les routes RESTful automatiques
router = DefaultRouter()
router.register(r"", ServiceViewSet, basename="services")

# Export des URLs du module services
urlpatterns = router.urls
