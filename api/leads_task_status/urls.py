"""
Routes API pour les statuts de tâches.
"""

from rest_framework.routers import DefaultRouter

from .views import LeadTaskStatusViewSet

router = DefaultRouter()

router.register(
    r"",
    LeadTaskStatusViewSet,
    basename="lead-task-status",
)

urlpatterns = router.urls