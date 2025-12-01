from django.urls import path
from rest_framework.routers import DefaultRouter

from api.contracts.contract_search import ContractSearchView
from api.contracts.views import ContractViewSet

router = DefaultRouter()
router.register(r"", ContractViewSet, basename="contract")

urlpatterns = [
    # Recherche de contrats (JSON)
    path("search/", ContractSearchView.as_view({'get': 'list'}), name="contract-search"),
    # Export PDF des contrats filtrés
    path("search/export-pdf/", ContractSearchView.as_view({'get': 'export_pdf'}), name="contract-search-export-pdf"),
]

urlpatterns += router.urls