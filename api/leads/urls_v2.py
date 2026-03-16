"""
API V2 des Leads

CRUD complet pour le CRM.
Ne casse pas l'API historique.
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .lead_filter import LeadFilterView
from .lead_search_v2 import LeadSearchViewV2
from .views_v2 import LeadViewSetV2


router = DefaultRouter()
router.register(r"", LeadViewSetV2, basename="lead-v2")


urlpatterns = [
    path("search/v2/", LeadSearchViewV2.as_view(), name="lead-search-v2"),
    path("filter/", LeadFilterView.as_view(), name="lead-filter"),
]


urlpatterns += router.urls