"""
Fichier de routage principal pour l'application `clients`.

Ce fichier enregistre les routes REST pour le `ClientViewSet`, exposant automatiquement
les endpoints CRUD via le routeur DRF. Toutes les opérations sont accessibles via `/api/clients/`.

Exemple d’URL générée :
- GET /api/clients/ : liste des clients
- POST /api/clients/ : création d’un client
- GET /api/clients/{id}/ : détails d’un client
- PUT/PATCH/DELETE /api/clients/{id}/ : modification ou suppression
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.clients.views import ClientViewSet

router = DefaultRouter()
router.register(r"", ClientViewSet, basename="client")

urlpatterns = [
    path("", include(router.urls)),
]
