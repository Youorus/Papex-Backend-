"""
Définit les routes URL pour l'application Leads.

Inclut :
- Un routeur DRF pour les opérations CRUD standards sur les leads.
- Un endpoint de recherche avancée via la vue LeadSearchView.
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .lead_search import LeadSearchView
from .promo_code_view import LeadPromoCodeView
from .views import LeadViewSet

# Routeur principal pour les vues de type ViewSet
router = DefaultRouter()
router.register(r"", LeadViewSet, basename="lead")

urlpatterns = [
    # Endpoint de recherche personnalisée (filtrage avancé)
    path("search/", LeadSearchView.as_view(), name="lead-search"),
    path('<int:lead_id>/promo-code/', LeadPromoCodeView.as_view(), name='lead-promo-code'),
]

urlpatterns += router.urls
