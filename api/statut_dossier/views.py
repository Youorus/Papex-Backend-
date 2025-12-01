from rest_framework import viewsets

from api.statut_dossier.models import StatutDossier
from api.statut_dossier.permissions import IsAdminOrReadOnly
from api.statut_dossier.serializers import StatutDossierSerializer


class StatutDossierViewSet(viewsets.ModelViewSet):
    """
    ViewSet CRUD pour la gestion des statuts dossier.
    Par défaut, toutes les routes nécessitent l’authentification.
    """

    queryset = StatutDossier.objects.all()
    serializer_class = StatutDossierSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None
