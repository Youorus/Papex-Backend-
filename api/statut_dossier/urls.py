from rest_framework.routers import DefaultRouter

from api.statut_dossier.views import StatutDossierViewSet

router = DefaultRouter()
router.register(r"", StatutDossierViewSet, basename="statut-dossiers")

urlpatterns = router.urls
