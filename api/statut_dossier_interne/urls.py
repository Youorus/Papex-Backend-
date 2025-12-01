from rest_framework.routers import DefaultRouter
from api.statut_dossier_interne.views import StatutDossierInterneViewSet

router = DefaultRouter()
router.register(r"", StatutDossierInterneViewSet, basename="statut-dossiers-internes")

urlpatterns = router.urls