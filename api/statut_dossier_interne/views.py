from rest_framework import viewsets
from api.statut_dossier_interne.models import StatutDossierInterne
from api.statut_dossier_interne.serializers import StatutDossierInterneSerializer
from api.statut_dossier_interne.permissions import IsAdminOrReadOnly


class StatutDossierInterneViewSet(viewsets.ModelViewSet):
    """
    ViewSet CRUD pour la gestion des statuts internes de dossiers.
    """

    queryset = StatutDossierInterne.objects.all()
    serializer_class = StatutDossierInterneSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None